#!/usr/bin/env python3
"""
Close Orphan Put Position

The SPY260220P00653000 long put is an orphan position that needs to be closed
to free up capital and comply with the 1-spread position limit in CLAUDE.md.
"""

import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.alpaca_client import get_alpaca_client


def close_orphan_put():
    """Close the orphan SPY 660 put position."""
    paper = os.getenv("PAPER_TRADING", "true").lower() == "true"
    client = get_alpaca_client(paper=paper)

    if not client:
        print("❌ Failed to get Alpaca client")
        return False

    # Get current positions
    positions = client.get_all_positions()

    orphan_symbol = "SPY260220P00653000"
    orphan_position = None

    for pos in positions:
        if pos.symbol == orphan_symbol:
            orphan_position = pos
            break

    if not orphan_position:
        print(f"❌ Orphan position {orphan_symbol} not found")
        print("Available positions:")
        for pos in positions:
            print(f"  - {pos.symbol}: {pos.qty} @ ${float(pos.current_price):.2f}")
        return False

    qty = abs(float(orphan_position.qty))
    current_price = float(orphan_position.current_price)
    unrealized_pl = float(orphan_position.unrealized_pl)

    print("📊 Found orphan position:")
    print(f"   Symbol: {orphan_symbol}")
    print(f"   Qty: {qty}")
    print(f"   Current Price: ${current_price:.2f}")
    print(f"   Unrealized P/L: ${unrealized_pl:.2f}")
    print()

    # Close the position by selling
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import MarketOrderRequest

    order_request = MarketOrderRequest(
        symbol=orphan_symbol,
        qty=qty,
        side=OrderSide.SELL,
        time_in_force=TimeInForce.GTC,  # Good til canceled - will execute at next market open
    )

    print(f"🔄 Submitting SELL order for {qty} {orphan_symbol}...")

    try:
        order = client.submit_order(order_request)
        print("✅ Order submitted successfully!")
        print(f"   Order ID: {order.id}")
        print(f"   Status: {order.status}")
        print(f"   Expected profit: ~${unrealized_pl:.2f}")
        return True
    except Exception as e:
        print(f"❌ Order failed: {e}")
        return False


if __name__ == "__main__":
    success = close_orphan_put()
    sys.exit(0 if success else 1)
