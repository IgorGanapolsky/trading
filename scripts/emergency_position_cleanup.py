#!/usr/bin/env python3
"""
Emergency Position Cleanup Script

Closes excess positions to bring portfolio back within risk limits:
- Max 1 iron condor (2 spreads max if both legs)
- Max 15% total portfolio risk

This script is meant to run via GitHub Actions with Alpaca credentials.
"""

import os
import sys
from datetime import datetime


def main():
    """Close excess positions to restore compliance."""
    # Check for required environment variables
    api_key = os.environ.get("ALPACA_API_KEY") or os.environ.get(
        "ALPACA_PAPER_TRADING_5K_API_KEY"
    )
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
    print(f"EMERGENCY POSITION CLEANUP - {datetime.now()}")
    print("=" * 60)

    client = TradingClient(api_key, api_secret, paper=True)

    # Get account info
    account = client.get_account()
    equity = float(account.equity)
    print(f"\nAccount Equity: ${equity:,.2f}")

    # Get all positions
    positions = client.get_all_positions()
    print(f"Total Positions: {len(positions)}")

    # Analyze positions - find spreads
    puts = {}  # strike -> position
    for pos in positions:
        symbol = pos.symbol
        if "P" in symbol and symbol.startswith("SPY"):
            # Parse strike
            strike = int(symbol[-8:]) / 1000
            puts[strike] = {
                "symbol": symbol,
                "qty": float(pos.qty),
                "side": "LONG" if float(pos.qty) > 0 else "SHORT",
                "unrealized_pl": float(pos.unrealized_pl),
            }

    print(f"\nSPY Put Positions: {len(puts)}")
    for strike, pos in sorted(puts.items()):
        print(f"  ${strike:.0f}: {pos['side']} {abs(pos['qty']):.0f} | P/L: ${pos['unrealized_pl']:+.2f}")

    # Find spreads (short + long pair with adjacent strikes)
    spreads = []
    sorted_strikes = sorted(puts.keys())

    for i, strike in enumerate(sorted_strikes):
        pos = puts[strike]
        if pos["side"] == "SHORT":
            # Look for long leg at lower strike (bull put spread)
            for j in range(i - 1, -1, -1):
                lower_strike = sorted_strikes[j]
                lower_pos = puts[lower_strike]
                if lower_pos["side"] == "LONG":
                    spreads.append(
                        {
                            "short_strike": strike,
                            "short_symbol": pos["symbol"],
                            "long_strike": lower_strike,
                            "long_symbol": lower_pos["symbol"],
                            "width": strike - lower_strike,
                            "combined_pl": pos["unrealized_pl"] + lower_pos["unrealized_pl"],
                        }
                    )
                    break

    print(f"\nIdentified Spreads: {len(spreads)}")
    for i, spread in enumerate(spreads):
        print(
            f"  {i + 1}. ${spread['short_strike']:.0f}/${spread['long_strike']:.0f} "
            f"(${spread['width']:.0f} wide) | P/L: ${spread['combined_pl']:+.2f}"
        )

    # Determine how many to close
    max_spreads = 1  # CLAUDE.md: 1 iron condor at a time
    excess_spreads = len(spreads) - max_spreads

    if excess_spreads <= 0:
        print(f"\n✅ Position count OK ({len(spreads)} spreads, max {max_spreads})")
        return

    print(f"\n⚠️  EXCESS SPREADS: {excess_spreads} (have {len(spreads)}, max {max_spreads})")

    # Close the spreads with worst P/L first
    spreads_to_close = sorted(spreads, key=lambda x: x["combined_pl"])[:excess_spreads]

    print(f"\nClosing {len(spreads_to_close)} spreads:")
    for spread in spreads_to_close:
        print(
            f"  - ${spread['short_strike']:.0f}/${spread['long_strike']:.0f} "
            f"(P/L: ${spread['combined_pl']:+.2f})"
        )

    # Execute closes
    orders_submitted = []
    for spread in spreads_to_close:
        # Close short leg (buy to close)
        print(f"\nClosing short leg: {spread['short_symbol']}")
        try:
            order = client.submit_order(
                MarketOrderRequest(
                    symbol=spread["short_symbol"],
                    qty=1,
                    side=OrderSide.BUY,  # Buy to close short
                    time_in_force=TimeInForce.DAY,
                )
            )
            print(f"  ✅ Order submitted: {order.id}")
            orders_submitted.append(order.id)
        except Exception as e:
            print(f"  ❌ Failed: {e}")

        # Close long leg (sell to close)
        print(f"Closing long leg: {spread['long_symbol']}")
        try:
            order = client.submit_order(
                MarketOrderRequest(
                    symbol=spread["long_symbol"],
                    qty=1,
                    side=OrderSide.SELL,  # Sell to close long
                    time_in_force=TimeInForce.DAY,
                )
            )
            print(f"  ✅ Order submitted: {order.id}")
            orders_submitted.append(order.id)
        except Exception as e:
            print(f"  ❌ Failed: {e}")

    print(f"\n{'=' * 60}")
    print(f"SUMMARY: Submitted {len(orders_submitted)} close orders")
    print(f"{'=' * 60}")

    if orders_submitted:
        print("\n✅ Run sync-system-state.yml to update local state after fills")


if __name__ == "__main__":
    main()
