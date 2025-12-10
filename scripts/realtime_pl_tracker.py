#!/usr/bin/env python3
"""
Real-time P/L Tracker - Updates every few minutes during market hours
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path

import alpaca_trade_api as tradeapi

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# Load from .env or environment
from dotenv import load_dotenv

load_dotenv()

api = tradeapi.REST(
    os.getenv("APCA_API_KEY_ID") or os.getenv("ALPACA_API_KEY"),
    os.getenv("APCA_SECRET_KEY") or os.getenv("ALPACA_SECRET_KEY"),
    os.getenv("APCA_API_BASE_URL")
    or os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets"),
    api_version="v2",
)


def get_current_positions():
    """Get current positions with P/L."""
    try:
        positions = api.list_positions()
        return [
            {
                "symbol": pos.symbol,
                "qty": float(pos.qty),
                "entry_price": float(pos.avg_entry_price),
                "current_price": float(pos.current_price),
                "unrealized_pl": float(pos.unrealized_pl),
                "unrealized_plpc": float(pos.unrealized_plpc) * 100,
            }
            for pos in positions
        ]
    except Exception as e:
        print(f"Error fetching positions: {e}")
        return []


def get_account_value():
    """Get current account value."""
    try:
        account = api.get_account()
        return {
            "equity": float(account.equity),
            "cash": float(account.cash),
            "portfolio_value": float(account.portfolio_value),
        }
    except Exception as e:
        print(f"Error fetching account: {e}")
        return None


def update_pl_log():
    """Update P/L log with current values."""
    positions = get_current_positions()
    account = get_account_value()

    if not account:
        return

    timestamp = datetime.now().isoformat()

    total_unrealized_pl = sum(p["unrealized_pl"] for p in positions)

    entry = {
        "timestamp": timestamp,
        "equity": account["equity"],
        "cash": account["cash"],
        "portfolio_value": account["portfolio_value"],
        "total_unrealized_pl": total_unrealized_pl,
        "positions": positions,
    }

    # Load existing log
    log_file = DATA_DIR / "realtime_pl_log.json"
    if log_file.exists():
        with open(log_file) as f:
            log = json.load(f)
    else:
        log = {"entries": []}

    log["entries"].append(entry)

    # Keep only last 1000 entries
    log["entries"] = log["entries"][-1000:]

    # Save
    with open(log_file, "w") as f:
        json.dump(log, f, indent=2)

    return entry


def is_market_hours():
    """Check if market is currently open."""
    try:
        clock = api.get_clock()
        return clock.is_open
    except Exception:
        return False


def main():
    """Run real-time P/L tracker."""
    print("=" * 60)
    print("📊 REAL-TIME P/L TRACKER")
    print("=" * 60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    update_interval = 300  # 5 minutes

    while True:
        try:
            if is_market_hours():
                entry = update_pl_log()
                if entry:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Updated P/L log")
                    print(f"  Equity: ${entry['equity']:,.2f}")
                    print(f"  Unrealized P/L: ${entry['total_unrealized_pl']:+,.2f}")
                    print(f"  Positions: {len(entry['positions'])}")
                    print()
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Market closed - waiting...")

            time.sleep(update_interval)

        except KeyboardInterrupt:
            print("\n\nStopped by user")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(update_interval)


if __name__ == "__main__":
    main()
