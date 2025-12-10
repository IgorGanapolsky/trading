#!/usr/bin/env python3
"""
5-Year Walk-Forward Validation Script

Runs comprehensive 5-year rolling walk-forward validation to detect if the strategy
has a real edge on unseen out-of-sample data. This is the gold standard validation
before deploying capital to any strategy.

The validation uses:
- 252-day (1 year) training windows
- 63-day (1 quarter) test windows
- Rolling forward by 63 days
- Multiple market regimes (2019-2024 includes COVID crash, bull run, etc.)

Usage:
    python scripts/run_5year_validation.py --start 2019-01-01 --end 2024-12-31
    python scripts/run_5year_validation.py --symbols SPY QQQ IWM  # Custom symbols
    python scripts/run_5year_validation.py --quick  # Fast test (fewer windows)

Author: Trading System
Created: 2025-12-09
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

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


def download_historical_data(
    symbols: list[str],
    start_date: str,
    end_date: str,
    cache_dir: Path = Path("data/cache/historical"),
) -> dict[str, pd.DataFrame]:
    """
    Download historical data for multiple symbols with caching.

    Args:
        symbols: List of ticker symbols
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        cache_dir: Directory for caching data

    Returns:
        Dictionary mapping symbols to DataFrames
    """
    import yfinance as yf

    cache_dir.mkdir(parents=True, exist_ok=True)
    data_dict = {}

    logger.info(f"Downloading historical data for {len(symbols)} symbols...")

    for symbol in symbols:
        # Check cache first
        cache_file = cache_dir / f"{symbol}_{start_date}_{end_date}.pkl"

        if cache_file.exists():
            logger.info(f"Loading {symbol} from cache")
            try:
                data_dict[symbol] = pd.read_pickle(cache_file)  # noqa: S301
                continue
            except Exception as e:
                logger.warning(f"Cache read failed for {symbol}: {e}")

        # Download from yfinance
        logger.info(f"Downloading {symbol} data...")
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date)

            if df.empty:
                logger.warning(f"No data returned for {symbol}")
                continue

            # Ensure we have required columns
            required_cols = ["Open", "High", "Low", "Close", "Volume"]
            if not all(col in df.columns for col in required_cols):
                logger.warning(f"Missing required columns for {symbol}")
                continue

            # Cache the data
            df.to_pickle(cache_file)
            data_dict[symbol] = df

            logger.info(f"Downloaded {len(df)} days of data for {symbol}")

        except Exception as e:
            logger.error(f"Failed to download {symbol}: {e}")
            continue

    return data_dict


def calculate_confidence_interval(
    values: list[float], confidence: float = 0.95
) -> tuple[float, float]:
    """Calculate confidence interval for a list of values."""
    if not values or len(values) < 2:
        return 0.0, 0.0

    mean = np.mean(values)
    std = np.std(values, ddof=1)
    n = len(values)

    # Use t-distribution for small samples
    try:
        from scipy import stats

        t_stat = stats.t.ppf((1 + confidence) / 2, n - 1)
    except ImportError:
        # Fallback to z-score if scipy not available
        t_stat = 1.96  # ~95% CI

    margin = t_stat * (std / np.sqrt(n))
    return mean - margin, mean + margin


def generate_comprehensive_report(
    results: BacktestMatrixResults,
    symbols: list[str],
    duration_minutes: float,
) -> str:
    """Generate detailed walk-forward validation report."""
    report = []

    report.append("=" * 100)
    report.append("5-YEAR WALK-FORWARD VALIDATION REPORT")
    report.append("Out-of-Sample Performance Analysis (The Truth)")
    report.append("=" * 100)

    # Header info
    report.append(f"\n📅 Validation Date: {results.evaluation_date[:10]}")
    report.append(f"⏱️  Execution Time: {duration_minutes:.1f} minutes")
    report.append(f"📊 Strategy: {results.strategy_name}")
    report.append(f"💹 Symbols: {', '.join(symbols)}")

    # Configuration
    report.append("\n" + "=" * 100)
    report.append("VALIDATION CONFIGURATION")
    report.append("=" * 100)
    report.append("   Train Window: 252 trading days (~1 year)")
    report.append("   Test Window: 63 trading days (~1 quarter)")
    report.append("   Step Size: 63 trading days (~1 quarter)")
    report.append(f"   Total Folds: {results.total_windows}")
    report.append(
        f"   Total Coverage: ~{results.total_windows * 63 // 252:.1f} years of out-of-sample testing"
    )

    # Key Performance Metrics
    report.append("\n" + "=" * 100)
    report.append("📈 OUT-OF-SAMPLE PERFORMANCE (What Matters)")
    report.append("=" * 100)

    # Calculate confidence intervals
    if results.windows:
        sharpe_values = [w.oos_sharpe for w in results.windows]
        return_values = [w.oos_return for w in results.windows]
        drawdown_values = [w.oos_max_drawdown for w in results.windows]
        win_rate_values = [w.oos_win_rate for w in results.windows]

        sharpe_ci_low, sharpe_ci_high = calculate_confidence_interval(sharpe_values)
        return_ci_low, return_ci_high = calculate_confidence_interval(return_values)
        dd_ci_low, dd_ci_high = calculate_confidence_interval(drawdown_values)
        win_ci_low, win_ci_high = calculate_confidence_interval(win_rate_values)

        report.append("\n   Sharpe Ratio:")
        report.append(f"     Mean: {results.mean_oos_sharpe:.3f}")
        report.append(f"     Std Dev: ±{results.std_oos_sharpe:.3f}")
        report.append(f"     95% CI: [{sharpe_ci_low:.3f}, {sharpe_ci_high:.3f}]")
        report.append(f"     Min/Max: [{min(sharpe_values):.2f}, {max(sharpe_values):.2f}]")

        report.append("\n   Return per Quarter:")
        report.append(f"     Mean: {results.mean_oos_return:.2f}%")
        report.append(f"     95% CI: [{return_ci_low:.2f}%, {return_ci_high:.2f}%]")
        report.append(f"     Min/Max: [{min(return_values):.2f}%, {max(return_values):.2f}%]")

        report.append("\n   Maximum Drawdown:")
        report.append(f"     Mean: {results.mean_oos_max_drawdown:.2f}%")
        report.append(f"     95% CI: [{dd_ci_low:.2f}%, {dd_ci_high:.2f}%]")
        report.append(f"     Worst: {max(drawdown_values):.2f}%")

        report.append("\n   Win Rate:")
        report.append(f"     Mean: {results.mean_oos_win_rate:.1f}%")
        report.append(f"     95% CI: [{win_ci_low:.1f}%, {win_ci_high:.1f}%]")
        report.append(f"     Min/Max: [{min(win_rate_values):.1f}%, {max(win_rate_values):.1f}%]")

    # Robustness Metrics
    report.append("\n" + "=" * 100)
    report.append("🛡️  ROBUSTNESS ANALYSIS")
    report.append("=" * 100)

    positive_sharpe_count = int(results.sharpe_consistency * results.total_windows)
    positive_return_count = int(results.return_consistency * results.total_windows)

    report.append("\n   Consistency Metrics:")
    report.append(
        f"     Positive Sharpe: {results.sharpe_consistency:.1%} "
        f"({positive_sharpe_count}/{results.total_windows} quarters)"
    )
    report.append(
        f"     Positive Return: {results.return_consistency:.1%} "
        f"({positive_return_count}/{results.total_windows} quarters)"
    )

    # Overfitting Analysis
    report.append("\n" + "=" * 100)
    report.append("🔍 OVERFITTING DETECTION")
    report.append("=" * 100)
    report.append(f"\n   Overfitting Score: {results.overfitting_score:.3f} / 1.0")
    report.append(f"   Avg Sharpe Decay (IS → OOS): {results.avg_sharpe_decay:.3f}")

    if results.overfitting_score < 0.3:
        report.append("   ✅ LOW overfitting - strategy generalizes well to unseen data")
    elif results.overfitting_score < 0.6:
        report.append("   ⚠️  MODERATE overfitting - review parameters and features")
    else:
        report.append("   ❌ HIGH overfitting - strategy is likely curve-fit to historical data")

    # Regime Breakdown
    if results.regime_performance:
        report.append("\n" + "=" * 100)
        report.append("🌍 PERFORMANCE BY MARKET REGIME")
        report.append("=" * 100)

        for regime, metrics in sorted(results.regime_performance.items()):
            regime_name = regime.replace("_", " ").title()
            report.append(f"\n   {regime_name}:")
            report.append(f"     Quarters: {metrics['count']}")
            report.append(f"     Mean Sharpe: {metrics['mean_sharpe']:.2f}")
            report.append(f"     Mean Return: {metrics['mean_return']:.2f}%")
            report.append(f"     Mean Drawdown: {metrics['mean_drawdown']:.2f}%")
            report.append(f"     Mean Win Rate: {metrics['mean_win_rate']:.1f}%")

    # Validation Results
    report.append("\n" + "=" * 100)
    report.append("✅ VALIDATION STATUS")
    report.append("=" * 100)

    if results.passed_validation:
        report.append("\n   🎉 PASSED - Strategy meets validation criteria")
    else:
        report.append("\n   ❌ FAILED - Strategy does not meet validation criteria")

    report.append("\n   Detailed Results:")
    for msg in results.validation_messages:
        if msg.startswith("PASS"):
            icon = "   ✅"
        elif msg.startswith("FAIL"):
            icon = "   ❌"
        else:
            icon = "   ⚠️ "
        report.append(f"{icon} {msg}")

    # Fold-by-Fold Details
    report.append("\n" + "=" * 100)
    report.append("📋 FOLD-BY-FOLD PERFORMANCE")
    report.append("=" * 100)

    header = f"{'Fold':<6} {'Test Period':<30} {'OOS Sharpe':<12} {'OOS Return':<12} {'OOS DD':<12} {'Regime':<20}"
    report.append(f"\n{header}")
    report.append("-" * 100)

    for window in results.windows:
        test_period = f"{window.test_start} to {window.test_end}"
        fold_num = f"#{window.window_id}"
        regime_name = window.regime.replace("_", " ").title()

        line = (
            f"{fold_num:<6} {test_period:<30} "
            f"{window.oos_sharpe:<12.2f} "
            f"{window.oos_return:<12.2f}% "
            f"{window.oos_max_drawdown:<12.2f}% "
            f"{regime_name:<20}"
        )
        report.append(line)

    # Final Verdict
    report.append("\n" + "=" * 100)
    report.append("🎯 FINAL VERDICT: DOES THE STRATEGY HAVE A REAL EDGE?")
    report.append("=" * 100)

    if results.passed_validation:
        report.append("\n✅ YES - Strategy shows consistent out-of-sample edge\n")
        report.append(f"   • {results.sharpe_consistency:.0%} of test quarters had positive Sharpe")
        report.append(
            f"   • Mean OOS Sharpe {results.mean_oos_sharpe:.2f} exceeds minimum threshold"
        )
        report.append(f"   • Mean OOS return {results.mean_oos_return:.2f}% per quarter")
        report.append(f"   • Overfitting score {results.overfitting_score:.2f} is acceptable")
        report.append("\n   💡 RECOMMENDATION: Strategy is ready for live deployment")
        report.append("      Consider starting with small position sizes and monitoring closely")

    else:
        report.append("\n❌ NO - Strategy lacks robust out-of-sample edge\n")

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

        report.append("\n   💡 RECOMMENDATION: DO NOT deploy - refine strategy first")
        report.append("      Focus on:")
        if results.overfitting_score > 0.5:
            report.append("      - Reducing overfitting (simplify model, add regularization)")
        if results.mean_oos_sharpe < 0.8:
            report.append("      - Improving signal quality and feature engineering")
        if results.mean_oos_max_drawdown > 15:
            report.append("      - Better risk management and position sizing")

    report.append("\n" + "=" * 100)

    return "\n".join(report)


def main():
    """Run 5-year walk-forward validation."""
    parser = argparse.ArgumentParser(
        description="Run 5-year walk-forward validation on trading strategy"
    )
    parser.add_argument(
        "--start",
        type=str,
        default="2019-01-01",
        help="Start date (YYYY-MM-DD), default: 2019-01-01",
    )
    parser.add_argument(
        "--end",
        type=str,
        default="2024-12-31",
        help="End date (YYYY-MM-DD), default: 2024-12-31",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["SPY", "QQQ", "IWM", "VOO", "VTI"],
        help="Symbols to validate (default: SPY QQQ IWM VOO VTI)",
    )
    parser.add_argument(
        "--daily-allocation",
        type=float,
        default=10.0,
        help="Daily allocation in dollars (default: 10.0)",
    )
    parser.add_argument(
        "--initial-capital",
        type=float,
        default=100000.0,
        help="Initial capital (default: 100000.0)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick test mode (larger step size for faster validation)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="reports",
        help="Output directory for reports (default: reports)",
    )

    args = parser.parse_args()

    # Print header
    print("\n" + "=" * 100)
    print("5-YEAR WALK-FORWARD VALIDATION")
    print("Testing Core Strategy on Out-of-Sample Data")
    print("=" * 100)
    print(f"\n📅 Date Range: {args.start} to {args.end}")
    print(f"💹 Symbols: {', '.join(args.symbols)}")
    print(f"💰 Initial Capital: ${args.initial_capital:,.0f}")
    print(f"💵 Daily Allocation: ${args.daily_allocation:.2f}")
    if args.quick:
        print("⚡ Quick mode enabled (larger step size)")
    print()

    start_time = time.time()

    try:
        # Download historical data
        logger.info("Step 1/3: Downloading historical data...")
        data_dict = download_historical_data(args.symbols, args.start, args.end)

        if not data_dict:
            logger.error("No data available for validation")
            sys.exit(1)

        logger.info(f"Successfully downloaded data for {len(data_dict)} symbols")

        # Configure validator
        train_window = 252  # 1 year
        test_window = 63  # 1 quarter
        step = 126 if args.quick else 63  # 2 quarters or 1 quarter

        validator = WalkForwardMatrixValidator(
            train_window_days=train_window,
            test_window_days=test_window,
            step_days=step,
        )

        logger.info("Step 2/3: Running walk-forward validation...")
        logger.info(f"Configuration: train={train_window}d, test={test_window}d, step={step}d")

        # Estimate number of windows
        from datetime import datetime

        start_dt = datetime.strptime(args.start, "%Y-%m-%d")
        end_dt = datetime.strptime(args.end, "%Y-%m-%d")
        total_days = (end_dt - start_dt).days
        estimated_windows = max(1, (total_days - train_window - test_window) // step)

        logger.info(f"Expected windows: ~{estimated_windows}")
        logger.info(f"Estimated time: ~{estimated_windows * 2:.0f} minutes")

        # Run validation
        strategy_params = {
            "daily_allocation": args.daily_allocation,
        }

        results = validator.run_matrix_evaluation(
            strategy_class=CoreStrategy,
            strategy_params=strategy_params,
            start_date=args.start,
            end_date=args.end,
            initial_capital=args.initial_capital,
        )

        duration_minutes = (time.time() - start_time) / 60

        logger.info("Step 3/3: Generating report...")

        # Generate comprehensive report
        report = generate_comprehensive_report(results, args.symbols, duration_minutes)

        print("\n" + report)

        # Save results
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")

        # Save JSON results
        json_filename = f"walk_forward_5year_{timestamp}.json"
        json_path = output_dir / json_filename
        results.save(json_path)
        logger.info(f"Results saved to {json_path}")

        # Save report
        report_filename = f"walk_forward_5year_{timestamp}.txt"
        report_path = output_dir / report_filename
        with open(report_path, "w") as f:
            f.write(report)
        logger.info(f"Report saved to {report_path}")

        # Create summary file
        summary = {
            "validation_date": timestamp,
            "period": f"{args.start} to {args.end}",
            "symbols": args.symbols,
            "total_windows": results.total_windows,
            "mean_oos_sharpe": results.mean_oos_sharpe,
            "mean_oos_return": results.mean_oos_return,
            "sharpe_consistency": results.sharpe_consistency,
            "overfitting_score": results.overfitting_score,
            "passed_validation": results.passed_validation,
            "execution_time_minutes": duration_minutes,
        }

        summary_path = output_dir / f"walk_forward_5year_summary_{timestamp}.json"
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)

        print("\n📁 Files saved:")
        print(f"   • {json_path}")
        print(f"   • {report_path}")
        print(f"   • {summary_path}")
        print()

        # Exit code based on validation result
        if results.passed_validation:
            print("✅ Validation PASSED - Strategy is ready for deployment")
            sys.exit(0)
        else:
            print("❌ Validation FAILED - Strategy needs improvement")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Validation interrupted by user")
        sys.exit(130)

    except Exception as e:
        logger.error(f"Validation failed: {e}", exc_info=True)
        print(f"\n❌ Validation failed with error: {e}")
        print("Check logs for details")
        sys.exit(2)


if __name__ == "__main__":
    main()
