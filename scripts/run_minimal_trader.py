#!/usr/bin/env python3
"""
Run Minimal Trader

Simple script to run the minimal viable trading system.
No complexity, no gates, just trade.

Usage:
    python scripts/run_minimal_trader.py           # Paper trading
    python scripts/run_minimal_trader.py --live    # Live trading (careful!)
"""

import logging
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestrator.minimal_trader import MinimalTrader


def main():
    """Run minimal trader."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    # Parse args
    live = "--live" in sys.argv
    paper = not live

    if live:
        print("\n" + "=" * 60)
        print("WARNING: LIVE TRADING MODE")
        print("Real money will be used!")
        print("=" * 60)
        confirm = input("Type 'YES' to confirm: ")
        if confirm != "YES":
            print("Aborted.")
            sys.exit(0)

    # Get daily budget from env or default
    daily_budget = float(os.environ.get("DAILY_INVESTMENT", "10.0"))

    print("\n" + "=" * 60)
    print("MINIMAL VIABLE TRADING SYSTEM")
    print("=" * 60)
    print(f"Mode: {'LIVE' if live else 'PAPER'}")
    print(f"Daily Budget: ${daily_budget:.2f}")
    print("=" * 60)

    # Run
    trader = MinimalTrader(paper=paper, daily_budget=daily_budget)
    results = trader.run_daily()

    # Print results
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    if results["circuit_breaker"]:
        print("CIRCUIT BREAKER TRIPPED - No trading today")
    else:
        print(f"Exits executed: {len(results['exits'])}")
        for exit in results["exits"]:
            print(f"  - {exit['symbol']}: {exit['reason']} (success={exit['success']})")

        print(f"\nEntries executed: {len(results['entries'])}")
        for entry in results["entries"]:
            print(
                f"  - {entry['symbol']}: conf={entry['confidence']:.2f}, "
                f"${entry['amount']:.2f} (success={entry['success']})"
            )

        if results["errors"]:
            print(f"\nErrors: {len(results['errors'])}")
            for error in results["errors"]:
                print(f"  - {error}")

    print("=" * 60)
    print("Done.")


if __name__ == "__main__":
    main()
