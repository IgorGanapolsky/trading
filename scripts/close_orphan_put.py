#!/usr/bin/env python3
"""
Close Orphan Position

Uses Alpaca's close_position() API to properly liquidate orphan positions.
Configurable via TARGET_SYMBOL environment variable.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.alpaca_client import get_alpaca_client


def close_orphan_put():
    """Close the orphan position using close_position() API."""
    # Target symbol - configurable via env var
    orphan_symbol = os.getenv("TARGET_SYMBOL", "SPY260220P00658000")
    paper = os.getenv("PAPER_TRADING", "true").lower() == "true"
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"

    print("=" * 60)
    print(f"CLOSE ORPHAN POSITION - {datetime.now()}")
    print("=" * 60)
    print(f"Target Symbol: {orphan_symbol}")
    print(f"Paper Trading: {paper}")
    print(f"Dry Run: {dry_run}")
    print()

    client = get_alpaca_client(paper=paper)

    if not client:
        print("❌ Failed to get Alpaca client")
        return False

    # Get current positions
    positions = client.get_all_positions()
    orphan_position = None

    print(f"Current Positions ({len(positions)}):")
    for pos in positions:
        qty = float(pos.qty)
        pl = float(pos.unrealized_pl)
        marker = " <-- TARGET" if pos.symbol == orphan_symbol else ""
        print(f"  {pos.symbol}: {qty:+.0f} | P/L: ${pl:+.2f}{marker}")
        if pos.symbol == orphan_symbol:
            orphan_position = pos

    if not orphan_position:
        print(f"\n✅ Position {orphan_symbol} not found - may already be closed")
        return True  # Success - position doesn't exist

    qty = float(orphan_position.qty)
    current_price = float(orphan_position.current_price)
    unrealized_pl = float(orphan_position.unrealized_pl)
    is_long = qty > 0

    print("\n🎯 Target Position:")
    print(f"   Symbol: {orphan_symbol}")
    print(f"   Qty: {qty:+.0f}")
    print(f"   Type: {'LONG' if is_long else 'SHORT'}")
    print(f"   Current Price: ${current_price:.2f}")
    print(f"   Unrealized P/L: ${unrealized_pl:.2f}")

    # Check market status
    clock = client.get_clock()
    print(f"\n⏰ Market: {'OPEN' if clock.is_open else 'CLOSED'}")

    if dry_run:
        print(f"\n🔍 DRY RUN - Would call: client.close_position('{orphan_symbol}')")
        return True

    # Use close_position() API - the recommended way to close positions
    print(f"\n📝 Calling close_position('{orphan_symbol}')...")
    try:
        result = client.close_position(orphan_symbol)

        # Handle response
        if isinstance(result, list):
            orders = result
        else:
            orders = [result] if result else []

        if orders:
            print("\n✅ POSITION CLOSE INITIATED!")
            for order in orders:
                print(f"   Order ID: {order.id}")
                print(f"   Status: {order.status}")
                print(f"   Symbol: {order.symbol}")
                print(f"   Qty: {order.qty}")
                print(f"   Side: {order.side}")
            return True
        else:
            print("\n⚠️ close_position returned no orders")
            return False

    except Exception as e:
        print(f"\n❌ CLOSE FAILED!")
        print(f"   Error Type: {type(e).__name__}")
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = close_orphan_put()
    print("\n" + "=" * 60)
    print("✅ Complete" if success else "❌ Failed")
    print("=" * 60)
    sys.exit(0 if success else 1)
