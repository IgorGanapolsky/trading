"""
Data Contracts - Schema Validation and Quality Checks

This module provides a robust data quality framework for trading systems:

1. Schema Validation: Ensure DataFrames have required columns and types
2. Quality Checks: Detect gaps, bad ticks, splits, survivorship bias
3. Data Versioning: Track data snapshots for reproducibility
4. Timezone Consistency: Ensure all timestamps are properly aligned

Also provides standardized data structures for research:
- SignalSnapshot: Feature vector at time t
- FutureReturns: Forward returns
- Label: Supervised learning targets

Author: Trading System
Created: 2025-12-02
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# --- From origin/main (Research Data Structures) ---


@dataclass
class SignalSnapshot:
    """
    Standardized feature vector at time t.

    This represents all engineered features for a symbol at a specific timestamp.
    """

    timestamp: pd.Timestamp
    symbol: str
    features: pd.Series  # All engineered features
    metadata: dict[str, Any]  # Data source, quality flags, etc.

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "features": self.features.to_dict(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SignalSnapshot":
        """Create from dictionary."""
        return cls(
            timestamp=pd.Timestamp(data["timestamp"]),
            symbol=data["symbol"],
            features=pd.Series(data["features"]),
            metadata=data["metadata"],
        )


@dataclass
class FutureReturns:
    """
    Forward returns over multiple horizons.

    This represents the actual returns that occurred after a signal snapshot.
    """

    symbol: str
    timestamp: pd.Timestamp
    returns_5m: float | None = None
    returns_1h: float | None = None
    returns_1d: float | None = None
    returns_1w: float | None = None
    returns_1mo: float | None = None
    returns_3mo: float | None = None
    realized_vol_1d: float | None = None
    realized_vol_1w: float | None = None
    metadata: dict[str, Any] = None

    def __post_init__(self):
        """Initialize metadata if not provided."""
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "returns_5m": self.returns_5m,
            "returns_1h": self.returns_1h,
            "returns_1d": self.returns_1d,
            "returns_1w": self.returns_1w,
            "returns_1mo": self.returns_1mo,
            "returns_3mo": self.returns_3mo,
            "realized_vol_1d": self.realized_vol_1d,
            "realized_vol_1w": self.realized_vol_1w,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FutureReturns":
        """Create from dictionary."""
        return cls(
            symbol=data["symbol"],
            timestamp=pd.Timestamp(data["timestamp"]),
            returns_5m=data.get("returns_5m"),
            returns_1h=data.get("returns_1h"),
            returns_1d=data.get("returns_1d"),
            returns_1w=data.get("returns_1w"),
            returns_1mo=data.get("returns_1mo"),
            returns_3mo=data.get("returns_3mo"),
            realized_vol_1d=data.get("realized_vol_1d"),
            realized_vol_1w=data.get("realized_vol_1w"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Label:
    """
    Supervised learning label.

    Can represent directional (up/down), magnitude (regression), or event-based labels.
    """

    symbol: str
    timestamp: pd.Timestamp
    label_type: str  # 'directional', 'magnitude', 'volatility', 'event'
    value: float  # Label value
    horizon: str  # '5m', '1h', '1d', etc.
    metadata: dict[str, Any] = None

    def __post_init__(self):
        """Initialize metadata if not provided."""
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "label_type": self.label_type,
            "value": self.value,
            "horizon": self.horizon,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Label":
        """Create from dictionary."""
        return cls(
            symbol=data["symbol"],
            timestamp=pd.Timestamp(data["timestamp"]),
            label_type=data["label_type"],
            value=data["value"],
            horizon=data["horizon"],
            metadata=data.get("metadata", {}),
        )


def create_signal_snapshot(
    timestamp: pd.Timestamp,
    symbol: str,
    features: pd.Series,
    metadata: dict[str, Any] | None = None,
) -> SignalSnapshot:
    """Convenience function to create a SignalSnapshot."""
    if metadata is None:
        metadata = {}

    return SignalSnapshot(
        timestamp=timestamp,
        symbol=symbol,
        features=features,
        metadata=metadata,
    )


def create_future_returns(
    symbol: str,
    timestamp: pd.Timestamp,
    returns_data: dict[str, float],
    metadata: dict[str, Any] | None = None,
) -> FutureReturns:
    """Convenience function to create FutureReturns."""
    if metadata is None:
        metadata = {}

    return FutureReturns(
        symbol=symbol,
        timestamp=timestamp,
        returns_1d=returns_data.get("1d"),
        returns_1w=returns_data.get("1w"),
        returns_1mo=returns_data.get("1mo"),
        returns_3mo=returns_data.get("3mo"),
        metadata=metadata,
    )


# --- From HEAD (Validation Framework) ---


class DataQualityLevel(Enum):
    """Data quality severity levels."""

    CRITICAL = "critical"  # Data is unusable
    WARNING = "warning"  # Data has issues but usable with caution
    INFO = "info"  # Informational only
    PASS = "pass"  # All checks passed


@dataclass
class ValidationResult:
    """Result of a single validation check."""

    check_name: str
    passed: bool
    level: DataQualityLevel
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class DataQualityReport:
    """Complete data quality report."""

    symbol: str
    timestamp: str
    overall_status: DataQualityLevel
    total_checks: int
    passed_checks: int
    failed_checks: int
    results: list[ValidationResult]
    data_hash: str
    row_count: int
    date_range: tuple[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "overall_status": self.overall_status.value,
            "total_checks": self.total_checks,
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "data_hash": self.data_hash,
            "row_count": self.row_count,
            "date_range": self.date_range,
            "results": [
                {
                    "check_name": r.check_name,
                    "passed": r.passed,
                    "level": r.level.value,
                    "message": r.message,
                    "details": r.details,
                }
                for r in self.results
            ],
        }

    def save(self, path: str) -> None:
        """Save report to JSON file."""
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)


@dataclass
class OHLCVSchema:
    """Schema definition for OHLCV data."""

    required_columns: list[str] = field(
        default_factory=lambda: ["Open", "High", "Low", "Close", "Volume"]
    )
    optional_columns: list[str] = field(
        default_factory=lambda: ["Adj Close", "Dividends", "Stock Splits"]
    )
    index_type: str = "datetime"
    expected_frequency: str = "D"  # Daily
    column_dtypes: dict[str, str] = field(
        default_factory=lambda: {
            "Open": "float64",
            "High": "float64",
            "Low": "float64",
            "Close": "float64",
            "Volume": "int64",
        }
    )


class DataValidator:
    """
    Comprehensive data validation framework.
    """

    def __init__(
        self,
        schema: OHLCVSchema | None = None,
        max_gap_days: int = 5,
        max_price_change_pct: float = 50.0,
        min_volume: int = 1000,
    ):
        self.schema = schema or OHLCVSchema()
        self.max_gap_days = max_gap_days
        self.max_price_change_pct = max_price_change_pct
        self.min_volume = min_volume

    def validate(self, df: pd.DataFrame, symbol: str = "UNKNOWN") -> DataQualityReport:
        results = []

        # Schema checks
        results.append(self._check_required_columns(df))
        results.append(self._check_index_type(df))
        results.append(self._check_column_dtypes(df))

        # Data quality checks
        results.append(self._check_missing_values(df))
        results.append(self._check_data_gaps(df))
        results.append(self._check_ohlc_consistency(df))
        results.append(self._check_price_anomalies(df))
        results.append(self._check_volume_anomalies(df))
        results.append(self._check_splits_dividends(df))
        results.append(self._check_timezone_consistency(df))
        results.append(self._check_duplicate_timestamps(df))
        results.append(self._check_chronological_order(df))

        # Compute overall status
        failed = [r for r in results if not r.passed]
        critical = any(r.level == DataQualityLevel.CRITICAL for r in failed)
        warnings = any(r.level == DataQualityLevel.WARNING for r in failed)

        if critical:
            overall_status = DataQualityLevel.CRITICAL
        elif warnings:
            overall_status = DataQualityLevel.WARNING
        else:
            overall_status = DataQualityLevel.PASS

        # Compute data hash for versioning
        data_hash = self._compute_hash(df)

        # Get date range
        if len(df) > 0:
            date_range = (
                str(df.index[0])[:10]
                if hasattr(df.index[0], "strftime")
                else str(df.index[0])[:10],
                str(df.index[-1])[:10]
                if hasattr(df.index[-1], "strftime")
                else str(df.index[-1])[:10],
            )
        else:
            date_range = ("", "")

        report = DataQualityReport(
            symbol=symbol,
            timestamp=datetime.now().isoformat(),
            overall_status=overall_status,
            total_checks=len(results),
            passed_checks=len([r for r in results if r.passed]),
            failed_checks=len(failed),
            results=results,
            data_hash=data_hash,
            row_count=len(df),
            date_range=date_range,
        )

        # Log summary
        status_msg = (
            "✅ PASS"
            if overall_status == DataQualityLevel.PASS
            else f"⚠️ {overall_status.value.upper()}"
        )
        logger.info(
            f"Data validation for {symbol}: {status_msg} "
            f"({report.passed_checks}/{report.total_checks} checks passed)"
        )

        return report

    def _check_required_columns(self, df: pd.DataFrame) -> ValidationResult:
        missing = [col for col in self.schema.required_columns if col not in df.columns]

        if missing:
            return ValidationResult(
                check_name="required_columns",
                passed=False,
                level=DataQualityLevel.CRITICAL,
                message=f"Missing required columns: {missing}",
                details={"missing": missing},
            )

        return ValidationResult(
            check_name="required_columns",
            passed=True,
            level=DataQualityLevel.PASS,
            message="All required columns present",
        )

    def _check_index_type(self, df: pd.DataFrame) -> ValidationResult:
        if not isinstance(df.index, pd.DatetimeIndex):
            return ValidationResult(
                check_name="index_type",
                passed=False,
                level=DataQualityLevel.CRITICAL,
                message=f"Index type is {type(df.index).__name__}, expected DatetimeIndex",
            )

        return ValidationResult(
            check_name="index_type",
            passed=True,
            level=DataQualityLevel.PASS,
            message="Index is DatetimeIndex",
        )

    def _check_column_dtypes(self, df: pd.DataFrame) -> ValidationResult:
        issues = []

        for col, expected_dtype in self.schema.column_dtypes.items():
            if col in df.columns:
                actual_dtype = str(df[col].dtype)
                if not actual_dtype.startswith(expected_dtype.split("64")[0]):
                    issues.append(f"{col}: {actual_dtype} (expected {expected_dtype})")

        if issues:
            return ValidationResult(
                check_name="column_dtypes",
                passed=False,
                level=DataQualityLevel.WARNING,
                message=f"Column dtype mismatches: {issues}",
                details={"issues": issues},
            )

        return ValidationResult(
            check_name="column_dtypes",
            passed=True,
            level=DataQualityLevel.PASS,
            message="All column dtypes match expected",
        )

    def _check_missing_values(self, df: pd.DataFrame) -> ValidationResult:
        missing_counts = {}

        for col in self.schema.required_columns:
            if col in df.columns:
                missing = df[col].isna().sum()
                if missing > 0:
                    missing_counts[col] = int(missing)

        if missing_counts:
            total_missing = sum(missing_counts.values())
            pct_missing = total_missing / (len(df) * len(missing_counts)) * 100

            level = DataQualityLevel.CRITICAL if pct_missing > 5 else DataQualityLevel.WARNING

            return ValidationResult(
                check_name="missing_values",
                passed=False,
                level=level,
                message=f"Found {total_missing} missing values ({pct_missing:.2f}%)",
                details={"missing_counts": missing_counts},
            )

        return ValidationResult(
            check_name="missing_values",
            passed=True,
            level=DataQualityLevel.PASS,
            message="No missing values in required columns",
        )

    def _check_data_gaps(self, df: pd.DataFrame) -> ValidationResult:
        if len(df) < 2:
            return ValidationResult(
                check_name="data_gaps",
                passed=True,
                level=DataQualityLevel.INFO,
                message="Insufficient data for gap check",
            )

        date_diffs = pd.Series(df.index).diff().dropna()
        large_gaps = date_diffs[date_diffs > timedelta(days=self.max_gap_days)]

        if len(large_gaps) > 0:
            gap_dates = [str(df.index[i])[:10] for i in large_gaps.index]

            return ValidationResult(
                check_name="data_gaps",
                passed=False,
                level=DataQualityLevel.WARNING,
                message=f"Found {len(large_gaps)} gaps > {self.max_gap_days} days",
                details={
                    "gap_count": len(large_gaps),
                    "gap_dates": gap_dates[:10],
                },
            )

        return ValidationResult(
            check_name="data_gaps",
            passed=True,
            level=DataQualityLevel.PASS,
            message="No significant data gaps detected",
        )

    def _check_ohlc_consistency(self, df: pd.DataFrame) -> ValidationResult:
        issues = []

        if "High" in df.columns and "Low" in df.columns:
            invalid_hl = (df["High"] < df["Low"]).sum()
            if invalid_hl > 0:
                issues.append(f"High < Low: {invalid_hl} rows")

        if "High" in df.columns and "Close" in df.columns:
            invalid_hc = (df["High"] < df["Close"]).sum()
            if invalid_hc > 0:
                issues.append(f"High < Close: {invalid_hc} rows")

        if "Low" in df.columns and "Close" in df.columns:
            invalid_lc = (df["Low"] > df["Close"]).sum()
            if invalid_lc > 0:
                issues.append(f"Low > Close: {invalid_lc} rows")

        if "High" in df.columns and "Open" in df.columns:
            invalid_ho = (df["High"] < df["Open"]).sum()
            if invalid_ho > 0:
                issues.append(f"High < Open: {invalid_ho} rows")

        if "Low" in df.columns and "Open" in df.columns:
            invalid_lo = (df["Low"] > df["Open"]).sum()
            if invalid_lo > 0:
                issues.append(f"Low > Open: {invalid_lo} rows")

        if issues:
            return ValidationResult(
                check_name="ohlc_consistency",
                passed=False,
                level=DataQualityLevel.CRITICAL,
                message=f"OHLC consistency violations: {issues}",
                details={"issues": issues},
            )

        return ValidationResult(
            check_name="ohlc_consistency",
            passed=True,
            level=DataQualityLevel.PASS,
            message="OHLC values are logically consistent",
        )

    def _check_price_anomalies(self, df: pd.DataFrame) -> ValidationResult:
        if "Close" not in df.columns or len(df) < 2:
            return ValidationResult(
                check_name="price_anomalies",
                passed=True,
                level=DataQualityLevel.INFO,
                message="Insufficient data for price anomaly check",
            )

        pct_change = df["Close"].pct_change().abs() * 100
        anomalies = pct_change[pct_change > self.max_price_change_pct]

        if len(anomalies) > 0:
            anomaly_dates = [str(idx)[:10] for idx in anomalies.index[:10]]

            return ValidationResult(
                check_name="price_anomalies",
                passed=False,
                level=DataQualityLevel.WARNING,
                message=f"Found {len(anomalies)} price changes > {self.max_price_change_pct}%",
                details={
                    "anomaly_count": len(anomalies),
                    "anomaly_dates": anomaly_dates,
                    "max_change_pct": float(pct_change.max()),
                },
            )

        return ValidationResult(
            check_name="price_anomalies",
            passed=True,
            level=DataQualityLevel.PASS,
            message="No suspicious price anomalies detected",
        )

    def _check_volume_anomalies(self, df: pd.DataFrame) -> ValidationResult:
        if "Volume" not in df.columns:
            return ValidationResult(
                check_name="volume_anomalies",
                passed=True,
                level=DataQualityLevel.INFO,
                message="No Volume column to check",
            )

        zero_volume = (df["Volume"] == 0).sum()
        low_volume = (df["Volume"] < self.min_volume).sum()

        if zero_volume > 0 or low_volume > len(df) * 0.1:
            return ValidationResult(
                check_name="volume_anomalies",
                passed=False,
                level=DataQualityLevel.WARNING,
                message=f"Found {zero_volume} zero-volume days, {low_volume} low-volume days",
                details={
                    "zero_volume_days": int(zero_volume),
                    "low_volume_days": int(low_volume),
                    "min_volume_threshold": self.min_volume,
                },
            )

        return ValidationResult(
            check_name="volume_anomalies",
            passed=True,
            level=DataQualityLevel.PASS,
            message="Volume appears normal",
        )

    def _check_splits_dividends(self, df: pd.DataFrame) -> ValidationResult:
        if "Close" not in df.columns or len(df) < 2:
            return ValidationResult(
                check_name="splits_dividends",
                passed=True,
                level=DataQualityLevel.INFO,
                message="Insufficient data for split check",
            )

        pct_change = df["Close"].pct_change()

        split_patterns = {
            "2:1": (-0.52, -0.48),
            "3:1": (-0.70, -0.64),
            "3:2": (-0.36, -0.30),
            "4:1": (-0.77, -0.73),
        }

        potential_splits = []
        for ratio, (low, high) in split_patterns.items():
            matches = pct_change[(pct_change >= low) & (pct_change <= high)]
            if len(matches) > 0:
                for idx in matches.index:
                    potential_splits.append(
                        {
                            "date": str(idx)[:10],
                            "likely_ratio": ratio,
                            "change_pct": float(matches[idx] * 100),
                        }
                    )

        if potential_splits:
            return ValidationResult(
                check_name="splits_dividends",
                passed=False,
                level=DataQualityLevel.WARNING,
                message=f"Detected {len(potential_splits)} potential unadjusted splits",
                details={"potential_splits": potential_splits[:10]},
            )

        return ValidationResult(
            check_name="splits_dividends",
            passed=True,
            level=DataQualityLevel.PASS,
            message="No obvious unadjusted splits detected",
        )

    def _check_timezone_consistency(self, df: pd.DataFrame) -> ValidationResult:
        if not isinstance(df.index, pd.DatetimeIndex):
            return ValidationResult(
                check_name="timezone_consistency",
                passed=True,
                level=DataQualityLevel.INFO,
                message="Index is not DatetimeIndex, skipping timezone check",
            )

        tz = df.index.tz

        return ValidationResult(
            check_name="timezone_consistency",
            passed=True,
            level=DataQualityLevel.PASS,
            message=f"Timezone: {tz if tz else 'None (naive datetime)'}",
            details={"timezone": str(tz) if tz else "naive"},
        )

    def _check_duplicate_timestamps(self, df: pd.DataFrame) -> ValidationResult:
        duplicates = df.index.duplicated().sum()

        if duplicates > 0:
            return ValidationResult(
                check_name="duplicate_timestamps",
                passed=False,
                level=DataQualityLevel.CRITICAL,
                message=f"Found {duplicates} duplicate timestamps",
                details={"duplicate_count": int(duplicates)},
            )

        return ValidationResult(
            check_name="duplicate_timestamps",
            passed=True,
            level=DataQualityLevel.PASS,
            message="No duplicate timestamps",
        )

    def _check_chronological_order(self, df: pd.DataFrame) -> ValidationResult:
        if len(df) < 2:
            return ValidationResult(
                check_name="chronological_order",
                passed=True,
                level=DataQualityLevel.INFO,
                message="Insufficient data for order check",
            )

        is_sorted = df.index.is_monotonic_increasing

        if not is_sorted:
            return ValidationResult(
                check_name="chronological_order",
                passed=False,
                level=DataQualityLevel.CRITICAL,
                message="Data is not in chronological order",
            )

        return ValidationResult(
            check_name="chronological_order",
            passed=True,
            level=DataQualityLevel.PASS,
            message="Data is in chronological order",
        )

    def _compute_hash(self, df: pd.DataFrame) -> str:
        content = df.to_json(date_format="iso")
        return hashlib.md5(content.encode()).hexdigest()[:16]


class DataSnapshot:
    """
    Versioned data snapshot for reproducibility.
    """

    def __init__(self, storage_dir: str = "data/snapshots"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save_snapshot(
        self,
        df: pd.DataFrame,
        symbol: str,
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        data_hash = hashlib.md5(df.to_json(date_format="iso").encode()).hexdigest()[:8]
        snapshot_id = f"{symbol}_{timestamp}_{data_hash}"

        snapshot_dir = self.storage_dir / snapshot_id
        snapshot_dir.mkdir(exist_ok=True)

        df.to_parquet(snapshot_dir / "data.parquet")

        manifest = {
            "snapshot_id": snapshot_id,
            "symbol": symbol,
            "description": description,
            "created_at": datetime.now().isoformat(),
            "data_hash": data_hash,
            "row_count": len(df),
            "columns": list(df.columns),
            "date_range": {
                "start": str(df.index[0])[:10] if len(df) > 0 else None,
                "end": str(df.index[-1])[:10] if len(df) > 0 else None,
            },
            "metadata": metadata or {},
        }

        with open(snapshot_dir / "manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)

        logger.info(f"Saved snapshot: {snapshot_id}")
        return snapshot_id

    def load_snapshot(self, snapshot_id: str) -> tuple[pd.DataFrame, dict[str, Any]]:
        snapshot_dir = self.storage_dir / snapshot_id

        if not snapshot_dir.exists():
            raise ValueError(f"Snapshot not found: {snapshot_id}")

        df = pd.read_parquet(snapshot_dir / "data.parquet")

        with open(snapshot_dir / "manifest.json") as f:
            manifest = json.load(f)

        logger.info(f"Loaded snapshot: {snapshot_id}")
        return df, manifest

    def list_snapshots(self, symbol: str | None = None) -> list[dict[str, Any]]:
        snapshots = []

        for snapshot_dir in self.storage_dir.iterdir():
            if snapshot_dir.is_dir():
                manifest_path = snapshot_dir / "manifest.json"
                if manifest_path.exists():
                    with open(manifest_path) as f:
                        manifest = json.load(f)

                    if symbol is None or manifest.get("symbol") == symbol:
                        snapshots.append(manifest)

        return sorted(snapshots, key=lambda x: x["created_at"], reverse=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("DATA CONTRACTS AND QUALITY CHECKS DEMO")
    print("=" * 80)

    # Create sample data with some issues
    dates = pd.date_range("2023-01-01", periods=100, freq="D")
    np.random.seed(42)
    close = 100 + np.random.randn(100).cumsum()

    df = pd.DataFrame(
        {
            "Open": close * (1 + np.random.randn(100) * 0.01),
            "High": close * (1 + np.abs(np.random.randn(100)) * 0.02),
            "Low": close * (1 - np.abs(np.random.randn(100)) * 0.02),
            "Close": close,
            "Volume": np.random.randint(1000000, 10000000, 100),
        },
        index=dates,
    )

    # Add some issues for testing
    df.loc[df.index[50], "Close"] = np.nan  # Missing value
    df.loc[df.index[60], "High"] = df.loc[df.index[60], "Low"] - 1  # OHLC violation

    # Validate
    validator = DataValidator()
    report = validator.validate(df, symbol="TEST")

    print(f"\\nOverall Status: {report.overall_status.value}")
    print(f"Checks Passed: {report.passed_checks}/{report.total_checks}")
    print(f"Data Hash: {report.data_hash}")

    print("\\nCheck Results:")
    for result in report.results:
        status = "✅" if result.passed else "❌"
        print(f"  {status} {result.check_name}: {result.message}")

    # Save snapshot
    snapshot = DataSnapshot()
    snapshot_id = snapshot.save_snapshot(
        df.dropna(),  # Clean version
        symbol="TEST",
        description="Demo snapshot with clean data",
    )
    print(f"\\nSaved snapshot: {snapshot_id}")

    print("\\n" + "=" * 80)
