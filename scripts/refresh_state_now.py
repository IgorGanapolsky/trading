#!/usr/bin/env python3
"""
State Refresh - Using Built-in Libraries Only

Works with any Python version - uses urllib instead of requests.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

# Load environment variables
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

DATA_DIR = Path("data")
SYSTEM_STATE_FILE = DATA_DIR / "system_state.json"
STARTING_BALANCE = 100000.0

ALPACA_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

if not ALPACA_KEY or not ALPACA_SECRET:
    print("ERROR: ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables must be set")
    sys.exit(1)


def make_request(url, method="GET", data=None):
    """Make HTTP request using urllib."""
    req = Request(url)
    req.add_header("APCA-API-KEY-ID", ALPACA_KEY)
    req.add_header("APCA-API-SECRET-KEY", ALPACA_SECRET)
    req.add_header("Content-Type", "application/json")

    if method == "POST" and data:
        req.data = json.dumps(data).encode("utf-8")
        req.get_method = lambda: "POST"

    try:
        with urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise Exception(f"API Error {e.code}: {error_body}")


def get_account_data():
    """Get current account status."""
    account = make_request(f"{ALPACA_BASE_URL}/v2/account")
    positions = make_request(f"{ALPACA_BASE_URL}/v2/positions")

    equity = float(account["equity"])
    cash = float(account["cash"])
    buying_power = float(account["buying_power"])
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


def update_system_state():
    """Update system_state.json with current account data."""
    print("=" * 80)
    print("🔄 REFRESHING SYSTEM STATE")
    print("=" * 80)

    if not SYSTEM_STATE_FILE.exists():
        print("ERROR: system_state.json not found")
        return False

    with open(SYSTEM_STATE_FILE) as f:
        state = json.load(f)

    print("\n📊 Fetching current account data from Alpaca...")
    try:
        account_data = get_account_data()
        positions = account_data.pop("positions", [])

        # Update account
        state["account"]["current_equity"] = account_data["equity"]
        state["account"]["cash"] = account_data["cash"]
        state["account"]["positions_value"] = account_data["positions_value"]
        state["account"]["total_pl"] = account_data["pl"]
        state["account"]["total_pl_pct"] = account_data["pl_pct"]

        # Update positions
        state["performance"]["open_positions"] = []
        for pos in positions:
            entry_price = float(pos.get("avg_entry_price", 0))
            current_price = float(pos.get("current_price", 0))
            qty = float(pos.get("qty", 0))
            market_value = float(pos.get("market_value", 0))

            unrealized_pl = (current_price - entry_price) * qty
            unrealized_pl_pct = (
                ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
            )

            state["performance"]["open_positions"].append(
                {
                    "symbol": pos["symbol"],
                    "tier": "unknown",
                    "amount": market_value,
                    "order_id": None,
                    "entry_date": datetime.now().isoformat(),
                    "entry_price": entry_price,
                    "current_price": current_price,
                    "quantity": qty,
                    "unrealized_pl": unrealized_pl,
                    "unrealized_pl_pct": unrealized_pl_pct,
                    "last_updated": datetime.now().isoformat(),
                }
            )

        # Update meta
        state["meta"]["last_updated"] = datetime.now().isoformat()

        # Save
        with open(SYSTEM_STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)

        print("\n✅ System state refreshed successfully!")
        print(f"   Equity: ${account_data['equity']:,.2f}")
        print(f"   P/L: ${account_data['pl']:+,.2f} ({account_data['pl_pct']:+.4f}%)")
        print(f"   Positions: {len(positions)}")

        for pos in state["performance"]["open_positions"]:
            symbol = pos["symbol"]
            pl = pos["unrealized_pl"]
            pl_pct = pos["unrealized_pl_pct"]
            status = "🟢" if pl > 0 else "🔴"
            print(f"   {status} {symbol}: ${pl:+,.2f} ({pl_pct:+.2f}%)")

        return True

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = update_system_state()
    sys.exit(0 if success else 1)
