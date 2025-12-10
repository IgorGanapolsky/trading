#!/usr/bin/env python3
"""
Core Strategy Backtest Runner

This script runs the canonical backtest for the core momentum strategy
and generates the $100/day target evaluation report.

Use this for:
- CI validation of strategy changes
- Generating baseline metrics
- Tracking progress toward $100/day goal

Usage:
    python scripts/run_core_backtest.py
    python scripts/run_core_backtest.py --period 90
    python scripts/run_core_backtest.py --save-reference

Author: Trading System
Created: 2025-12-03
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def run_backtest(
    period_days: int = 60,
    initial_capital: float = 10000.0,
    save_reference: bool = False,
) -> dict:
    """
    Run the core strategy backtest with target evaluation.

    Args:
        period_days: Number of days to backtest
        initial_capital: Starting capital
        save_reference: If True, save as reference backtest

    Returns:
        Dict with backtest results and target evaluation
    """
    try:
        from src.backtesting.backtest_engine import BacktestEngine
        from src.backtesting.target_integration import (
            BacktestTargetValidator,
            evaluate_backtest_with_target,
            save_target_evaluation,
        )
        from src.strategies.core_strategy import CoreStrategy
        from src.strategies.registry import StrategyMetrics, get_registry, initialize_registry
    except ImportError as e:
        logger.error(f"Import error: {e}")
        logger.info("Some dependencies may be missing. Running in minimal mode.")
        return {"error": str(e)}

    # Calculate dates
    end_date = datetime.now() - timedelta(days=1)  # Yesterday
    start_date = end_date - timedelta(days=period_days)

    logger.info("=" * 60)
    logger.info("CORE STRATEGY BACKTEST")
    logger.info("=" * 60)
    logger.info(f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    logger.info(f"Initial Capital: ${initial_capital:,.2f}")
    logger.info("")

    # Create strategy
    strategy = CoreStrategy(
        daily_allocation=10.0,
        use_sentiment=False,  # Disable for faster backtest
    )

    # Create and run backtest engine
    engine = BacktestEngine(
        strategy=strategy,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        initial_capital=initial_capital,
        enable_slippage=True,
    )

    try:
        results = engine.run()
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        return {"error": str(e)}

    # Generate standard report
    logger.info("")
    print(results.generate_report())

    # Evaluate against $100/day target
    target_report = evaluate_backtest_with_target(results, target_daily=100.0)

    # Print target section
    print(target_report.generate_report_section())

    # Validate for CI
    validator = BacktestTargetValidator()
    passed, failures = validator.validate(results)

    print("")
    print("=" * 60)
    print("CI VALIDATION")
    print("=" * 60)
    if passed:
        print("✅ PASSED - All metrics within acceptable range")
    else:
        print("❌ FAILED - Issues found:")
        for f in failures:
            print(f"  - {f}")
    print("")

    # Save results
    output_dir = Path("data/backtest_results")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save target evaluation
    save_target_evaluation(
        results,
        filepath=output_dir / "core_momentum_target_eval.json",
        target_daily=100.0,
    )

    # Save full results
    result_data = {
        "timestamp": datetime.now().isoformat(),
        "strategy": "core_momentum",
        "period": {
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d"),
            "days": period_days,
        },
        "results": {
            "total_return_pct": results.total_return,
            "sharpe_ratio": results.sharpe_ratio,
            "max_drawdown_pct": results.max_drawdown,
            "win_rate": results.win_rate,
            "total_trades": results.total_trades,
            "final_capital": results.final_capital,
        },
        "target_evaluation": target_report.to_dict(),
        "validation": {
            "passed": passed,
            "failures": failures,
        },
    }

    with open(output_dir / "core_momentum_latest.json", "w") as f:
        json.dump(result_data, f, indent=2)

    logger.info(f"Results saved to {output_dir}/core_momentum_latest.json")

    # If saving reference backtest
    if save_reference:
        reference_file = output_dir / "core_momentum_reference.json"
        with open(reference_file, "w") as f:
            json.dump(result_data, f, indent=2)
        logger.info(f"Reference backtest saved to {reference_file}")

        # Also save equity curve as CSV
        import pandas as pd

        equity_df = pd.DataFrame(
            {
                "date": results.dates,
                "equity": results.equity_curve,
            }
        )
        equity_df.to_csv(output_dir / "core_momentum_reference_equity.csv", index=False)
        logger.info("Reference equity curve saved as CSV")

        # Update strategy registry
        try:
            initialize_registry()
            registry = get_registry()
            registry.update_metrics(
                "core_momentum",
                StrategyMetrics(
                    sharpe_ratio=results.sharpe_ratio,
                    max_drawdown=results.max_drawdown,
                    win_rate=results.win_rate,
                    avg_daily_pnl=target_report.target_metrics.average_daily_pnl,
                    total_return_pct=results.total_return,
                    total_trades=results.total_trades,
                    backtest_date=datetime.now().strftime("%Y-%m-%d"),
                    backtest_period=f"{period_days} days",
                    hit_rate_100_day=target_report.target_metrics.pct_days_hit_target,
                ),
            )
            logger.info("Strategy registry updated with latest metrics")
        except Exception as e:
            logger.warning(f"Could not update registry: {e}")

    return result_data


def compare_to_reference(current_results: dict) -> dict:
    """Compare current results to reference backtest."""
    reference_file = Path("data/backtest_results/core_momentum_reference.json")

    if not reference_file.exists():
        return {"comparison": "No reference backtest found"}

    with open(reference_file) as f:
        reference = json.load(f)

    current = current_results.get("results", {})
    ref = reference.get("results", {})

    comparison = {
        "sharpe_diff": current.get("sharpe_ratio", 0) - ref.get("sharpe_ratio", 0),
        "win_rate_diff": current.get("win_rate", 0) - ref.get("win_rate", 0),
        "max_dd_diff": current.get("max_drawdown_pct", 0) - ref.get("max_drawdown_pct", 0),
        "return_diff": current.get("total_return_pct", 0) - ref.get("total_return_pct", 0),
    }

    print("")
    print("=" * 60)
    print("COMPARISON TO REFERENCE BACKTEST")
    print("=" * 60)
    print(f"  Sharpe Ratio:  {comparison['sharpe_diff']:+.2f}")
    print(f"  Win Rate:      {comparison['win_rate_diff']:+.1f}%")
    print(f"  Max Drawdown:  {comparison['max_dd_diff']:+.1f}%")
    print(f"  Total Return:  {comparison['return_diff']:+.2f}%")
    print("")

    if comparison["sharpe_diff"] < -0.1 or comparison["win_rate_diff"] < -2:
        print("⚠️  WARNING: Metrics have degraded from reference!")
    elif comparison["sharpe_diff"] > 0.1:
        print("✅ IMPROVEMENT: Metrics improved from reference!")
    else:
        print("➡️  STABLE: Metrics within expected range")

    return comparison


def main():
    parser = argparse.ArgumentParser(description="Run core strategy backtest")
    parser.add_argument(
        "--period",
        type=int,
        default=60,
        help="Backtest period in days (default: 60)",
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=10000.0,
        help="Initial capital (default: 10000)",
    )
    parser.add_argument(
        "--save-reference",
        action="store_true",
        help="Save as reference backtest",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Compare results to reference backtest",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="Run in CI mode (exit 1 on failure)",
    )

    args = parser.parse_args()

    results = run_backtest(
        period_days=args.period,
        initial_capital=args.capital,
        save_reference=args.save_reference,
    )

    if "error" in results:
        logger.error(f"Backtest failed: {results['error']}")
        sys.exit(1)

    if args.compare:
        compare_to_reference(results)

    if args.ci:
        if not results.get("validation", {}).get("passed", False):
            logger.error("CI validation failed")
            sys.exit(1)
        logger.info("CI validation passed")
        sys.exit(0)


if __name__ == "__main__":
    main()
