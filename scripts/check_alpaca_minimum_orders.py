#!/usr/bin/env python3
"""
Check Alpaca API Minimum Order Requirements
Investigates minimum order sizes for stocks/ETFs
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

load_dotenv()

try:
    from alpaca.common.exceptions import APIError
    from alpaca.trading.client import TradingClient
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import MarketOrderRequest
except ImportError:
    print("⚠️  Alpaca SDK not available - checking via REST API")

    ALPACA_KEY = os.getenv("ALPACA_API_KEY")
    ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY")
    BASE_URL = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets")

    if ALPACA_KEY and ALPACA_SECRET:
        print("✅ API credentials found")
        print(f"Base URL: {BASE_URL}")
        print()
        print("📚 Alpaca API Minimum Order Requirements:")
        print("-" * 80)
        print("According to Alpaca documentation:")
        print("- Minimum order size: $1.00 USD (for fractional shares)")
        print("- Some assets may have higher minimums")
        print("- Market orders require sufficient buying power")
        print()
        print("⚠️  If bond orders are failing, possible causes:")
        print("1. Order amount < $1.00 minimum")
        print("2. Insufficient buying power")
        print("3. Account trading restrictions")
        print("4. Market hours restrictions")
        print()
        print("💡 Recommendation: Test with $1.00 minimum to verify")
    else:
        print("❌ ALPACA_API_KEY and ALPACA_SECRET_KEY not found")
    sys.exit(0)

from core.alpaca_trader import AlpacaTrader


def check_minimum_orders():
    """Check Alpaca minimum order requirements"""
    print("=" * 80)
    print("ALPACA MINIMUM ORDER REQUIREMENTS CHECK")
    print("=" * 80)
    print()

    try:
        trader = AlpacaTrader(paper=True)
        print("✅ Connected to Alpaca API")
        print()

        # Get account info
        account_info = trader.get_account_info()
        print("💰 Account Status")
        print("-" * 80)
        print(f"Buying Power: ${account_info.get('buying_power', 0):,.2f}")
        print(f"Cash: ${account_info.get('cash', 0):,.2f}")
        print(f"Trading Blocked: {account_info.get('trading_blocked', False)}")
        print()

        # Test different order amounts
        test_amounts = [0.50, 0.90, 1.00, 1.50, 2.00]
        symbol = "BND"

        print("🧪 Testing Order Validation")
        print("-" * 80)
        print(f"Symbol: {symbol}")
        print("Tier: T1_CORE")
        print()

        for amount in test_amounts:
            try:
                trader.validate_order_amount(symbol, amount, tier="T1_CORE")
                print(f"✅ ${amount:.2f}: Validation PASSED")
            except Exception as e:
                print(f"❌ ${amount:.2f}: Validation FAILED - {type(e).__name__}: {e}")

        print()
        print("=" * 80)
        print("📚 Alpaca API Documentation Notes")
        print("=" * 80)
        print("- Minimum order size: $1.00 USD (for fractional shares)")
        print("- Orders < $1.00 may be rejected by Alpaca")
        print("- Current bond allocation: $0.90 (below $1.00 minimum)")
        print()
        print("💡 RECOMMENDATION:")
        print("   Increase bond allocation threshold to $1.00 minimum")
        print("   Or increase daily allocation to make bond amount >= $1.00")
        print()

    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    check_minimum_orders()
