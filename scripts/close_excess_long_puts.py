#!/usr/bin/env python3
"""
Close Excess Long Puts Script

Specifically closes the excess SPY260220P00658000 contracts that are
causing the position imbalance and -$1,248 loss.

EMERGENCY: Jan 22, 2026
- Have 8 long SPY260220P00658000
- Have 2 short SPY260220P00653000
- IMBALANCE: 6 extra long puts bleeding money
"""

import os
import sys
from datetime import datetime


def main():
    """Close excess long puts to restore balance."""
    # Check for required environment variables
    api_key = os.environ.get("ALPACA_API_KEY") or os.environ.get("ALPACA_PAPER_TRADING_5K_API_KEY")
    api_secret = os.environ.get("ALPACA_SECRET_KEY") or os.environ.get(
        "ALPACA_PAPER_TRADING_5K_API_SECRET"
    )

    if not api_key or not api_secret:
        print("ERROR: Missing Alpaca API credentials")
        print("Set ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables")
        sys.exit(1)

    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest
    except ImportError:
        print("ERROR: alpaca-py not installed. Run: pip install alpaca-py")
        sys.exit(1)

    print("=" * 60)
    print(f"CLOSE EXCESS LONG PUTS - {datetime.now()}")
    print("=" * 60)

    client = TradingClient(api_key, api_secret, paper=True)

    # Get account info
    account = client.get_account()
    equity = float(account.equity)
    print(f"\nAccount Equity: ${equity:,.2f}")

    # Get all positions
    positions = client.get_all_positions()

    # Find the SPY260220P00658000 position
    target_symbol = "SPY260220P00658000"
    target_position = None

    print(f"\nLooking for {target_symbol}...")
    for pos in positions:
        print(f"  - {pos.symbol}: qty={pos.qty}, P/L=${float(pos.unrealized_pl):+.2f}")
        if pos.symbol == target_symbol:
            target_position = pos

    if not target_position:
        print(f"\n✅ {target_symbol} not found - may already be closed")
        return

    current_qty = int(float(target_position.qty))
    current_pl = float(target_position.unrealized_pl)

    print(f"\nFound {target_symbol}:")
    print(f"  Current Qty: {current_qty}")
    print(f"  Unrealized P/L: ${current_pl:+.2f}")

    # Determine how many to close
    # We want to match the short side (2 contracts at $653)
    # So close excess: 8 - 2 = 6 contracts
    target_qty = 2  # Match the short side
    excess_qty = max(0, current_qty - target_qty)

    if excess_qty <= 0:
        print(f"\n✅ Position is balanced (qty={current_qty}, target={target_qty})")
        return

    print(f"\n⚠️  EXCESS LONG PUTS: {excess_qty}")
    print(f"  Have: {current_qty}")
    print(f"  Want: {target_qty}")
    print(f"  Closing: {excess_qty}")

    # Check market status first
    clock = client.get_clock()
    print(f"\nMarket Status: {'OPEN' if clock.is_open else 'CLOSED'}")
    if not clock.is_open:
        print(f"  Next open: {clock.next_open}")
        print("  ⚠️ Market closed - order will queue for next open")

    # Execute close - SELL to close LONG positions
    print(f"\nSubmitting SELL order for {excess_qty} contracts...")
    print(f"  Symbol: {target_symbol}")
    print(f"  Side: SELL (to close long)")
    print(f"  Time in Force: DAY")

    try:
        order = client.submit_order(
            MarketOrderRequest(
                symbol=target_symbol,
                qty=excess_qty,
                side=OrderSide.SELL,  # Sell to close long
                time_in_force=TimeInForce.DAY,  # DAY is correct for options
            )
        )
        print(f"  ✅ Order submitted: {order.id}")
        print(f"  Status: {order.status}")
        print(f"  Symbol: {order.symbol}")
        print(f"  Qty: {order.qty}")
        print(f"  Side: {order.side}")
    except Exception as e:
        print(f"  ❌ FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print(f"\n{'=' * 60}")
    print(f"DONE - Closed {excess_qty} excess long puts")
    print("Run sync-system-state.yml to update local state after fills")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
