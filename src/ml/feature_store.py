"""
Feature Store for ML Trading Models

Provides persistent storage, versioning, and retrieval of computed features.
Prevents redundant computation and enables reproducible model training.

Key Features:
- Feature versioning with metadata tracking
- Efficient caching with TTL (time-to-live)
- Feature drift detection
- Per-symbol normalization parameter storage
- Integration with walk-forward validation

Architecture:
- SQLite backend for persistence
- In-memory LRU cache for hot features
- JSON serialization for portability

Author: Trading System
Created: 2025-12-01
"""

import hashlib
import json
import logging
import sqlite3
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class FeatureMetadata:
    """Metadata for a feature set."""

    feature_id: str
    symbol: str
    version: int
    created_at: str
    feature_names: list[str]
    data_start: str
    data_end: str
    num_samples: int
    normalization_params: dict[str, dict[str, float]]
    source_hash: str  # Hash of source data for reproducibility
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "symbol": self.symbol,
            "version": self.version,
            "created_at": self.created_at,
            "feature_names": self.feature_names,
            "data_start": self.data_start,
            "data_end": self.data_end,
            "num_samples": self.num_samples,
            "normalization_params": self.normalization_params,
            "source_hash": self.source_hash,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FeatureMetadata":
        return cls(**data)


@dataclass
class FeatureDriftReport:
    """Report on feature drift between versions."""

    symbol: str
    old_version: int
    new_version: int
    drift_detected: bool
    drift_features: list[str]
    drift_scores: dict[str, float]
    recommendation: str
    timestamp: str


class LRUCache:
    """Simple LRU cache for hot features."""

    def __init__(self, capacity: int = 100):
        self.capacity = capacity
        self.cache: OrderedDict = OrderedDict()

    def get(self, key: str) -> Any | None:
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        return None

    def put(self, key: str, value: Any) -> None:
        if key in self.cache:
            self.cache.move_to_end(key)
        else:
            if len(self.cache) >= self.capacity:
                self.cache.popitem(last=False)
        self.cache[key] = value

    def invalidate(self, key: str) -> None:
        self.cache.pop(key, None)

    def clear(self) -> None:
        self.cache.clear()


