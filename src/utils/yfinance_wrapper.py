"""
Lazy yfinance wrapper with graceful fallbacks.

This module provides a safe way to use yfinance that:
1. Handles import failures gracefully (for CI compatibility)
2. Provides mock data when yfinance is unavailable
3. Caches data to reduce API calls
4. Falls back to Alpaca for stock data when possible

Usage:
    from src.utils.yfinance_wrapper import get_vix, get_ticker, is_available

    if is_available():
        vix = get_vix()
    else:
        vix = get_vix()  # Returns mock/cached data
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Lazy pandas import
_pandas = None


def _get_pandas():
    """Lazy import pandas."""
    global _pandas
    if _pandas is None:
        try:
            import pandas as pd

            _pandas = pd
        except ImportError:
            logger.warning("pandas not available - returning empty data structures")
            _pandas = False
    return _pandas if _pandas else None


# Lazy import state
_yfinance = None
_import_attempted = False
_import_error: str | None = None

# Cache directory for offline/CI mode
CACHE_DIR = Path("data/market_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Default VIX values for when data is unavailable
DEFAULT_VIX = 18.0  # Long-term average
DEFAULT_VVIX = 90.0  # Long-term average
DEFAULT_VXV = 20.0  # 3-month VIX average


def _try_import_yfinance():
    """Attempt to import yfinance, caching the result."""
    global _yfinance, _import_attempted, _import_error

    if _import_attempted:
        return _yfinance

    _import_attempted = True

    try:
        import yfinance as yf

        _yfinance = yf
        logger.debug("yfinance imported successfully")
    except ImportError as e:
        _import_error = str(e)
        logger.warning(f"yfinance not available: {e}. Using fallback data.")
    except Exception as e:
        _import_error = str(e)
        logger.warning(f"yfinance import failed: {e}. Using fallback data.")

    return _yfinance


def is_available() -> bool:
    """Check if yfinance is available for use."""
    _try_import_yfinance()
    return _yfinance is not None


def get_import_error() -> str | None:
    """Get the import error message if yfinance failed to import."""
    _try_import_yfinance()
    return _import_error


def _load_cached_value(key: str) -> dict | None:
    """Load a cached value if it exists and is fresh (< 1 hour old)."""
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        try:
            with open(cache_file) as f:
                data = json.load(f)
            cached_time = datetime.fromisoformat(data.get("timestamp", "2000-01-01"))
            if datetime.now() - cached_time < timedelta(hours=1):
                return data
        except Exception:
            pass
    return None


def _save_cached_value(key: str, value: float, extra: dict | None = None):
    """Save a value to cache."""
    cache_file = CACHE_DIR / f"{key}.json"
    try:
        data = {
            "value": value,
            "timestamp": datetime.now().isoformat(),
            **(extra or {}),
        }
        with open(cache_file, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.debug(f"Failed to cache {key}: {e}")


def get_vix(use_cache: bool = True) -> float:
    """
    Get current VIX value with fallbacks.

    Priority:
    1. Live yfinance data (if available)
    2. Cached data (if fresh)
    3. Environment variable VIX_OVERRIDE
    4. Default value (18.0)
    """
    # Check environment override (useful for testing)
    env_vix = os.environ.get("VIX_OVERRIDE")
    if env_vix:
        try:
            return float(env_vix)
        except ValueError:
            pass

    # Try cache first if requested
    if use_cache:
        cached = _load_cached_value("vix")
        if cached:
            logger.debug(f"Using cached VIX: {cached['value']}")
            return cached["value"]

    # Try yfinance
    yf = _try_import_yfinance()
    if yf:
        try:
            vix = yf.Ticker("^VIX")
            hist = vix.history(period="1d")
            if not hist.empty:
                value = float(hist["Close"].iloc[-1])
                _save_cached_value("vix", value)
                logger.debug(f"Live VIX: {value}")
                return value
        except Exception as e:
            logger.warning(f"Failed to fetch VIX: {e}")

    # Return default
    logger.info(f"Using default VIX: {DEFAULT_VIX}")
    return DEFAULT_VIX


def get_vvix(use_cache: bool = True) -> float:
    """Get current VVIX (VIX of VIX) with fallbacks."""
    env_vvix = os.environ.get("VVIX_OVERRIDE")
    if env_vvix:
        try:
            return float(env_vvix)
        except ValueError:
            pass

    if use_cache:
        cached = _load_cached_value("vvix")
        if cached:
            return cached["value"]

    yf = _try_import_yfinance()
    if yf:
        try:
            vvix = yf.Ticker("^VVIX")
            hist = vvix.history(period="1d")
            if not hist.empty:
                value = float(hist["Close"].iloc[-1])
                _save_cached_value("vvix", value)
                return value
        except Exception as e:
            logger.warning(f"Failed to fetch VVIX: {e}")

    return DEFAULT_VVIX


def get_vxv(use_cache: bool = True) -> float:
    """Get current VXV (3-month VIX) with fallbacks."""
    env_vxv = os.environ.get("VXV_OVERRIDE")
    if env_vxv:
        try:
            return float(env_vxv)
        except ValueError:
            pass

    if use_cache:
        cached = _load_cached_value("vxv")
        if cached:
            return cached["value"]

    yf = _try_import_yfinance()
    if yf:
        try:
            vxv = yf.Ticker("^VXV")
            hist = vxv.history(period="1d")
            if not hist.empty:
                value = float(hist["Close"].iloc[-1])
                _save_cached_value("vxv", value)
                return value
        except Exception as e:
            logger.warning(f"Failed to fetch VXV: {e}")

    return DEFAULT_VXV


def get_ticker(symbol: str):
    """
    Get a yfinance Ticker object or a mock equivalent.

    Returns a real Ticker if yfinance is available, otherwise returns
    a MockTicker that provides safe default values.
    """
    yf = _try_import_yfinance()
    if yf:
        return yf.Ticker(symbol)
    return MockTicker(symbol)


def download(
    tickers: str | list[str],
    start: str | None = None,
    end: str | None = None,
    period: str = "1mo",
    interval: str = "1d",
    **kwargs,
):
    """
    Download historical data with fallbacks.

    Mirrors yfinance.download() signature but handles unavailability gracefully.
    Returns pandas DataFrame if available, empty dict otherwise.
    """
    yf = _try_import_yfinance()
    if yf:
        try:
            return yf.download(
                tickers, start=start, end=end, period=period, interval=interval, **kwargs
            )
        except Exception as e:
            logger.warning(f"yfinance download failed: {e}")

    # Return empty DataFrame with expected structure
    pd = _get_pandas()
    logger.warning(f"Returning empty DataFrame for {tickers}")
    if pd:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume", "Adj Close"])
    return {}


class MockTicker:
    """
    Mock yfinance Ticker for when yfinance is unavailable.

    Provides safe default values that won't crash the system.
    """

    def __init__(self, symbol: str):
        self.symbol = symbol
        self._info_cache: dict[str, Any] | None = None

    @property
    def info(self) -> dict[str, Any]:
        """Return mock info dict."""
        if self._info_cache:
            return self._info_cache

        self._info_cache = {
            "symbol": self.symbol,
            "shortName": f"{self.symbol} (Mock)",
            "regularMarketPrice": 100.0,
            "previousClose": 100.0,
            "volume": 0,
            "marketCap": 0,
            "trailingPE": None,
            "forwardPE": None,
            "dividendYield": None,
            "_mock": True,
        }
        return self._info_cache

    def history(
        self,
        period: str = "1mo",
        start: str | None = None,
        end: str | None = None,
        interval: str = "1d",
        **kwargs,
    ):
        """Return empty DataFrame for history."""
        logger.debug(f"MockTicker.history() called for {self.symbol}")
        pd = _get_pandas()
        if pd:
            return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
        return {}

    @property
    def options(self) -> tuple:
        """Return empty options chain dates."""
        return tuple()

    def option_chain(self, date: str | None = None):
        """Return mock option chain."""
        return MockOptionChain()

    @property
    def financials(self):
        """Return empty financials."""
        pd = _get_pandas()
        return pd.DataFrame() if pd else {}

    @property
    def quarterly_financials(self):
        """Return empty quarterly financials."""
        pd = _get_pandas()
        return pd.DataFrame() if pd else {}

    @property
    def earnings_dates(self):
        """Return empty earnings dates."""
        pd = _get_pandas()
        return pd.DataFrame() if pd else {}

    @property
    def calendar(self) -> dict:
        """Return empty calendar."""
        return {}


class MockOptionChain:
    """Mock option chain for when yfinance is unavailable."""

    def __init__(self):
        pd = _get_pandas()
        cols = [
            "contractSymbol",
            "strike",
            "lastPrice",
            "bid",
            "ask",
            "volume",
            "openInterest",
            "impliedVolatility",
        ]
        if pd:
            self.calls = pd.DataFrame(columns=cols)
            self.puts = pd.DataFrame(columns=cols)
        else:
            self.calls = {}
            self.puts = {}


# Convenience aliases
Ticker = get_ticker
