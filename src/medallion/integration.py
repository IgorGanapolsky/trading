"""
Medallion Architecture Integration

Provides integration points between the new Medallion architecture
and existing trading system components.

This module:
1. Wraps MarketDataProvider to feed Bronze layer
2. Integrates with existing DataProcessor for Silver features
3. Connects to FeatureStore for Gold layer persistence
4. Provides drop-in replacement for ML inference pipeline
"""

import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import torch

from src.medallion.gold import DEFAULT_CONTRACT, FeatureContract
from src.medallion.pipeline import get_medallion_pipeline

logger = logging.getLogger(__name__)


class MedallionDataProcessor:
    """
    Drop-in replacement for DataProcessor using Medallion architecture.

    Maintains backward compatibility while adding data quality guarantees.
    """

    def __init__(
        self,
        sequence_length: int = 60,
        feature_columns: list[str] | None = None,
        use_medallion: bool = True,
    ):
        self.sequence_length = sequence_length
        self.feature_columns = feature_columns or DEFAULT_CONTRACT.features
        self.use_medallion = use_medallion

        if use_medallion:
            self.pipeline = get_medallion_pipeline()
            logger.info("MedallionDataProcessor using Medallion architecture")
        else:
            # Fallback to legacy DataProcessor
            from src.ml.data_processor import DataProcessor

            self._legacy_processor = DataProcessor(
                sequence_length=sequence_length,
                feature_columns=feature_columns
                or [
                    "Close",
                    "Volume",
                    "Returns",
                    "RSI",
                    "MACD",
                    "Signal",
                    "Volatility",
                ],
            )
            logger.info("MedallionDataProcessor using legacy DataProcessor")

    def prepare_inference_data(self, symbol: str) -> torch.Tensor | None:
        """
        Prepare inference-ready tensor for a symbol.

        Uses Medallion pipeline for data quality and consistency.
        """
        if not self.use_medallion:
            return self._legacy_processor.prepare_inference_data(symbol)

        # Fetch raw data
        try:
            from src.utils.market_data import get_market_data_provider

            provider = get_market_data_provider()
            result = provider.get_daily_bars(symbol, lookback_days=self.sequence_length + 30)
            raw_data = result.data

            if raw_data.empty:
                logger.warning(f"No data available for {symbol}")
                return None

        except Exception as e:
            logger.error(f"Failed to fetch data for {symbol}: {e}")
            return None

        # Process through Medallion pipeline
        try:
            tensor = self.pipeline.get_inference_ready(
                symbol,
                raw_data,
                source=f"inference_{datetime.now().strftime('%Y%m%d')}",
            )
            return tensor
        except Exception as e:
            logger.error(f"Medallion pipeline failed for {symbol}: {e}")
            return None

    def prepare_training_data(
        self,
        symbol: str,
        period: str = "2y",
        train_ratio: float = 0.8,
    ) -> tuple[torch.Tensor, torch.Tensor] | None:
        """
        Prepare train/test split tensors for training.

        Normalization is fit ONLY on training data to prevent leakage.
        """
        if not self.use_medallion:
            # Legacy path - basic split without proper leakage prevention
            from src.ml.data_processor import DataProcessor

            processor = DataProcessor()
            df = processor.fetch_data(symbol, period=period)
            df = processor.add_technical_indicators(df)
            df = processor.fit_transform(df)
            sequences = processor.create_sequences(df)
            split = int(len(sequences) * train_ratio)
            return sequences[:split], sequences[split:]

        # Fetch historical data
        try:
            from src.utils.market_data import get_market_data_provider

            provider = get_market_data_provider()
            lookback_days = 365 * 2 if period == "2y" else 365
            result = provider.get_daily_bars(symbol, lookback_days=lookback_days)
            raw_data = result.data

            if raw_data.empty or len(raw_data) < self.sequence_length * 2:
                logger.warning(f"Insufficient data for training {symbol}")
                return None

        except Exception as e:
            logger.error(f"Failed to fetch training data for {symbol}: {e}")
            return None

        # Process through Medallion pipeline
        try:
            train, test, lineage = self.pipeline.get_training_ready(
                symbol,
                raw_data,
                source=f"training_{datetime.now().strftime('%Y%m%d')}",
                train_ratio=train_ratio,
            )

            logger.info(
                f"Training data prepared for {symbol}: "
                f"train={train.shape}, test={test.shape}, "
                f"quality={lineage.silver_quality_score:.2%}"
            )

            return train, test

        except Exception as e:
            logger.error(f"Medallion training pipeline failed for {symbol}: {e}")
            return None

    def validate_data_quality(
        self,
        symbol: str,
        raw_data: pd.DataFrame,
    ) -> dict[str, Any]:
        """
        Validate data quality before training.

        Returns quality report with issues and recommendations.
        """
        if not self.use_medallion:
            return {"status": "skipped", "reason": "Medallion not enabled"}

        report = self.pipeline.validate_data(symbol, raw_data)
        return report.to_dict()