class FeatureStore:
    """
    Persistent feature store for ML trading models.

    Stores computed features with versioning, normalization parameters,
    and metadata for reproducible training.

    Args:
        db_path: Path to SQLite database
        cache_capacity: Number of feature sets to cache in memory
        ttl_hours: Time-to-live for cached features (0 = no expiry)
    """

    def __init__(
        self,
        db_path: str = "data/ml/feature_store.db",
        cache_capacity: int = 100,
        ttl_hours: int = 24,
    ):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.cache = LRUCache(capacity=cache_capacity)
        self.ttl = timedelta(hours=ttl_hours) if ttl_hours > 0 else None

        self._init_database()
        logger.info(f"FeatureStore initialized at {db_path}")

    def _init_database(self) -> None:
        """Initialize SQLite database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feature_sets (
                    feature_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    feature_names TEXT NOT NULL,
                    data_start TEXT,
                    data_end TEXT,
                    num_samples INTEGER,
                    normalization_params TEXT,
                    source_hash TEXT,
                    extra TEXT,
                    features_blob BLOB
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol_version
                ON feature_sets(symbol, version DESC)
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS feature_versions (
                    symbol TEXT PRIMARY KEY,
                    latest_version INTEGER DEFAULT 0,
                    updated_at TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS drift_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    old_version INTEGER,
                    new_version INTEGER,
                    drift_detected INTEGER,
                    drift_features TEXT,
                    drift_scores TEXT,
                    recommendation TEXT,
                    created_at TEXT
                )
            """)

            conn.commit()

    def store_features(
        self,
        symbol: str,
        features_df: pd.DataFrame,
        feature_names: list[str] | None = None,
        normalization_params: dict[str, dict[str, float]] | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> FeatureMetadata:
        """
        Store a feature set with automatic versioning.

        Args:
            symbol: Stock symbol
            features_df: DataFrame with computed features
            feature_names: List of feature column names
            normalization_params: Dict of {feature: {mean, std}} for denormalization
            extra_metadata: Additional metadata to store

        Returns:
            FeatureMetadata for stored features
        """
        # Get next version
        version = self._get_next_version(symbol)

        # Compute source hash for reproducibility
        source_hash = self._compute_hash(features_df)

        # Extract feature names if not provided
        if feature_names is None:
            feature_names = list(features_df.columns)

        # Compute normalization params if not provided
        if normalization_params is None:
            normalization_params = self._compute_normalization_params(features_df, feature_names)

        # Create metadata
        metadata = FeatureMetadata(
            feature_id=f"{symbol}_v{version}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            symbol=symbol,
            version=version,
            created_at=datetime.now().isoformat(),
            feature_names=feature_names,
            data_start=str(features_df.index[0]) if len(features_df) > 0 else "",
            data_end=str(features_df.index[-1]) if len(features_df) > 0 else "",
            num_samples=len(features_df),
            normalization_params=normalization_params,
            source_hash=source_hash,
            extra=extra_metadata or {},
        )

        # Serialize features
        features_blob = self._serialize_features(features_df)

        # Store in database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO feature_sets
                (feature_id, symbol, version, created_at, feature_names,
                 data_start, data_end, num_samples, normalization_params,
                 source_hash, extra, features_blob)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    metadata.feature_id,
                    metadata.symbol,
                    metadata.version,
                    metadata.created_at,
                    json.dumps(metadata.feature_names),
                    metadata.data_start,
                    metadata.data_end,
                    metadata.num_samples,
                    json.dumps(metadata.normalization_params),
                    metadata.source_hash,
                    json.dumps(metadata.extra),
                    features_blob,
                ),
            )

            # Update version tracker
            conn.execute(
                """
                INSERT OR REPLACE INTO feature_versions (symbol, latest_version, updated_at)
                VALUES (?, ?, ?)
            """,
                (symbol, version, datetime.now().isoformat()),
            )

            conn.commit()

        # Cache the feature set
        cache_key = f"{symbol}_v{version}"
        self.cache.put(cache_key, (metadata, features_df))

        logger.info(
            f"Stored feature set {metadata.feature_id}: "
            f"{len(feature_names)} features, {len(features_df)} samples"
        )

        return metadata

    def get_features(
        self,
        symbol: str,
        version: int | None = None,
        include_data: bool = True,
    ) -> tuple[FeatureMetadata, pd.DataFrame | None] | None:
        """
        Retrieve a feature set by symbol and version.

        Args:
            symbol: Stock symbol
            version: Feature version (None = latest)
            include_data: Whether to include the actual feature data

        Returns:
            Tuple of (metadata, features_df) or None if not found
        """
        if version is None:
            version = self._get_latest_version(symbol)
            if version == 0:
                return None

        # Check cache
        cache_key = f"{symbol}_v{version}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            metadata, features_df = cached
            if (
                self.ttl is None
                or datetime.fromisoformat(metadata.created_at) > datetime.now() - self.ttl
            ):
                if include_data:
                    return metadata, features_df
                else:
                    return metadata, None

        # Fetch from database
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT feature_id, symbol, version, created_at, feature_names,
                       data_start, data_end, num_samples, normalization_params,
                       source_hash, extra, features_blob
                FROM feature_sets
                WHERE symbol = ? AND version = ?
            """,
                (symbol, version),
            )

            row = cursor.fetchone()
            if row is None:
                return None

            metadata = FeatureMetadata(
                feature_id=row[0],
                symbol=row[1],
                version=row[2],
                created_at=row[3],
                feature_names=json.loads(row[4]),
                data_start=row[5],
                data_end=row[6],
                num_samples=row[7],
                normalization_params=json.loads(row[8]),
                source_hash=row[9],
                extra=json.loads(row[10]) if row[10] else {},
            )

            features_df = None
            if include_data and row[11]:
                features_df = self._deserialize_features(row[11])
                # Update cache
                self.cache.put(cache_key, (metadata, features_df))

            return metadata, features_df

    def get_normalization_params(self, symbol: str) -> dict[str, dict[str, float]] | None:
        """
        Get normalization parameters for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Dict of {feature: {mean, std}} or None
        """
        result = self.get_features(symbol, include_data=False)
        if result is None:
            return None
        metadata, _ = result
        return metadata.normalization_params

    def detect_drift(
        self,
        symbol: str,
        new_features: pd.DataFrame,
        threshold: float = 0.3,
    ) -> FeatureDriftReport:
        """
        Detect feature drift between stored and new features.

        Args:
            symbol: Stock symbol
            new_features: New feature DataFrame to compare
            threshold: Drift threshold (0-1, higher = more drift tolerance)

        Returns:
            FeatureDriftReport with drift analysis
        """
        result = self.get_features(symbol, include_data=True)

        if result is None:
            return FeatureDriftReport(
                symbol=symbol,
                old_version=0,
                new_version=1,
                drift_detected=False,
                drift_features=[],
                drift_scores={},
                recommendation="No previous features - store new features",
                timestamp=datetime.now().isoformat(),
            )

        metadata, old_features = result

        if old_features is None or old_features.empty:
            return FeatureDriftReport(
                symbol=symbol,
                old_version=metadata.version,
                new_version=metadata.version + 1,
                drift_detected=False,
                drift_features=[],
                drift_scores={},
                recommendation="No previous feature data - store new features",
                timestamp=datetime.now().isoformat(),
            )

        # Calculate drift for each feature
        drift_scores = {}
        drift_features = []

        for col in metadata.feature_names:
            if col not in new_features.columns:
                continue

            old_vals = old_features[col].dropna().values
            new_vals = new_features[col].dropna().values

            if len(old_vals) == 0 or len(new_vals) == 0:
                continue

            # Use KL divergence approximation via histogram comparison
            drift_score = self._calculate_drift_score(old_vals, new_vals)
            drift_scores[col] = drift_score

            if drift_score > threshold:
                drift_features.append(col)

        drift_detected = len(drift_features) > 0

        if drift_detected:
            recommendation = (
                f"Drift detected in {len(drift_features)} features. "
                f"Consider retraining model with new data distribution."
            )
        else:
            recommendation = "No significant drift. Safe to use existing model."

        report = FeatureDriftReport(
            symbol=symbol,
            old_version=metadata.version,
            new_version=metadata.version + 1,
            drift_detected=drift_detected,
            drift_features=drift_features,
            drift_scores=drift_scores,
            recommendation=recommendation,
            timestamp=datetime.now().isoformat(),
        )

        # Store report
        self._store_drift_report(report)

        return report

    def list_versions(self, symbol: str) -> list[FeatureMetadata]:
        """
        List all stored versions for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            List of FeatureMetadata for all versions
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT feature_id, symbol, version, created_at, feature_names,
                       data_start, data_end, num_samples, normalization_params,
                       source_hash, extra
                FROM feature_sets
                WHERE symbol = ?
                ORDER BY version DESC
            """,
                (symbol,),
            )

            results = []
            for row in cursor.fetchall():
                metadata = FeatureMetadata(
                    feature_id=row[0],
                    symbol=row[1],
                    version=row[2],
                    created_at=row[3],
                    feature_names=json.loads(row[4]),
                    data_start=row[5],
                    data_end=row[6],
                    num_samples=row[7],
                    normalization_params=json.loads(row[8]),
                    source_hash=row[9],
                    extra=json.loads(row[10]) if row[10] else {},
                )
                results.append(metadata)

            return results

    def delete_old_versions(self, symbol: str, keep_versions: int = 3) -> int:
        """
        Delete old versions, keeping the most recent.

        Args:
            symbol: Stock symbol
            keep_versions: Number of versions to keep

        Returns:
            Number of deleted versions
        """
        with sqlite3.connect(self.db_path) as conn:
            # Get versions to delete
            cursor = conn.execute(
                """
                SELECT version FROM feature_sets
                WHERE symbol = ?
                ORDER BY version DESC
            """,
                (symbol,),
            )

            versions = [row[0] for row in cursor.fetchall()]

            if len(versions) <= keep_versions:
                return 0

            versions_to_delete = versions[keep_versions:]

            for version in versions_to_delete:
                conn.execute(
                    "DELETE FROM feature_sets WHERE symbol = ? AND version = ?",
                    (symbol, version),
                )
                # Invalidate cache
                self.cache.invalidate(f"{symbol}_v{version}")

            conn.commit()

            deleted = len(versions_to_delete)
            logger.info(f"Deleted {deleted} old versions for {symbol}")
            return deleted

    def _get_next_version(self, symbol: str) -> int:
        """Get next version number for a symbol."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT latest_version FROM feature_versions WHERE symbol = ?",
                (symbol,),
            )
            row = cursor.fetchone()
            return (row[0] + 1) if row else 1

    def _get_latest_version(self, symbol: str) -> int:
        """Get latest version number for a symbol."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT latest_version FROM feature_versions WHERE symbol = ?",
                (symbol,),
            )
            row = cursor.fetchone()
            return row[0] if row else 0

    def _compute_hash(self, df: pd.DataFrame) -> str:
        """Compute hash of DataFrame for reproducibility."""
        content = df.to_json(date_format="iso")
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _compute_normalization_params(
        self, df: pd.DataFrame, feature_names: list[str]
    ) -> dict[str, dict[str, float]]:
        """Compute normalization parameters for features."""
        params = {}
        for col in feature_names:
            if col in df.columns:
                params[col] = {
                    "mean": float(df[col].mean()),
                    "std": float(df[col].std()),
                    "min": float(df[col].min()),
                    "max": float(df[col].max()),
                }
        return params

    def _serialize_features(self, df: pd.DataFrame) -> bytes:
        """Serialize DataFrame to bytes."""
        return df.to_parquet() if hasattr(df, "to_parquet") else df.to_json().encode()

    def _deserialize_features(self, blob: bytes) -> pd.DataFrame:
        """Deserialize bytes to DataFrame."""
        try:
            from io import BytesIO

            return pd.read_parquet(BytesIO(blob))
        except Exception:
            return pd.read_json(blob.decode())

    def _calculate_drift_score(self, old_vals: np.ndarray, new_vals: np.ndarray) -> float:
        """Calculate drift score using histogram comparison."""
        # Normalize to same scale
        combined = np.concatenate([old_vals, new_vals])
        bins = np.linspace(np.min(combined), np.max(combined), 50)

        old_hist, _ = np.histogram(old_vals, bins=bins, density=True)
        new_hist, _ = np.histogram(new_vals, bins=bins, density=True)

        # Add small epsilon to avoid division by zero
        old_hist = old_hist + 1e-10
        new_hist = new_hist + 1e-10

        # Jensen-Shannon divergence (symmetric, bounded 0-1)
        m = 0.5 * (old_hist + new_hist)
        js_divergence = 0.5 * (
            np.sum(old_hist * np.log(old_hist / m)) + np.sum(new_hist * np.log(new_hist / m))
        )

        return float(js_divergence)

    def _store_drift_report(self, report: FeatureDriftReport) -> None:
        """Store drift report in database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO drift_reports
                (symbol, old_version, new_version, drift_detected,
                 drift_features, drift_scores, recommendation, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    report.symbol,
                    report.old_version,
                    report.new_version,
                    1 if report.drift_detected else 0,
                    json.dumps(report.drift_features),
                    json.dumps(report.drift_scores),
                    report.recommendation,
                    report.timestamp,
                ),
            )
            conn.commit()


