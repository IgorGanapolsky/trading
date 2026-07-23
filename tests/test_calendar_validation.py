#!/usr/bin/env python3
"""
Tests for calendar_validation.py

Covers: is_trading_day, get_next_trading_day, validate_schedule_time, get_alpaca_client.
All Alpaca API calls are mocked -- no live network needed.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.calendar_validation import (
    get_next_trading_day,
    is_trading_day,
    validate_schedule_time,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MONDAY = datetime(2026, 2, 16, 10, 0, 0)  # Monday
SATURDAY = datetime(2026, 2, 21, 10, 0, 0)  # Saturday
SUNDAY = datetime(2026, 2, 22, 10, 0, 0)  # Sunday


# NOTE: get_alpaca_client tests removed — function now imported from
# src.utils.alpaca_client (tested in tests/test_alpaca_client.py)


# ---------------------------------------------------------------------------
# is_trading_day
# ---------------------------------------------------------------------------


@patch("src.utils.calendar_validation.get_alpaca_client")
def test_is_trading_day_true_when_calendar_returns_entry(mock_client_fn):
    """Calendar API returns an entry -> True."""
    mock_client = MagicMock()
    mock_client.get_calendar.return_value = [MagicMock()]  # one entry
    mock_client_fn.return_value = mock_client

    assert is_trading_day(MONDAY) is True


@patch("src.utils.calendar_validation.get_alpaca_client")
def test_is_trading_day_false_when_calendar_empty(mock_client_fn):
    """Calendar API returns empty list -> False (holiday / weekend)."""
    mock_client = MagicMock()
    mock_client.get_calendar.return_value = []
    mock_client_fn.return_value = mock_client

    assert is_trading_day(SATURDAY) is False


@patch("src.utils.calendar_validation.get_alpaca_client")
def test_is_trading_day_fallback_weekday_on_api_error(mock_client_fn):
    """On API error, fall back to weekday check (Mon-Fri = True)."""
    mock_client_fn.side_effect = Exception("network timeout")

    assert is_trading_day(MONDAY) is True  # Monday -> True
    assert is_trading_day(SATURDAY) is False  # Saturday -> False
    assert is_trading_day(SUNDAY) is False  # Sunday -> False


@patch("src.utils.calendar_validation.get_alpaca_client")
def test_is_trading_day_passes_correct_date_string(mock_client_fn):
    """Should format the date as YYYY-MM-DD for the API call."""
    mock_client = MagicMock()
    mock_client.get_calendar.return_value = [MagicMock()]
    mock_client_fn.return_value = mock_client

    target = datetime(2026, 7, 4, 9, 30, 0)
    is_trading_day(target)

    mock_client.get_calendar.assert_called_once_with(start="2026-07-04", end="2026-07-04")


# ---------------------------------------------------------------------------
# get_next_trading_day
# ---------------------------------------------------------------------------


@patch("src.utils.calendar_validation.is_trading_day")
def test_get_next_trading_day_returns_same_day_if_trading(mock_is_td):
    """If from_date is already a trading day, return it immediately."""
    mock_is_td.return_value = True

    result = get_next_trading_day(MONDAY)
    assert result == MONDAY


@patch("src.utils.calendar_validation.is_trading_day")
def test_get_next_trading_day_skips_weekend(mock_is_td):
    """Saturday -> skip Sat, Sun -> return Monday."""
    # Saturday=False, Sunday=False, Monday=True
    mock_is_td.side_effect = [False, False, True]

    result = get_next_trading_day(SATURDAY)
    expected_monday = SATURDAY + timedelta(days=2)
    assert result == expected_monday


@patch("src.utils.calendar_validation.is_trading_day")
def test_get_next_trading_day_defaults_to_now(mock_is_td):
    """When from_date is None, should use datetime.now()."""
    mock_is_td.return_value = True

    result = get_next_trading_day()
    # Just verify it returns a datetime close to now
    assert isinstance(result, datetime)
    assert abs((result - datetime.now()).total_seconds()) < 5


@patch("src.utils.calendar_validation.is_trading_day", return_value=False)
def test_get_next_trading_day_raises_after_max_days(mock_is_td):
    """Should raise ValueError if no trading day found within 10 days."""
    with pytest.raises(ValueError, match="No trading day found"):
        get_next_trading_day(MONDAY)

    # Confirm it checked exactly 10 days
    assert mock_is_td.call_count == 10


# ---------------------------------------------------------------------------
# validate_schedule_time
# ---------------------------------------------------------------------------


@patch("src.utils.calendar_validation.is_trading_day", return_value=True)
def test_validate_schedule_time_no_adjustment_needed(mock_is_td):
    """If already a trading day, return the same datetime unchanged."""
    dt = datetime(2026, 2, 16, 14, 30, 0)
    result = validate_schedule_time(dt)
    assert result == dt


@patch("src.utils.calendar_validation.get_next_trading_day")
@patch("src.utils.calendar_validation.is_trading_day", return_value=False)
def test_validate_schedule_time_adjusts_to_next_trading_day(mock_is_td, mock_next):
    """Should move to next trading day but keep original time."""
    scheduled = datetime(2026, 2, 21, 14, 30, 45)  # Saturday 2:30:45 PM
    next_monday = datetime(2026, 2, 23, 0, 0, 0)  # Monday midnight
    mock_next.return_value = next_monday

    result = validate_schedule_time(scheduled)

    # Date from next trading day, time from original schedule
    assert result.year == 2026
    assert result.month == 2
    assert result.day == 23
    assert result.hour == 14
    assert result.minute == 30
    assert result.second == 45


@patch("src.utils.calendar_validation.get_next_trading_day")
@patch("src.utils.calendar_validation.is_trading_day", return_value=False)
def test_validate_schedule_time_preserves_hour_minute_second(mock_is_td, mock_next):
    """Time components (h/m/s) must survive the date adjustment."""
    scheduled = datetime(2026, 3, 1, 9, 15, 59)
    mock_next.return_value = datetime(2026, 3, 2, 0, 0, 0)

    result = validate_schedule_time(scheduled)
    assert (result.hour, result.minute, result.second) == (9, 15, 59)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@patch("src.utils.calendar_validation.get_alpaca_client")
def test_is_trading_day_all_weekdays(mock_client_fn):
    """Verify API fallback treats Mon-Fri as trading days."""
    mock_client_fn.side_effect = Exception("offline")

    # Mon=0 through Fri=4
    for weekday_offset in range(5):
        day = datetime(2026, 2, 16) + timedelta(days=weekday_offset)  # Mon-Fri
        assert is_trading_day(day) is True, f"weekday {day.weekday()} should be True"


@patch("src.utils.calendar_validation.is_trading_day")
def test_get_next_trading_day_holiday_on_friday(mock_is_td):
    """Friday holiday -> skip Fri, Sat, Sun -> return Monday."""
    friday = datetime(2026, 4, 3, 10, 0, 0)  # Good Friday
    # Fri=False, Sat=False, Sun=False, Mon=True
    mock_is_td.side_effect = [False, False, False, True]

    result = get_next_trading_day(friday)
    expected_monday = friday + timedelta(days=3)
    assert result == expected_monday


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
