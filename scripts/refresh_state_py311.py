#!/usr/bin/env python3
"""
State Refresh Script - Python 3.11 Compatible

Alternative to daily_checkin.py that works around Python 3.14 compatibility issues.
Uses direct API calls without problematic dependencies.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Use requests directly (more compatible)
try:
    import requests
except ImportError:
    print("ERROR: requests library required. Install with: pip install requests")
    sys.exit(1)

DATA_DIR = Path("data")
SYSTEM_STATE_FILE = DATA_DIR / "system_state.json"
STARTING_BALANCE = 100000.0

ALPACA_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

if not ALPACA_KEY or not ALPACA_SECRET:
    print("ERROR: ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables must be set")
    sys.exit(1)


def get_account_data():
    """Get current account status using direct API calls."""
    headers = {
        "APCA-API-KEY-ID": ALPACA_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET,
    }

    try:
        # Get account
        response = requests.get(f"{ALPACA_BASE_URL}/v2/account", headers=headers)
        response.raise_for_status()
        account = response.json()

        # Get positions
        positions_response = requests.get(f"{ALPACA_BASE_URL}/v2/positions", headers=headers)
        positions_response.raise_for_status()
        positions = positions_response.json()

        equity = float(account["equity"])
        cash = float(account["cash"])
        buying_power = float(account["buying_power"])

        # Calculate positions value
        positions_value = sum(float(p["market_value"]) for p in positions)

        return {
            "equity": equity,
            "cash": cash,
            "buying_power": buying_power,
            "pl": equity - STARTING_BALANCE,
            "pl_pct": ((equity - STARTING_BALANCE) / STARTING_BALANCE) * 100,
            "positions_value": positions_value,
            "positions": positions,
        }
    except Exception as e:
        print(f"ERROR fetching account data: {e}")
        raise


def get_positions_summary(positions):
    """Format positions summary."""
    summary = []
    for pos in positions:
        entry_price = float(pos.get("avg_entry_price", 0))
        current_price = float(pos.get("current_price", 0))
        qty = float(pos.get("qty", 0))
        market_value = float(pos.get("market_value", 0))

        unrealized_pl = (current_price - entry_price) * qty
        unrealized_pl_pct = (
            ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
        )

        summary.append(
            {
                "symbol": pos["symbol"],
                "quantity": qty,
                "entry_price": entry_price,
                "current_price": current_price,
                "market_value": market_value,
                "unrealized_pl": unrealized_pl,
                "unrealized_pl_pct": unrealized_pl_pct,
            }
        )

    return summary


def update_system_state():
    """Update system_state.json with current account data."""
    print("=" * 80)
    print("🔄 REFRESHING SYSTEM STATE")
    print("=" * 80)

    # Load existing state
    if SYSTEM_STATE_FILE.exists():
        with open(SYSTEM_STATE_FILE) as f:
            state = json.load(f)
    else:
        print("ERROR: system_state.json not found. Run daily_checkin.py first.")
        return False

    # Get current account data
    print("\n📊 Fetching current account data...")
    account_data = get_account_data()
    positions = account_data.pop("positions", [])

    # Update account section
    state["account"]["current_equity"] = account_data["equity"]
    state["account"]["cash"] = account_data["cash"]
    state["account"]["positions_value"] = account_data["positions_value"]
    state["account"]["total_pl"] = account_data["pl"]
    state["account"]["total_pl_pct"] = account_data["pl_pct"]

    # Update positions
    positions_summary = get_positions_summary(positions)
    state["performance"]["open_positions"] = [
        {
            "symbol": p["symbol"],
            "tier": "unknown",  # Will be updated by trading scripts
            "amount": p["market_value"],
            "order_id": None,
            "entry_date": datetime.now().isoformat(),
            "entry_price": p["entry_price"],
            "current_price": p["current_price"],
            "quantity": p["quantity"],
            "unrealized_pl": p["unrealized_pl"],
            "unrealized_pl_pct": p["unrealized_pl_pct"],
            "last_updated": datetime.now().isoformat(),
        }
        for p in positions_summary
    ]

    # Update meta
    state["meta"]["last_updated"] = datetime.now().isoformat()

    # Save state
    with open(SYSTEM_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

    print("\n✅ System state refreshed successfully!")
    print(f"   Equity: ${account_data['equity']:,.2f}")
    print(f"   P/L: ${account_data['pl']:+,.2f} ({account_data['pl_pct']:+.4f}%)")
    print(f"   Positions: {len(positions_summary)}")

    return True


if __name__ == "__main__":
    try:
        success = update_system_state()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