class MedallionMLInference:
    """
    ML inference wrapper using Medallion architecture.

    Ensures consistent data processing between training and inference.
    """

    def __init__(
        self,
        model_path: str | None = None,
        contract: FeatureContract | None = None,
    ):
        self.pipeline = get_medallion_pipeline()
        self.contract = contract or DEFAULT_CONTRACT
        self.model = None

        if model_path:
            self._load_model(model_path)

    def _load_model(self, model_path: str) -> None:
        """Load trained model."""
        try:
            self.model = torch.load(model_path)
            self.model.eval()
            logger.info(f"Loaded model from {model_path}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")

    def get_signal(
        self,
        symbol: str,
        raw_data: pd.DataFrame | None = None,
    ) -> dict[str, Any]:
        """
        Get trading signal for a symbol.

        Returns:
            Dict with action, confidence, and metadata
        """
        # Get inference tensor
        if raw_data is not None:
            tensor = self.pipeline.get_inference_ready(symbol, raw_data)
        else:
            # Fetch fresh data
            processor = MedallionDataProcessor()
            tensor = processor.prepare_inference_data(symbol)

        if tensor is None:
            return {
                "symbol": symbol,
                "action": "hold",
                "confidence": 0.0,
                "reason": "Insufficient data",
            }

        # Run inference
        if self.model is None:
            return {
                "symbol": symbol,
                "action": "hold",
                "confidence": 0.0,
                "reason": "No model loaded",
            }

        try:
            with torch.no_grad():
                output = self.model(tensor)

                # Assume model outputs action probabilities
                if isinstance(output, tuple):
                    action_probs = output[0]
                else:
                    action_probs = output

                action_idx = action_probs.argmax(dim=-1).item()
                confidence = action_probs.softmax(dim=-1).max().item()

                actions = ["hold", "buy", "sell"]
                action = actions[action_idx] if action_idx < len(actions) else "hold"

                return {
                    "symbol": symbol,
                    "action": action,
                    "confidence": confidence,
                    "action_probs": action_probs.tolist(),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

        except Exception as e:
            logger.error(f"Inference failed for {symbol}: {e}")
            return {
                "symbol": symbol,
                "action": "hold",
                "confidence": 0.0,
                "reason": f"Inference error: {e}",
            }


def integrate_with_existing_pipeline() -> None:
    """
    Integration helper to connect Medallion with existing code.

    Call this during system startup to enable Medallion processing.
    """
    import os

    # Set environment flag for Medallion
    os.environ["USE_MEDALLION_ARCHITECTURE"] = "true"

    # Initialize pipeline
    pipeline = get_medallion_pipeline()

    logger.info(
        "Medallion Architecture integrated. "
        "Data flow: Bronze (raw) → Silver (validated) → Gold (ML-ready)"
    )

    return pipeline


if __name__ == "__main__":
    import numpy as np

    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("MEDALLION INTEGRATION DEMO")
    print("=" * 80)

    # Test MedallionDataProcessor
    print("\n1. Testing MedallionDataProcessor")
    print("-" * 40)

    # Create sample data for demo
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    raw_data = pd.DataFrame(
        {
            "Open": np.random.randn(100).cumsum() + 100,
            "High": np.random.randn(100).cumsum() + 102,
            "Low": np.random.randn(100).cumsum() + 98,
            "Close": np.random.randn(100).cumsum() + 100,
            "Volume": np.random.randint(1000000, 10000000, 100),
        },
        index=dates,
    )

    processor = MedallionDataProcessor(use_medallion=True)

    # Note: This would need actual market data provider setup
    # For demo, we'll use the pipeline directly
    pipeline = get_medallion_pipeline()

    train, test, lineage = pipeline.get_training_ready("DEMO", raw_data, train_ratio=0.8)

    print(f"   Train shape: {train.shape}")
    print(f"   Test shape: {test.shape}")
    print(f"   Quality score: {lineage.silver_quality_score:.2%}")

    # Data quality validation
    print("\n2. Data Quality Validation")
    print("-" * 40)

    quality = processor.validate_data_quality("DEMO", raw_data)
    print(f"   Passed: {quality.get('passed', 'N/A')}")
    print(f"   Issues: {quality.get('issues', [])}")

    print("\n" + "=" * 80)
    print("MEDALLION INTEGRATION COMPLETE")
    print("=" * 80)
