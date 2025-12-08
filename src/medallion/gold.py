"""
Gold Layer - ML-Ready Feature Sets

The Gold layer produces final, consumption-ready feature sets
optimized for ML model training and inference.

Key Responsibilities:
- Feature normalization with saved parameters
- Sequence creation for LSTM models
- Train/test split management
- Feature contract enforcement
- Integration with existing FeatureStore

Output: Normalized feature tensors ready for model consumption.
"""

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch

logger = logging.getLogger(__name__)


@dataclass
class FeatureContract:
    """
    Contract defining expected ML features.

    Enforces consistency between training and inference.
    """

    name: str
    version: str
    features: list[str]
    sequence_length: int
    normalization_method: str  # "zscore", "minmax", "none"

    # Expected ranges (for validation)
    expected_ranges: dict[str, tuple[float, float]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "features": self.features,
            "sequence_length": self.sequence_length,
            "normalization_method": self.normalization_method,
            "expected_ranges": self.expected_ranges,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FeatureContract":
        return cls(**data)


@dataclass
class GoldMetadata:
    """Metadata for a Gold feature set."""

    batch_id: str
    symbol: str
    silver_batch_id: str  # Lineage
    contract_name: str
    contract_version: str
    processing_time: str
    num_samples: int
    num_features: int
    sequence_length: int
    normalization_params: dict[str, dict[str, float]]
    data_start: str
    data_end: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "symbol": self.symbol,
            "silver_batch_id": self.silver_batch_id,
            "contract_name": self.contract_name,
            "contract_version": self.contract_version,
            "processing_time": self.processing_time,
            "num_samples": self.num_samples,
            "num_features": self.num_features,
            "sequence_length": self.sequence_length,
            "normalization_params": self.normalization_params,
            "data_start": self.data_start,
            "data_end": self.data_end,
        }


# Default feature contract for our trading ML
DEFAULT_CONTRACT = FeatureContract(
    name="trading_lstm_v1",
    version="1.0",
    features=[
        "Close",
        "Volume",
        "Returns",
        "RSI",
        "MACD",
        "Signal",
        "Volatility",
        "Momentum_5",
        "Momentum_10",
        "BB_Width",
        "ATR",
    ],
    sequence_length=60,
    normalization_method="zscore",
    expected_ranges={
        "RSI": (0.0, 100.0),
        "Returns": (-0.5, 0.5),
        "Volatility": (0.0, 1.0),
    },
)