# Convenience function for integration
def get_feature_store() -> FeatureStore:
    """Get or create the global feature store instance."""
    return FeatureStore()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("FEATURE STORE DEMO")
    print("=" * 80)

    # Create sample features
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    features_df = pd.DataFrame(
        {
            "Close": np.random.randn(100).cumsum() + 100,
            "Volume": np.random.randint(1000000, 10000000, 100),
            "RSI": np.random.uniform(30, 70, 100),
            "MACD": np.random.randn(100) * 0.5,
        },
        index=dates,
    )

    store = FeatureStore(db_path="data/ml/feature_store_demo.db")

    # Store features
    print("\nStoring features...")
    metadata = store.store_features(
        symbol="SPY",
        features_df=features_df,
        extra_metadata={"source": "demo", "strategy": "momentum"},
    )
    print(f"  Stored: {metadata.feature_id}")
    print(f"  Version: {metadata.version}")
    print(f"  Features: {metadata.feature_names}")

    # Retrieve features
    print("\nRetrieving features...")
    result = store.get_features("SPY")
    if result:
        meta, df = result
        print(f"  Retrieved: {meta.feature_id}")
        print(f"  Samples: {len(df)}")

    # Check for drift
    print("\nChecking for drift...")
    new_features = features_df.copy()
    new_features["RSI"] = new_features["RSI"] + 20  # Introduce drift

    drift_report = store.detect_drift("SPY", new_features)
    print(f"  Drift detected: {drift_report.drift_detected}")
    print(f"  Drifted features: {drift_report.drift_features}")
    print(f"  Recommendation: {drift_report.recommendation}")

    print("\n" + "=" * 80)
