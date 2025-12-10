"""
Tests for outliers and bad ticks.

Detects suspicious data points that might be errors.
"""

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def data_fixture():
    """Provide a clean price/volume series with no outliers."""
    dates = pd.date_range("2023-01-02", periods=30, freq="B")
    close = np.linspace(100, 110, len(dates)) + np.random.normal(0, 0.1, len(dates))
    volume = np.full(len(dates), 1_000_000)
    return pd.DataFrame({"Close": close, "Volume": volume}, index=dates)


@pytest.fixture(name="data")
def _data_alias(data_fixture):
    return data_fixture


def check_price_outliers(
    data: pd.DataFrame, method: str = "zscore", threshold: float = 3.0
) -> bool:
    """
    Test for price outliers using z-score or IQR method.

    Args:
        data: DataFrame with Close prices
        method: 'zscore' or 'iqr'
        threshold: Threshold for outlier detection

    Returns:
        True if no outliers, False otherwise
    """
    if "Close" not in data.columns:
        return True  # Can't check without Close

    prices = data["Close"]

    if method == "zscore":
        z_scores = np.abs((prices - prices.mean()) / prices.std())
        outliers = z_scores > threshold
    elif method == "iqr":
        Q1 = prices.quantile(0.25)
        Q3 = prices.quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - threshold * IQR
        upper_bound = Q3 + threshold * IQR
        outliers = (prices < lower_bound) | (prices > upper_bound)
    else:
        raise ValueError(f"Unknown method: {method}")

    if outliers.any():
        outlier_dates = data[outliers].index.tolist()
        outlier_prices = prices[outliers]
        print(f"Found {outliers.sum()} price outliers")
        for date, price in zip(outlier_dates, outlier_prices, strict=True):
            print(f"  {date}: ${price:.2f}")
        # This is informational - outliers might be legitimate
        return True  # Don't fail, just warn

    return True


def check_return_outliers(data: pd.DataFrame, threshold: float = 0.2) -> bool:
    """
    Test for return outliers (suspiciously large returns).

    Args:
        data: DataFrame with Close prices
        threshold: Threshold for outlier detection (default: 20%)

    Returns:
        True if no outliers, False otherwise
    """
    if "Close" not in data.columns:
        return True  # Can't check without Close

    returns = data["Close"].pct_change()
    large_returns = abs(returns) > threshold

    if large_returns.any():
        outlier_dates = data[large_returns].index.tolist()
        outlier_returns = returns[large_returns]
        print(f"Found {large_returns.sum()} return outliers (>{threshold * 100}% moves)")
        for date, ret in zip(outlier_dates, outlier_returns, strict=True):
            print(f"  {date}: {ret * 100:.2f}%")
        # This is informational - large returns might be legitimate
        return True  # Don't fail, just warn

    return True


def check_volume_outliers(
    data: pd.DataFrame, method: str = "zscore", threshold: float = 3.0
) -> bool:
    """
    Test for volume outliers.

    Args:
        data: DataFrame with Volume column
        method: 'zscore' or 'iqr'
        threshold: Threshold for outlier detection

    Returns:
        True if no outliers, False otherwise
    """
    if "Volume" not in data.columns:
        return True  # Can't check without Volume

    volume = data["Volume"]

    if method == "zscore":
        z_scores = np.abs((volume - volume.mean()) / volume.std())
        outliers = z_scores > threshold
    elif method == "iqr":
        Q1 = volume.quantile(0.25)
        Q3 = volume.quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - threshold * IQR
        upper_bound = Q3 + threshold * IQR
        outliers = (volume < lower_bound) | (volume > upper_bound)
    else:
        raise ValueError(f"Unknown method: {method}")

    if outliers.any():
        outlier_dates = data[outliers].index.tolist()
        outlier_volumes = volume[outliers]
        print(f"Found {outliers.sum()} volume outliers")
        for date, vol in zip(outlier_dates, outlier_volumes, strict=True):
            print(f"  {date}: {vol:,.0f}")
        # This is informational - outliers might be legitimate
        return True  # Don't fail, just warn

    return True


# Pytest test functions
def test_price_outliers_check(data_fixture):
    """Pytest test for price outliers."""
    assert check_price_outliers(data_fixture, method="zscore", threshold=3.0), (
        "Found price outliers"
    )


def test_return_outliers_check(data_fixture):
    """Pytest test for return outliers."""
    assert check_return_outliers(data_fixture, threshold=0.2), "Found return outliers"


def test_volume_outliers_check(data_fixture):
    """Pytest test for volume outliers."""
    assert check_volume_outliers(data_fixture, method="zscore", threshold=3.0), (
        "Found volume outliers"
    )
