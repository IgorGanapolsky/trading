#!/usr/bin/env python3
"""
Test Bond Order Execution
Manually tests BND order execution to capture exact errors
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

load_dotenv()

from core.alpaca_trader import AlpacaTrader


def test_bnd_order():
    """Test executing a BND order to capture exact error"""
    print("=" * 80)
    print("BOND ORDER EXECUTION TEST")
    print("=" * 80)
    print()

    # Test with actual bond allocation
    test_amount = 0.90  # 15% of $6.00 daily allocation

    print("📊 Test Configuration")
    print("-" * 80)
    print("Symbol: BND")
    print(f"Amount: ${test_amount:.2f}")
    print("Tier: T1_CORE")
    print()

    try:
        trader = AlpacaTrader(paper=True)
        print("✅ Alpaca trader initialized")
        print()

        # Check account info
        account_info = trader.get_account_info()
        print("💰 Account Information")
        print("-" * 80)
        print(f"Buying Power: ${account_info.get('buying_power', 0):,.2f}")
        print(f"Cash: ${account_info.get('cash', 0):,.2f}")
        print(f"Equity: ${account_info.get('portfolio_value', 0):,.2f}")
        print()

        # Validate order amount first
        print("🔍 Order Validation")
        print("-" * 80)
        try:
            trader.validate_order_amount("BND", test_amount, tier="T1_CORE")
            print(f"✅ Order validation passed: ${test_amount:.2f}")
        except Exception as e:
            print(f"❌ Order validation FAILED: {type(e).__name__}: {e}")
            return
        print()

        # Attempt to execute order
        print("🚀 Executing BND Order")
        print("-" * 80)
        print(f"Attempting to execute: BND ${test_amount:.2f}")
        print()

        order_result = trader.execute_order(
            symbol="BND",
            amount_usd=test_amount,
            side="buy",
            tier="T1_CORE",
        )

        print("=" * 80)
        print("✅ ORDER EXECUTED SUCCESSFULLY!")
        print("=" * 80)
        print(f"Order ID: {order_result.get('id', 'N/A')}")
        print(f"Symbol: {order_result.get('symbol', 'N/A')}")
        print(f"Status: {order_result.get('status', 'N/A')}")
        print(f"Amount: ${order_result.get('notional', test_amount):.2f}")
        print()

    except Exception as e:
        print("=" * 80)
        print("❌ ORDER EXECUTION FAILED")
        print("=" * 80)
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {e}")
        print()
        print("Full Exception Details:")
        import traceback

        traceback.print_exc()
        print()
        print("=" * 80)
        print("DIAGNOSIS:")
        print("-" * 80)
        error_str = str(e).lower()
        if "minimum" in error_str or "too small" in error_str:
            print("⚠️  Issue: Order amount may be below Alpaca's minimum")
            print(f"   Current test amount: ${test_amount:.2f}")
            print("   Solution: Check Alpaca API minimum order requirements")
        elif "validation" in error_str or "validate" in error_str:
            print("⚠️  Issue: Order validation failed")
            print("   Solution: Check validate_order_amount() logic")
        elif "buying power" in error_str or "insufficient" in error_str:
            print("⚠️  Issue: Insufficient buying power")
            print("   Solution: Check account balance")
        elif "blocked" in error_str or "permission" in error_str:
            print("⚠️  Issue: Trading blocked or permission denied")
            print("   Solution: Check account status and permissions")
        else:
            print("⚠️  Issue: Unknown error - see exception details above")
        print()


if __name__ == "__main__":
    test_bnd_order()
