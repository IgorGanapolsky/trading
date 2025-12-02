#!/usr/bin/env python3
"""
Backtest Example - Full Integration with CoreStrategy

This example demonstrates how to run a complete backtest using the
CoreStrategy and BacktestEngine.

Usage:
    python examples/backtest_example.py
"""

import logging
import sys
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, "/Users/igorganapolsky/workspace/git/apps/trading")

from src.backtesting.backtest_engine import BacktestEngine
from src.strategies.core_strategy import CoreStrategy


def run_backtest(
    start_date: str,
    end_date: str,
    daily_allocation: float = 6.0,
    initial_capital: float = 100000.0,
):
    """
    Run a backtest with the specified parameters.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        daily_allocation: Daily investment amount
        initial_capital: Starting capital

    Returns:
        BacktestResults object
    """
    print("\n" + "=" * 80)
    print("BACKTESTING CORE STRATEGY")
    print("=" * 80)
    print(f"Period: {start_date} to {end_date}")
    print(f"Daily Allocation: ${daily_allocation}")
    print(f"Initial Capital: ${initial_capital:,.2f}")

    # Create strategy (disable sentiment for faster testing)
    print("\n1. Initializing CoreStrategy...")
    strategy = CoreStrategy(
        daily_allocation=daily_allocation,
        etf_universe=["SPY", "QQQ", "VOO"],
        stop_loss_pct=0.05,
        use_sentiment=False,  # Disable for faster backtesting
    )
    print("   ✓ Strategy initialized")

    # Create backtest engine
    print("\n2. Creating BacktestEngine...")
    engine = BacktestEngine(
        strategy=strategy,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
    )
    print("   ✓ Engine created")

    # Run backtest
    print("\n3. Running backtest (this may take a few minutes)...")
    results = engine.run()
    print("   ✓ Backtest complete")

    return results


def main():
    """Main execution."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Calculate 60-day backtest period
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)  # ~60 trading days

    # Run backtest
    try:
        results = run_backtest(
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            daily_allocation=6.0,
            initial_capital=100000.0,
        )

        # Display comprehensive report
        print("\n" + "=" * 80)
        print("BACKTEST REPORT")
        print("=" * 80)
        print(results.generate_report())

        # Additional analysis
        print("\n" + "=" * 80)
        print("DETAILED ANALYSIS")
        print("=" * 80)

        # Performance rating
        rating = results.to_dict()["performance_rating"]
        print(f"\nPerformance Rating: {rating}")

        # Go/No-Go decision
        print("\n" + "=" * 80)
        print("GO/NO-GO DECISION FOR LIVE TRADING")
        print("=" * 80)

        checks = {
            "Total Return > 5%": results.total_return > 5.0,
            "Sharpe Ratio > 1.0": results.sharpe_ratio > 1.0,
            "Max Drawdown < 10%": results.max_drawdown < 10.0,
            "Win Rate > 55%": results.win_rate > 55.0,
            "Sufficient Trades": results.total_trades > 30,
        }

        all_passed = True
        for check, passed in checks.items():
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"{status}: {check}")
            if not passed:
                all_passed = False

        print("\n" + "-" * 80)
        if all_passed:
            print("✓ RECOMMENDATION: Strategy is ready for paper trading")
        else:
            print("✗ RECOMMENDATION: Strategy needs improvement before going live")
            print("   Consider tuning parameters and re-running backtest")

        print("\n" + "=" * 80)
        print("NEXT STEPS")
        print("=" * 80)
        if all_passed:
            print("1. Deploy to paper trading environment")
            print("2. Monitor for 30+ days")
            print("3. Validate real-time performance matches backtest")
            print("4. If paper trading successful → consider live trading")
        else:
            print("1. Analyze losing trades")
            print("2. Tune strategy parameters")
            print("3. Re-run backtest")
            print("4. Repeat until success criteria met")

        return 0

    except Exception as e:
        print(f"\n✗ Backtest failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
