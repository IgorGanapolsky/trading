#!/usr/bin/env python3
"""
Simple test script for backtesting engine (without CoreStrategy dependencies)

This demonstrates the backtest engine with a mock strategy to avoid dependency issues.
"""

import logging
import sys

sys.path.insert(0, "/Users/igorganapolsky/workspace/git/apps/trading")

from src.backtesting.backtest_results import BacktestResults


# Mock simple strategy for testing
class MockStrategy:
    """Simple mock strategy for testing without complex dependencies."""

    def __init__(self, daily_allocation=6.0):
        self.daily_allocation = daily_allocation
        self.etf_universe = ["SPY", "QQQ", "VOO"]

    def _get_market_sentiment(self):
        return None  # Neutral


def test_backtest_results():
    """Test BacktestResults data structure."""
    print("\n" + "=" * 80)
    print("TEST 1: BacktestResults Data Structure")
    print("=" * 80)

    # Create sample results
    results = BacktestResults(
        trades=[
            {
                "date": "2025-09-01",
                "symbol": "SPY",
                "amount": 6.0,
                "price": 450.0,
            },
            {
                "date": "2025-09-02",
                "symbol": "QQQ",
                "amount": 6.0,
                "price": 380.0,
            },
        ],
        equity_curve=[100000, 100100, 100300],
        dates=["2025-09-01", "2025-09-02", "2025-09-03"],
        total_return=0.30,
        sharpe_ratio=1.5,
        max_drawdown=2.5,
        win_rate=60.0,
        total_trades=2,
        profitable_trades=1,
        average_trade_return=0.15,
        initial_capital=100000.0,
        final_capital=100300.0,
        start_date="2025-09-01",
        end_date="2025-09-03",
        trading_days=3,
    )

    # Test report generation
    report = results.generate_report()
    print("\nGenerated Report:")
    print(report)

    # Test dict conversion
    results_dict = results.to_dict()
    print(f"\nDict conversion successful: {len(results_dict)} fields")

    # Verify key metrics
    assert results.total_return == 0.30, "Total return mismatch"
    assert results.sharpe_ratio == 1.5, "Sharpe ratio mismatch"
    assert results.total_trades == 2, "Trade count mismatch"

    print("\n✓ BacktestResults test PASSED")
    return True


def test_backtest_engine_structure():
    """Test BacktestEngine structure without running full backtest."""
    print("\n" + "=" * 80)
    print("TEST 2: BacktestEngine Structure")
    print("=" * 80)

    # Import here to avoid circular dependency issues
    from src.backtesting.backtest_engine import BacktestEngine

    # Create mock strategy
    mock_strategy = MockStrategy(daily_allocation=6.0)

    # Create engine
    engine = BacktestEngine(
        strategy=mock_strategy,
        start_date="2025-09-01",
        end_date="2025-09-15",
        initial_capital=100000.0,
    )

    print("\n✓ Engine initialized successfully")
    print(f"  - Start date: {engine.start_date.strftime('%Y-%m-%d')}")
    print(f"  - End date: {engine.end_date.strftime('%Y-%m-%d')}")
    print(f"  - Initial capital: ${engine.initial_capital:,.2f}")
    print(f"  - Strategy: {type(engine.strategy).__name__}")
    print(f"  - ETF Universe: {engine.strategy.etf_universe}")

    # Test date range generation
    trading_dates = engine._get_trading_dates()
    print(f"\n✓ Trading dates generated: {len(trading_dates)} days")

    print("\n✓ BacktestEngine structure test PASSED")
    return True


def main():
    """Run all tests."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("\n" + "=" * 80)
    print("BACKTEST ENGINE - SIMPLE TEST SUITE")
    print("=" * 80)

    try:
        # Run tests
        test1_passed = test_backtest_results()
        test2_passed = test_backtest_engine_structure()

        # Summary
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"Test 1 (BacktestResults): {'✓ PASSED' if test1_passed else '✗ FAILED'}")
        print(f"Test 2 (BacktestEngine):  {'✓ PASSED' if test2_passed else '✗ FAILED'}")
        print("\n✓ ALL TESTS PASSED")
        print("=" * 80)

        print("\n" + "=" * 80)
        print("USAGE INSTRUCTIONS")
        print("=" * 80)
        print("\nTo run a full backtest with your CoreStrategy:")
        print("\n  from src.strategies.core_strategy import CoreStrategy")
        print("  from src.backtesting.backtest_engine import BacktestEngine")
        print("\n  strategy = CoreStrategy(daily_allocation=6.0, use_sentiment=False)")
        print("  engine = BacktestEngine(")
        print("      strategy=strategy,")
        print('      start_date="2025-09-01",')
        print('      end_date="2025-10-31",')
        print("      initial_capital=100000")
        print("  )")
        print("  results = engine.run()")
        print("  print(results.generate_report())")
        print("\n" + "=" * 80)

        return 0

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
