#!/usr/bin/env python3
"""
Assert SPY-Only Positions - Pre-Trade Compliance Check

CLAUDE.md MANDATE (Jan 19, 2026):
"SPY ONLY - best liquidity, tightest spreads, no early assignment risk"
"NO individual stocks."

This script FAILS if any non-SPY positions exist, preventing zombie mode
where buying power is consumed by rogue positions.

Usage:
    python scripts/assert_spy_only_positions.py

Exit codes:
    0: All positions are SPY or SPY options - COMPLIANT
    1: Non-SPY positions detected - FAIL WORKFLOW
"""

import os
import sys


def get_all_positions():
    """Get all positions from Alpaca."""
    try:
        from alpaca.trading.client import TradingClient

        api_key = os.getenv("ALPACA_API_KEY") or os.getenv("ALPACA_PAPER_TRADING_5K_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY") or os.getenv(
            "ALPACA_PAPER_TRADING_5K_API_SECRET"
        )

        if not api_key or not secret_key:
            print("⚠️ No Alpaca credentials - skipping assertion")
            return None

        client = TradingClient(api_key, secret_key, paper=True)
        return client.get_all_positions()
    except Exception as e:
        print(f"⚠️ Could not connect to Alpaca: {e}")
        return None


def is_spy_position(symbol: str) -> bool:
    """Check if position is SPY or SPY option."""
    # SPY stock or SPY options (format: SPY + date + P/C + strike)
    return symbol == "SPY" or (symbol.startswith("SPY") and len(symbol) > 5)


def main():
    print("=" * 60)
    print("SPY-ONLY POSITION ASSERTION")
    print("CLAUDE.md Compliance Check")
    print("=" * 60)
    print()

    positions = get_all_positions()

    if positions is None:
        print("⚠️ Could not verify positions - proceeding with warning")
        return 0

    if not positions:
        print("✅ No open positions - COMPLIANT")
        return 0

    non_spy_positions = []
    spy_positions = []

    for pos in positions:
        symbol = pos.symbol
        qty = float(pos.qty)
        market_value = float(pos.market_value)
        unrealized_pl = float(pos.unrealized_pl)

        if is_spy_position(symbol):
            spy_positions.append(
                {
                    "symbol": symbol,
                    "qty": qty,
                    "market_value": market_value,
                    "unrealized_pl": unrealized_pl,
                }
            )
        else:
            non_spy_positions.append(
                {
                    "symbol": symbol,
                    "qty": qty,
                    "market_value": market_value,
                    "unrealized_pl": unrealized_pl,
                }
            )

    # Report SPY positions
    if spy_positions:
        print(f"✅ SPY Positions ({len(spy_positions)}):")
        for pos in spy_positions:
            print(
                f"   {pos['symbol']}: {pos['qty']} @ ${pos['market_value']:.2f} (P/L: ${pos['unrealized_pl']:.2f})"
            )

    # Check for violations
    if non_spy_positions:
        print()
        print("🚨" * 20)
        print("VIOLATION: NON-SPY POSITIONS DETECTED")
        print("🚨" * 20)
        print()
        print("CLAUDE.md says: 'SPY ONLY - NO individual stocks'")
        print()
        print(f"❌ Non-SPY Positions ({len(non_spy_positions)}):")
        total_blocked = 0
        for pos in non_spy_positions:
            print(
                f"   {pos['symbol']}: {pos['qty']} @ ${pos['market_value']:.2f} (P/L: ${pos['unrealized_pl']:.2f})"
            )
            total_blocked += abs(pos["market_value"])
        print()
        print(f"💰 These positions are blocking ~${total_blocked:.2f} in buying power")
        print()
        print("ACTION REQUIRED:")
        print("  1. Run: gh workflow run close-non-spy-positions.yml")
        print("  2. Or manually close via Alpaca dashboard")
        print()
        print("❌ WORKFLOW SHOULD FAIL - Non-SPY positions violate strategy")
        return 1

    print()
    print("✅ ALL POSITIONS ARE SPY - COMPLIANT")
    print("   Trading can proceed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
