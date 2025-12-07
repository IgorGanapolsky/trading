"""
Returns-based features for trading strategy research.

Provides multi-horizon return calculations and return-based features.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def calculate_returns(
    prices: pd.Series,
    method: str = "simple",
    periods: int = 1,
) -> pd.Series:
    """
    Calculate simple or log returns over specified periods.

    Args:
        prices: Price series (typically Close prices)
        method: 'simple' or 'log' returns
        periods: Number of periods to look back

    Returns:
        Series of returns
    """
    if method == "simple":
        return prices.pct_change(periods=periods)
    elif method == "log":
        return np.log(prices / prices.shift(periods=periods))
    else:
        raise ValueError(f"Unknown method: {method}. Use 'simple' or 'log'")


def calculate_multi_horizon_returns(
    prices: pd.Series,
    horizons: list[str] | None = None,
) -> pd.DataFrame:
    """
    Calculate returns over multiple horizons.

    Args:
        prices: Price series (typically Close prices)
        horizons: List of horizon strings, e.g., ['1m', '5m', '1h', '1d', '1w']
                  If None, uses default horizons

    Returns:
        DataFrame with columns for each horizon
    """
    if horizons is None:
        horizons = ["1m", "5m", "1h", "1d", "1w"]

    # Map horizon strings to periods (assuming daily data)
    # For intraday data, these would need to be adjusted
    horizon_map = {
        "1m": 1,  # 1 minute (if minute data)
        "5m": 5,  # 5 minutes
        "1h": 60,  # 1 hour (if minute data)
        "1d": 1,  # 1 day
        "1w": 5,  # 1 week (5 trading days)
        "1mo": 21,  # 1 month (~21 trading days)
        "3mo": 63,  # 3 months (~63 trading days)
        "6mo": 126,  # 6 months (~126 trading days)
    }

    results = {}
    for horizon in horizons:
        periods = horizon_map.get(horizon, 1)
        returns = calculate_returns(prices, periods=periods)
        results[f"returns_{horizon}"] = returns

    return pd.DataFrame(results)


def calculate_cumulative_returns(
    returns: pd.Series,
    window: int,
) -> pd.Series:
    """
    Calculate cumulative returns over a rolling window.

    Args:
        returns: Return series
        window: Rolling window size

    Returns:
        Series of cumulative returns
    """
    return (1 + returns).rolling(window=window).apply(lambda x: x.prod() - 1, raw=False)


def calculate_rolling_returns(
    prices: pd.Series,
    windows: list[int],
) -> pd.DataFrame:
    """
    Calculate rolling returns over multiple windows.

    Args:
        prices: Price series
        windows: List of window sizes (e.g., [5, 10, 20, 60])

    Returns:
        DataFrame with columns for each window
    """
    results = {}
    for window in windows:
        returns = calculate_returns(prices, periods=window)
        results[f"returns_{window}d"] = returns

    return pd.DataFrame(results)
