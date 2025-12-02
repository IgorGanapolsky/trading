#!/usr/bin/env python3
"""
POST-EXECUTION VERIFICATION SCRIPT
Verifies trades actually executed and reports VERIFIED results.

Anti-Lying Mandate Compliance:
- Queries Alpaca API for ground truth
- Distinguishes submitted vs filled orders
- Reports honest P/L (even if negative)
- No assumptions or estimates
"""

import os
import sys
from datetime import date, datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import alpaca_trade_api as tradeapi

# Configuration - Load from .env
from dotenv import load_dotenv

load_dotenv()

ALPACA_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY")

if not ALPACA_KEY or not ALPACA_SECRET:
    raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables must be set")


def verify_execution():
    """Verify today's trade execution with ACTUAL Alpaca API data."""

    print("=" * 70)
    print("🔍 POST-EXECUTION VERIFICATION REPORT")
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %I:%M %p %Z')}")
    print("=" * 70)

    # Initialize Alpaca
    api = tradeapi.REST(ALPACA_KEY, ALPACA_SECRET, "https://paper-api.alpaca.markets")

    # Get account data (GROUND TRUTH)
    account = api.get_account()

    print("\n📊 GROUND TRUTH (Alpaca API)")
    print("-" * 70)
    print(f"Portfolio Value:  ${float(account.equity):,.2f}")
    print(f"Cash:             ${float(account.cash):,.2f}")
    print(f"Positions Value:  ${float(account.portfolio_value):,.2f}")
    print(f"Buying Power:     ${float(account.buying_power):,.2f}")

    # Get all orders for today
    today = date.today().isoformat()
    orders = api.list_orders(status="all", after=today, limit=100)

    print(f"\n📋 TODAY'S ORDERS ({len(orders)} total)")
    print("-" * 70)

    filled_orders = []
    pending_orders = []
    failed_orders = []

    for order in orders:
        status = order.status
        symbol = order.symbol
        qty = float(order.qty) if order.qty else 0
        filled_qty = float(order.filled_qty) if order.filled_qty else 0

        if status == "filled":
            filled_orders.append(order)
            print(
                f"✅ FILLED:  {symbol:6} | Qty: {filled_qty:8.4f} | ${float(order.filled_avg_price) * filled_qty:.2f}"
            )
        elif status in ["new", "accepted", "pending_new"]:
            pending_orders.append(order)
            print(f"⏳ PENDING: {symbol:6} | Qty: {qty:8.4f} | Status: {status}")
        else:
            failed_orders.append(order)
            print(f"❌ FAILED:  {symbol:6} | Qty: {qty:8.4f} | Status: {status}")

    # Get current positions
    positions = api.list_positions()

    print(f"\n💼 CURRENT POSITIONS ({len(positions)} open)")
    print("-" * 70)

    total_pl = 0.0
    for pos in positions:
        pl = float(pos.unrealized_pl)
        pl_pct = float(pos.unrealized_plpc) * 100
        total_pl += pl

        status_emoji = "✅" if pl >= 0 else "❌"
        print(
            f"{status_emoji} {pos.symbol:6} | Qty: {float(pos.qty):8.4f} | "
            f"Value: ${float(pos.market_value):8.2f} | "
            f"P/L: ${pl:+7.2f} ({pl_pct:+.2f}%)"
        )

    print("-" * 70)
    print(f"Total Unrealized P/L: ${total_pl:+,.2f}")

    # Honesty Check
    print("\n✅ HONESTY CHECK")
    print("-" * 70)
    print("✅ Data source: Alpaca API (verified)")
    print(f"✅ Filled orders: {len(filled_orders)} (ACTUAL executions)")
    print(f"⏳ Pending orders: {len(pending_orders)} (NOT executed yet)")
    print(f"❌ Failed orders: {len(failed_orders)}")
    print("✅ No assumptions or estimates used")
    print("✅ All P/L values are unrealized (paper trading)")

    # Status summary
    print("\n📈 EXECUTION STATUS")
    print("-" * 70)

    if len(filled_orders) > 0:
        print(f"✅ SUCCESS: {len(filled_orders)} orders executed")
        print(f"💰 Current P/L: ${total_pl:+,.2f}")
        if total_pl > 0:
            print("🎉 PROFITABLE (verified)")
        elif total_pl < 0:
            print("📉 LOSING (honest assessment)")
        else:
            print("➡️  BREAK-EVEN")
    else:
        print("⚠️  NO EXECUTIONS YET")
        if len(pending_orders) > 0:
            print(f"⏳ {len(pending_orders)} orders still pending")
            print("💡 Check back after market opens (9:30 AM ET)")

    print("=" * 70)

    return {
        "equity": float(account.equity),
        "pl": total_pl,
        "filled_count": len(filled_orders),
        "pending_count": len(pending_orders),
        "failed_count": len(failed_orders),
        "positions_count": len(positions),
    }


if __name__ == "__main__":
    try:
        results = verify_execution()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)
