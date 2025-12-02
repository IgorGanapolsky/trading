#!/usr/bin/env python3
"""
TRADE STALENESS MONITOR

Detects when trading automation fails silently by checking:
- Time since last trade execution
- Whether trades are happening on expected schedule (weekdays)
- GitHub Actions workflow status

Exit codes:
    0 = OK, 1 = WARNING, 2 = ERROR
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.state_manager import StateManager


def main():
    print(f"\n{'=' * 70}")
    print("🔍 TRADE STALENESS MONITOR")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %I:%M %p ET')}")
    print(f"{'=' * 70}\n")

    try:
        state_mgr = StateManager()
        staleness = state_mgr.check_trade_staleness()

        status_emoji = {"OK": "✅", "WARNING": "⚠️", "ERROR": "❌"}
        emoji = status_emoji.get(staleness["status"], "❓")

        print(f"{emoji} {staleness['status']}: {staleness['message']}\n")

        if staleness.get("last_trade_date"):
            print(f"Last Trade: {staleness['last_trade_date']}")
            hours = staleness.get("hours_since_last_trade", 0)
            print(f"Time Since: {hours:.1f} hours ({hours / 24:.1f} days)\n")

        if staleness.get("recommended_action"):
            print(f"Action: {staleness['recommended_action']}\n")

        return (
            2 if staleness["status"] == "ERROR" else (1 if staleness["status"] == "WARNING" else 0)
        )
    except Exception as e:
        print(f"❌ ERROR: {e}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
