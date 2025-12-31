#!/usr/bin/env python3
"""
Fix Win Rate From Closed Trades

This script recalculates the win_rate from actual closed_trades data,
fixing the mismatch between the counter-based calculation and reality.

Created: Dec 31, 2025 (Fix for lying dashboard metrics)
"""

import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

STATE_FILE = Path("data/system_state.json")


def calculate_accurate_win_rate() -> dict:
    """
    Calculate accurate win rate from closed_trades list.

    Returns:
        Dict with corrected metrics and discrepancy info
    """
    if not STATE_FILE.exists():
        logger.error(f"State file not found: {STATE_FILE}")
        return {"error": "State file not found"}

    with open(STATE_FILE) as f:
        state = json.load(f)

    performance = state.get("performance", {})
    closed_trades = performance.get("closed_trades", [])

    # Count actual winners from closed_trades
    actual_winners = 0
    actual_losers = 0

    for trade in closed_trades:
        pl = trade.get("pl", 0)
        if pl > 0:
            actual_winners += 1
        elif pl < 0:
            actual_losers += 1
        # pl == 0 is neither win nor loss

    total_closed = len(closed_trades)

    # Calculate actual win rate
    actual_win_rate = (actual_winners / total_closed * 100) if total_closed > 0 else 0.0

    # Get reported values
    reported_win_rate = performance.get("win_rate", 0.0)
    reported_winners = performance.get("winning_trades", 0)
    reported_losers = performance.get("losing_trades", 0)

    # Calculate discrepancy
    discrepancy = abs(actual_win_rate - reported_win_rate)

    return {
        "reported": {
            "win_rate": reported_win_rate,
            "winning_trades": reported_winners,
            "losing_trades": reported_losers,
        },
        "actual": {
            "win_rate": round(actual_win_rate, 2),
            "winning_trades": actual_winners,
            "losing_trades": actual_losers,
            "total_closed": total_closed,
        },
        "discrepancy": round(discrepancy, 2),
        "needs_fix": discrepancy > 0.5,  # More than 0.5% difference
    }


def fix_win_rate() -> bool:
    """
    Fix the win_rate by recalculating from closed_trades.

    Returns:
        True if fix was applied, False otherwise
    """
    if not STATE_FILE.exists():
        logger.error(f"State file not found: {STATE_FILE}")
        return False

    with open(STATE_FILE) as f:
        state = json.load(f)

    performance = state.get("performance", {})
    closed_trades = performance.get("closed_trades", [])

    # Count actual winners/losers
    actual_winners = 0
    actual_losers = 0

    for trade in closed_trades:
        pl = trade.get("pl", 0)
        if pl > 0:
            actual_winners += 1
        elif pl < 0:
            actual_losers += 1

    total_closed = len(closed_trades)
    actual_win_rate = (actual_winners / total_closed * 100) if total_closed > 0 else 0.0

    # Log the fix
    old_win_rate = performance.get("win_rate", 0.0)
    old_winners = performance.get("winning_trades", 0)
    old_losers = performance.get("losing_trades", 0)

    logger.info(f"Fixing win_rate: {old_win_rate:.1f}% -> {actual_win_rate:.1f}%")
    logger.info(f"Fixing winning_trades: {old_winners} -> {actual_winners}")
    logger.info(f"Fixing losing_trades: {old_losers} -> {actual_losers}")

    # Apply fix
    performance["win_rate"] = round(actual_win_rate, 2)
    performance["winning_trades"] = actual_winners
    performance["losing_trades"] = actual_losers
    performance["_win_rate_source"] = "calculated_from_closed_trades"
    performance["_win_rate_fixed_at"] = __import__("datetime").datetime.now().isoformat()

    state["performance"] = performance

    # Save
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

    logger.info(f"Win rate fixed and saved to {STATE_FILE}")
    return True


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Fix win rate from closed trades")
    parser.add_argument("--check", action="store_true", help="Check for discrepancy without fixing")
    parser.add_argument("--fix", action="store_true", help="Apply the fix")
    args = parser.parse_args()

    if args.check or not args.fix:
        result = calculate_accurate_win_rate()
        print("\n=== Win Rate Analysis ===")
        print(f"Reported win_rate: {result['reported']['win_rate']:.1f}%")
        print(f"Actual win_rate:   {result['actual']['win_rate']:.1f}%")
        print(f"Discrepancy:       {result['discrepancy']:.1f}%")
        print()
        print(f"Reported winners:  {result['reported']['winning_trades']}")
        print(f"Actual winners:    {result['actual']['winning_trades']}")
        print()
        print(f"Reported losers:   {result['reported']['losing_trades']}")
        print(f"Actual losers:     {result['actual']['losing_trades']}")
        print()
        print(f"Total closed:      {result['actual']['total_closed']}")
        print()

        if result["needs_fix"]:
            print("STATUS: FIX NEEDED - Run with --fix to correct")
        else:
            print(" STATUS: OK - No significant discrepancy")

        if not args.fix:
            return

    if args.fix:
        success = fix_win_rate()
        if success:
            print("\n WIN RATE FIXED SUCCESSFULLY")
        else:
            print("\n FAILED TO FIX WIN RATE")


if __name__ == "__main__":
    main()