class GoldLayer:
    """
    Gold Layer: ML-ready feature production.

    Transforms Silver enriched data into normalized feature tensors
    with consistent contracts for training and inference.
    """

    def __init__(
        self,
        base_path: str = "data/gold",
        default_contract: FeatureContract | None = None,
    ):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Subdirectories
        (self.base_path / "feature_store").mkdir(exist_ok=True)
        (self.base_path / "training_sets").mkdir(exist_ok=True)
        (self.base_path / "ml_ready").mkdir(exist_ok=True)

        self.default_contract = default_contract or DEFAULT_CONTRACT

        # Catalog database
        self.catalog_path = self.base_path / "catalog.db"
        self._init_catalog()

        # Cache for normalization params
        self._norm_params_cache: dict[str, dict[str, dict[str, float]]] = {}

        logger.info(f"GoldLayer initialized at {self.base_path}")

    def _init_catalog(self) -> None:
        """Initialize the gold catalog database."""
        with sqlite3.connect(self.catalog_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS gold_batches (
                    batch_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    silver_batch_id TEXT,
                    contract_name TEXT,
                    contract_version TEXT,
                    processing_time TEXT NOT NULL,
                    num_samples INTEGER,
                    num_features INTEGER,
                    sequence_length INTEGER,
                    normalization_params TEXT,
                    data_start TEXT,
                    data_end TEXT,
                    tensor_path TEXT,
                    metadata_path TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_gold_symbol
                ON gold_batches(symbol, processing_time DESC)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feature_contracts (
                    name TEXT PRIMARY KEY,
                    version TEXT,
                    contract_json TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS normalization_params (
                    symbol TEXT PRIMARY KEY,
                    params_json TEXT,
                    fitted_at TEXT,
                    sample_count INTEGER
                )
            """)
            conn.commit()

    def process(
        self,
        symbol: str,
        silver_data: pd.DataFrame,
        silver_batch_id: str | None = None,
        contract: FeatureContract | None = None,
        fit_normalization: bool = True,
    ) -> tuple[torch.Tensor, GoldMetadata]:
        """
        Process silver data into ML-ready feature tensors.

        Args:
            symbol: Stock symbol
            silver_data: Enriched data from Silver layer
            silver_batch_id: Optional silver batch ID for lineage
            contract: Feature contract to use (default if None)
            fit_normalization: If True, fit new normalization params

        Returns:
            Tuple of (feature tensor, metadata)
        """
        contract = contract or self.default_contract
        processing_time = datetime.now(timezone.utc)
        batch_id = f"gold_{symbol}_{processing_time.strftime('%Y%m%d_%H%M%S')}"

        # Step 1: Select features per contract
        feature_data = self._select_features(silver_data, contract)

        # Step 2: Normalize features
        if fit_normalization:
            normalized_data, norm_params = self._fit_normalize(
                symbol, feature_data, contract
            )
        else:
            norm_params = self._load_norm_params(symbol)
            if norm_params is None:
                raise ValueError(
                    f"Gold: No normalization params found for {symbol}. "
                    "Set fit_normalization=True for training."
                )
            normalized_data = self._apply_normalize(feature_data, norm_params, contract)

        # Step 3: Create sequences for LSTM
        sequences = self._create_sequences(normalized_data, contract.sequence_length)

        if len(sequences) == 0:
            raise ValueError(
                f"Gold: Not enough data to create sequences. "
                f"Need {contract.sequence_length} rows, got {len(normalized_data)}"
            )

        # Step 4: Convert to tensor
        tensor = torch.FloatTensor(sequences)

        # Prepare metadata
        metadata = GoldMetadata(
            batch_id=batch_id,
            symbol=symbol.upper(),
            silver_batch_id=silver_batch_id or "unknown",
            contract_name=contract.name,
            contract_version=contract.version,
            processing_time=processing_time.isoformat(),
            num_samples=len(sequences),
            num_features=len(contract.features),
            sequence_length=contract.sequence_length,
            normalization_params=norm_params,
            data_start=str(silver_data.index[0]) if len(silver_data) > 0 else "",
            data_end=str(silver_data.index[-1]) if len(silver_data) > 0 else "",
        )

        # Store tensor and metadata
        self._store_batch(tensor, metadata)

        logger.info(
            f"Gold: Created {len(sequences)} sequences for {symbol} "
            f"(shape: {tensor.shape}, batch: {batch_id})"
        )

        return tensor, metadata

    def get_inference_tensor(
        self,
        symbol: str,
        silver_data: pd.DataFrame,
        contract: FeatureContract | None = None,
    ) -> torch.Tensor | None:
        """
        Create inference tensor using saved normalization params.

        This ensures inference uses the same normalization as training.

        Args:
            symbol: Stock symbol
            silver_data: Latest enriched data
            contract: Feature contract to use

        Returns:
            Tensor ready for model inference, or None if not enough data
        """
        contract = contract or self.default_contract

        # Load saved normalization params
        norm_params = self._load_norm_params(symbol)
        if norm_params is None:
            logger.warning(
                f"Gold: No saved normalization params for {symbol}. "
                "Using fit on current data (may cause drift)."
            )
            return self.process(symbol, silver_data, contract=contract, fit_normalization=True)[0]

        # Select features
        feature_data = self._select_features(silver_data, contract)

        # Apply saved normalization
        normalized_data = self._apply_normalize(feature_data, norm_params, contract)

        # Create single sequence (last sequence_length rows)
        if len(normalized_data) < contract.sequence_length:
            logger.warning(
                f"Gold: Not enough data for inference. "
                f"Need {contract.sequence_length}, got {len(normalized_data)}"
            )
            return None

        last_sequence = normalized_data.iloc[-contract.sequence_length :].values

        # Return as batch of 1: (1, seq_len, features)
        return torch.FloatTensor(last_sequence).unsqueeze(0)

    def get_training_split(
        self,
        symbol: str,
        silver_data: pd.DataFrame,
        train_ratio: float = 0.8,
        contract: FeatureContract | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor, GoldMetadata]:
        """
        Create train/test split tensors.

        IMPORTANT: Normalization is fit ONLY on training data to prevent leakage.

        Args:
            symbol: Stock symbol
            silver_data: Enriched data from Silver layer
            train_ratio: Ratio of data for training (default 0.8)
            contract: Feature contract to use

        Returns:
            Tuple of (train_tensor, test_tensor, metadata)
        """
        contract = contract or self.default_contract

        # Split data temporally (no shuffling for time series)
        split_idx = int(len(silver_data) * train_ratio)
        train_data = silver_data.iloc[:split_idx]
        test_data = silver_data.iloc[split_idx:]

        # Select features
        train_features = self._select_features(train_data, contract)
        test_features = self._select_features(test_data, contract)

        # Fit normalization on TRAINING data only
        normalized_train, norm_params = self._fit_normalize(
            symbol, train_features, contract
        )

        # Apply to test data using training params
        normalized_test = self._apply_normalize(test_features, norm_params, contract)

        # Create sequences
        train_sequences = self._create_sequences(normalized_train, contract.sequence_length)
        test_sequences = self._create_sequences(normalized_test, contract.sequence_length)

        train_tensor = torch.FloatTensor(train_sequences)
        test_tensor = torch.FloatTensor(test_sequences)

        # Metadata
        processing_time = datetime.now(timezone.utc)
        metadata = GoldMetadata(
            batch_id=f"gold_split_{symbol}_{processing_time.strftime('%Y%m%d_%H%M%S')}",
            symbol=symbol.upper(),
            silver_batch_id="split",
            contract_name=contract.name,
            contract_version=contract.version,
            processing_time=processing_time.isoformat(),
            num_samples=len(train_sequences) + len(test_sequences),
            num_features=len(contract.features),
            sequence_length=contract.sequence_length,
            normalization_params=norm_params,
            data_start=str(silver_data.index[0]),
            data_end=str(silver_data.index[-1]),
        )

        logger.info(
            f"Gold: Created train/test split for {symbol} "
            f"(train: {len(train_sequences)}, test: {len(test_sequences)})"
        )

        return train_tensor, test_tensor, metadata

    def _select_features(
        self,
        data: pd.DataFrame,
        contract: FeatureContract,
    ) -> pd.DataFrame:
        """Select features per contract, filling missing with zeros."""
        result = pd.DataFrame(index=data.index)

        for feature in contract.features:
            if feature in data.columns:
                result[feature] = data[feature]
            else:
                logger.warning(f"Gold: Missing feature {feature}, filling with 0")
                result[feature] = 0.0

        return result

    def _fit_normalize(
        self,
        symbol: str,
        data: pd.DataFrame,
        contract: FeatureContract,
    ) -> tuple[pd.DataFrame, dict[str, dict[str, float]]]:
        """Fit normalization on data and return normalized data + params."""
        norm_params = {}
        normalized = data.copy()

        for col in contract.features:
            if col not in data.columns:
                continue

            if contract.normalization_method == "zscore":
                mean = float(data[col].mean())
                std = float(data[col].std())
                std = std if std != 0 else 1.0

                norm_params[col] = {"mean": mean, "std": std}
                normalized[col] = (data[col] - mean) / std

            elif contract.normalization_method == "minmax":
                min_val = float(data[col].min())
                max_val = float(data[col].max())
                range_val = max_val - min_val if max_val != min_val else 1.0

                norm_params[col] = {"min": min_val, "max": max_val}
                normalized[col] = (data[col] - min_val) / range_val

            else:  # no normalization
                norm_params[col] = {}

        # Save normalization params
        self._save_norm_params(symbol, norm_params)

        return normalized, norm_params

    def _apply_normalize(
        self,
        data: pd.DataFrame,
        norm_params: dict[str, dict[str, float]],
        contract: FeatureContract,
    ) -> pd.DataFrame:
        """Apply saved normalization parameters."""
        normalized = data.copy()

        for col in contract.features:
            if col not in data.columns or col not in norm_params:
                continue

            params = norm_params[col]

            if contract.normalization_method == "zscore":
                mean = params.get("mean", 0.0)
                std = params.get("std", 1.0)
                normalized[col] = (data[col] - mean) / std

            elif contract.normalization_method == "minmax":
                min_val = params.get("min", 0.0)
                max_val = params.get("max", 1.0)
                range_val = max_val - min_val if max_val != min_val else 1.0
                normalized[col] = (data[col] - min_val) / range_val

        return normalized

    def _create_sequences(
        self,
        data: pd.DataFrame,
        sequence_length: int,
    ) -> np.ndarray:
        """Create sequences for LSTM from DataFrame."""
        values = data.values

        if len(values) < sequence_length:
            return np.array([])

        sequences = []
        for i in range(len(values) - sequence_length + 1):
            sequences.append(values[i : i + sequence_length])

        return np.array(sequences)

    def _save_norm_params(
        self,
        symbol: str,
        params: dict[str, dict[str, float]],
    ) -> None:
        """Save normalization parameters for future inference."""
        with sqlite3.connect(self.catalog_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO normalization_params
                (symbol, params_json, fitted_at, sample_count)
                VALUES (?, ?, ?, ?)
            """,
                (
                    symbol.upper(),
                    json.dumps(params),
                    datetime.now(timezone.utc).isoformat(),
                    0,  # Could track sample count if needed
                ),
            )
            conn.commit()

        # Update cache
        self._norm_params_cache[symbol.upper()] = params

    def _load_norm_params(
        self,
        symbol: str,
    ) -> dict[str, dict[str, float]] | None:
        """Load saved normalization parameters."""
        # Check cache first
        if symbol.upper() in self._norm_params_cache:
            return self._norm_params_cache[symbol.upper()]

        with sqlite3.connect(self.catalog_path) as conn:
            cursor = conn.execute(
                "SELECT params_json FROM normalization_params WHERE symbol = ?",
                (symbol.upper(),),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            params = json.loads(row[0])
            self._norm_params_cache[symbol.upper()] = params
            return params

    def _store_batch(self, tensor: torch.Tensor, metadata: GoldMetadata) -> None:
        """Store tensor and metadata to disk."""
        tensor_path = self.base_path / "ml_ready" / f"{metadata.batch_id}.pt"
        metadata_path = self.base_path / "ml_ready" / f"{metadata.batch_id}_meta.json"

        torch.save(tensor, tensor_path)

        with open(metadata_path, "w") as f:
            json.dump(metadata.to_dict(), f, indent=2)

        # Record in catalog
        with sqlite3.connect(self.catalog_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO gold_batches
                (batch_id, symbol, silver_batch_id, contract_name, contract_version,
                 processing_time, num_samples, num_features, sequence_length,
                 normalization_params, data_start, data_end, tensor_path, metadata_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    metadata.batch_id,
                    metadata.symbol,
                    metadata.silver_batch_id,
                    metadata.contract_name,
                    metadata.contract_version,
                    metadata.processing_time,
                    metadata.num_samples,
                    metadata.num_features,
                    metadata.sequence_length,
                    json.dumps(metadata.normalization_params),
                    metadata.data_start,
                    metadata.data_end,
                    str(tensor_path),
                    str(metadata_path),
                ),
            )
            conn.commit()

    def get_latest(
        self,
        symbol: str,
    ) -> tuple[torch.Tensor, GoldMetadata] | None:
        """Get the latest gold tensor for a symbol."""
        with sqlite3.connect(self.catalog_path) as conn:
            cursor = conn.execute(
                """
                SELECT tensor_path, metadata_path FROM gold_batches
                WHERE symbol = ?
                ORDER BY processing_time DESC
                LIMIT 1
            """,
                (symbol.upper(),),
            )

            row = cursor.fetchone()
            if row is None:
                return None

            tensor_path = Path(row[0])
            metadata_path = Path(row[1])

            if not tensor_path.exists():
                logger.warning(f"Gold tensor not found: {tensor_path}")
                return None

            tensor = torch.load(tensor_path)

            with open(metadata_path) as f:
                meta_dict = json.load(f)
                metadata = GoldMetadata(**meta_dict)

            return tensor, metadata


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("GOLD LAYER DEMO")
    print("=" * 80)

    # Create sample silver data (enriched)
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    silver_data = pd.DataFrame(
        {
            "Open": np.random.randn(100).cumsum() + 100,
            "High": np.random.randn(100).cumsum() + 102,
            "Low": np.random.randn(100).cumsum() + 98,
            "Close": np.random.randn(100).cumsum() + 100,
            "Volume": np.random.randint(1000000, 10000000, 100),
            "Returns": np.random.randn(100) * 0.02,
            "RSI": np.random.uniform(30, 70, 100),
            "MACD": np.random.randn(100) * 0.5,
            "Signal": np.random.randn(100) * 0.3,
            "Volatility": np.abs(np.random.randn(100) * 0.02),
            "Momentum_5": np.random.randn(100) * 0.05,
            "Momentum_10": np.random.randn(100) * 0.08,
            "BB_Width": np.abs(np.random.randn(100) * 0.1),
            "ATR": np.abs(np.random.randn(100) * 2),
        },
        index=dates,
    )

    gold = GoldLayer(base_path="data/gold")

    # Process to gold
    tensor, metadata = gold.process("SPY", silver_data, silver_batch_id="demo_silver")

    print(f"\nCreated tensor: {tensor.shape}")
    print(f"  Samples: {metadata.num_samples}")
    print(f"  Features: {metadata.num_features}")
    print(f"  Sequence length: {metadata.sequence_length}")
    print(f"  Contract: {metadata.contract_name} v{metadata.contract_version}")

    # Test train/test split
    train, test, split_meta = gold.get_training_split("SPY", silver_data)
    print(f"\nTrain/Test split:")
    print(f"  Train: {train.shape}")
    print(f"  Test: {test.shape}")

    # Test inference tensor
    inference = gold.get_inference_tensor("SPY", silver_data)
    print(f"\nInference tensor: {inference.shape}")

    print("\n" + "=" * 80)
