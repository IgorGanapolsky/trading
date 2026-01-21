#!/usr/bin/env python3
"""
Close Orphan SPY Puts

LL-275: Close the orphan SPY260220P00658000 positions that violate
iron condor structure. These deep ITM puts create unbalanced risk.
"""

import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.alpaca_client import get_alpaca_client


def close_orphan_spy_puts():
    """Close orphan SPY long puts that aren't part of a proper spread."""
    paper = os.getenv("PAPER_TRADING", "true").lower() == "true"
    client = get_alpaca_client(paper=paper)

    if not client:
        print("❌ Failed to get Alpaca client")
        return False

    # Get current positions
    positions = client.get_all_positions()

    # Find SPY put positions
    spy_puts = []
    for pos in positions:
        if pos.symbol.startswith("SPY") and "P" in pos.symbol[9:]:
            spy_puts.append(pos)

    print(f"📊 Found {len(spy_puts)} SPY put positions")

    # Identify orphan puts (long puts that aren't paired with short puts)
    # Current issue: SPY260220P00658000 is orphan deep ITM put
    orphan_symbol = "SPY260220P00658000"
    orphan_position = None

    for pos in spy_puts:
        print(
            f"  - {pos.symbol}: qty={pos.qty}, price=${float(pos.current_price):.2f}, P/L=${float(pos.unrealized_pl):.2f}"
        )
        if pos.symbol == orphan_symbol and float(pos.qty) > 0:
            orphan_position = pos

    if not orphan_position:
        print(f"\n✅ No orphan position {orphan_symbol} found - may already be closed")
        return True

    qty = abs(float(orphan_position.qty))
    current_price = float(orphan_position.current_price)
    unrealized_pl = float(orphan_position.unrealized_pl)

    print("\n📊 Found ORPHAN position to close:")
    print(f"   Symbol: {orphan_symbol}")
    print(f"   Qty: {qty} LONG")
    print(f"   Current Price: ${current_price:.2f}")
    print(f"   Unrealized P/L: ${unrealized_pl:.2f}")
    print()

    # SELL to close long puts
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import MarketOrderRequest

    order_request = MarketOrderRequest(
        symbol=orphan_symbol,
        qty=int(qty),  # Options must be whole numbers
        side=OrderSide.SELL,
        time_in_force=TimeInForce.GTC,
    )

    print(f"🔄 Submitting SELL to close order for {int(qty)} {orphan_symbol}...")

    try:
        order = client.submit_order(order_request)
        print("✅ Order submitted successfully!")
        print(f"   Order ID: {order.id}")
        print(f"   Status: {order.status}")
        print(f"   Expected P/L: ~${unrealized_pl:.2f}")
        return True
    except Exception as e:
        print(f"❌ Order failed: {e}")
        return False


if __name__ == "__main__":
    success = close_orphan_spy_puts()
    sys.exit(0 if success else 1)
