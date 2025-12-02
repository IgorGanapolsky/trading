#!/usr/bin/env python3
"""
Test script for backtesting engine

This script demonstrates how to use the backtest engine with the CoreStrategy.
It runs a simple backtest and displays the results.

Usage:
    python test_backtest.py
"""

import logging
import sys
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, "/Users/igorganapolsky/workspace/git/apps/trading")

from src.backtesting.backtest_engine import BacktestEngine
from src.strategies.core_strategy import CoreStrategy


def main():
    """Run a simple backtest example."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("\n" + "=" * 80)
    print("BACKTEST ENGINE TEST")
    print("=" * 80)

    # Create strategy (disable sentiment for faster testing)
    print("\n1. Initializing CoreStrategy...")
    strategy = CoreStrategy(
        daily_allocation=6.0,
        etf_universe=["SPY", "QQQ", "VOO"],
        use_sentiment=False,  # Disable for faster testing
    )
    print("   ✓ Strategy initialized")

    # Calculate date range (last 60 days for quick test)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)  # ~60 trading days

    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    print(f"\n2. Setting up backtest period: {start_date_str} to {end_date_str}")

    # Create backtest engine
    engine = BacktestEngine(
        strategy=strategy,
        start_date=start_date_str,
        end_date=end_date_str,
        initial_capital=100000.0,
    )
    print("   ✓ Backtest engine initialized")

    # Run backtest
    print("\n3. Running backtest...")
    try:
        results = engine.run()
        print("   ✓ Backtest completed successfully")

        # Display results
        print("\n" + "=" * 80)
        print(results.generate_report())

        # Additional quick stats
        print("\n" + "=" * 80)
        print("QUICK STATS")
        print("=" * 80)
        print(f"Total Trades Executed: {results.total_trades}")
        print(f"Trading Days Simulated: {results.trading_days}")
        print(
            f"Average Trades/Day: {results.total_trades / results.trading_days:.2f}"
            if results.trading_days > 0
            else "N/A"
        )

        if results.total_trades > 0:
            print("\nSample Trade (First):")
            first_trade = results.trades[0]
            print(
                f"  Date: {first_trade['date']}, Symbol: {first_trade['symbol']}, "
                f"Price: ${first_trade['price']:.2f}, Amount: ${first_trade['amount']:.2f}"
            )

        # Export results to dict (could be saved to JSON)
        results_dict = results.to_dict()
        print(f"\nResults can be exported as dictionary with {len(results_dict)} fields")

        print("\n" + "=" * 80)
        print("TEST COMPLETED SUCCESSFULLY")
        print("=" * 80)

        return 0

    except Exception as e:
        print(f"\n✗ Error during backtest: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
