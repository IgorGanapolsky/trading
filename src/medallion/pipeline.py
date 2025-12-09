"""
Medallion Pipeline - End-to-End Data Processing

Orchestrates the Bronze → Silver → Gold data flow for ML trading.

Usage:
    pipeline = MedallionPipeline()

    # Full pipeline: raw data → ML tensor
    tensor, lineage = pipeline.process_full(symbol, raw_data, source="alpaca")

    # Incremental: just get inference tensor from latest data
    tensor = pipeline.get_inference_ready(symbol, raw_data)

    # Training: get train/test split with proper normalization
    train, test = pipeline.get_training_ready(symbol, raw_data)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import torch

from src.medallion.bronze import BronzeLayer
from src.medallion.gold import FeatureContract, GoldLayer, GoldMetadata
from src.medallion.silver import DataQualityReport, SilverLayer

logger = logging.getLogger(__name__)


@dataclass
class PipelineLineage:
    """Complete lineage tracking through all layers."""

    symbol: str
    pipeline_run_id: str
    timestamp: str

    bronze_batch_id: str
    silver_batch_id: str
    gold_batch_id: str

    bronze_source: str
    bronze_rows: int

    silver_quality_score: float
    silver_features: list[str]

    gold_tensor_shape: tuple[int, ...]
    gold_contract: str

    processing_time_ms: float
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "pipeline_run_id": self.pipeline_run_id,
            "timestamp": self.timestamp,
            "bronze": {
                "batch_id": self.bronze_batch_id,
                "source": self.bronze_source,
                "rows": self.bronze_rows,
            },
            "silver": {
                "batch_id": self.silver_batch_id,
                "quality_score": self.silver_quality_score,
                "features": self.silver_features,
            },
            "gold": {
                "batch_id": self.gold_batch_id,
                "tensor_shape": list(self.gold_tensor_shape),
                "contract": self.gold_contract,
            },
            "processing_time_ms": self.processing_time_ms,
            "issues": self.issues,
        }


class MedallionPipeline:
    """
    End-to-end Medallion data pipeline.

    Orchestrates Bronze → Silver → Gold processing with:
    - Full lineage tracking
    - Quality gates between layers
    - Cached intermediate results
    - Inference vs training modes
    """

    def __init__(
        self,
        bronze_path: str = "data/bronze",
        silver_path: str = "data/silver",
        gold_path: str = "data/gold",
        strict_quality: bool = False,
    ):
        self.bronze = BronzeLayer(base_path=bronze_path)
        self.silver = SilverLayer(base_path=silver_path)
        self.gold = GoldLayer(base_path=gold_path)

        self.strict_quality = strict_quality

        logger.info("MedallionPipeline initialized (Bronze → Silver → Gold)")

    def process_full(
        self,
        symbol: str,
        raw_data: pd.DataFrame,
        source: str = "unknown",
        contract: FeatureContract | None = None,
        fit_normalization: bool = True,
    ) -> tuple[torch.Tensor, PipelineLineage]:
        """
        Process raw data through full pipeline to ML-ready tensor.

        Args:
            symbol: Stock symbol
            raw_data: Raw OHLCV DataFrame
            source: Data source identifier
            contract: Optional feature contract
            fit_normalization: Whether to fit new normalization params

        Returns:
            Tuple of (ML-ready tensor, lineage tracking)
        """
        start_time = datetime.now(timezone.utc)
        run_id = f"pipeline_{symbol}_{start_time.strftime('%Y%m%d_%H%M%S')}"
        issues = []

        # ===== BRONZE LAYER =====
        logger.info(f"[{symbol}] Bronze: Ingesting {len(raw_data)} raw rows")
        bronze_meta = self.bronze.ingest(symbol, raw_data, source)

        # ===== SILVER LAYER =====
        logger.info(f"[{symbol}] Silver: Validating and enriching data")
        try:
            silver_data, silver_meta, quality_report = self.silver.process(
                symbol,
                raw_data,
                bronze_batch_id=bronze_meta.batch_id,
                strict_quality=self.strict_quality,
            )
        except ValueError as e:
            issues.append(f"Silver quality failure: {e}")
            if self.strict_quality:
                raise
            # Fallback: process without strict quality
            silver_data, silver_meta, quality_report = self.silver.process(
                symbol,
                raw_data,
                bronze_batch_id=bronze_meta.batch_id,
                strict_quality=False,
            )

        if quality_report.issues:
            issues.extend(quality_report.issues)

        # ===== GOLD LAYER =====
        logger.info(f"[{symbol}] Gold: Creating ML-ready features")
        gold_tensor, gold_meta = self.gold.process(
            symbol,
            silver_data,
            silver_batch_id=silver_meta.batch_id,
            contract=contract,
            fit_normalization=fit_normalization,
        )

        # Build lineage
        end_time = datetime.now(timezone.utc)
        processing_time_ms = (end_time - start_time).total_seconds() * 1000

        lineage = PipelineLineage(
            symbol=symbol,
            pipeline_run_id=run_id,
            timestamp=start_time.isoformat(),
            bronze_batch_id=bronze_meta.batch_id,
            bronze_source=source,
            bronze_rows=bronze_meta.row_count,
            silver_batch_id=silver_meta.batch_id,
            silver_quality_score=silver_meta.quality_score,
            silver_features=silver_meta.feature_columns,
            gold_batch_id=gold_meta.batch_id,
            gold_tensor_shape=tuple(gold_tensor.shape),
            gold_contract=f"{gold_meta.contract_name} v{gold_meta.contract_version}",
            processing_time_ms=processing_time_ms,
            issues=issues,
        )

        logger.info(
            f"[{symbol}] Pipeline complete: {gold_tensor.shape} in {processing_time_ms:.0f}ms"
        )

        return gold_tensor, lineage

    def get_inference_ready(
        self,
        symbol: str,
        raw_data: pd.DataFrame,
        source: str = "inference",
        contract: FeatureContract | None = None,
    ) -> torch.Tensor | None:
        """
        Get inference-ready tensor from raw data.

        Uses saved normalization parameters from training.

        Args:
            symbol: Stock symbol
            raw_data: Latest raw OHLCV data
            source: Data source identifier
            contract: Optional feature contract

        Returns:
            Inference tensor (1, seq_len, features) or None
        """
        # Bronze: ingest (for audit trail)
        bronze_meta = self.bronze.ingest(symbol, raw_data, source, validate=True)

        # Silver: enrich
        silver_data, silver_meta, _ = self.silver.process(
            symbol,
            raw_data,
            bronze_batch_id=bronze_meta.batch_id,
            strict_quality=False,
        )

        # Gold: get inference tensor with saved normalization
        return self.gold.get_inference_tensor(symbol, silver_data, contract)

    def get_training_ready(
        self,
        symbol: str,
        raw_data: pd.DataFrame,
        source: str = "training",
        train_ratio: float = 0.8,
        contract: FeatureContract | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor, PipelineLineage]:
        """
        Get train/test split tensors from raw data.

        Normalization is fit ONLY on training data to prevent leakage.

        Args:
            symbol: Stock symbol
            raw_data: Raw OHLCV data for training
            source: Data source identifier
            train_ratio: Ratio for train split
            contract: Optional feature contract

        Returns:
            Tuple of (train_tensor, test_tensor, lineage)
        """
        start_time = datetime.now(timezone.utc)
        run_id = f"training_{symbol}_{start_time.strftime('%Y%m%d_%H%M%S')}"

        # Bronze: ingest
        bronze_meta = self.bronze.ingest(symbol, raw_data, source)

        # Silver: enrich
        silver_data, silver_meta, quality_report = self.silver.process(
            symbol,
            raw_data,
            bronze_batch_id=bronze_meta.batch_id,
            strict_quality=False,
        )

        # Gold: train/test split
        train_tensor, test_tensor, gold_meta = self.gold.get_training_split(
            symbol,
            silver_data,
            train_ratio=train_ratio,
            contract=contract,
        )

        # Build lineage
        end_time = datetime.now(timezone.utc)
        processing_time_ms = (end_time - start_time).total_seconds() * 1000

        lineage = PipelineLineage(
            symbol=symbol,
            pipeline_run_id=run_id,
            timestamp=start_time.isoformat(),
            bronze_batch_id=bronze_meta.batch_id,
            bronze_source=source,
            bronze_rows=bronze_meta.row_count,
            silver_batch_id=silver_meta.batch_id,
            silver_quality_score=silver_meta.quality_score,
            silver_features=silver_meta.feature_columns,
            gold_batch_id=gold_meta.batch_id,
            gold_tensor_shape=(
                train_tensor.shape[0] + test_tensor.shape[0],
                train_tensor.shape[1],
                train_tensor.shape[2],
            ),
            gold_contract=f"{gold_meta.contract_name} v{gold_meta.contract_version}",
            processing_time_ms=processing_time_ms,
            issues=quality_report.issues,
        )

        logger.info(
            f"[{symbol}] Training split: train={train_tensor.shape}, test={test_tensor.shape}"
        )

        return train_tensor, test_tensor, lineage

    def get_latest_from_cache(
        self,
        symbol: str,
    ) -> tuple[torch.Tensor, GoldMetadata] | None:
        """
        Get latest cached gold tensor without reprocessing.

        Useful for quick inference when data hasn't changed.
        """
        return self.gold.get_latest(symbol)

    def validate_data(
        self,
        symbol: str,
        raw_data: pd.DataFrame,
    ) -> DataQualityReport:
        """
        Validate raw data without storing.

        Useful for pre-flight checks before processing.
        """
        # Create a temporary silver layer for validation
        silver_data, _, quality_report = self.silver.process(
            symbol,
            raw_data,
            strict_quality=False,
        )
        return quality_report

    def get_lineage(
        self,
        symbol: str,
    ) -> dict[str, Any] | None:
        """
        Get latest processing lineage for a symbol.

        Returns bronze → silver → gold batch IDs and metadata.
        """
        bronze = self.bronze.get_latest(symbol)
        silver = self.silver.get_latest(symbol)
        gold = self.gold.get_latest(symbol)

        if bronze is None:
            return None

        _, bronze_meta = bronze
        silver_meta = silver[1] if silver else None
        gold_meta = gold[1] if gold else None

        return {
            "symbol": symbol,
            "bronze": bronze_meta.to_dict(),
            "silver": silver_meta.to_dict() if silver_meta else None,
            "gold": gold_meta.to_dict() if gold_meta else None,
        }


# Convenience function for quick access
_pipeline_instance: MedallionPipeline | None = None


def get_medallion_pipeline() -> MedallionPipeline:
    """Get or create global pipeline instance."""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = MedallionPipeline()
    return _pipeline_instance


if __name__ == "__main__":
    import numpy as np

    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("MEDALLION PIPELINE DEMO")
    print("=" * 80)

    # Create sample raw data
    dates = pd.date_range("2024-01-01", periods=120, freq="D")
    raw_data = pd.DataFrame(
        {
            "Open": np.random.randn(120).cumsum() + 100,
            "High": np.random.randn(120).cumsum() + 102,
            "Low": np.random.randn(120).cumsum() + 98,
            "Close": np.random.randn(120).cumsum() + 100,
            "Volume": np.random.randint(1000000, 10000000, 120),
        },
        index=dates,
    )

    pipeline = MedallionPipeline()

    # Full pipeline processing
    print("\n1. Full Pipeline Processing")
    print("-" * 40)
    tensor, lineage = pipeline.process_full("SPY", raw_data, source="demo")
    print(f"   Output tensor: {tensor.shape}")
    print(f"   Bronze batch: {lineage.bronze_batch_id}")
    print(f"   Silver quality: {lineage.silver_quality_score:.2%}")
    print(f"   Gold contract: {lineage.gold_contract}")
    print(f"   Processing time: {lineage.processing_time_ms:.0f}ms")

    # Training split
    print("\n2. Training Split")
    print("-" * 40)
    train, test, train_lineage = pipeline.get_training_ready("SPY", raw_data)
    print(f"   Train tensor: {train.shape}")
    print(f"   Test tensor: {test.shape}")

    # Inference tensor
    print("\n3. Inference Tensor")
    print("-" * 40)
    inference = pipeline.get_inference_ready("SPY", raw_data)
    print(f"   Inference tensor: {inference.shape}")

    # Lineage check
    print("\n4. Lineage Tracking")
    print("-" * 40)
    full_lineage = pipeline.get_lineage("SPY")
    print(f"   Bronze source: {full_lineage['bronze']['source']}")
    print(f"   Silver features: {len(full_lineage['silver']['feature_columns'])} columns")
    print(f"   Gold samples: {full_lineage['gold']['num_samples']}")

    print("\n" + "=" * 80)
    print("MEDALLION ARCHITECTURE READY FOR ML TRADING")
    print("=" * 80)
