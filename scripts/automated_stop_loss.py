#!/usr/bin/env python3
"""
Automated Stop-Loss Management

CTO/CFO Decision: Implement automated stop-loss orders on all positions.
Uses direct API calls to avoid Python 3.14 compatibility issues.
"""

import os
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: requests library required")
    sys.exit(1)

DATA_DIR = Path("data")
SYSTEM_STATE_FILE = DATA_DIR / "system_state.json"

ALPACA_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

if not ALPACA_KEY or not ALPACA_SECRET:
    print("ERROR: Alpaca credentials not found")
    sys.exit(1)


def get_positions():
    """Get current positions from Alpaca."""
    headers = {
        "APCA-API-KEY-ID": ALPACA_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET,
    }

    try:
        response = requests.get(f"{ALPACA_BASE_URL}/v2/positions", headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"ERROR fetching positions: {e}")
        return []


def get_existing_orders():
    """Get existing stop orders."""
    headers = {
        "APCA-API-KEY-ID": ALPACA_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET,
    }

    try:
        response = requests.get(
            f"{ALPACA_BASE_URL}/v2/orders", headers=headers, params={"status": "open"}
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"ERROR fetching orders: {e}")
        return []


def place_stop_order(symbol, qty, stop_price):
    """Place a stop-loss order."""
    headers = {
        "APCA-API-KEY-ID": ALPACA_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET,
    }

    data = {
        "symbol": symbol,
        "qty": str(qty),
        "side": "sell",
        "type": "stop",
        "stop_price": str(stop_price),
        "time_in_force": "gtc",
    }

    try:
        response = requests.post(f"{ALPACA_BASE_URL}/v2/orders", headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"ERROR placing stop order: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"Response: {e.response.text}")
        return None


def implement_stop_losses():
    """Implement stop-loss strategy on all positions."""
    print("=" * 80)
    print("🛡️  AUTOMATED STOP-LOSS IMPLEMENTATION")
    print("=" * 80)

    # Get positions
    positions = get_positions()
    if not positions:
        print("No open positions found.")
        return

    # Get existing orders
    existing_orders = get_existing_orders()
    existing_stops = {o["symbol"]: o for o in existing_orders if o["type"] == "stop"}

    print(f"\n📊 Analyzing {len(positions)} positions...\n")

    actions_taken = []

    for pos in positions:
        symbol = pos["symbol"]
        qty = float(pos["qty"])
        entry_price = float(pos["avg_entry_price"])
        current_price = float(pos["current_price"])

        unrealized_pl_pct = (
            ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
        )

        print(f"{symbol}:")
        print(f"  Entry: ${entry_price:.2f}, Current: ${current_price:.2f}")
        print(f"  Quantity: {qty:.4f} shares")
        print(f"  Unrealized P/L: {unrealized_pl_pct:+.2f}%")

        # Check if stop already exists
        if symbol in existing_stops:
            existing_stop = existing_stops[symbol]
            print(f"  ✅ Stop-loss already exists at ${float(existing_stop['stop_price']):.2f}")
            continue

        # Decision logic based on CFO decisions
        stop_price = None
        reason = None

        if unrealized_pl_pct < -5:
            # Critical loss - stop at -5%
            stop_price = entry_price * 0.95
            reason = "Critical loss exceeds 5%"
        elif unrealized_pl_pct < -2:
            # Warning loss - stop at -2%
            stop_price = entry_price * 0.98
            reason = "Loss exceeds 2% threshold"
        elif unrealized_pl_pct > 1:
            # Profitable - trail stop at +1%
            stop_price = entry_price * 1.01
            reason = "Trail stop at +1% profit"
        else:
            # Within acceptable range - set protective stop at -2%
            stop_price = entry_price * 0.98
            reason = "Protective stop at -2%"

        if stop_price:
            print(f"  🎯 Setting stop-loss: ${stop_price:.2f} ({reason})")

            order = place_stop_order(symbol, qty, stop_price)
            if order:
                actions_taken.append(
                    {
                        "symbol": symbol,
                        "action": "stop_loss_placed",
                        "stop_price": stop_price,
                        "order_id": order.get("id"),
                        "reason": reason,
                    }
                )
                print(f"  ✅ Stop-loss order placed: {order.get('id')}")
            else:
                print("  ❌ Failed to place stop-loss order")
                actions_taken.append(
                    {
                        "symbol": symbol,
                        "action": "stop_loss_failed",
                        "reason": reason,
                    }
                )

        print()

    # Summary
    print("=" * 80)
    print("📋 SUMMARY")
    print("=" * 80)
    placed = [a for a in actions_taken if "placed" in a.get("action", "")]
    print(f"Stop-losses placed: {len(placed)}")

    for action in placed:
        print(f"  ✅ {action['symbol']}: ${action['stop_price']:.2f} ({action['reason']})")

    if not placed:
        print("  No new stop-losses needed (all positions already protected)")

    return actions_taken


if __name__ == "__main__":
    try:
        implement_stop_losses()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
