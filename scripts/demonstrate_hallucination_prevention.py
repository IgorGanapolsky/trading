#!/usr/bin/env python3
"""
Demonstrate how staleness detection prevents hallucinations

This recreates the exact scenario that caused the Nov 4 hallucination:
- State file from Oct 30 (5 days old)
- CTO reads it on Nov 4 and reports "Day 2"
- New system BLOCKS this and forces data refresh
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from state_manager import STATE_FILE, StateManager


def backup_state():
    """Backup current state"""
    if STATE_FILE.exists():
        backup_file = STATE_FILE.with_suffix(".json.backup")
        with open(STATE_FILE) as src, open(backup_file, "w") as dst:
            dst.write(src.read())
        return True
    return False


def restore_state():
    """Restore state from backup"""
    backup_file = STATE_FILE.with_suffix(".json.backup")
    if backup_file.exists():
        with open(backup_file) as src, open(STATE_FILE, "w") as dst:
            dst.write(src.read())
        backup_file.unlink()
        return True
    return False


def simulate_oct_30_state():
    """Create state as it was on Oct 30, 2025"""
    if not STATE_FILE.exists():
        print(f"❌ State file not found: {STATE_FILE}")
        return False

    with open(STATE_FILE) as f:
        state = json.load(f)

    # Set state to look like Oct 30, 2025 at 10:00 AM
    oct_30 = datetime(2025, 10, 30, 10, 0, 0)
    state["meta"]["last_updated"] = oct_30.isoformat()

    # Old challenge data (Day 2)
    state["challenge"]["current_day"] = 2
    state["challenge"]["start_date"] = "2025-10-29"

    # Old account data
    state["account"]["current_equity"] = 100000.02
    state["account"]["total_pl"] = 0.02
    state["account"]["total_pl_pct"] = 0.0002

    # Old performance data
    state["performance"]["total_trades"] = 2
    state["performance"]["winning_trades"] = 2

    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

    print("✅ Simulated Oct 30 state (Day 2 data)")
    return True


def main():
    print("=" * 70)
    print("HALLUCINATION PREVENTION DEMONSTRATION")
    print("=" * 70)
    print("\nScenario: CTO tries to read 5-day-old state on Nov 4, 2025")
    print("Expected: System BLOCKS load and forces data refresh")
    print("=" * 70)

    # Backup current state
    if not backup_state():
        print("❌ No state file found - cannot test")
        return

    try:
        # Simulate Oct 30 state
        if not simulate_oct_30_state():
            return

        print("\n📅 Today is November 4, 2025")
        print("📁 State file last updated: October 30, 2025 (5 days ago)")
        print("📊 State shows: Day 2 of challenge, P/L +$0.02")
        print("\n🤖 CTO attempts to load state...\n")

        # Try to load the stale state
        try:
            StateManager()
            print("\n❌ FAILURE: State loaded without blocking!")
            print("This would cause hallucination: reporting Day 2 when it's actually Day 7")

        except ValueError as e:
            print("✅ SUCCESS: Staleness detection BLOCKED the load!")
            print("\n" + "=" * 70)
            print("ERROR MESSAGE SHOWN TO CTO:")
            print("=" * 70)
            print(str(e))
            print("\n✅ This prevents hallucination!")
            print("✅ CTO is forced to refresh data before proceeding")
            print("✅ Accurate reporting guaranteed")

    finally:
        # Restore original state
        restore_state()
        print("\n" + "=" * 70)
        print("✅ Original state restored")


if __name__ == "__main__":
    main()
