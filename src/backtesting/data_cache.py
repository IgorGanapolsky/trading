"""
OHLCV Data Cache Module

Provides persistent caching for historical market data used in backtesting.
Uses a medallion architecture (bronze/silver/gold) for data quality management.

Features:
    - Parquet-based storage for efficient read/write
    - Automatic cache invalidation based on age
    - Multi-source support (Alpaca, yfinance)
    - Incremental data updates
    - Data validation and quality checks

Author: Trading System
Created: 2025-12-09
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class CacheMetadata:
    """Metadata for cached data."""

    symbol: str
    start_date: str
    end_date: str
    source: str
    created_at: str
    last_updated: str
    row_count: int
    checksum: str
    quality_score: float


class OHLCVDataCache:
    """
    Persistent cache for OHLCV market data.

    Uses a medallion architecture:
    - Bronze: Raw data as fetched from source
    - Silver: Cleaned and validated data
    - Gold: Aggregated and analysis-ready data
    """

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        max_age_days: int = 7,
        use_parquet: bool = True,
    ):
        """
        Initialize data cache.

        Args:
            cache_dir: Directory for cache storage (default: data/market_cache)
            max_age_days: Maximum age in days before cache is considered stale
            use_parquet: Use parquet format (True) or CSV (False)
        """
        if cache_dir is None:
            cache_dir = Path(os.getenv("TRADING_DIR", ".")) / "data" / "market_cache"

        self.cache_dir = Path(cache_dir)
        self.max_age_days = max_age_days
        self.use_parquet = use_parquet

        # Create directory structure
        self.bronze_dir = self.cache_dir / "bronze"
        self.silver_dir = self.cache_dir / "silver"
        self.gold_dir = self.cache_dir / "gold"
        self.metadata_dir = self.cache_dir / "metadata"

        for directory in [self.bronze_dir, self.silver_dir, self.gold_dir, self.metadata_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        logger.info(f"OHLCV cache initialized at {self.cache_dir}")

    def get(
        self,
        symbol: str,
        start_date: str | datetime,
        end_date: str | datetime,
        tier: str = "silver",
    ) -> pd.DataFrame | None:
        """
        Get cached data for a symbol.

        Args:
            symbol: Ticker symbol
            start_date: Start date (YYYY-MM-DD or datetime)
            end_date: End date (YYYY-MM-DD or datetime)
            tier: Data tier (bronze/silver/gold)

        Returns:
            DataFrame with OHLCV data or None if not cached
        """
        start_str = self._normalize_date(start_date)
        end_str = self._normalize_date(end_date)

        # Check if we have valid cached data
        cache_file = self._get_cache_path(symbol, tier)
        if not cache_file.exists():
            logger.debug(f"No cache found for {symbol}")
            return None

        # Check cache freshness
        if not self._is_cache_fresh(symbol, tier):
            logger.info(f"Cache for {symbol} is stale, will need refresh")
            return None

        # Load cached data
        try:
            df = self._load_data(cache_file)

            # Filter to requested date range
            df.index = pd.to_datetime(df.index)
            start_dt = pd.to_datetime(start_str)
            end_dt = pd.to_datetime(end_str)

            filtered = df[(df.index >= start_dt) & (df.index <= end_dt)]

            if filtered.empty:
                logger.warning(f"No data in cache for {symbol} in range {start_str} to {end_str}")
                return None

            logger.info(f"Retrieved {len(filtered)} bars for {symbol} from cache")
            return filtered

        except Exception as e:
            logger.error(f"Failed to load cache for {symbol}: {e}")
            return None

    def put(
        self,
        symbol: str,
        data: pd.DataFrame,
        source: str = "unknown",
        tier: str = "bronze",
    ) -> bool:
        """
        Store data in cache.

        Args:
            symbol: Ticker symbol
            data: DataFrame with OHLCV data (index should be datetime)
            source: Data source identifier
            tier: Data tier to store in

        Returns:
            True if successful
        """
        if data is None or data.empty:
            logger.warning(f"No data to cache for {symbol}")
            return False

        try:
            # Ensure proper column names
            data = self._normalize_columns(data)

            # Validate data
            quality_score = self._validate_data(data)
            if quality_score < 0.5:
                logger.warning(f"Data quality for {symbol} is low: {quality_score:.2f}")

            # Save data
            cache_file = self._get_cache_path(symbol, tier)
            self._save_data(data, cache_file)

            # Save metadata
            metadata = CacheMetadata(
                symbol=symbol,
                start_date=str(data.index.min().date()),
                end_date=str(data.index.max().date()),
                source=source,
                created_at=datetime.now().isoformat(),
                last_updated=datetime.now().isoformat(),
                row_count=len(data),
                checksum=self._calculate_checksum(data),
                quality_score=quality_score,
            )
            self._save_metadata(symbol, tier, metadata)

            logger.info(f"Cached {len(data)} bars for {symbol} to {tier}")
            return True

        except Exception as e:
            logger.error(f"Failed to cache data for {symbol}: {e}")
            return False

    def update(
        self,
        symbol: str,
        new_data: pd.DataFrame,
        source: str = "unknown",
        tier: str = "bronze",
    ) -> bool:
        """
        Update cache with new data (append or merge).

        Args:
            symbol: Ticker symbol
            new_data: New DataFrame to merge
            source: Data source
            tier: Data tier

        Returns:
            True if successful
        """
        existing = self.get(symbol, "1900-01-01", "2100-12-31", tier)

        if existing is not None:
            # Merge with existing data
            combined = pd.concat([existing, new_data])
            combined = combined[~combined.index.duplicated(keep="last")]
            combined = combined.sort_index()
        else:
            combined = new_data

        return self.put(symbol, combined, source, tier)

    def promote(self, symbol: str, from_tier: str = "bronze", to_tier: str = "silver") -> bool:
        """
        Promote data from one tier to another after validation.

        Args:
            symbol: Ticker symbol
            from_tier: Source tier
            to_tier: Destination tier

        Returns:
            True if successful
        """
        data = self.get(symbol, "1900-01-01", "2100-12-31", from_tier)
        if data is None:
            logger.warning(f"No data to promote for {symbol}")
            return False

        # Apply cleaning for silver tier
        if to_tier == "silver":
            data = self._clean_data(data)

        # Apply aggregation for gold tier
        elif to_tier == "gold":
            data = self._aggregate_data(data)

        # Get source from original metadata
        metadata = self._load_metadata(symbol, from_tier)
        source = metadata.source if metadata else "promoted"

        return self.put(symbol, data, source, to_tier)

    def invalidate(self, symbol: str, tier: str | None = None) -> bool:
        """
        Invalidate cache for a symbol.

        Args:
            symbol: Ticker symbol
            tier: Specific tier to invalidate (None = all tiers)

        Returns:
            True if any cache was invalidated
        """
        tiers = [tier] if tier else ["bronze", "silver", "gold"]
        invalidated = False

        for t in tiers:
            cache_file = self._get_cache_path(symbol, t)
            metadata_file = self._get_metadata_path(symbol, t)

            if cache_file.exists():
                cache_file.unlink()
                invalidated = True

            if metadata_file.exists():
                metadata_file.unlink()

        if invalidated:
            logger.info(f"Invalidated cache for {symbol}")

        return invalidated

    def list_cached_symbols(self, tier: str = "silver") -> list[str]:
        """List all symbols with cached data in a tier."""
        tier_dir = getattr(self, f"{tier}_dir")
        extension = ".parquet" if self.use_parquet else ".csv"

        symbols = []
        for file in tier_dir.glob(f"*{extension}"):
            symbols.append(file.stem)

        return sorted(symbols)

    def get_cache_info(self, symbol: str, tier: str = "silver") -> dict[str, Any] | None:
        """Get cache information for a symbol."""
        metadata = self._load_metadata(symbol, tier)
        if metadata is None:
            return None

        cache_file = self._get_cache_path(symbol, tier)
        file_size = cache_file.stat().st_size if cache_file.exists() else 0

        return {
            "symbol": metadata.symbol,
            "start_date": metadata.start_date,
            "end_date": metadata.end_date,
            "source": metadata.source,
            "created_at": metadata.created_at,
            "last_updated": metadata.last_updated,
            "row_count": metadata.row_count,
            "quality_score": metadata.quality_score,
            "file_size_bytes": file_size,
            "is_fresh": self._is_cache_fresh(symbol, tier),
        }

    def _get_cache_path(self, symbol: str, tier: str) -> Path:
        """Get cache file path for a symbol."""
        tier_dir = getattr(self, f"{tier}_dir")
        extension = ".parquet" if self.use_parquet else ".csv"
        return tier_dir / f"{symbol}{extension}"

    def _get_metadata_path(self, symbol: str, tier: str) -> Path:
        """Get metadata file path."""
        return self.metadata_dir / f"{symbol}_{tier}.json"

    def _normalize_date(self, date: str | datetime) -> str:
        """Normalize date to YYYY-MM-DD string."""
        if isinstance(date, datetime):
            return date.strftime("%Y-%m-%d")
        return date

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names to standard format."""
        column_map = {
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
            "adj_close": "Adj Close",
            "adjusted_close": "Adj Close",
        }

        df = df.copy()
        df.columns = [column_map.get(c.lower(), c) for c in df.columns]

        # Ensure required columns exist
        required = ["Open", "High", "Low", "Close", "Volume"]
        for col in required:
            if col not in df.columns:
                logger.warning(f"Missing required column: {col}")

        return df

    def _validate_data(self, df: pd.DataFrame) -> float:
        """
        Validate data quality.

        Returns quality score from 0 to 1.
        """
        score = 1.0

        # Check for required columns
        required = ["Open", "High", "Low", "Close", "Volume"]
        missing = [c for c in required if c not in df.columns]
        score -= len(missing) * 0.1

        # Check for null values
        null_pct = df.isnull().sum().sum() / (len(df) * len(df.columns))
        score -= null_pct

        # Check OHLC validity (High >= Low, Open/Close within High/Low)
        if all(c in df.columns for c in ["Open", "High", "Low", "Close"]):
            invalid_hl = (df["High"] < df["Low"]).sum()
            invalid_o = ((df["Open"] > df["High"]) | (df["Open"] < df["Low"])).sum()
            invalid_c = ((df["Close"] > df["High"]) | (df["Close"] < df["Low"])).sum()
            invalid_pct = (invalid_hl + invalid_o + invalid_c) / (len(df) * 3)
            score -= invalid_pct * 0.5

        # Check for zero/negative prices
        if "Close" in df.columns:
            bad_prices = (df["Close"] <= 0).sum() / len(df)
            score -= bad_prices * 0.3

        # Check for gaps > 5%
        if "Close" in df.columns and len(df) > 1:
            returns = df["Close"].pct_change().abs()
            big_gaps = (returns > 0.05).sum() / len(returns)
            score -= big_gaps * 0.1

        return max(0.0, min(1.0, score))

    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean data for silver tier."""
        df = df.copy()

        # Forward-fill missing values
        df = df.ffill()

        # Remove duplicate indices
        df = df[~df.index.duplicated(keep="last")]

        # Sort by date
        df = df.sort_index()

        # Fix invalid OHLC (High < Low)
        if all(c in df.columns for c in ["High", "Low"]):
            mask = df["High"] < df["Low"]
            df.loc[mask, ["High", "Low"]] = df.loc[mask, ["Low", "High"]].values

        # Remove rows with zero/negative close
        if "Close" in df.columns:
            df = df[df["Close"] > 0]

        return df

    def _aggregate_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Aggregate data for gold tier (add calculated fields)."""
        df = df.copy()

        if len(df) < 2:
            return df

        # Add daily returns
        df["Return"] = df["Close"].pct_change()

        # Add moving averages
        df["SMA_20"] = df["Close"].rolling(20).mean()
        df["SMA_50"] = df["Close"].rolling(50).mean()

        # Add volatility
        df["Volatility_20"] = df["Return"].rolling(20).std() * np.sqrt(252)

        # Add volume moving average
        df["Volume_MA_20"] = df["Volume"].rolling(20).mean()
        df["Volume_Ratio"] = df["Volume"] / df["Volume_MA_20"]

        return df

    def _is_cache_fresh(self, symbol: str, tier: str) -> bool:
        """Check if cache is still fresh."""
        metadata = self._load_metadata(symbol, tier)
        if metadata is None:
            return False

        try:
            last_updated = datetime.fromisoformat(metadata.last_updated)
            age = datetime.now() - last_updated
            return age.days <= self.max_age_days
        except Exception:
            return False

    def _calculate_checksum(self, df: pd.DataFrame) -> str:
        """Calculate checksum for data integrity."""
        # Use hash of shape and sample values
        content = f"{df.shape}_{df.iloc[0].to_json() if len(df) > 0 else ''}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def _save_data(self, df: pd.DataFrame, path: Path) -> None:
        """Save DataFrame to file."""
        if self.use_parquet:
            df.to_parquet(path)
        else:
            df.to_csv(path)

    def _load_data(self, path: Path) -> pd.DataFrame:
        """Load DataFrame from file."""
        if self.use_parquet:
            return pd.read_parquet(path)
        else:
            return pd.read_csv(path, index_col=0, parse_dates=True)

    def _save_metadata(self, symbol: str, tier: str, metadata: CacheMetadata) -> None:
        """Save metadata to file."""
        path = self._get_metadata_path(symbol, tier)
        with open(path, "w") as f:
            json.dump(
                {
                    "symbol": metadata.symbol,
                    "start_date": metadata.start_date,
                    "end_date": metadata.end_date,
                    "source": metadata.source,
                    "created_at": metadata.created_at,
                    "last_updated": metadata.last_updated,
                    "row_count": metadata.row_count,
                    "checksum": metadata.checksum,
                    "quality_score": metadata.quality_score,
                },
                f,
                indent=2,
            )

    def _load_metadata(self, symbol: str, tier: str) -> CacheMetadata | None:
        """Load metadata from file."""
        path = self._get_metadata_path(symbol, tier)
        if not path.exists():
            return None

        try:
            with open(path) as f:
                data = json.load(f)
                return CacheMetadata(**data)
        except Exception as e:
            logger.warning(f"Failed to load metadata for {symbol}: {e}")
            return None


# Global cache instance
_cache: OHLCVDataCache | None = None


def get_data_cache() -> OHLCVDataCache:
    """Get the global data cache instance."""
    global _cache
    if _cache is None:
        _cache = OHLCVDataCache()
    return _cache


def cached_fetch(
    symbol: str,
    start_date: str,
    end_date: str,
    fetch_func: callable,
    source: str = "custom",
) -> pd.DataFrame | None:
    """
    Fetch data with automatic caching.

    Args:
        symbol: Ticker symbol
        start_date: Start date
        end_date: End date
        fetch_func: Function to call if cache miss (takes symbol, start, end)
        source: Source identifier

    Returns:
        DataFrame with OHLCV data
    """
    cache = get_data_cache()

    # Try cache first
    data = cache.get(symbol, start_date, end_date)
    if data is not None:
        return data

    # Fetch fresh data
    try:
        data = fetch_func(symbol, start_date, end_date)
        if data is not None and not data.empty:
            cache.put(symbol, data, source, "bronze")
            cache.promote(symbol, "bronze", "silver")
            return cache.get(symbol, start_date, end_date)
    except Exception as e:
        logger.error(f"Failed to fetch data for {symbol}: {e}")

    return None
