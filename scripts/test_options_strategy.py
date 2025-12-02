#!/usr/bin/env python3
"""
Test script for Options Strategy Logic (Covered Calls).
Simulates a portfolio with 100 shares of SPY to test contract selection.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.strategies.options_strategy import OptionsStrategy


def main():
    load_dotenv()

    print("=" * 60)
    print("🧪 TESTING COVERED CALL STRATEGY LOGIC")
    print("=" * 60)

    try:
        # 1. Initialize Strategy
        print("\n1. Initializing Options Strategy...")
        strategy = OptionsStrategy(paper=True)
        print("✅ Strategy initialized.")

        # 2. Mock Portfolio (Inject 100 shares of SPY)
        print("\n2. Mocking Portfolio (100 shares of SPY)...")
        # We'll mock the get_positions method to return a fake position
        strategy.trader.get_positions = MagicMock(
            return_value=[
                {
                    "symbol": "SPY",
                    "qty": "100",
                    "current_price": "600.00",  # Approx current price
                    "side": "long",
                }
            ]
        )
        print("✅ Portfolio mocked.")

        # 3. Execute Strategy Logic
        print("\n3. Running Strategy Execution...")
        results = strategy.execute_daily()

        # 4. Analyze Results
        if results:
            print(f"\n✅ Strategy found {len(results)} opportunity(ies)!")
            for res in results:
                print("\n🎯 PROPOSED TRADE:")
                print(f"   Underlying: {res['underlying']}")
                print(f"   Option:     {res['option_symbol']}")
                print(f"   Strike:     ${res['strike']:.2f}")
                print(f"   Expiration: {res['expiration']}")
                print(f"   Premium:    ${res['premium']:.2f}")
                print(f"   Delta:      {res['delta']:.4f}")
                print(f"   Contracts:  {res['contracts']}")

                # Calculate Yield
                notional = 600.00 * 100
                premium_total = res["premium"] * 100
                yield_pct = (premium_total / notional) * 100
                print(f"   Est. Yield: {yield_pct:.2f}% (Monthly)")
        else:
            print("\n⚠️  No opportunities found. (Check market hours/data availability)")

    except Exception as e:
        print("\n❌ FAILURE: Strategy test failed.")
        print(f"   Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
