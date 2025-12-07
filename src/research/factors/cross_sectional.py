"""
Cross-sectional features for trading strategy research.

Provides rank-based features (percentile ranks, z-scores) for relative comparisons.
"""

import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


def calculate_percentile_ranks(
    data: pd.Series | pd.DataFrame,
    window: int | None = None,
    method: str = "linear",
) -> pd.Series | pd.DataFrame:
    """
    Calculate percentile ranks (0-100) for cross-sectional comparison.

    Args:
        data: Series or DataFrame of values to rank
        window: Rolling window for ranking. If None, ranks across all data.
        method: Ranking method ('linear', 'min', 'max', 'average', 'dense')

    Returns:
        Series or DataFrame of percentile ranks
    """
    if window is None:
        # Rank across entire series
        if isinstance(data, pd.Series):
            return data.rank(pct=True, method=method) * 100
        else:
            return data.rank(pct=True, method=method, axis=0) * 100
    else:
        # Rolling window ranking
        if isinstance(data, pd.Series):
            return data.rolling(window=window).apply(
                lambda x: pd.Series(x).rank(pct=True, method=method).iloc[-1] * 100,
                raw=False,
            )
        else:
            # For DataFrame, rank each column independently
            ranked = data.copy()
            for col in data.columns:
                ranked[col] = (
                    data[col]
                    .rolling(window=window)
                    .apply(
                        lambda x: pd.Series(x).rank(pct=True, method=method).iloc[-1] * 100,
                        raw=False,
                    )
                )
            return ranked


def calculate_z_scores(
    data: pd.Series | pd.DataFrame,
    window: int | None = None,
) -> pd.Series | pd.DataFrame:
    """
    Calculate z-scores (standardized values) for cross-sectional comparison.

    Args:
        data: Series or DataFrame of values
        window: Rolling window for z-score calculation. If None, uses all data.

    Returns:
        Series or DataFrame of z-scores
    """
    if window is None:
        # Z-score across entire series
        mean = data.mean()
        std = data.std()
        return (data - mean) / std
    else:
        # Rolling window z-score
        mean = data.rolling(window=window).mean()
        std = data.rolling(window=window).std()
        return (data - mean) / std


def calculate_cross_sectional_momentum(
    returns: pd.DataFrame,
    lookback: int = 20,
) -> pd.DataFrame:
    """
    Calculate cross-sectional momentum (rank of returns).

    Args:
        returns: DataFrame of returns (columns = symbols, index = dates)
        lookback: Lookback period for momentum calculation

    Returns:
        DataFrame of momentum ranks
    """
    # Calculate cumulative returns over lookback period
    momentum = (1 + returns).rolling(window=lookback).apply(lambda x: x.prod() - 1, raw=False)

    # Rank cross-sectionally (at each time point)
    momentum_ranks = momentum.rank(axis=1, pct=True, method="average") * 100

    return momentum_ranks


def calculate_cross_sectional_mean_reversion(
    prices: pd.DataFrame,
    window: int = 20,
) -> pd.DataFrame:
    """
    Calculate cross-sectional mean reversion signal.

    Args:
        prices: DataFrame of prices (columns = symbols, index = dates)
        window: Rolling window size

    Returns:
        DataFrame of mean reversion signals (negative = oversold, positive = overbought)
    """
    # Calculate deviation from rolling mean
    rolling_mean = prices.rolling(window=window).mean()
    deviation = (prices - rolling_mean) / rolling_mean

    # Rank cross-sectionally (negative rank = oversold, positive = overbought)
    mean_reversion = deviation.rank(axis=1, pct=True, method="average") * 100 - 50

    return mean_reversion


def calculate_relative_strength(
    symbol_returns: pd.Series,
    benchmark_returns: pd.Series,
    window: int = 20,
) -> pd.Series:
    """
    Calculate relative strength vs benchmark.

    Args:
        symbol_returns: Return series for symbol
        benchmark_returns: Return series for benchmark
        window: Rolling window size

    Returns:
        Series of relative strength (positive = outperforming)
    """
    symbol_cumret = (
        (1 + symbol_returns).rolling(window=window).apply(lambda x: x.prod() - 1, raw=False)
    )
    benchmark_cumret = (
        (1 + benchmark_returns).rolling(window=window).apply(lambda x: x.prod() - 1, raw=False)
    )

    relative_strength = symbol_cumret - benchmark_cumret

    return relative_strength
