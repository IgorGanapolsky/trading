"""
Bronze Layer - Raw Data Landing Zone

The Bronze layer stores raw market data in its original, unaltered form.
This is the source of truth for all downstream processing.

Key Principles:
- IMMUTABLE: Data is never modified after ingestion
- APPEND-ONLY: New data is added, old data preserved
- FULL HISTORY: All raw data retained for reproducibility
- TIMESTAMPED: Every record has ingestion timestamp

Storage Format:
- Parquet files for efficient storage and querying
- Partitioned by symbol and date
- Metadata tracked in SQLite catalog
"""

import hashlib
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class BronzeMetadata:
    """Metadata for a bronze data batch."""

    batch_id: str
    symbol: str
    source: str  # alpaca, polygon, yfinance, etc.
    ingestion_time: str
    data_start: str
    data_end: str
    row_count: int
    checksum: str  # For data integrity verification
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "symbol": self.symbol,
            "source": self.source,
            "ingestion_time": self.ingestion_time,
            "data_start": self.data_start,
            "data_end": self.data_end,
            "row_count": self.row_count,
            "checksum": self.checksum,
            "schema_version": self.schema_version,
        }


class BronzeLayer:
    """
    Bronze Layer: Raw data storage with immutability guarantees.

    Responsibilities:
    - Ingest raw OHLCV data from various sources
    - Store data in immutable, append-only format
    - Track lineage and provenance
    - Provide point-in-time data access for backtesting
    """

    REQUIRED_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]

    def __init__(self, base_path: str = "data/bronze"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Subdirectories for different sources
        (self.base_path / "alpaca").mkdir(exist_ok=True)
        (self.base_path / "polygon").mkdir(exist_ok=True)
        (self.base_path / "raw_ohlcv").mkdir(exist_ok=True)

        # Catalog database
        self.catalog_path = self.base_path / "catalog.db"
        self._init_catalog()

        logger.info(f"BronzeLayer initialized at {self.base_path}")

    def _init_catalog(self) -> None:
        """Initialize the bronze catalog database."""
        with sqlite3.connect(self.catalog_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bronze_batches (
                    batch_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    source TEXT NOT NULL,
                    ingestion_time TEXT NOT NULL,
                    data_start TEXT,
                    data_end TEXT,
                    row_count INTEGER,
                    checksum TEXT,
                    schema_version TEXT,
                    file_path TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol_source
                ON bronze_batches(symbol, source, ingestion_time DESC)
            """)
            conn.commit()

    def ingest(
        self,
        symbol: str,
        data: pd.DataFrame,
        source: str,
        validate: bool = True,
    ) -> BronzeMetadata:
        """
        Ingest raw market data into the bronze layer.

        Args:
            symbol: Stock symbol (e.g., "SPY")
            data: Raw OHLCV DataFrame with DatetimeIndex
            source: Data source identifier (e.g., "alpaca", "polygon")
            validate: Whether to validate data schema

        Returns:
            BronzeMetadata for the ingested batch

        Raises:
            ValueError: If data validation fails
        """
        if validate:
            self._validate_schema(data)

        # Generate unique batch ID
        ingestion_time = datetime.now(timezone.utc)
        batch_id = f"{symbol}_{source}_{ingestion_time.strftime('%Y%m%d_%H%M%S')}"

        # Compute checksum for integrity
        checksum = self._compute_checksum(data)

        # Prepare metadata
        metadata = BronzeMetadata(
            batch_id=batch_id,
            symbol=symbol.upper(),
            source=source,
            ingestion_time=ingestion_time.isoformat(),
            data_start=str(data.index[0]) if len(data) > 0 else "",
            data_end=str(data.index[-1]) if len(data) > 0 else "",
            row_count=len(data),
            checksum=checksum,
        )

        # Store data as parquet (immutable, efficient)
        file_path = self._get_file_path(symbol, source, ingestion_time)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Add ingestion metadata to DataFrame before storing
        data_with_meta = data.copy()
        data_with_meta["_batch_id"] = batch_id
        data_with_meta["_ingestion_time"] = ingestion_time.isoformat()
        data_with_meta["_source"] = source

        data_with_meta.to_parquet(file_path, index=True)

        # Update catalog
        self._record_batch(metadata, file_path)

        logger.info(
            f"Bronze: Ingested {len(data)} rows for {symbol} from {source} (batch: {batch_id})"
        )

        return metadata

    def get_latest(
        self,
        symbol: str,
        source: str | None = None,
    ) -> tuple[pd.DataFrame, BronzeMetadata] | None:
        """
        Get the latest raw data for a symbol.

        Args:
            symbol: Stock symbol
            source: Optional source filter

        Returns:
            Tuple of (DataFrame, metadata) or None if not found
        """
        with sqlite3.connect(self.catalog_path) as conn:
            if source:
                cursor = conn.execute(
                    """
                    SELECT batch_id, symbol, source, ingestion_time, data_start,
                           data_end, row_count, checksum, schema_version, file_path
                    FROM bronze_batches
                    WHERE symbol = ? AND source = ?
                    ORDER BY ingestion_time DESC
                    LIMIT 1
                """,
                    (symbol.upper(), source),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT batch_id, symbol, source, ingestion_time, data_start,
                           data_end, row_count, checksum, schema_version, file_path
                    FROM bronze_batches
                    WHERE symbol = ?
                    ORDER BY ingestion_time DESC
                    LIMIT 1
                """,
                    (symbol.upper(),),
                )

            row = cursor.fetchone()
            if row is None:
                return None

            metadata = BronzeMetadata(
                batch_id=row[0],
                symbol=row[1],
                source=row[2],
                ingestion_time=row[3],
                data_start=row[4],
                data_end=row[5],
                row_count=row[6],
                checksum=row[7],
                schema_version=row[8],
            )

            file_path = Path(row[9])
            if not file_path.exists():
                logger.warning(f"Bronze file not found: {file_path}")
                return None

            data = pd.read_parquet(file_path)

            # Verify integrity
            meta_cols = ["_batch_id", "_ingestion_time", "_source"]
            clean_data = data.drop(columns=meta_cols, errors="ignore")
            if self._compute_checksum(clean_data) != metadata.checksum:
                logger.warning(f"Checksum mismatch for {metadata.batch_id}")

            return data, metadata

    def get_historical(
        self,
        symbol: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        source: str | None = None,
    ) -> pd.DataFrame:
        """
        Get historical raw data for a symbol within a date range.

        Merges data from multiple batches if needed.

        Args:
            symbol: Stock symbol
            start_date: Optional start date filter
            end_date: Optional end date filter
            source: Optional source filter

        Returns:
            Combined DataFrame of raw data
        """
        with sqlite3.connect(self.catalog_path) as conn:
            query = """
                SELECT file_path FROM bronze_batches
                WHERE symbol = ?
            """
            params: list[Any] = [symbol.upper()]

            if source:
                query += " AND source = ?"
                params.append(source)

            query += " ORDER BY ingestion_time DESC"

            cursor = conn.execute(query, params)
            file_paths = [row[0] for row in cursor.fetchall()]

        if not file_paths:
            return pd.DataFrame()

        # Load and combine all relevant batches
        dfs = []
        for fp in file_paths:
            try:
                df = pd.read_parquet(fp)
                # Remove metadata columns for clean output
                df = df.drop(columns=["_batch_id", "_ingestion_time", "_source"], errors="ignore")
                dfs.append(df)
            except Exception as e:
                logger.warning(f"Failed to load {fp}: {e}")

        if not dfs:
            return pd.DataFrame()

        combined = pd.concat(dfs)
        combined = combined[~combined.index.duplicated(keep="last")]
        combined = combined.sort_index()

        # Apply date filters
        if start_date:
            combined = combined[combined.index >= start_date]
        if end_date:
            combined = combined[combined.index <= end_date]

        return combined

    def list_batches(
        self,
        symbol: str | None = None,
        source: str | None = None,
        limit: int = 100,
    ) -> list[BronzeMetadata]:
        """List bronze batches with optional filters."""
        with sqlite3.connect(self.catalog_path) as conn:
            query = "SELECT * FROM bronze_batches WHERE 1=1"
            params: list[Any] = []

            if symbol:
                query += " AND symbol = ?"
                params.append(symbol.upper())
            if source:
                query += " AND source = ?"
                params.append(source)

            query += f" ORDER BY ingestion_time DESC LIMIT {limit}"

            cursor = conn.execute(query, params)

            results = []
            for row in cursor.fetchall():
                results.append(
                    BronzeMetadata(
                        batch_id=row[0],
                        symbol=row[1],
                        source=row[2],
                        ingestion_time=row[3],
                        data_start=row[4],
                        data_end=row[5],
                        row_count=row[6],
                        checksum=row[7],
                        schema_version=row[8],
                    )
                )

            return results

    def _validate_schema(self, data: pd.DataFrame) -> None:
        """Validate that data has required OHLCV columns."""
        missing = set(self.REQUIRED_COLUMNS) - set(data.columns)
        if missing:
            raise ValueError(f"Bronze: Missing required columns: {missing}")

        if not isinstance(data.index, pd.DatetimeIndex):
            raise ValueError("Bronze: Index must be DatetimeIndex")

    def _compute_checksum(self, data: pd.DataFrame) -> str:
        """Compute MD5 checksum of DataFrame for integrity verification."""
        content = data.to_json(date_format="iso")
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _get_file_path(self, symbol: str, source: str, timestamp: datetime) -> Path:
        """Generate file path for bronze data."""
        date_str = timestamp.strftime("%Y%m%d")
        return self.base_path / source / f"{symbol.upper()}_{date_str}.parquet"

    def _record_batch(self, metadata: BronzeMetadata, file_path: Path) -> None:
        """Record batch metadata in catalog."""
        with sqlite3.connect(self.catalog_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO bronze_batches
                (batch_id, symbol, source, ingestion_time, data_start,
                 data_end, row_count, checksum, schema_version, file_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    metadata.batch_id,
                    metadata.symbol,
                    metadata.source,
                    metadata.ingestion_time,
                    metadata.data_start,
                    metadata.data_end,
                    metadata.row_count,
                    metadata.checksum,
                    metadata.schema_version,
                    str(file_path),
                ),
            )
            conn.commit()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import numpy as np

    print("=" * 80)
    print("BRONZE LAYER DEMO")
    print("=" * 80)

    # Create sample raw data
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    raw_data = pd.DataFrame(
        {
            "Open": np.random.randn(30).cumsum() + 100,
            "High": np.random.randn(30).cumsum() + 102,
            "Low": np.random.randn(30).cumsum() + 98,
            "Close": np.random.randn(30).cumsum() + 100,
            "Volume": np.random.randint(1000000, 10000000, 30),
        },
        index=dates,
    )

    bronze = BronzeLayer(base_path="data/bronze")

    # Ingest raw data
    metadata = bronze.ingest("SPY", raw_data, source="demo")
    print(f"\nIngested batch: {metadata.batch_id}")
    print(f"Rows: {metadata.row_count}")
    print(f"Checksum: {metadata.checksum}")

    # Retrieve latest
    result = bronze.get_latest("SPY")
    if result:
        df, meta = result
        print(f"\nRetrieved: {len(df)} rows from {meta.source}")

    print("\n" + "=" * 80)
