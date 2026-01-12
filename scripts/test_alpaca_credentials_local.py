#!/usr/bin/env python3
"""
Test Alpaca credentials locally.

USAGE:
  Set environment variables, then run this script.
  python3 scripts/test_alpaca_credentials_local.py

This bypasses GitHub Actions to test if credentials work directly.
"""

import sys

try:
    from alpaca.trading.client import TradingClient
except ImportError:
    print("❌ alpaca-py not installed")
    print("   Run: pip install alpaca-py")
    sys.exit(1)


def test_credentials():
    """Test Alpaca API credentials for paper trading."""
    from src.utils.alpaca_client import get_alpaca_credentials

    api_key, secret_key = get_alpaca_credentials()

    if not api_key or not secret_key:
        print("❌ Missing credentials")
        print("   Set ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables")
        return False

    print("Testing credentials:")
    print(f"  API Key: {api_key[:8]}...{api_key[-4:]}")
    print(f"  Secret:  {secret_key[:8]}...{secret_key[-4:]}")
    print("  Mode:    PAPER")
    print()

    try:
        # Test paper trading
        print("Connecting to Alpaca Paper Trading API...")
        client = TradingClient(api_key=api_key, secret_key=secret_key, paper=True)

        print("Fetching account info...")
        account = client.get_account()

        print("\n✅ SUCCESS - Paper trading credentials are VALID")
        print(f"   Account Status: {account.status}")
        print(f"   Equity: ${float(account.equity):,.2f}")
        print(f"   Buying Power: ${float(account.buying_power):,.2f}")
        print(f"   Cash: ${float(account.cash):,.2f}")
        return True

    except Exception as e:
        print(f"\n❌ FAILED - {type(e).__name__}")
        print(f"   Error: {e}")

        error_str = str(e).lower()
        print("\n💡 Diagnosis:")

        if "unauthorized" in error_str or "forbidden" in error_str:
            print("   - Credentials are INVALID or EXPIRED")
            print("   - Possible causes:")
            print("     1. Keys are for LIVE account (not paper)")
            print("     2. Keys were regenerated after adding to GitHub")
            print("     3. Typo when copying keys")
            print("   - Solution: Regenerate paper trading keys from Alpaca dashboard")

        elif "ssl" in error_str or "certificate" in error_str:
            print("   - SSL/TLS connection issue")
            print("   - Check network/firewall settings")

        else:
            print("   - Unknown error - check Alpaca API status")
            print("   - Visit: https://alpaca.markets/support")

        return False


if __name__ == "__main__":
    success = test_credentials()
    sys.exit(0 if success else 1)
