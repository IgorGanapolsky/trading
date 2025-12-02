#!/usr/bin/env python3
"""
Test staleness detection system
Simulates different staleness scenarios
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from state_manager import STATE_FILE, StateManager


def backup_state():
    """Backup current state"""
    if STATE_FILE.exists():
        backup_file = STATE_FILE.with_suffix(".json.backup")
        with open(STATE_FILE) as src, open(backup_file, "w") as dst:
            dst.write(src.read())
        print(f"✅ Backed up state to {backup_file}")
        return True
    return False


def restore_state():
    """Restore state from backup"""
    backup_file = STATE_FILE.with_suffix(".json.backup")
    if backup_file.exists():
        with open(backup_file) as src, open(STATE_FILE, "w") as dst:
            dst.write(src.read())
        print(f"✅ Restored state from {backup_file}")
        backup_file.unlink()
        return True
    return False


def set_state_age(hours_old: float):
    """Set state to be a specific age"""
    if not STATE_FILE.exists():
        print(f"❌ State file not found: {STATE_FILE}")
        return False

    with open(STATE_FILE) as f:
        state = json.load(f)

    # Set last_updated to be hours_old ago
    fake_time = datetime.now() - timedelta(hours=hours_old)
    state["meta"]["last_updated"] = fake_time.isoformat()

    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

    print(f"✅ Set state to be {hours_old:.1f} hours ({hours_old / 24:.1f} days) old")
    return True


def test_scenario(name: str, hours_old: float, should_fail: bool = False):
    """Test a specific staleness scenario"""
    print("\n" + "=" * 70)
    print(f"TEST: {name}")
    print(f"Age: {hours_old:.1f} hours ({hours_old / 24:.1f} days)")
    print("=" * 70)

    # Set the state age
    if not set_state_age(hours_old):
        return False

    # Try to load state
    try:
        sm = StateManager()
        print("\n✅ StateManager loaded successfully")
        print(f"Status: {sm.state['meta']['staleness_status']}")
        print(
            f"Confidence: {sm.state['meta']['self_evaluation']['confidence_in_state'] * 100:.0f}%"
        )

        if should_fail:
            print("\n❌ FAILED: Should have raised ValueError for EXPIRED state")
            return False

        return True
    except ValueError as e:
        if should_fail:
            print("\n✅ Correctly blocked EXPIRED state")
            print(f"Error message:\n{str(e)[:200]}...")
            return True
        else:
            print("\n❌ FAILED: Should NOT have raised ValueError")
            print(f"Error: {e}")
            return False


def main():
    print("=" * 70)
    print("STALENESS DETECTION TEST SUITE")
    print("=" * 70)

    # Backup current state
    if not backup_state():
        print("❌ No state file found - cannot test")
        return

    try:
        results = []

        # Test 1: FRESH state (12 hours)
        results.append(
            (
                "FRESH (12 hours)",
                test_scenario("FRESH State - 12 hours old", hours_old=12, should_fail=False),
            )
        )

        # Test 2: AGING state (36 hours)
        results.append(
            (
                "AGING (36 hours)",
                test_scenario("AGING State - 36 hours old", hours_old=36, should_fail=False),
            )
        )

        # Test 3: STALE state (60 hours / 2.5 days)
        results.append(
            (
                "STALE (2.5 days)",
                test_scenario("STALE State - 2.5 days old", hours_old=60, should_fail=False),
            )
        )

        # Test 4: EXPIRED state (96 hours / 4 days)
        results.append(
            (
                "EXPIRED (4 days)",
                test_scenario("EXPIRED State - 4 days old", hours_old=96, should_fail=True),
            )
        )

        # Print summary
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        for name, passed in results:
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{status}: {name}")

        all_passed = all(r[1] for r in results)
        if all_passed:
            print("\n🎉 ALL TESTS PASSED - Staleness detection working correctly!")
        else:
            print("\n⚠️  SOME TESTS FAILED - Review results above")

    finally:
        # Always restore original state
        restore_state()
        print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
