#!/usr/bin/env python3
"""
Test Alpaca API Connectivity

Quick script to verify Alpaca API keys are working correctly.
Runs in CI to verify secrets are properly configured.

Usage:
    python3 scripts/test_alpaca_connectivity.py
    python3 scripts/test_alpaca_connectivity.py --paper  # Test paper trading
    python3 scripts/test_alpaca_connectivity.py --live   # Test live/brokerage
"""

import argparse
import os
import sys


def test_connectivity(paper: bool = True) -> dict:
    """Test Alpaca API connectivity."""
    result = {
        "mode": "paper" if paper else "live",
        "connected": False,
        "account_status": None,
        "cash": None,
        "buying_power": None,
        "error": None,
    }

    try:
        from alpaca.trading.client import TradingClient
    except ImportError:
        result["error"] = "alpaca-py not installed"
        return result

    # Get API keys from environment
    if paper:
        api_key = os.environ.get("ALPACA_PAPER_TRADING_5K_API_KEY") or os.environ.get(
            "ALPACA_API_KEY"
        )
        api_secret = os.environ.get(
            "ALPACA_PAPER_TRADING_5K_API_SECRET"
        ) or os.environ.get("ALPACA_SECRET_KEY")
    else:
        api_key = os.environ.get("ALPACA_BROKERAGE_TRADING_API_KEY") or os.environ.get(
            "ALPACA_API_KEY"
        )
        api_secret = os.environ.get(
            "ALPACA_BROKERAGE_TRADING_API_SECRET"
        ) or os.environ.get("ALPACA_SECRET_KEY")

    if not api_key or not api_secret:
        result["error"] = "API keys not found in environment"
        return result

    try:
        client = TradingClient(api_key=api_key, secret_key=api_secret, paper=paper)
        account = client.get_account()

        result["connected"] = True
        result["account_status"] = str(account.status)
        result["cash"] = float(account.cash)
        result["buying_power"] = float(account.buying_power)

    except Exception as e:
        result["error"] = str(e)

    return result


def main():
    parser = argparse.ArgumentParser(description="Test Alpaca API connectivity")
    parser.add_argument("--paper", action="store_true", help="Test paper trading API")
    parser.add_argument("--live", action="store_true", help="Test live/brokerage API")
    args = parser.parse_args()

    # Default to paper if neither specified
    if not args.paper and not args.live:
        args.paper = True

    results = []

    if args.paper:
        print("Testing PAPER trading API...")
        result = test_connectivity(paper=True)
        results.append(result)
        if result["connected"]:
            print(f"  CONNECTED - Status: {result['account_status']}")
            print(f"  Cash: ${result['cash']:,.2f}")
            print(f"  Buying Power: ${result['buying_power']:,.2f}")
        else:
            print(f"  FAILED - {result['error']}")

    if args.live:
        print("Testing LIVE/BROKERAGE API...")
        result = test_connectivity(paper=False)
        results.append(result)
        if result["connected"]:
            print(f"  CONNECTED - Status: {result['account_status']}")
            print(f"  Cash: ${result['cash']:,.2f}")
            print(f"  Buying Power: ${result['buying_power']:,.2f}")
        else:
            print(f"  FAILED - {result['error']}")

    # Exit with error if any connection failed
    if any(not r["connected"] for r in results):
        sys.exit(1)

    print("\nAll connectivity tests passed!")
    sys.exit(0)


if __name__ == "__main__":
    main()
