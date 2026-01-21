#!/usr/bin/env python3
"""
Check if US markets are currently closed.
Used by CI to determine if it's safe to run backtests.

Exit codes:
  0 - Market is closed (safe to backtest)
  1 - Market is open (skip backtest)
"""

import os
import sys
from datetime import datetime, time
from zoneinfo import ZoneInfo

# US market holidays for 2025-2026
MARKET_HOLIDAYS = {
    # 2025
    "2025-01-01",  # New Year's Day
    "2025-01-20",  # MLK Day
    "2025-02-17",  # Presidents' Day
    "2025-04-18",  # Good Friday
    "2025-05-26",  # Memorial Day
    "2025-06-19",  # Juneteenth
    "2025-07-04",  # Independence Day
    "2025-09-01",  # Labor Day
    "2025-11-27",  # Thanksgiving
    "2025-12-25",  # Christmas
    # 2026
    "2026-01-01",  # New Year's Day
    "2026-01-19",  # MLK Day
    "2026-02-16",  # Presidents' Day
    "2026-04-03",  # Good Friday
    "2026-05-25",  # Memorial Day
    "2026-06-19",  # Juneteenth
    "2026-07-03",  # Independence Day (observed)
    "2026-09-07",  # Labor Day
    "2026-11-26",  # Thanksgiving
    "2026-12-25",  # Christmas
}


def is_market_closed() -> bool:
    """
    Check if US stock market is currently closed.

    Returns True if:
    - Weekend (Saturday/Sunday)
    - Market holiday
    - Outside regular trading hours (9:30 AM - 4:00 PM ET)
    """
    ny_tz = ZoneInfo("America/New_York")
    now = datetime.now(ny_tz)

    # Check weekend
    if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
        print(f"✅ Weekend: {now.strftime('%A')}")
        return True

    # Check holidays
    date_str = now.strftime("%Y-%m-%d")
    if date_str in MARKET_HOLIDAYS:
        print(f"✅ Market holiday: {date_str}")
        return True

    # Check time (market hours: 9:30 AM - 4:00 PM ET)
    market_open = time(9, 30)
    market_close = time(16, 0)
    current_time = now.time()

    if current_time < market_open:
        print(f"✅ Pre-market: {now.strftime('%H:%M')} ET (market opens at 9:30 AM)")
        return True

    if current_time >= market_close:
        print(f"✅ After-hours: {now.strftime('%H:%M')} ET (market closed at 4:00 PM)")
        return True

    # Market is open
    print(f"⚠️ Market is OPEN: {now.strftime('%H:%M')} ET")
    return False


def main():
    print("🕐 Checking market hours...")
    print(
        f"   Current time: {datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d %H:%M:%S %Z')}"
    )

    if is_market_closed():
        print("\n✅ Market is CLOSED - safe to run backtests")
        # Set GitHub Actions output
        github_output = os.environ.get("GITHUB_OUTPUT")
        if github_output:
            with open(github_output, "a") as f:
                f.write("market_closed=true\n")
        return 0
    else:
        print("\n⚠️ Market is OPEN - skipping backtest to avoid interference")
        github_output = os.environ.get("GITHUB_OUTPUT")
        if github_output:
            with open(github_output, "a") as f:
                f.write("market_closed=false\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
