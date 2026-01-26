#!/usr/bin/env python3
"""
Direct Position Close via DELETE endpoint.

Uses DELETE /v2/positions/{symbol} to close ALL option positions.
This clears the slate so the system can open new iron condors.

Updated: Jan 26, 2026 - Now closes ALL option positions (not just one)
"""

import os
import sys
from datetime import datetime


def is_option(symbol: str) -> bool:
    """Check if symbol is an option (OCC format)."""
    return len(symbol) > 10


def main():
    """Close ALL option positions using DELETE endpoint."""
    api_key = os.environ.get("ALPACA_API_KEY") or os.environ.get("ALPACA_PAPER_TRADING_5K_API_KEY")
    api_secret = os.environ.get("ALPACA_SECRET_KEY") or os.environ.get(
        "ALPACA_PAPER_TRADING_5K_API_SECRET"
    )

    if not api_key or not api_secret:
        print("ERROR: Missing Alpaca API credentials")
        sys.exit(1)

    try:
        from alpaca.trading.client import TradingClient
    except ImportError:
        print("ERROR: alpaca-py not installed")
        sys.exit(1)

    print("=" * 60)
    print(f"CLOSE ALL OPTION POSITIONS - {datetime.now()}")
    print("=" * 60)

    client = TradingClient(api_key, api_secret, paper=True)

    # Get account info
    account = client.get_account()
    print(f"\nAccount Equity: ${float(account.equity):,.2f}")
    print(f"Account Cash: ${float(account.cash):,.2f}")

    # Get current positions
    positions = client.get_all_positions()
    print(f"\nTotal Positions: {len(positions)}")

    # Filter to options only
    option_positions = [pos for pos in positions if is_option(pos.symbol)]
    stock_positions = [pos for pos in positions if not is_option(pos.symbol)]

    print(f"Option Positions: {len(option_positions)}")
    print(f"Stock Positions: {len(stock_positions)}")

    if not option_positions:
        print("\n✅ No option positions to close!")
        return

    print("\nOption Positions to Close:")
    total_pl = 0
    for pos in option_positions:
        pl = float(pos.unrealized_pl)
        total_pl += pl
        qty = float(pos.qty)
        side = "LONG" if qty > 0 else "SHORT"
        print(f"  {pos.symbol}: {side} {abs(qty):.0f} @ ${float(pos.current_price):.2f} | P/L: ${pl:+.2f}")

    print(f"\nTotal Option P/L: ${total_pl:+.2f}")

    # Close each option position
    print("\n" + "=" * 60)
    print("CLOSING ALL OPTION POSITIONS")
    print("=" * 60)

    closed = 0
    failed = 0

    for pos in option_positions:
        symbol = pos.symbol
        qty = float(pos.qty)
        side = "LONG" if qty > 0 else "SHORT"

        print(f"\nClosing {symbol} ({side} {abs(qty):.0f})...")

        try:
            # close_position() automatically handles order side
            result = client.close_position(symbol)

            if hasattr(result, 'id'):
                print(f"  ✅ SUCCESS - Order ID: {result.id}")
            else:
                print(f"  ✅ SUCCESS - Result: {result}")
            closed += 1

        except Exception as e:
            print(f"  ❌ FAILED: {type(e).__name__}: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULT: {closed} closed, {failed} failed")
    print("=" * 60)

    # Final account status
    account = client.get_account()
    print(f"\nFinal Equity: ${float(account.equity):,.2f}")
    print(f"Final Cash: ${float(account.cash):,.2f}")

    if failed > 0:
        print("\n⚠️  Some positions failed to close")
        print("Manual close may be required via Alpaca Dashboard:")
        print("https://app.alpaca.markets/paper/dashboard/positions")
        sys.exit(1)
    else:
        print("\n✅ All option positions closed successfully!")
        print("Run sync-system-state.yml to update local state after fills")


if __name__ == "__main__":
    main()
