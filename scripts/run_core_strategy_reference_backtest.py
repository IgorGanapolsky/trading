#!/usr/bin/env python3
"""
Run Reference Backtest for Core Strategy

This script runs the reference backtest for the frozen core strategy
and compares metrics against baseline. Used in CI to validate changes.

Usage:
    python scripts/run_core_strategy_reference_backtest.py
    python scripts/run_core_strategy_reference_backtest.py --save-reference  # Save as new baseline
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.backtesting.backtest_engine import BacktestEngine
from src.strategies.core_strategy_frozen import CoreStrategyFrozen
from src.target_model import TargetModel, TargetModelConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REFERENCE_BACKTEST_DIR = Path(__file__).parent.parent / "data" / "reference_backtests"
REFERENCE_METRICS_FILE = REFERENCE_BACKTEST_DIR / "core_strategy_metrics.json"
REFERENCE_EQUITY_FILE = REFERENCE_BACKTEST_DIR / "core_strategy_equity.csv"


def run_reference_backtest() -> dict:
    """Run reference backtest for core strategy."""
    logger.info("Running reference backtest for Core Strategy...")

    # Initialize strategy
    strategy = CoreStrategyFrozen(daily_allocation=10.0)

    # Run backtest (1-2 years)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=730)  # ~2 years

    engine = BacktestEngine(
        strategy=strategy,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        initial_capital=100000.0,
        enable_slippage=True,
    )

    results = engine.run()

    # Extract metrics
    metrics = {
        "sharpe_ratio": results.sharpe_ratio,
        "avg_daily_pnl": results.avg_daily_pnl,
        "pct_days_above_target": results.pct_days_above_target,
        "max_drawdown": results.max_drawdown,
        "worst_5day_drawdown": results.worst_5day_drawdown,
        "worst_20day_drawdown": results.worst_20day_drawdown,
        "total_return": results.total_return,
        "win_rate": results.win_rate,
        "backtest_date": datetime.now().isoformat(),
        "start_date": results.start_date,
        "end_date": results.end_date,
        "trading_days": results.trading_days,
    }

    # Save equity curve
    REFERENCE_BACKTEST_DIR.mkdir(parents=True, exist_ok=True)
    import pandas as pd

    equity_df = pd.DataFrame(
        {
            "date": results.dates,
            "equity": results.equity_curve,
        }
    )
    equity_df.to_csv(REFERENCE_EQUITY_FILE, index=False)
    logger.info(f"Saved equity curve to {REFERENCE_EQUITY_FILE}")

    return metrics


def compare_with_baseline(new_metrics: dict) -> tuple[bool, list[str]]:
    """Compare new metrics with baseline."""
    if not REFERENCE_METRICS_FILE.exists():
        logger.warning("No baseline metrics found. This will be saved as new baseline.")
        return True, []

    with open(REFERENCE_METRICS_FILE) as f:
        baseline = json.load(f)

    is_valid, warnings = CoreStrategyFrozen.validate_metrics(new_metrics)

    # Generate diff report
    diff_report = []
    diff_report.append("METRIC COMPARISON:")
    diff_report.append("-" * 80)

    for key in ["sharpe_ratio", "avg_daily_pnl", "pct_days_above_target", "max_drawdown"]:
        baseline_val = baseline.get(key, 0)
        new_val = new_metrics.get(key, 0)
        change = new_val - baseline_val
        change_pct = (change / baseline_val * 100) if baseline_val != 0 else 0

        status = "✅" if change >= 0 or abs(change_pct) < 5 else "⚠️"
        diff_report.append(
            f"{status} {key}: {baseline_val:.2f} → {new_val:.2f} ({change:+.2f}, {change_pct:+.1f}%)"
        )

    diff_report.append("-" * 80)
    diff_report.append(f"Overall: {'✅ PASS' if is_valid else '❌ FAIL'}")

    return is_valid, warnings + diff_report


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run reference backtest for core strategy")
    parser.add_argument(
        "--save-reference", action="store_true", help="Save results as new baseline"
    )
    args = parser.parse_args()

    # Run backtest
    metrics = run_reference_backtest()

    # Compare with baseline
    is_valid, warnings = compare_with_baseline(metrics)

    # Print results
    print("\n" + "=" * 80)
    print("REFERENCE BACKTEST RESULTS")
    print("=" * 80)
    print()

    for warning in warnings:
        print(warning)

    print()
    print("METRICS:")
    for key, value in metrics.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")

    # Analyze vs $100/day target
    print()
    print("=" * 80)
    print("$100/DAY TARGET ANALYSIS")
    print("=" * 80)

    target_model = TargetModel(TargetModelConfig(capital=100000.0))
    analysis = target_model.analyze_backtest_vs_target(
        avg_daily_pnl=metrics["avg_daily_pnl"],
        pct_days_above_target=metrics["pct_days_above_target"],
        worst_5day_drawdown=metrics["worst_5day_drawdown"],
        worst_20day_drawdown=metrics["worst_20day_drawdown"],
        sharpe_ratio=metrics["sharpe_ratio"],
    )

    print(target_model.generate_target_report(analysis))

    # Save if requested
    if args.save_reference:
        REFERENCE_BACKTEST_DIR.mkdir(parents=True, exist_ok=True)
        with open(REFERENCE_METRICS_FILE, "w") as f:
            json.dump(metrics, f, indent=2)
        logger.info(f"Saved new baseline metrics to {REFERENCE_METRICS_FILE}")

    # Exit with error code if validation failed
    if not is_valid:
        print("\n❌ VALIDATION FAILED: Metrics degraded beyond tolerance.")
        print(
            "If this degradation is intentional, add 'ACCEPT_METRIC_DEGRADATION' to PR description."
        )
        sys.exit(1)
    else:
        print("\n✅ VALIDATION PASSED")


if __name__ == "__main__":
    main()
