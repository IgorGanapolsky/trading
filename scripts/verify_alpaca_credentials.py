#!/usr/bin/env python3
"""
Verify Alpaca credentials and account access.
Tests both paper and real trading credentials.
"""

import os
import sys
from datetime import datetime

try:
    from alpaca.common.exceptions import APIError
    from alpaca.trading.client import TradingClient
except ImportError:
    print("❌ alpaca-py not installed. Run: pip install alpaca-py")
    sys.exit(1)


def verify_credentials(api_key: str, secret_key: str, label: str, paper: bool = True) -> dict:
    """
    Verify Alpaca credentials and return account info.

    Args:
        api_key: Alpaca API key
        secret_key: Alpaca secret key
        label: Label for this test (e.g., "Paper Trading", "Real Trading")
        paper: Whether this is a paper trading account

    Returns:
        Dictionary with verification results
    """
    print(f"\n{'=' * 60}")
    print(f"Testing: {label}")
    print(f"{'=' * 60}")

    if not api_key or not secret_key:
        print(f"❌ Missing credentials for {label}")
        return {"success": False, "error": "Missing credentials"}

    # Mask credentials for display
    masked_key = f"{api_key[:6]}...{api_key[-4:]}" if len(api_key) > 10 else "***"
    masked_secret = f"{secret_key[:6]}...{secret_key[-4:]}" if len(secret_key) > 10 else "***"

    print(f"API Key: {masked_key}")
    print(f"Secret: {masked_secret}")
    print(f"Paper Mode: {paper}")

    try:
        # Create trading client
        client = TradingClient(api_key, secret_key, paper=paper)

        # Get account info
        account = client.get_account()

        # Extract key metrics
        result = {
            "success": True,
            "account_number": account.account_number,
            "status": account.status,
            "equity": float(account.equity),
            "cash": float(account.cash),
            "buying_power": float(account.buying_power),
            "portfolio_value": float(account.portfolio_value),
            "pattern_day_trader": account.pattern_day_trader,
            "trading_blocked": account.trading_blocked,
            "account_blocked": account.account_blocked,
        }

        # Display results
        print("\n✅ Credentials VERIFIED")
        print(f"Account Number: {result['account_number']}")
        print(f"Status: {result['status']}")
        print(f"Equity: ${result['equity']:,.2f}")
        print(f"Cash: ${result['cash']:,.2f}")
        print(f"Buying Power: ${result['buying_power']:,.2f}")
        print(f"Portfolio Value: ${result['portfolio_value']:,.2f}")
        print(f"Pattern Day Trader: {result['pattern_day_trader']}")
        print(f"Trading Blocked: {result['trading_blocked']}")
        print(f"Account Blocked: {result['account_blocked']}")

        # Check for any issues
        if result["trading_blocked"] or result["account_blocked"]:
            print("\n⚠️  WARNING: Account has restrictions!")

        if result["status"] != "ACTIVE":
            print(f"\n⚠️  WARNING: Account status is {result['status']}")

        return result

    except APIError as e:
        print(f"\n❌ API Error: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return {"success": False, "error": str(e)}


def main():
    """Main verification routine."""
    print(f"\n{'#' * 60}")
    print("# Alpaca Credentials Verification")
    print(f"# {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#' * 60}")

    # Test Paper Trading credentials (from env or GitHub secrets)
    paper_key = os.getenv("ALPACA_PAPER_API_KEY") or os.getenv("ALPACA_API_KEY")
    paper_secret = os.getenv("ALPACA_PAPER_SECRET_KEY") or os.getenv("ALPACA_SECRET_KEY")

    # Test Real Trading credentials (separate env vars)
    real_key = os.getenv("ALPACA_REAL_API_KEY")
    real_secret = os.getenv("ALPACA_REAL_SECRET_KEY")

    results = {}

    # Verify Paper Trading
    if paper_key and paper_secret:
        results["paper"] = verify_credentials(
            paper_key, paper_secret, "Paper Trading Account", paper=True
        )
    else:
        print("\n⚠️  No paper trading credentials found in environment")

    # Verify Real Trading
    if real_key and real_secret:
        results["real"] = verify_credentials(
            real_key, real_secret, "Real Money Trading Account", paper=False
        )
    else:
        print("\n⚠️  No real trading credentials found in environment")
        print("    Set ALPACA_REAL_API_KEY and ALPACA_REAL_SECRET_KEY to test")

    # Summary
    print(f"\n{'=' * 60}")
    print("VERIFICATION SUMMARY")
    print(f"{'=' * 60}")

    if "paper" in results and results["paper"]["success"]:
        print("✅ Paper Trading: VERIFIED")
        print(f"   Portfolio Value: ${results['paper']['portfolio_value']:,.2f}")
    else:
        print("❌ Paper Trading: FAILED")

    if "real" in results and results["real"]["success"]:
        print("✅ Real Trading: VERIFIED")
        print(f"   Portfolio Value: ${results['real']['portfolio_value']:,.2f}")
        print("\n⚠️  CAUTION: Real money account is accessible!")
    else:
        print("⚠️  Real Trading: NOT TESTED (credentials not provided)")

    print(f"{'=' * 60}\n")

    # Exit with appropriate code
    if results:
        if any(r.get("success") for r in results.values()):
            sys.exit(0)

    sys.exit(1)


if __name__ == "__main__":
    main()
