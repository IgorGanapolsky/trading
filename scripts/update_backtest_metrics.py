#!/usr/bin/env python3
"""
Update Strategy Registry with Backtest Metrics

This script reads backtest results and updates the strategy registry,
enabling tracking of which strategies are performing well and should
be prioritized for deployment.

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

from strategies.strategy_registry import (
    BacktestMetrics,
    StrategyRegistry,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def load_backtest_result(backtest_file: Path) -> dict:
    """Load backtest result from JSON file."""
    try:
        with open(backtest_file) as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load backtest file {backtest_file}: {e}")
        return {}


def parse_backtest_to_metrics(backtest_data: dict) -> BacktestMetrics:
    """Convert backtest result to BacktestMetrics."""
    return BacktestMetrics(
        start_date=backtest_data.get("start_date", ""),
        end_date=backtest_data.get("end_date", ""),
        total_return_pct=backtest_data.get("total_return", 0.0),
        sharpe_ratio=backtest_data.get("sharpe_ratio", 0.0),
        max_drawdown_pct=backtest_data.get("max_drawdown", 0.0),
        win_rate_pct=backtest_data.get("win_rate", 0.0),
        avg_daily_pnl=backtest_data.get("avg_daily_pnl", 0.0),
        total_trades=backtest_data.get("total_trades", 0),
    )


def update_strategy_from_backtest(
    strategy_id: str, backtest_file: Path, registry: StrategyRegistry
) -> bool:
    """Update strategy registry with backtest results."""
    # Load backtest
    backtest_data = load_backtest_result(backtest_file)
    if not backtest_data:
        return False

    # Convert to metrics
    metrics = parse_backtest_to_metrics(backtest_data)

    # Update registry
    success = registry.update_backtest_metrics(strategy_id, metrics)

    if success:
        logger.info(f"Updated {strategy_id} with backtest results:")
        logger.info(f"  Sharpe: {metrics.sharpe_ratio:.2f}")
        logger.info(f"  Win Rate: {metrics.win_rate_pct:.1f}%")
        logger.info(f"  Daily P&L: ${metrics.avg_daily_pnl:.2f}")
        logger.info(f"  Max Drawdown: {metrics.max_drawdown_pct:.1f}%")

    return success


def scan_and_update_all_backtests(backtest_dir: Path = Path("data/backtests")) -> int:
    """Scan backtest directory and update all strategies."""
    if not backtest_dir.exists():
        logger.error(f"Backtest directory not found: {backtest_dir}")
        return 0

    registry = StrategyRegistry()
    updated_count = 0

    # Find all backtest JSON files
    backtest_files = list(backtest_dir.glob("**/*_backtest.json"))

    logger.info(f"Found {len(backtest_files)} backtest files")

    for backtest_file in backtest_files:
        # Try to infer strategy ID from filename
        # Format: <strategy_id>_backtest.json or <strategy_id>_YYYY-MM-DD_backtest.json
        filename = backtest_file.stem

        # Remove _backtest suffix
        if filename.endswith("_backtest"):
            filename = filename[:-9]

        # Remove date suffix if present
        parts = filename.split("_")
        if len(parts) > 1 and parts[-1].replace("-", "").isdigit():
            strategy_id = "_".join(parts[:-1])
        else:
            strategy_id = filename

        # Check if strategy exists in registry
        if strategy_id in registry.strategies:
            logger.info(f"Updating {strategy_id} from {backtest_file.name}")
            if update_strategy_from_backtest(strategy_id, backtest_file, registry):
                updated_count += 1
        else:
            logger.warning(f"Strategy {strategy_id} not in registry, skipping")

    return updated_count


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Update strategy registry with backtest metrics")
    parser.add_argument("--strategy-id", help="Specific strategy ID to update")
    parser.add_argument("--backtest-file", type=Path, help="Path to backtest JSON file")
    parser.add_argument(
        "--scan-all", action="store_true", help="Scan all backtests in data/backtests/ and update"
    )
    parser.add_argument(
        "--backtest-dir",
        type=Path,
        default=Path("data/backtests"),
        help="Directory to scan for backtests (default: data/backtests)",
    )

    args = parser.parse_args()

    if args.scan_all:
        logger.info("Scanning all backtests...")
        updated = scan_and_update_all_backtests(args.backtest_dir)
        print(f"\n✅ Updated {updated} strategies with backtest metrics\n")

        # Show registry report
        registry = StrategyRegistry()
        print(registry.generate_report())

    elif args.strategy_id and args.backtest_file:
        registry = StrategyRegistry()
        success = update_strategy_from_backtest(args.strategy_id, args.backtest_file, registry)

        if success:
            print(f"\n✅ Successfully updated {args.strategy_id}\n")
            print(registry.generate_report())
        else:
            print(f"\n❌ Failed to update {args.strategy_id}\n")
            sys.exit(1)

    else:
        parser.print_help()
        print("\nExamples:")
        print("  # Update specific strategy")
        print(
            "  python3 scripts/update_backtest_metrics.py --strategy-id momentum_v1 --backtest-file data/backtests/momentum_v1_backtest.json"
        )
        print("\n  # Scan and update all")
        print("  python3 scripts/update_backtest_metrics.py --scan-all")


if __name__ == "__main__":
    main()
