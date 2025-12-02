#!/usr/bin/env python3
"""
Test script to verify Alpaca Options API capability.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.options_client import AlpacaOptionsClient


def main():
    load_dotenv()

    print("=" * 60)
    print("🧪 TESTING ALPACA OPTIONS CAPABILITY")
    print("=" * 60)

    try:
        # 1. Initialize Client
        print("\n1. Initializing Options Client...")
        client = AlpacaOptionsClient(paper=True)
        print("✅ Client initialized successfully.")

        # 2. Check Account
        print("\n2. Checking Account Status...")
        is_enabled = client.check_options_enabled()
        print(f"✅ Account check passed. Options enabled: {is_enabled}")

        # 3. Fetch Option Chain for SPY
        symbol = "SPY"
        print(f"\n3. Fetching Option Chain for {symbol}...")
        contracts = client.get_option_chain(symbol)

        if contracts:
            print(f"✅ Successfully retrieved {len(contracts)} contracts for {symbol}.")

            print("\n📊 Sample Contracts (First 5):")
            print("-" * 60)
            print(f"{'Symbol':<25} | {'Price':<10} | {'IV':<8} | {'Delta':<8}")
            print("-" * 60)

            for contract in contracts[:5]:
                price = contract["latest_trade_price"] or 0.0
                iv = contract["implied_volatility"] or 0.0
                greeks = contract.get("greeks") or {}
                delta = greeks.get("delta") or 0.0

                print(f"{contract['symbol']:<25} | ${price:<9.2f} | {iv:<8.4f} | {delta:<8.4f}")
            print("-" * 60)

            # 4. Success Message
            print("\n🎉 SUCCESS: Options API is working and accessible!")
            print("   We can proceed with Phase 1: Infrastructure.")

        else:
            print(
                f"⚠️  No contracts found for {symbol}. Market might be closed or data unavailable."
            )

    except Exception as e:
        print("\n❌ FAILURE: Options capability test failed.")
        print(f"   Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
