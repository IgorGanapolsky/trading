#!/usr/bin/env python3
"""
Close Orphan/Violating Put Positions

Closes positions that violate CLAUDE.md rules:
- SOFI positions (SPY ONLY policy)
- Orphan puts without matching spreads

Updated: Jan 20, 2026 - Target SOFI260213P00032000 short put
"""

import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.alpaca_client import get_alpaca_client


def close_orphan_put():
    """Close orphan or violating put positions."""
    paper = os.getenv("PAPER_TRADING", "true").lower() == "true"
    client = get_alpaca_client(paper=paper)

    if not client:
        print("❌ Failed to get Alpaca client")
        return False

    # Get current positions
    positions = client.get_all_positions()
    print(f"📋 Found {len(positions)} positions")

    # Priority: SOFI positions first (violate SPY ONLY rule)
    # Then SPY orphans
    target_symbols = [
        "SOFI260213P00032000",  # Current SOFI short put - VIOLATES SPY ONLY
        "SPY260220P00653000",   # Legacy orphan
    ]

    target_position = None
    for symbol in target_symbols:
        for pos in positions:
            if pos.symbol == symbol:
                target_position = pos
                print(f"🎯 Found target: {symbol}")
                break
        if target_position:
            break

    if not target_position:
        print("❌ No target positions found to close")
        print("Available positions:")
        for pos in positions:
            qty = float(pos.qty)
            price = float(pos.current_price)
            pl = float(pos.unrealized_pl)
            print(f"  - {pos.symbol}: {qty} @ ${price:.2f} (P/L: ${pl:.2f})")
        return False

    symbol = target_position.symbol
    qty = float(target_position.qty)
    current_price = float(target_position.current_price)
    unrealized_pl = float(target_position.unrealized_pl)

    print("📊 Target position:")
    print(f"   Symbol: {symbol}")
    print(f"   Qty: {qty}")
    print(f"   Current Price: ${current_price:.2f}")
    print(f"   Unrealized P/L: ${unrealized_pl:.2f}")
    print()

    # Determine order side based on position
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import MarketOrderRequest

    if qty < 0:
        # SHORT position -> BUY to close
        order_side = OrderSide.BUY
        order_qty = abs(qty)
        print(f"🔄 SHORT position detected -> BUY {int(order_qty)} to close")
    else:
        # LONG position -> SELL to close
        order_side = OrderSide.SELL
        order_qty = qty
        print(f"🔄 LONG position detected -> SELL {int(order_qty)} to close")

    order_request = MarketOrderRequest(
        symbol=symbol,
        qty=order_qty,
        side=order_side,
        time_in_force=TimeInForce.DAY,
    )

    print(f"\n📝 Submitting {order_side.value} order for {int(order_qty)} {symbol}...")

    try:
        order = client.submit_order(order_request)
        print("✅ Order submitted successfully!")
        print(f"   Order ID: {order.id}")
        print(f"   Status: {order.status}")
        print(f"   Expected P/L: ~${unrealized_pl:.2f}")
        return True
    except Exception as e:
        print(f"❌ Order failed: {e}")
        # Try close_position as backup
        print("\n🔄 Trying close_position() as backup...")
        try:
            order = client.close_position(symbol)
            print(f"✅ Backup close succeeded! Order ID: {order.id}")
            return True
        except Exception as e2:
            print(f"❌ Backup also failed: {e2}")
            return False


if __name__ == "__main__":
    success = close_orphan_put()
    sys.exit(0 if success else 1)
