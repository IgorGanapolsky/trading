"""
Tests for gaps in time series data.

Ensures no missing trading days in the data.
"""

import pandas as pd
import pytest


@pytest.fixture
def data_fixture():
    """Provide a simple business-day time series without gaps or weekends."""
    dates = pd.date_range("2023-01-02", periods=30, freq="B")  # Business days
    return pd.DataFrame({"value": range(len(dates))}, index=dates)


# Alias fixture so tests expecting 'data' receive the same frame
@pytest.fixture(name="data")
def _data_alias(data_fixture):
    return data_fixture


def test_no_gaps_in_trading_days(data: pd.DataFrame) -> bool:
    """
    Test that there are no gaps in trading days.

    Args:
        data: DataFrame with datetime index

    Returns:
        True if no gaps, False otherwise
    """
    if not isinstance(data.index, pd.DatetimeIndex):
        raise ValueError("Data must have DatetimeIndex")

    # Get unique dates
    dates = data.index.normalize().unique()
    dates = pd.Series(dates).sort_values()

    if len(dates) < 2:
        return True  # Not enough data to check

    # Calculate gaps (excluding weekends)
    date_diff = dates.diff()
    # Trading days should be consecutive (1 day apart) or have weekends (2-3 days apart)
    # Gaps > 3 days might indicate missing data
    large_gaps = date_diff > pd.Timedelta(days=3)

    if large_gaps.any():
        gap_dates = dates[large_gaps.shift(-1).fillna(False)]
        print(f"Found {large_gaps.sum()} gaps > 3 days")
        print(f"Gap dates: {gap_dates.tolist()}")
        return False

    return True


def test_no_weekend_data(data: pd.DataFrame) -> bool:
    """
    Test that there is no weekend data (Saturday/Sunday).

    Args:
        data: DataFrame with datetime index

    Returns:
        True if no weekend data, False otherwise
    """
    if not isinstance(data.index, pd.DatetimeIndex):
        raise ValueError("Data must have DatetimeIndex")

    # Check for weekend days
    weekend_mask = data.index.weekday >= 5  # Saturday=5, Sunday=6
    weekend_data = data[weekend_mask]

    if len(weekend_data) > 0:
        print(f"Found {len(weekend_data)} weekend data points")
        print(f"Weekend dates: {weekend_data.index.tolist()}")
        return False

    return True


def test_consistent_frequency(data: pd.DataFrame, expected_freq: str = "B") -> bool:
    """
    Test that data has consistent frequency.

    Args:
        data: DataFrame with datetime index
        expected_freq: Expected frequency ('D' for daily, 'H' for hourly, etc.)

    Returns:
        True if frequency is consistent, False otherwise
    """
    if not isinstance(data.index, pd.DatetimeIndex):
        raise ValueError("Data must have DatetimeIndex")

    # Infer frequency
    inferred_freq = pd.infer_freq(data.index)

    if inferred_freq != expected_freq:
        print(f"Expected frequency: {expected_freq}, got: {inferred_freq}")
        return False

    return True


# Pytest test functions
def test_data_gaps(data_fixture):
    """Pytest test for data gaps."""
    assert test_no_gaps_in_trading_days(data_fixture), "Found gaps in trading days"


def test_weekend_data(data_fixture):
    """Pytest test for weekend data."""
    assert test_no_weekend_data(data_fixture), "Found weekend data"


def test_frequency_consistency(data_fixture):
    """Pytest test for frequency consistency."""
    assert test_consistent_frequency(data_fixture, expected_freq="B"), "Frequency is not consistent"
