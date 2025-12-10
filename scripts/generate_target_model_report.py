#!/usr/bin/env python3
"""
Generate Target Model Report with Current Progress

This script generates a comprehensive report showing:
1. What's required to hit $100/day target
2. Current actual performance
3. Progress toward target
4. Gap analysis and recommendations

Author: Trading System
Created: 2025-12-03
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from analytics.target_model import generate_target_model_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def load_system_state() -> dict:
    """Load current system state."""
    state_file = Path("data/system_state.json")
    if state_file.exists():
        try:
            with open(state_file) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load system state: {e}")
    return {}


def load_recent_backtests() -> dict:
    """Load most recent backtest results."""
    backtest_dir = Path("data/backtests")
    if not backtest_dir.exists():
        return {}

    # Find most recent backtest file
    backtest_files = sorted(
        backtest_dir.glob("**/*_backtest.json"), key=lambda p: p.stat().st_mtime, reverse=True
    )

    if not backtest_files:
        return {}

    try:
        with open(backtest_files[0]) as f:
            data = json.load(f)
            data["backtest_file"] = str(backtest_files[0])
            return data
    except Exception as e:
        logger.error(f"Failed to load backtest: {e}")
        return {}


def calculate_actual_metrics(state: dict, backtest: dict) -> dict:
    """Calculate actual performance metrics from system state and backtests."""
    metrics = {
        "actual_daily_pnl": 0.0,
        "actual_win_rate": 0.0,
        "actual_sharpe": 0.0,
        "actual_trades_per_day": 0.0,
        "days_measured": 0,
    }

    # Try to get from backtest first (more accurate)
    if backtest:
        metrics["actual_sharpe"] = backtest.get("sharpe_ratio", 0.0)
        metrics["actual_win_rate"] = backtest.get("win_rate", 0.0) / 100.0  # Convert to 0-1

        # Calculate daily P&L from backtest
        total_return = backtest.get("total_return", 0.0)
        initial_capital = backtest.get("initial_capital", 100000.0)
        trading_days = backtest.get("trading_days", 1)

        if trading_days > 0:
            total_profit = (total_return / 100.0) * initial_capital
            metrics["actual_daily_pnl"] = total_profit / trading_days
            metrics["days_measured"] = trading_days

        total_trades = backtest.get("total_trades", 0)
        if trading_days > 0:
            metrics["actual_trades_per_day"] = total_trades / trading_days

    # Fall back to system state if no backtest
    elif state:
        # This would need actual implementation based on system_state.json structure
        # For now, use placeholder logic
        metrics["days_measured"] = 30  # Placeholder

    return metrics


def generate_full_report(
    target_daily_income: float = 100.0,
    available_capital: float = 100000.0,
    include_progress: bool = True,
) -> str:
    """Generate complete target model report with progress."""
    lines = []

    # Load actual data
    state = load_system_state()
    backtest = load_recent_backtests()

    # Calculate actual metrics
    if include_progress and (state or backtest):
        metrics = calculate_actual_metrics(state, backtest)

        # Generate report with progress
        report = generate_target_model_report(
            target_daily_income=target_daily_income,
            available_capital=available_capital,
            actual_daily_pnl=metrics["actual_daily_pnl"],
            actual_win_rate=metrics["actual_win_rate"],
            actual_sharpe=metrics["actual_sharpe"],
            actual_trades_per_day=metrics["actual_trades_per_day"],
            days_measured=metrics["days_measured"],
        )

        lines.append(report)

        # Add data sources
        lines.append("")
        lines.append("=" * 80)
        lines.append("DATA SOURCES")
        lines.append("=" * 80)
        if backtest:
            lines.append(f"Backtest: {backtest.get('backtest_file', 'N/A')}")
            lines.append(
                f"  Period: {backtest.get('start_date', 'N/A')} to {backtest.get('end_date', 'N/A')}"
            )
            lines.append(f"  Trading Days: {backtest.get('trading_days', 0)}")
        if state:
            lines.append("System State: data/system_state.json")
            lines.append(f"  Last Updated: {state.get('last_updated', 'N/A')}")
        lines.append("=" * 80)
    else:
        # Just target model without progress
        report = generate_target_model_report(
            target_daily_income=target_daily_income,
            available_capital=available_capital,
        )
        lines.append(report)

    return "\n".join(lines)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate $100/day target model report with progress tracking"
    )
    parser.add_argument(
        "--target", type=float, default=100.0, help="Target daily net income (default: $100)"
    )
    parser.add_argument(
        "--capital", type=float, default=100000.0, help="Available capital (default: $100,000)"
    )
    parser.add_argument(
        "--no-progress", action="store_true", help="Skip progress tracking, just show requirements"
    )
    parser.add_argument("--output", type=Path, help="Save report to file")

    args = parser.parse_args()

    # Generate report
    report = generate_full_report(
        target_daily_income=args.target,
        available_capital=args.capital,
        include_progress=not args.no_progress,
    )

    # Print to console
    print(report)

    # Save to file if requested
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            f.write(report)
        print(f"\nReport saved to: {args.output}")


if __name__ == "__main__":
    main()
