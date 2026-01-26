#!/usr/bin/env python3
"""
Close All Option Positions

Closes all open option positions using Alpaca's close_position() API.
Created Jan 26, 2026 to clean up orphan positions from partial fills.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.alpaca_client import get_alpaca_client


def close_all_options():
    """Close all option positions."""
    paper = os.getenv("PAPER_TRADING", "true").lower() == "true"
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"

    print("=" * 60)
    print(f"CLOSE ALL OPTION POSITIONS - {datetime.now()}")
    print("=" * 60)
    print(f"Paper Trading: {paper}")
    print(f"Dry Run: {dry_run}")
    print()

    client = get_alpaca_client(paper=paper)

    if not client:
        print("Failed to get Alpaca client")
        return False

    # Get current positions
    positions = client.get_all_positions()

    # Filter for option positions (symbols > 10 chars)
    option_positions = [p for p in positions if len(p.symbol) > 10]

    print(f"Total positions: {len(positions)}")
    print(f"Option positions: {len(option_positions)}")
    print()

    if not option_positions:
        print("No option positions to close")
        return True

    print("Option positions to close:")
    for pos in option_positions:
        qty = float(pos.qty)
        pl = float(pos.unrealized_pl)
        print(f"  {pos.symbol}: {qty:+.0f} | P/L: ${pl:+.2f}")

    if dry_run:
        print(f"\nDRY RUN - Would close {len(option_positions)} positions")
        return True

    # Close each option position
    success_count = 0
    for pos in option_positions:
        print(f"\nClosing {pos.symbol}...")
        try:
            result = client.close_position(pos.symbol)
            print(f"   Close initiated: Order {result.id if hasattr(result, 'id') else result}")
            success_count += 1
        except Exception as e:
            print(f"   Failed: {e}")

    print(f"\n{'=' * 60}")
    print(f"Closed {success_count}/{len(option_positions)} positions")
    print("=" * 60)

    return success_count == len(option_positions)


if __name__ == "__main__":
    success = close_all_options()
    sys.exit(0 if success else 1)
