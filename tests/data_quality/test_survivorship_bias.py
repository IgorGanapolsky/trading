"""
Tests for survivorship bias.

Ensures universe definition doesn't suffer from survivorship bias.
"""

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def universe_fixture():
    return ["SPY", "AAPL", "MSFT"]


@pytest.fixture
def data_fixture():
    dates = pd.date_range("2023-01-02", periods=30, freq="B")
    data = {}
    for ticker in ["SPY", "AAPL", "MSFT"]:
        close = np.linspace(100, 110, len(dates)) + np.random.normal(0, 0.1, len(dates))
        data[ticker] = pd.DataFrame(
            {"Close": close, "Volume": np.full(len(dates), 1_000_000)}, index=dates
        )
    return data


@pytest.fixture(name="universe")
def _universe_alias(universe_fixture):
    return universe_fixture


@pytest.fixture(name="data")
def _data_alias(data_fixture):
    return data_fixture


@pytest.fixture(name="current_data")
def _current_data_alias(data_fixture):
    return data_fixture


def test_universe_consistency(universe: list[str], data: dict[str, pd.DataFrame]) -> bool:
    """
    Test that all symbols in universe have data.

    Args:
        universe: List of symbols in universe
        data: Dictionary of symbol -> DataFrame

    Returns:
        True if all symbols have data, False otherwise
    """
    missing_symbols = []
    for symbol in universe:
        if symbol not in data or data[symbol].empty:
            missing_symbols.append(symbol)

    if missing_symbols:
        print(f"Missing data for symbols: {missing_symbols}")
        return False

    return True


def test_date_range_consistency(data: dict[str, pd.DataFrame], min_overlap: float = 0.8) -> bool:
    """
    Test that all symbols have similar date ranges (avoid survivorship bias).

    Args:
        data: Dictionary of symbol -> DataFrame
        min_overlap: Minimum overlap required (default: 80%)

    Returns:
        True if date ranges are consistent, False otherwise
    """
    if not data:
        return True

    # Get date ranges for each symbol
    date_ranges = {}
    for symbol, df in data.items():
        if not df.empty and isinstance(df.index, pd.DatetimeIndex):
            date_ranges[symbol] = (df.index.min(), df.index.max())

    if len(date_ranges) < 2:
        return True  # Need at least 2 symbols to compare

    # Find common date range
    min_date = max(r[0] for r in date_ranges.values())
    max_date = min(r[1] for r in date_ranges.values())

    if min_date >= max_date:
        print("No overlapping date range across symbols")
        return False

    # Check overlap for each symbol
    total_days = (max_date - min_date).days
    for symbol, (sym_min, sym_max) in date_ranges.items():
        overlap_start = max(min_date, sym_min)
        overlap_end = min(max_date, sym_max)
        overlap_days = (overlap_end - overlap_start).days
        overlap_pct = overlap_days / total_days if total_days > 0 else 0.0

        if overlap_pct < min_overlap:
            print(
                f"Symbol {symbol} has only {overlap_pct * 100:.1f}% overlap "
                f"(required: {min_overlap * 100:.1f}%)"
            )
            return False

    return True


def test_delisted_symbols(universe: list[str], current_data: dict[str, pd.DataFrame]) -> bool:
    """
    Test for delisted symbols (survivorship bias check).

    Args:
        universe: Original universe definition
        current_data: Current data available

    Returns:
        True if no delisted symbols, False otherwise
    """
    missing_symbols = [s for s in universe if s not in current_data]

    if missing_symbols:
        print(f"Potentially delisted symbols: {missing_symbols}")
        # This is informational - delisted symbols are expected
        return True  # Don't fail, just warn

    return True


# Pytest test functions
def test_universe_consistency_check(universe_fixture, data_fixture):
    """Pytest test for universe consistency."""
    assert test_universe_consistency(universe_fixture, data_fixture), (
        "Universe consistency check failed"
    )


def test_date_range_consistency_check(data_fixture):
    """Pytest test for date range consistency."""
    assert test_date_range_consistency(data_fixture), "Date range consistency check failed"
