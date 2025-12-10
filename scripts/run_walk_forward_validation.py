#!/usr/bin/env python3
"""
Walk-Forward Validation Runner

Runs comprehensive 3+ year walk-forward validation to test if the strategy
has a real edge on out-of-sample data. This is the gold standard for
detecting overfitting and ensuring strategy robustness.

Usage:
    python scripts/run_walk_forward_validation.py
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtesting.walk_forward_matrix import (
    BacktestMatrixResults,
    WalkForwardMatrixValidator,
)
from src.strategies.core_strategy import CoreStrategy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def calculate_confidence_intervals(
    values: list[float], confidence: float = 0.95
) -> tuple[float, float]:
    """Calculate confidence intervals for a metric."""
    if not values or len(values) < 2:
        return 0.0, 0.0

    mean = np.mean(values)
    std = np.std(values, ddof=1)
    n = len(values)

    # t-statistic for 95% CI
    from scipy import stats

    t_stat = stats.t.ppf((1 + confidence) / 2, n - 1)
    margin = t_stat * (std / np.sqrt(n))

    return mean - margin, mean + margin


def generate_comprehensive_report(results: BacktestMatrixResults) -> str:
    """Generate comprehensive walk-forward validation report."""
    report = []

    report.append("=" * 80)
    report.append("WALK-FORWARD VALIDATION REPORT")
    report.append("3+ Year Out-of-Sample Performance Analysis")
    report.append("=" * 80)

    # Configuration
    report.append("\n📊 VALIDATION CONFIGURATION")
    report.append(f"   Strategy: {results.strategy_name}")
    report.append(f"   Evaluation Date: {results.evaluation_date[:10]}")
    report.append(f"   Total Windows: {results.total_windows}")
    report.append("   Train Window: 252 trading days (~1 year)")
    report.append("   Test Window: 63 trading days (~1 quarter)")
    report.append("   Step Size: 21 trading days (~1 month)")

    # Key Metrics
    report.append("\n📈 OUT-OF-SAMPLE PERFORMANCE (THE TRUTH)")
    report.append(f"   Mean OOS Sharpe Ratio: {results.mean_oos_sharpe:.2f}")
    report.append(f"   Std OOS Sharpe: ±{results.std_oos_sharpe:.2f}")

    # Calculate 95% confidence intervals
    if results.windows:
        sharpe_values = [w.oos_sharpe for w in results.windows]
        return_values = [w.oos_return for w in results.windows]
        win_rate_values = [w.oos_win_rate for w in results.windows]

        sharpe_ci_low, sharpe_ci_high = calculate_confidence_intervals(sharpe_values)
        return_ci_low, return_ci_high = calculate_confidence_intervals(return_values)
        win_ci_low, win_ci_high = calculate_confidence_intervals(win_rate_values)

        report.append(f"   95% CI Sharpe: [{sharpe_ci_low:.2f}, {sharpe_ci_high:.2f}]")
        report.append(f"   Mean OOS Return: {results.mean_oos_return:.2f}%")
        report.append(f"   95% CI Return: [{return_ci_low:.2f}%, {return_ci_high:.2f}%]")
        report.append(f"   Mean OOS Win Rate: {results.mean_oos_win_rate:.1f}%")
        report.append(f"   95% CI Win Rate: [{win_ci_low:.1f}%, {win_ci_high:.1f}%]")
    else:
        report.append(f"   Mean OOS Return: {results.mean_oos_return:.2f}%")
        report.append(f"   Mean OOS Win Rate: {results.mean_oos_win_rate:.1f}%")

    report.append(f"   Mean OOS Max Drawdown: {results.mean_oos_max_drawdown:.2f}%")

    # Robustness Metrics
    report.append("\n🛡️  ROBUSTNESS ANALYSIS")
    report.append(
        f"   Sharpe Consistency: {results.sharpe_consistency:.1%} "
        f"({int(results.sharpe_consistency * results.total_windows)}/{results.total_windows} windows positive)"
    )
    report.append(
        f"   Return Consistency: {results.return_consistency:.1%} "
        f"({int(results.return_consistency * results.total_windows)}/{results.total_windows} windows profitable)"
    )

    # Overfitting Detection
    report.append("\n🔍 OVERFITTING ANALYSIS")
    report.append(f"   Avg Sharpe Decay (IS → OOS): {results.avg_sharpe_decay:.2f}")
    report.append(f"   Overfitting Score: {results.overfitting_score:.2f} / 1.0")

    if results.overfitting_score < 0.3:
        report.append("   ✅ LOW overfitting - strategy generalizes well")
    elif results.overfitting_score < 0.6:
        report.append("   ⚠️  MODERATE overfitting - review parameters")
    else:
        report.append("   ❌ HIGH overfitting - strategy likely curve-fit")

    # Regime Performance
    if results.regime_performance:
        report.append("\n🌍 REGIME PERFORMANCE BREAKDOWN")
        for regime, metrics in results.regime_performance.items():
            report.append(f"\n   {regime.upper().replace('_', ' ')}:")
            report.append(f"     Windows: {metrics['count']}")
            report.append(f"     Mean Sharpe: {metrics['mean_sharpe']:.2f}")
            report.append(f"     Mean Return: {metrics['mean_return']:.2f}%")
            report.append(f"     Mean Drawdown: {metrics['mean_drawdown']:.2f}%")
            report.append(f"     Mean Win Rate: {metrics['mean_win_rate']:.1f}%")

    # Validation Results
    report.append("\n✅ VALIDATION STATUS")
    if results.passed_validation:
        report.append("   ✅ PASSED - Strategy meets validation criteria")
    else:
        report.append("   ❌ FAILED - Strategy does not meet validation criteria")

    for msg in results.validation_messages:
        icon = "   ✅" if msg.startswith("PASS") else "   ❌" if msg.startswith("FAIL") else "   ⚠️ "
        report.append(f"{icon} {msg}")

    # Window Details
    report.append("\n📋 FOLD-BY-FOLD PERFORMANCE")
    report.append(
        f"{'Fold':<6} {'Train Period':<30} {'Test Period':<30} {'OOS Sharpe':<12} {'OOS Return':<12} {'Regime':<20}"
    )
    report.append("-" * 120)

    for window in results.windows:
        train_period = f"{window.train_start} to {window.train_end}"
        test_period = f"{window.test_start} to {window.test_end}"
        fold_num = f"#{window.window_id}"
        sharpe_str = f"{window.oos_sharpe:.2f}"
        return_str = f"{window.oos_return:.2f}%"
        regime_str = window.regime.replace("_", " ").title()

        report.append(
            f"{fold_num:<6} {train_period:<30} {test_period:<30} {sharpe_str:<12} {return_str:<12} {regime_str:<20}"
        )

    # Final Verdict
    report.append("\n" + "=" * 80)
    report.append("FINAL VERDICT: DOES THE STRATEGY HAVE A REAL EDGE?")
    report.append("=" * 80)

    if results.passed_validation:
        report.append("✅ YES - Strategy shows consistent out-of-sample edge")
        report.append(f"   • {results.sharpe_consistency:.0%} of test periods had positive Sharpe")
        report.append(
            f"   • Mean OOS Sharpe {results.mean_oos_sharpe:.2f} exceeds minimum threshold"
        )
        report.append(f"   • Overfitting score {results.overfitting_score:.2f} is acceptable")
        report.append("\n   RECOMMENDATION: Deploy with confidence")
    else:
        report.append("❌ NO - Strategy lacks robust out-of-sample edge")
        failures = []

        if results.mean_oos_sharpe < 0.8:
            failures.append(f"Mean OOS Sharpe {results.mean_oos_sharpe:.2f} < 0.8")
        if results.avg_sharpe_decay > 0.5:
            failures.append(f"Sharpe decay {results.avg_sharpe_decay:.2f} > 0.5 (overfitting)")
        if results.mean_oos_max_drawdown > 15:
            failures.append(f"Mean drawdown {results.mean_oos_max_drawdown:.1f}% > 15%")
        if results.sharpe_consistency < 0.6:
            failures.append(f"Only {results.sharpe_consistency:.0%} of windows were profitable")

        for failure in failures:
            report.append(f"   • {failure}")

        report.append("\n   RECOMMENDATION: DO NOT deploy - refine strategy first")

    report.append("=" * 80)

    return "\n".join(report)


def main():
    """Run comprehensive walk-forward validation."""
    print("\n" + "=" * 80)
    print("WALK-FORWARD VALIDATION - 3+ YEAR BACKTEST")
    print("Testing Core Strategy on Out-of-Sample Data")
    print("=" * 80 + "\n")

    # Configuration
    START_DATE = "2022-01-01"  # 3 years of data
    END_DATE = "2025-12-04"  # Current date
    INITIAL_CAPITAL = 100000.0

    # Strategy parameters
    strategy_params = {
        "daily_allocation": 10.0,  # $10/day as per current R&D phase
    }

    # Create validator with proper windows
    # 252 trading days = ~1 year train
    # 63 trading days = ~1 quarter test
    # 21 trading days = ~1 month step
    validator = WalkForwardMatrixValidator(
        train_window_days=252,
        test_window_days=63,
        step_days=21,
    )

    logger.info("Starting walk-forward validation...")
    logger.info(f"Period: {START_DATE} to {END_DATE}")
    logger.info("Train window: 252 days (~1 year)")
    logger.info("Test window: 63 days (~1 quarter)")
    logger.info("Expected folds: ~10+")

    try:
        # Run validation
        results = validator.run_matrix_evaluation(
            strategy_class=CoreStrategy,
            strategy_params=strategy_params,
            start_date=START_DATE,
            end_date=END_DATE,
            initial_capital=INITIAL_CAPITAL,
        )

        # Generate report
        report = generate_comprehensive_report(results)
        print("\n" + report)

        # Save results
        output_dir = Path("data/backtests/walk_forward_results")
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save JSON results
        json_path = output_dir / f"walk_forward_results_{timestamp}.json"
        results.save(json_path)
        logger.info(f"Results saved to {json_path}")

        # Save report
        report_path = output_dir / f"walk_forward_report_{timestamp}.txt"
        with open(report_path, "w") as f:
            f.write(report)
        logger.info(f"Report saved to {report_path}")

        # Save latest symlinks
        latest_json = output_dir / "latest_results.json"
        latest_report = output_dir / "latest_report.txt"

        if latest_json.exists():
            latest_json.unlink()
        if latest_report.exists():
            latest_report.unlink()

        os.symlink(json_path.name, latest_json)
        os.symlink(report_path.name, latest_report)

        print("\n✅ Results saved to:")
        print(f"   • {json_path}")
        print(f"   • {report_path}")
        print(f"   • {latest_json} (latest)")
        print(f"   • {latest_report} (latest)")

        # Return exit code based on validation
        sys.exit(0 if results.passed_validation else 1)

    except Exception as e:
        logger.error(f"Walk-forward validation failed: {e}", exc_info=True)
        print(f"\n❌ Validation failed with error: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
