from datetime import datetime
from zoneinfo import ZoneInfo

from scripts.rth_market_executor import is_regular_trading_hours

ET = ZoneInfo("America/New_York")


def test_is_regular_trading_hours_outside():
    # Sunday at 10:00 AM ET is not a trading day
    sunday = datetime(2026, 7, 26, 10, 0, 0, tzinfo=ET)
    assert is_regular_trading_hours(sunday) is False


def test_is_regular_trading_hours_weekday_outside_hours():
    # Monday at 08:00 AM ET (pre-market) is outside RTH bounds
    monday_pre = datetime(2026, 7, 27, 8, 0, 0, tzinfo=ET)
    assert is_regular_trading_hours(monday_pre) is False
