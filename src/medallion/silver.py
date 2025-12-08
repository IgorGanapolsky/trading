"""
Silver Layer - Validated, Cleaned, Enriched Data

The Silver layer transforms Bronze raw data into a cleaned,
validated, enterprise-ready format.

Key Responsibilities:
- Data validation (schema, ranges, types)
- Cleaning (handle nulls, outliers, duplicates)
- Enrichment (add technical indicators, computed fields)
- Quality checks (completeness, consistency)

Output: Clean OHLCV data with technical indicators ready for Gold layer.
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

logger = logging.getLogger(__name__)


@dataclass
class DataQualityReport:
    """Quality report for a Silver data batch."""

    symbol: str
    batch_id: str
    timestamp: str

    # Completeness
    total_rows: int
    valid_rows: int
    completeness_pct: float

    # Validity
    null_counts: dict[str, int]
    outlier_counts: dict[str, int]
    duplicate_count: int

    # Consistency
    gap_dates: list[str]
    price_anomalies: list[dict[str, Any]]

    # Overall
    passed: bool
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "batch_id": self.batch_id,
            "timestamp": self.timestamp,
            "total_rows": self.total_rows,
            "valid_rows": self.valid_rows,
            "completeness_pct": self.completeness_pct,
            "null_counts": self.null_counts,
            "outlier_counts": self.outlier_counts,
            "duplicate_count": self.duplicate_count,
            "gap_dates": self.gap_dates,
            "price_anomalies": self.price_anomalies,
            "passed": self.passed,
            "issues": self.issues,
        }


@dataclass
class SilverMetadata:
    """Metadata for a Silver data batch."""

    batch_id: str
    symbol: str
    bronze_batch_id: str  # Lineage tracking
    processing_time: str
    data_start: str
    data_end: str
    row_count: int
    feature_columns: list[str]
    quality_score: float  # 0-1, based on quality report

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "symbol": self.symbol,
            "bronze_batch_id": self.bronze_batch_id,
            "processing_time": self.processing_time,
            "data_start": self.data_start,
            "data_end": self.data_end,
            "row_count": self.row_count,
            "feature_columns": self.feature_columns,
            "quality_score": self.quality_score,
        }


class SilverLayer:
    """
    Silver Layer: Data validation, cleaning, and enrichment.

    Transforms Bronze raw data into clean, validated data with
    technical indicators for downstream ML consumption.
    """

    # Price reasonability bounds (relative to median)
    PRICE_BOUNDS = {"min_ratio": 0.5, "max_ratio": 2.0}

    # Volume reasonability bounds
    VOLUME_BOUNDS = {"min": 0, "max_ratio": 100.0}

    # Required output columns after enrichment
    OUTPUT_COLUMNS = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
        "Returns",
        "RSI",
        "MACD",
        "Signal",
        "Volatility",
        "Volume_Change",
    ]

    def __init__(self, base_path: str = "data/silver"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Subdirectories
        (self.base_path / "validated").mkdir(exist_ok=True)
        (self.base_path / "features").mkdir(exist_ok=True)
        (self.base_path / "quality_reports").mkdir(exist_ok=True)

        # Catalog database
        self.catalog_path = self.base_path / "catalog.db"
        self._init_catalog()

        logger.info(f"SilverLayer initialized at {self.base_path}")

    def _init_catalog(self) -> None:
        """Initialize the silver catalog database."""
        with sqlite3.connect(self.catalog_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS silver_batches (
                    batch_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    bronze_batch_id TEXT,
                    processing_time TEXT NOT NULL,
                    data_start TEXT,
                    data_end TEXT,
                    row_count INTEGER,
                    feature_columns TEXT,
                    quality_score REAL,
                    file_path TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_silver_symbol
                ON silver_batches(symbol, processing_time DESC)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS quality_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    report_json TEXT,
                    created_at TEXT
                )
            """)
            conn.commit()

    def process(
        self,
        symbol: str,
        bronze_data: pd.DataFrame,
        bronze_batch_id: str | None = None,
        strict_quality: bool = True,
    ) -> tuple[pd.DataFrame, SilverMetadata, DataQualityReport]:
        """
        Process bronze data into silver layer.

        Steps:
        1. Validate data quality
        2. Clean data (nulls, duplicates, outliers)
        3. Enrich with technical indicators
        4. Final quality check

        Args:
            symbol: Stock symbol
            bronze_data: Raw data from Bronze layer
            bronze_batch_id: Optional bronze batch ID for lineage
            strict_quality: If True, raise on quality failures

        Returns:
            Tuple of (processed DataFrame, metadata, quality report)

        Raises:
            ValueError: If strict_quality=True and quality check fails
        """
        processing_time = datetime.now(timezone.utc)
        batch_id = f"silver_{symbol}_{processing_time.strftime('%Y%m%d_%H%M%S')}"

        # Step 1: Quality assessment
        quality_report = self._assess_quality(symbol, batch_id, bronze_data)

        if strict_quality and not quality_report.passed:
            raise ValueError(
                f"Silver: Quality check failed for {symbol}: {quality_report.issues}"
            )

        # Step 2: Clean data
        cleaned_data = self._clean_data(bronze_data.copy())

        # Step 3: Enrich with technical indicators
        enriched_data = self._enrich_data(cleaned_data)

        # Step 4: Final validation
        final_report = self._assess_quality(symbol, batch_id, enriched_data)

        # Calculate quality score
        quality_score = final_report.completeness_pct / 100.0

        # Prepare metadata
        metadata = SilverMetadata(
            batch_id=batch_id,
            symbol=symbol.upper(),
            bronze_batch_id=bronze_batch_id or "unknown",
            processing_time=processing_time.isoformat(),
            data_start=str(enriched_data.index[0]) if len(enriched_data) > 0 else "",
            data_end=str(enriched_data.index[-1]) if len(enriched_data) > 0 else "",
            row_count=len(enriched_data),
            feature_columns=list(enriched_data.columns),
            quality_score=quality_score,
        )

        # Store processed data
        file_path = self._store_data(enriched_data, metadata)

        # Store quality report
        self._store_quality_report(final_report)

        # Record in catalog
        self._record_batch(metadata, file_path)

        logger.info(
            f"Silver: Processed {len(enriched_data)} rows for {symbol} "
            f"(quality: {quality_score:.2%}, batch: {batch_id})"
        )

        return enriched_data, metadata, final_report

    def get_latest(
        self,
        symbol: str,
    ) -> tuple[pd.DataFrame, SilverMetadata] | None:
        """Get the latest silver data for a symbol."""
        with sqlite3.connect(self.catalog_path) as conn:
            cursor = conn.execute(
                """
                SELECT batch_id, symbol, bronze_batch_id, processing_time,
                       data_start, data_end, row_count, feature_columns,
                       quality_score, file_path
                FROM silver_batches
                WHERE symbol = ?
                ORDER BY processing_time DESC
                LIMIT 1
            """,
                (symbol.upper(),),
            )

            row = cursor.fetchone()
            if row is None:
                return None

            metadata = SilverMetadata(
                batch_id=row[0],
                symbol=row[1],
                bronze_batch_id=row[2],
                processing_time=row[3],
                data_start=row[4],
                data_end=row[5],
                row_count=row[6],
                feature_columns=json.loads(row[7]),
                quality_score=row[8],
            )

            file_path = Path(row[9])
            if not file_path.exists():
                logger.warning(f"Silver file not found: {file_path}")
                return None

            data = pd.read_parquet(file_path)
            return data, metadata

    def _assess_quality(
        self,
        symbol: str,
        batch_id: str,
        data: pd.DataFrame,
    ) -> DataQualityReport:
        """Assess data quality and generate report."""
        issues = []

        # Null counts
        null_counts = data.isnull().sum().to_dict()
        total_nulls = sum(null_counts.values())
        if total_nulls > 0:
            issues.append(f"Found {total_nulls} null values")

        # Duplicate detection
        duplicate_count = data.index.duplicated().sum()
        if duplicate_count > 0:
            issues.append(f"Found {duplicate_count} duplicate timestamps")

        # Outlier detection (simple IQR method)
        outlier_counts = {}
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col in data.columns:
                q1 = data[col].quantile(0.25)
                q3 = data[col].quantile(0.75)
                iqr = q3 - q1
                outliers = ((data[col] < q1 - 3 * iqr) | (data[col] > q3 + 3 * iqr)).sum()
                outlier_counts[col] = int(outliers)
                if outliers > 0:
                    issues.append(f"Found {outliers} outliers in {col}")

        # Gap detection (missing trading days)
        gap_dates = []
        if isinstance(data.index, pd.DatetimeIndex) and len(data) > 1:
            expected_days = pd.bdate_range(data.index[0], data.index[-1])
            actual_days = set(data.index.date)
            missing = [str(d) for d in expected_days if d.date() not in actual_days]
            gap_dates = missing[:10]  # Limit to first 10
            if len(missing) > 5:
                issues.append(f"Found {len(missing)} missing trading days")

        # Price anomaly detection (OHLC consistency)
        price_anomalies = []
        if all(col in data.columns for col in ["Open", "High", "Low", "Close"]):
            # High should be >= Open, Close, Low
            high_violations = data[
                (data["High"] < data["Open"])
                | (data["High"] < data["Close"])
                | (data["High"] < data["Low"])
            ]
            if len(high_violations) > 0:
                price_anomalies.extend([
                    {"date": str(idx), "issue": "High < other prices"}
                    for idx in high_violations.index[:5]
                ])
                issues.append(f"Found {len(high_violations)} OHLC consistency violations")

        # Calculate completeness
        total_rows = len(data)
        valid_rows = total_rows - duplicate_count
        completeness_pct = (valid_rows / total_rows * 100) if total_rows > 0 else 0

        # Pass/fail decision
        passed = len(issues) == 0 or (
            total_nulls < total_rows * 0.05  # <5% nulls OK
            and duplicate_count == 0
            and len(price_anomalies) == 0
        )

        return DataQualityReport(
            symbol=symbol,
            batch_id=batch_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_rows=total_rows,
            valid_rows=valid_rows,
            completeness_pct=completeness_pct,
            null_counts=null_counts,
            outlier_counts=outlier_counts,
            duplicate_count=duplicate_count,
            gap_dates=gap_dates,
            price_anomalies=price_anomalies,
            passed=passed,
            issues=issues,
        )

    def _clean_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Clean data: handle nulls, duplicates, outliers."""
        # Remove duplicates
        data = data[~data.index.duplicated(keep="last")]

        # Sort by index
        data = data.sort_index()

        # Handle nulls with forward fill then backward fill
        data = data.ffill().bfill()

        # Clip extreme outliers (beyond 5 std devs)
        for col in ["Open", "High", "Low", "Close"]:
            if col in data.columns:
                mean = data[col].mean()
                std = data[col].std()
                if std > 0:
                    data[col] = data[col].clip(mean - 5 * std, mean + 5 * std)

        # Ensure Volume is non-negative
        if "Volume" in data.columns:
            data["Volume"] = data["Volume"].clip(lower=0)

        return data

    def _enrich_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicators to the data."""
        if data.empty:
            return data

        # 1. Returns
        data["Returns"] = data["Close"].pct_change()

        # 2. RSI (14-period)
        delta = data["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-10)  # Avoid division by zero
        data["RSI"] = 100 - (100 / (1 + rs))

        # 3. MACD (12, 26, 9)
        exp1 = data["Close"].ewm(span=12, adjust=False).mean()
        exp2 = data["Close"].ewm(span=26, adjust=False).mean()
        data["MACD"] = exp1 - exp2
        data["Signal"] = data["MACD"].ewm(span=9, adjust=False).mean()
        data["MACD_Histogram"] = data["MACD"] - data["Signal"]

        # 4. Volatility (20-day rolling std dev of returns)
        data["Volatility"] = data["Returns"].rolling(window=20).std()

        # 5. Volume Change
        data["Volume_Change"] = data["Volume"].pct_change()

        # 6. Price momentum (5, 10, 20 day)
        data["Momentum_5"] = data["Close"].pct_change(5)
        data["Momentum_10"] = data["Close"].pct_change(10)
        data["Momentum_20"] = data["Close"].pct_change(20)

        # 7. Bollinger Bands
        data["BB_Middle"] = data["Close"].rolling(window=20).mean()
        bb_std = data["Close"].rolling(window=20).std()
        data["BB_Upper"] = data["BB_Middle"] + 2 * bb_std
        data["BB_Lower"] = data["BB_Middle"] - 2 * bb_std
        data["BB_Width"] = (data["BB_Upper"] - data["BB_Lower"]) / data["BB_Middle"]

        # 8. Average True Range (ATR)
        high_low = data["High"] - data["Low"]
        high_close = (data["High"] - data["Close"].shift()).abs()
        low_close = (data["Low"] - data["Close"].shift()).abs()
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        data["ATR"] = true_range.rolling(window=14).mean()

        # Fill NaNs from indicator calculations
        data = data.ffill().bfill().fillna(0)

        return data

    def _store_data(self, data: pd.DataFrame, metadata: SilverMetadata) -> Path:
        """Store processed data to parquet."""
        file_path = self.base_path / "features" / f"{metadata.batch_id}.parquet"
        data.to_parquet(file_path, index=True)
        return file_path

    def _store_quality_report(self, report: DataQualityReport) -> None:
        """Store quality report in database."""
        with sqlite3.connect(self.catalog_path) as conn:
            conn.execute(
                """
                INSERT INTO quality_reports (batch_id, symbol, report_json, created_at)
                VALUES (?, ?, ?, ?)
            """,
                (
                    report.batch_id,
                    report.symbol,
                    json.dumps(report.to_dict()),
                    report.timestamp,
                ),
            )
            conn.commit()

    def _record_batch(self, metadata: SilverMetadata, file_path: Path) -> None:
        """Record batch metadata in catalog."""
        with sqlite3.connect(self.catalog_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO silver_batches
                (batch_id, symbol, bronze_batch_id, processing_time,
                 data_start, data_end, row_count, feature_columns,
                 quality_score, file_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    metadata.batch_id,
                    metadata.symbol,
                    metadata.bronze_batch_id,
                    metadata.processing_time,
                    metadata.data_start,
                    metadata.data_end,
                    metadata.row_count,
                    json.dumps(metadata.feature_columns),
                    metadata.quality_score,
                    str(file_path),
                ),
            )
            conn.commit()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("SILVER LAYER DEMO")
    print("=" * 80)

    # Create sample bronze data (with some issues)
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    bronze_data = pd.DataFrame(
        {
            "Open": np.random.randn(60).cumsum() + 100,
            "High": np.random.randn(60).cumsum() + 102,
            "Low": np.random.randn(60).cumsum() + 98,
            "Close": np.random.randn(60).cumsum() + 100,
            "Volume": np.random.randint(1000000, 10000000, 60),
        },
        index=dates,
    )

    # Add some nulls to test cleaning
    bronze_data.loc[bronze_data.index[5], "Close"] = np.nan

    silver = SilverLayer(base_path="data/silver")

    # Process bronze data
    enriched, metadata, quality = silver.process(
        "SPY", bronze_data, bronze_batch_id="demo_bronze", strict_quality=False
    )

    print(f"\nProcessed batch: {metadata.batch_id}")
    print(f"Input rows: {len(bronze_data)}, Output rows: {len(enriched)}")
    print(f"Quality score: {metadata.quality_score:.2%}")
    print(f"Features added: {[c for c in enriched.columns if c not in bronze_data.columns]}")
    print(f"Quality issues: {quality.issues}")

    print("\n" + "=" * 80)
