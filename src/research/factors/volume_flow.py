"""
Volume and flow-based features for trading strategy research.

Provides volume profile, order flow imbalance, and VWAP deviation features.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def calculate_volume_profile(
    volume: pd.Series,
    prices: pd.Series,
    bins: int = 20,
) -> pd.DataFrame:
    """
    Calculate volume profile (volume at different price levels).

    Args:
        volume: Volume series
        prices: Price series
        bins: Number of price bins

    Returns:
        DataFrame with volume profile features
    """
    # Create price bins
    price_bins = pd.cut(prices, bins=bins, labels=False)

    # Aggregate volume by price bin
    volume_profile = volume.groupby(price_bins).sum()

    # Normalize
    total_volume = volume_profile.sum()
    if total_volume > 0:
        volume_profile = volume_profile / total_volume

    return pd.DataFrame({"volume_profile": volume_profile})


def calculate_vwap_deviation(
    prices: pd.Series,
    volume: pd.Series,
    window: int = 20,
) -> pd.Series:
    """
    Calculate deviation from Volume-Weighted Average Price (VWAP).

    Args:
        prices: Price series (typically Close)
        volume: Volume series
        window: Rolling window size

    Returns:
        Series of VWAP deviations (as percentage)
    """
    # Calculate VWAP
    typical_price = prices  # Could use (high + low + close) / 3
    vwap = (typical_price * volume).rolling(window=window).sum() / volume.rolling(
        window=window
    ).sum()

    # Calculate deviation
    deviation = (prices - vwap) / vwap * 100

    return deviation


def calculate_volume_ratio(
    volume: pd.Series,
    window: int = 20,
) -> pd.Series:
    """
    Calculate current volume relative to average volume.

    Args:
        volume: Volume series
        window: Rolling window size for average

    Returns:
        Series of volume ratios (current / average)
    """
    avg_volume = volume.rolling(window=window).mean()
    ratio = volume / avg_volume

    return ratio


def calculate_volume_weighted_returns(
    returns: pd.Series,
    volume: pd.Series,
    window: int = 20,
) -> pd.Series:
    """
    Calculate volume-weighted returns.

    Args:
        returns: Return series
        volume: Volume series
        window: Rolling window size

    Returns:
        Series of volume-weighted returns
    """
    weighted_returns = (returns * volume).rolling(window=window).sum() / volume.rolling(
        window=window
    ).sum()

    return weighted_returns


def calculate_obv(
    prices: pd.Series,
    volume: pd.Series,
) -> pd.Series:
    """
    Calculate On-Balance Volume (OBV).

    Args:
        prices: Price series
        volume: Volume series

    Returns:
        Series of OBV values
    """
    price_change = prices.diff()
    obv = (volume * np.sign(price_change)).cumsum()

    return obv


def calculate_volume_price_trend(
    prices: pd.Series,
    volume: pd.Series,
) -> pd.Series:
    """
    Calculate Volume Price Trend (VPT).

    Args:
        prices: Price series
        volume: Volume series

    Returns:
        Series of VPT values
    """
    price_change_pct = prices.pct_change()
    vpt = (volume * price_change_pct).cumsum()

    return vpt
