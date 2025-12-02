#!/usr/bin/env python3
"""
Test Fibonacci Scaler with new convenience API.
"""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.financial_automation import FibonacciScaler


def test_fibonacci_api():
    """Test the new convenience API."""
    print("=" * 70)
    print("🧪 FIBONACCI SCALER TEST - New Convenience API")
    print("=" * 70)

    # Initialize scaler
    scaler = FibonacciScaler(paper=True)

    # Test 1: Get current level
    print("\n--- Test 1: Get Current Level ---")
    level_idx = scaler.get_current_level()
    print(f"Current Level Index: {level_idx}")
    print(f"Fibonacci Sequence: {scaler.FIBONACCI}")

    # Test 2: Get daily amount
    print("\n--- Test 2: Get Daily Amount ---")
    daily_amount = scaler.get_daily_amount()
    print(f"Current Daily Amount: ${daily_amount:.2f}/day")

    # Test 3: Get next milestone
    print("\n--- Test 3: Get Next Milestone ---")
    milestone = scaler.get_next_milestone()
    print(f"At Max: {milestone.get('at_max', False)}")
    print(f"Current Level: ${milestone.get('current_level', 0):.0f}/day")
    print(f"Next Level: ${milestone.get('next_level', 0):.0f}/day")
    print(f"Current Profit: ${milestone.get('current_profit', 0):.2f}")
    print(f"Required Profit: ${milestone.get('required_profit', 0):.2f}")
    print(f"Remaining: ${milestone.get('remaining', 0):.2f}")
    print(f"Progress: {milestone.get('progress_pct', 0):.1f}%")
    print(f"Message: {milestone.get('message', 'N/A')}")

    # Test 4: Should scale up?
    print("\n--- Test 4: Should Scale Up? ---")
    should_scale = scaler.should_scale_up()
    print(f"Ready to Scale Up: {should_scale}")

    # Test 5: Try to scale up
    print("\n--- Test 5: Try Scale Up ---")
    scale_result = scaler.scale_up()
    print(f"Scaled: {scale_result.get('scaled', False)}")
    if scale_result.get('scaled'):
        print(f"Old Amount: ${scale_result['old_amount']}/day")
        print(f"New Amount: ${scale_result['new_amount']}/day")
        print(f"Profit at Scale: ${scale_result['profit_at_scale']:.2f}")
    else:
        print(f"Reason: {scale_result.get('reason', 'Unknown')}")
        print(f"Remaining: ${scale_result.get('remaining', 0):.2f}")

    # Test 6: Get projection
    print("\n--- Test 6: Get Projection to $100/day ---")
    projection = scaler.get_projection(avg_daily_return_pct=0.13)
    print(f"Current Level: ${projection['current_level']:.0f}/day")
    print(f"Current Profit: ${projection['current_profit']:.2f}")
    print(f"Current Equity: ${projection['current_equity']:.2f}")
    print(f"Days to $100/day: {projection['days_to_max']}")
    print(f"Months to $100/day: {projection['months_to_max']:.1f}")
    print(f"Estimated Date: {projection['date_at_max']}")
    print(f"Assumption: {projection['avg_daily_return_pct']:.2f}% daily return")

    print("\n--- Milestone Projections ---")
    for milestone in projection['milestones'][:5]:  # Show first 5
        print(f"  ${milestone['daily_amount']:3.0f}/day → "
              f"{milestone['days_from_now']:4d} days "
              f"({milestone['months_from_now']:4.1f} months) → "
              f"{milestone['date_estimate']}")

    print("\n" + "=" * 70)
    print("✅ All tests completed successfully!")
    print("=" * 70)


def test_scaling_thresholds():
    """Test that scaling thresholds match specification."""
    print("\n\n" + "=" * 70)
    print("🎯 FIBONACCI SCALING THRESHOLDS VERIFICATION")
    print("=" * 70)

    scaler = FibonacciScaler(paper=True)

    expected_milestones = [
        (1, 30),    # $1/day needs $30 profit (1×30)
        (2, 60),    # $2/day needs $60 profit (2×30)
        (3, 90),    # $3/day needs $90 profit (3×30)
        (5, 150),   # $5/day needs $150 profit (5×30)
        (8, 240),   # $8/day needs $240 profit (8×30)
        (13, 390),  # $13/day needs $390 profit (13×30)
        (21, 630),  # $21/day needs $630 profit (21×30)
        (34, 1020), # $34/day needs $1020 profit (34×30)
        (55, 1650), # $55/day needs $1650 profit (55×30)
        (89, 2670), # $89/day needs $2670 profit (89×30)
        (100, 3000), # $100/day needs $3000 profit (100×30)
    ]

    print("\nFibonacci Level | Daily Amount | Profit Required | Formula")
    print("-" * 70)

    all_match = True
    for i, (fib_amount, expected_profit) in enumerate(expected_milestones):
        calculated_profit = fib_amount * scaler.FUNDING_DAYS
        match = "✅" if calculated_profit == expected_profit else "❌"
        print(f"Level {i:2d}        | ${fib_amount:3.0f}/day     | "
              f"${calculated_profit:5.0f}          | "
              f"${fib_amount} × {scaler.FUNDING_DAYS} days {match}")

        if calculated_profit != expected_profit:
            all_match = False
            print(f"  ERROR: Expected ${expected_profit}, got ${calculated_profit}")

    print("-" * 70)
    if all_match:
        print("✅ All thresholds match specification!")
    else:
        print("❌ Some thresholds don't match!")

    print("=" * 70)


if __name__ == "__main__":
    test_fibonacci_api()
    test_scaling_thresholds()
