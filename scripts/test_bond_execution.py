#!/usr/bin/env python3
"""
Test Bond Execution Logic
Simulates the bond execution path to identify issues
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_bond_allocation():
    """Test bond allocation calculation"""
    print("=" * 80)
    print("BOND EXECUTION TEST")
    print("=" * 80)
    print()

    # Test with different daily allocations
    test_allocations = [6.0, 10.0, 100.0, 900.0, 1500.0]

    BOND_ALLOCATION_PCT = 0.15
    MIN_THRESHOLD = 0.50

    print("💰 ALLOCATION CALCULATION TEST")
    print("-" * 80)
    print(f"{'Daily Allocation':<20} {'Bond Amount':<15} {'Will Execute':<15}")
    print("-" * 80)

    for daily_alloc in test_allocations:
        bond_amount = daily_alloc * BOND_ALLOCATION_PCT
        will_execute = "✅ YES" if bond_amount >= MIN_THRESHOLD else "❌ NO"
        print(f"${daily_alloc:<19.2f} ${bond_amount:<14.2f} {will_execute}")

    print()
    print("📊 CURRENT SYSTEM STATE")
    print("-" * 80)

    # Based on Nov 11 trade: SPY $6.00
    actual_daily = 6.0
    actual_bond = actual_daily * BOND_ALLOCATION_PCT

    print(f"Actual Daily Allocation (from trades): ${actual_daily:.2f}")
    print(f"Expected Bond Allocation (15%): ${actual_bond:.2f}")
    print(f"Threshold: ${MIN_THRESHOLD:.2f}")
    print(f"Bond should execute: {'✅ YES' if actual_bond >= MIN_THRESHOLD else '❌ NO'}")
    print()

    print("🔍 EXECUTION LOGIC CHECK")
    print("-" * 80)
    print("Code path in core_strategy.py:")
    print("  1. Calculate bond_amount = allocation_to_use * 0.15")
    print("  2. Check: if bond_amount >= 0.50:")
    print("  3. Execute: alpaca_trader.execute_order(symbol='BND', ...)")
    print()
    print(f"With ${actual_daily:.2f} daily allocation:")
    print(f"  bond_amount = ${actual_daily:.2f} * 0.15 = ${actual_bond:.2f}")
    print(f"  ${actual_bond:.2f} >= ${MIN_THRESHOLD:.2f} = {actual_bond >= MIN_THRESHOLD}")
    print()

    if actual_bond >= MIN_THRESHOLD:
        print("⚠️  ISSUE IDENTIFIED:")
        print("   Bonds SHOULD be executing but aren't!")
        print("   Possible causes:")
        print("   1. Exception being caught silently in try/except")
        print("   2. Alpaca API rejecting orders")
        print("   3. Order validation failing")
        print("   4. Execution path not being reached")
        print("   5. Market hours restriction")
    else:
        print("✅ Allocation too small - bonds won't execute")

    print()
    print("=" * 80)


if __name__ == "__main__":
    test_bond_allocation()
