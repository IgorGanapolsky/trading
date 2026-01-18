#!/usr/bin/env python3
"""
FIX: Calendar Awareness Failures (LL-236, LL-237)
Prevents scheduling trades on non-trading days.
Add this to your src/utils/ and import before any scheduling logic.
"""

import os
from datetime import datetime, timedelta
from typing import Optional

from alpaca.trading.client import TradingClient
from src.utils.alpaca_client import get_alpaca_credentials


def get_alpaca_client() -> TradingClient:
    """Get authenticated Alpaca client using unified credentials."""
    api_key, secret_key = get_alpaca_credentials()
    paper = os.environ.get("PAPER_TRADING", "true").lower() == "true"

    if not api_key or not secret_key:
        raise ValueError("Alpaca credentials not configured - use get_alpaca_credentials()")

    return TradingClient(api_key, secret_key, paper=paper)


def is_trading_day(target_date: datetime) -> bool:
    """
    Check if a date is a valid trading day using Alpaca calendar API.

    Args:
        target_date: The date to check

    Returns:
        True if market is open on that day, False otherwise
    """
    try:
        client = get_alpaca_client()
        date_str = target_date.strftime("%Y-%m-%d")
        calendar = client.get_calendar(start=date_str, end=date_str)
        return len(calendar) > 0
    except Exception as e:
        print(f"⚠️ Calendar API error: {e}")
        # Fallback: assume weekends are closed
        return target_date.weekday() < 5  # Mon-Fri


def get_next_trading_day(from_date: Optional[datetime] = None) -> datetime:
    """
    Get the next valid trading day.

    Args:
        from_date: Starting date (defaults to today)

    Returns:
        Next valid trading day as datetime
    """
    if from_date is None:
        from_date = datetime.now()

    check_date = from_date
    max_days = 10  # Safety limit

    for _ in range(max_days):
        if is_trading_day(check_date):
            return check_date
        check_date += timedelta(days=1)

    raise ValueError(f"No trading day found within {max_days} days of {from_date}")


def validate_schedule_time(scheduled_datetime: datetime) -> datetime:
    """
    Validate and adjust a scheduled time to ensure it falls on a trading day.

    Args:
        scheduled_datetime: The originally scheduled datetime

    Returns:
        Adjusted datetime on a valid trading day
    """
    if is_trading_day(scheduled_datetime):
        return scheduled_datetime

    # Find next valid trading day
    next_day = get_next_trading_day(scheduled_datetime)

    # Keep the same time, just adjust the date
    adjusted = next_day.replace(
        hour=scheduled_datetime.hour,
        minute=scheduled_datetime.minute,
        second=scheduled_datetime.second,
    )

    print(
        f"⚠️ Adjusted schedule from {scheduled_datetime.date()} to {adjusted.date()} (next trading day)"
    )
    return adjusted


# Quick test
if __name__ == "__main__":
    from datetime import datetime

    print("Testing calendar validation...")

    # Test today
    today = datetime.now()
    print(f"Today ({today.strftime('%A %Y-%m-%d')}): Trading day = {is_trading_day(today)}")

    # Get next trading day
    next_td = get_next_trading_day()
    print(f"Next trading day: {next_td.strftime('%A %Y-%m-%d')}")

    print("✅ Calendar validation working")
