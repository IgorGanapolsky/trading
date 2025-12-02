#!/usr/bin/env python3
"""
Stop-Loss Implementation - Using Built-in Libraries Only
"""

import json
import os
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

# Load environment variables
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

ALPACA_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

if not ALPACA_KEY or not ALPACA_SECRET:
    print("ERROR: Alpaca credentials not found")
    sys.exit(1)


def make_request(url, method="GET", data=None):
    """Make HTTP request."""
    req = Request(url)
    req.add_header("APCA-API-KEY-ID", ALPACA_KEY)
    req.add_header("APCA-API-SECRET-KEY", ALPACA_SECRET)
    req.add_header("Content-Type", "application/json")

    if method == "POST" and data:
        req.data = json.dumps(data).encode("utf-8")
        req.get_method = lambda: "POST"

    with urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


def get_positions():
    """Get current positions."""
    return make_request(f"{ALPACA_BASE_URL}/v2/positions")


def get_existing_orders():
    """Get existing stop orders."""
    try:
        return make_request(f"{ALPACA_BASE_URL}/v2/orders?status=open")
    except:
        return []


def place_stop_order(symbol, qty, stop_price):
    """Place stop-loss order."""
    # Use exact qty from position (Alpaca handles precision)
    # But ensure we don't exceed available quantity
    qty_rounded = round(qty, 8)  # More precision for fractional shares
    if qty_rounded <= 0:
        return None

    # Fractional orders must use DAY, not GTC
    time_in_force = "day" if abs(qty_rounded - int(qty_rounded)) > 0.0001 else "gtc"

    data = {
        "symbol": symbol,
        "qty": qty_rounded,
        "side": "sell",
        "type": "stop",
        "stop_price": round(stop_price, 2),
        "time_in_force": time_in_force,
    }

    try:
        req = Request(f"{ALPACA_BASE_URL}/v2/orders")
        req.add_header("APCA-API-KEY-ID", ALPACA_KEY)
        req.add_header("APCA-API-SECRET-KEY", ALPACA_SECRET)
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(data).encode("utf-8")
        req.get_method = lambda: "POST"

        with urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result
    except HTTPError as e:
        error_body = e.read().decode("utf-8") if hasattr(e, "read") else str(e)
        print(f"  ❌ API Error {e.code}: {error_body[:200]}")
        return None
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return None


def implement_stop_losses():
    """Implement stop-loss strategy."""
    print("=" * 80)
    print("🛡️  IMPLEMENTING STOP-LOSSES")
    print("=" * 80)

    positions = get_positions()
    if not positions:
        print("No open positions found.")
        return

    existing_orders = get_existing_orders()
    existing_stops = {o["symbol"]: o for o in existing_orders if o.get("type") == "stop"}

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
        print(f"  P/L: {unrealized_pl_pct:+.2f}%")

        if symbol in existing_stops:
            print("  ✅ Stop-loss already exists")
            continue

        # CFO Decision: Stop-loss strategy
        stop_price = None
        reason = None

        if unrealized_pl_pct < -5:
            stop_price = entry_price * 0.95
            reason = "Critical: Loss > 5%"
        elif unrealized_pl_pct < -2:
            stop_price = entry_price * 0.98
            reason = "Warning: Loss > 2%"
        elif unrealized_pl_pct > 1:
            stop_price = entry_price * 1.01
            reason = "Trail stop: Profit > 1%"
        else:
            stop_price = entry_price * 0.98
            reason = "Protective: -2%"

        print(f"  🎯 Setting stop at ${stop_price:.2f} ({reason})")
        order = place_stop_order(symbol, qty, stop_price)

        if order:
            actions_taken.append(
                {
                    "symbol": symbol,
                    "stop_price": stop_price,
                    "order_id": order.get("id"),
                }
            )
            print(f"  ✅ Stop-loss placed: {order.get('id')}")
        print()

    print("=" * 80)
    print("📋 SUMMARY")
    print("=" * 80)
    print(f"Stop-losses placed: {len(actions_taken)}")
    for action in actions_taken:
        print(f"  ✅ {action['symbol']}: ${action['stop_price']:.2f}")

    return actions_taken


if __name__ == "__main__":
    try:
        implement_stop_losses()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
