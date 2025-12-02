#!/usr/bin/env python3
"""
Test the exact Nov 3 scenario to ensure it would be prevented.

Nov 3 Incident:
- Expected: $8/day ($6 T1 + $2 T2)
- Actual: $1,600 deployed (200x too large)
- Result: Financial loss

This test simulates that scenario to verify the validation
would have caught and prevented it.
"""

import os
import sys

# Set up environment
os.environ["DAILY_INVESTMENT"] = "10.0"
os.environ["ALPACA_API_KEY"] = "test_key"
os.environ["ALPACA_SECRET_KEY"] = "test_secret"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.core.alpaca_trader import AlpacaTrader, OrderExecutionError


def test_nov3_scenario():
    """Test the exact Nov 3 scenario."""
    print("=" * 80)
    print("NOV 3 INCIDENT SIMULATION")
    print("=" * 80)
    print()
    print("Scenario: Attempting to place $1,600 order (200x expected $8)")
    print("Expected behavior: ORDER SHOULD BE REJECTED with loud error")
    print()

    # Create mock trader
    class MockTrader:
        def __init__(self):
            self.daily_investment = float(os.getenv("DAILY_INVESTMENT", "10.0"))
            self.TIER_ALLOCATIONS = AlpacaTrader.TIER_ALLOCATIONS
            self.MAX_ORDER_MULTIPLIER = AlpacaTrader.MAX_ORDER_MULTIPLIER

        validate_order_amount = AlpacaTrader.validate_order_amount

    trader = MockTrader()

    # Simulate Nov 3 orders
    test_orders = [
        {"symbol": "SPY", "amount": 800.0, "tier": "T1_CORE", "expected": 6.0},
        {"symbol": "NVDA", "amount": 800.0, "tier": "T2_GROWTH", "expected": 2.0},
    ]

    total_deployed = 0
    total_rejected = 0

    for order in test_orders:
        print(f"Testing: {order['symbol']} ${order['amount']} (tier: {order['tier']})")
        print(f"  Expected: ${order['expected']}")
        print(f"  Multiplier: {order['amount'] / order['expected']:.1f}x")

        try:
            trader.validate_order_amount(order["symbol"], order["amount"], order["tier"])
        except OrderExecutionError:
            print("  ✅ VALIDATION SUCCESS - Order was REJECTED (good!)")
            total_rejected += order["amount"]

        print()

    # Results
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"Total that would have been deployed: ${total_deployed:.2f}")
    print(f"Total rejected by validation: ${total_rejected:.2f}")
    print()

    if total_deployed == 0 and total_rejected == 1600.0:
        print("✅ SUCCESS! Nov 3 incident would have been PREVENTED.")
        print("The validation system caught the 200x error before money was deployed.")
        return True
    else:
        print("❌ FAILURE! Validation did not prevent the incident.")
        return False


if __name__ == "__main__":
    success = test_nov3_scenario()
    sys.exit(0 if success else 1)
