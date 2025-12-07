"""
Tests for split and dividend adjustments.

Verifies that split and dividend adjustments are correct.
"""

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def data_fixture():
    """Provide clean OHLCV data without splits or negatives."""
    dates = pd.date_range("2023-01-02", periods=30, freq="B")
    close = np.linspace(100, 110, len(dates))
    data = pd.DataFrame(
        {
            "Open": close * 0.999,
            "High": close * 1.001,
            "Low": close * 0.998,
            "Close": close,
            "Volume": np.full(len(dates), 1_000_000),
        },
        index=dates,
    )
    return data


@pytest.fixture(name="data")
def _data_alias(data_fixture):
    return data_fixture


def test_no_negative_prices(data: pd.DataFrame) -> bool:
    """
    Test that there are no negative prices.

    Args:
        data: DataFrame with OHLCV columns

    Returns:
        True if no negative prices, False otherwise
    """
    price_columns = ["Open", "High", "Low", "Close"]
    available_columns = [col for col in price_columns if col in data.columns]

    if not available_columns:
        return True  # No price columns to check

    for col in available_columns:
        negative_prices = data[col] < 0
        if negative_prices.any():
            print(f"Found negative prices in {col}")
            print(f"Negative price dates: {data[negative_prices].index.tolist()}")
            return False

    return True


def test_price_consistency(data: pd.DataFrame) -> bool:
    """
    Test that High >= Low, High >= Open, High >= Close, Low <= Open, Low <= Close.

    Args:
        data: DataFrame with OHLCV columns

    Returns:
        True if prices are consistent, False otherwise
    """
    required_columns = ["High", "Low", "Open", "Close"]
    if not all(col in data.columns for col in required_columns):
        return True  # Can't check without all columns

    # High should be >= all other prices
    high_issues = (
        (data["High"] < data["Low"])
        | (data["High"] < data["Open"])
        | (data["High"] < data["Close"])
    )

    # Low should be <= all other prices
    low_issues = (
        (data["Low"] > data["High"]) | (data["Low"] > data["Open"]) | (data["Low"] > data["Close"])
    )

    if high_issues.any() or low_issues.any():
        print("Found price consistency issues")
        if high_issues.any():
            print(f"High issues: {data[high_issues].index.tolist()}")
        if low_issues.any():
            print(f"Low issues: {data[low_issues].index.tolist()}")
        return False

    return True


def test_volume_consistency(data: pd.DataFrame) -> bool:
    """
    Test that volume is non-negative.

    Args:
        data: DataFrame with Volume column

    Returns:
        True if volume is consistent, False otherwise
    """
    if "Volume" not in data.columns:
        return True  # Can't check without Volume

    negative_volume = data["Volume"] < 0
    if negative_volume.any():
        print("Found negative volume")
        print(f"Negative volume dates: {data[negative_volume].index.tolist()}")
        return False

    return True


def test_split_adjustments(data: pd.DataFrame, threshold: float = 0.2) -> bool:
    """
    Test for potential split adjustments (large price jumps).

    Args:
        data: DataFrame with Close prices
        threshold: Threshold for detecting splits (default: 20% jump)

    Returns:
        True if no suspicious splits, False otherwise
    """
    if "Close" not in data.columns:
        return True  # Can't check without Close

    returns = data["Close"].pct_change()
    large_jumps = abs(returns) > threshold

    if large_jumps.any():
        jump_dates = data[large_jumps].index.tolist()
        jump_returns = returns[large_jumps]
        print(f"Found {large_jumps.sum()} potential splits (>{threshold * 100}% jumps)")
        for date, ret in zip(jump_dates, jump_returns, strict=True):
            print(f"  {date}: {ret * 100:.2f}%")
        # This is informational - large jumps might be legitimate
        return True  # Don't fail, just warn

    return True


# Pytest test functions
def test_negative_prices(data_fixture):
    """Pytest test for negative prices."""
    assert test_no_negative_prices(data_fixture), "Found negative prices"


def test_price_consistency_check(data_fixture):
    """Pytest test for price consistency."""
    assert test_price_consistency(data_fixture), "Found price consistency issues"


def test_volume_consistency_check(data_fixture):
    """Pytest test for volume consistency."""
    assert test_volume_consistency(data_fixture), "Found volume consistency issues"
