#!/usr/bin/env python3
"""
Direct Position Close via DELETE endpoint.

Uses DELETE /v2/positions/{symbol} instead of submitting a sell order.
This may bypass the cash-secured put calculation bug.

EMERGENCY: Jan 22, 2026
"""

import os
import sys
from datetime import datetime


def main():
    """Close position using DELETE endpoint."""
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
    print(f"DIRECT POSITION CLOSE - {datetime.now()}")
    print("=" * 60)

    client = TradingClient(api_key, api_secret, paper=True)

    # Target symbol
    target_symbol = "SPY260220P00658000"

    # Get current positions
    positions = client.get_all_positions()
    print(f"\nCurrent Positions: {len(positions)}")

    target_pos = None
    for pos in positions:
        print(f"  {pos.symbol}: qty={pos.qty}, P/L=${float(pos.unrealized_pl):+.2f}")
        if pos.symbol == target_symbol:
            target_pos = pos

    if not target_pos:
        print(f"\n{target_symbol} not found - may already be closed")
        return

    print(f"\nTarget Position Found:")
    print(f"  Symbol: {target_pos.symbol}")
    print(f"  Qty: {target_pos.qty}")
    print(f"  Unrealized P/L: ${float(target_pos.unrealized_pl):+.2f}")

    # Try close_position endpoint (DELETE /v2/positions/{symbol})
    print(f"\nAttempting close_position({target_symbol})...")
    print("This uses DELETE endpoint instead of order submission")

    try:
        # This is the key difference - using close_position() directly
        # instead of submitting a sell order
        result = client.close_position(target_symbol)
        print(f"\n  SUCCESS!")
        print(f"  Order ID: {result.id if hasattr(result, 'id') else result}")
        print(f"  Status: {result.status if hasattr(result, 'status') else 'submitted'}")
    except Exception as e:
        print(f"\n  FAILED: {type(e).__name__}: {e}")

        # Try with qty parameter to close partial
        print("\nTrying partial close (6 contracts)...")
        try:
            from alpaca.trading.requests import ClosePositionRequest
            close_request = ClosePositionRequest(qty="6")
            result = client.close_position(target_symbol, close_position_request=close_request)
            print(f"  SUCCESS!")
            print(f"  Order ID: {result.id if hasattr(result, 'id') else result}")
        except Exception as e2:
            print(f"  FAILED: {type(e2).__name__}: {e2}")

            # Last resort - try closing just 1
            print("\nTrying to close just 1 contract...")
            try:
                close_request = ClosePositionRequest(qty="1")
                result = client.close_position(target_symbol, close_position_request=close_request)
                print(f"  SUCCESS!")
                print(f"  Order ID: {result.id if hasattr(result, 'id') else result}")
            except Exception as e3:
                print(f"  FAILED: {type(e3).__name__}: {e3}")
                print("\n" + "=" * 60)
                print("ALL API METHODS FAILED")
                print("MANUAL CLOSE REQUIRED via Alpaca Dashboard:")
                print("https://app.alpaca.markets/paper/dashboard/positions")
                print("=" * 60)
                sys.exit(1)

    print(f"\n{'=' * 60}")
    print("POSITION CLOSE INITIATED")
    print("Run sync-system-state.yml to update local state after fills")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
