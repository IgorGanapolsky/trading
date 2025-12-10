#!/usr/bin/env python3
"""
Strategy Inventory Script

Shows all strategies, their latest backtest dates, key metrics, and any
overlapping branches/PRs to avoid duplicate work.

Usage:
    python scripts/strategy_inventory.py
    python scripts/strategy_inventory.py --json  # JSON output
    python scripts/strategy_inventory.py --check-overlaps  # Check for overlapping work
"""

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.strategies.strategy_registry import StrategyRegistry, get_registry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_branches() -> list[str]:
    """Get list of all branches."""
    try:
        result = subprocess.run(
            ["git", "branch", "-a"],
            capture_output=True,
            text=True,
            check=True,
        )
        branches = [
            line.strip().replace("*", "").replace("remotes/origin/", "").strip()
            for line in result.stdout.split("\n")
            if line.strip() and "HEAD" not in line
        ]
        return sorted(set(branches))
    except Exception as e:
        logger.warning(f"Failed to get branches: {e}")
        return []


def get_open_prs() -> list[dict[str, str]]:
    """Get list of open PRs."""
    try:
        result = subprocess.run(
            ["gh", "pr", "list", "--state", "open", "--json", "number,title,headRefName"],
            capture_output=True,
            text=True,
            check=True,
        )
        prs = json.loads(result.stdout)
        return prs
    except Exception as e:
        logger.warning(f"Failed to get PRs: {e}")
        return []


def check_strategy_files() -> dict[str, dict[str, str]]:
    """Auto-discover strategies from strategy files."""
    strategies_dir = Path(__file__).parent.parent / "src" / "strategies"
    discovered = {}

    for strategy_file in strategies_dir.glob("*_strategy.py"):
        if strategy_file.name == "__init__.py" or strategy_file.name == "strategy_registry.py":
            continue

        # Try to extract class name from file
        class_name = strategy_file.stem.replace("_", " ").title().replace(" ", "")
        module_path = f"src.strategies.{strategy_file.stem}"

        discovered[strategy_file.stem] = {
            "module_path": module_path,
            "class_name": class_name,
            "file_path": str(strategy_file),
        }

    return discovered


def check_overlaps(
    registry: StrategyRegistry, branches: list[str], prs: list[dict]
) -> dict[str, list[str]]:
    """
    Check for overlapping branches/PRs that touch the same strategies.

    Returns:
        Dictionary mapping strategy names to overlapping branches/PRs
    """
    overlaps = {}

    # Check branches
    for branch in branches:
        # Simple heuristic: check if branch name contains strategy-related keywords
        branch_lower = branch.lower()
        for strategy_name, strategy_meta in registry.strategies.items():
            if (
                strategy_name.lower() in branch_lower
                or strategy_meta.class_name.lower() in branch_lower
            ):
                if strategy_name not in overlaps:
                    overlaps[strategy_name] = []
                overlaps[strategy_name].append(f"branch:{branch}")

    # Check PRs
    for pr in prs:
        pr_title = pr.get("title", "").lower()
        pr_branch = pr.get("headRefName", "").lower()
        for strategy_name, strategy_meta in registry.strategies.items():
            if (
                strategy_name.lower() in pr_title
                or strategy_meta.class_name.lower() in pr_title
                or strategy_name.lower() in pr_branch
            ):
                if strategy_name not in overlaps:
                    overlaps[strategy_name] = []
                overlaps[strategy_name].append(f"pr:{pr['number']}:{pr['title']}")

    return overlaps


def print_inventory(
    registry: StrategyRegistry, overlaps: dict[str, list[str]], json_output: bool = False
) -> None:
    """Print strategy inventory."""
    strategies = registry.list_strategies()

    if json_output:
        output = {
            "strategies": [
                {
                    "name": s.name,
                    "module_path": s.module_path,
                    "class_name": s.class_name,
                    "description": s.description,
                    "pipeline_stage": s.pipeline_stage,
                    "last_backtest_date": s.last_backtest_date,
                    "last_backtest_metrics": s.last_backtest_metrics,
                    "branches_touching": s.branches_touching,
                    "prs_touching": s.prs_touching,
                    "overlaps": overlaps.get(s.name, []),
                }
                for s in strategies
            ],
            "total_strategies": len(strategies),
        }
        print(json.dumps(output, indent=2))
        return

    # Human-readable output
    print("=" * 100)
    print("STRATEGY INVENTORY")
    print("=" * 100)
    print()

    if not strategies:
        print("No strategies registered.")
        print("\nTo register strategies, use:")
        print("  from src.strategies.strategy_registry import register_strategy")
        print("  register_strategy('name', 'module.path', 'ClassName', 'Description')")
        return

    for strategy in strategies:
        print(f"Strategy: {strategy.name}")
        print(f"  Module: {strategy.module_path}.{strategy.class_name}")
        print(f"  Description: {strategy.description}")
        print(f"  Pipeline Stage: {strategy.pipeline_stage}")
        print(f"  Last Backtest: {strategy.last_backtest_date or 'Never'}")
        if strategy.last_backtest_metrics:
            metrics = strategy.last_backtest_metrics
            print(f"    Sharpe: {metrics.get('sharpe_ratio', 'N/A'):.2f}")
            print(f"    Avg Daily P&L: ${metrics.get('avg_daily_pnl', 0):.2f}")
            print(f"    % Days ≥ $100: {metrics.get('pct_days_above_target', 0):.1f}%")
        print(f"  Branches Touching: {', '.join(strategy.branches_touching) or 'None'}")
        print(f"  PRs Touching: {', '.join(strategy.prs_touching) or 'None'}")
        if overlaps.get(strategy.name):
            print(f"  ⚠️  OVERLAPS: {', '.join(overlaps[strategy.name])}")
        print()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Strategy inventory and overlap checker")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    parser.add_argument(
        "--check-overlaps", action="store_true", help="Check for overlapping branches/PRs"
    )
    parser.add_argument(
        "--auto-register", action="store_true", help="Auto-register discovered strategies"
    )
    args = parser.parse_args()

    registry = get_registry()

    # Auto-discover strategies if requested
    if args.auto_register:
        discovered = check_strategy_files()
        for name, info in discovered.items():
            if name not in registry.strategies:
                registry.register(
                    name=name,
                    module_path=info["module_path"],
                    class_name=info["class_name"],
                    description=f"Auto-discovered strategy from {info['file_path']}",
                    pipeline_stage="signals",
                )
        registry.save()
        logger.info(f"Auto-registered {len(discovered)} strategies")

    # Check overlaps if requested
    overlaps = {}
    if args.check_overlaps:
        branches = get_branches()
        prs = get_open_prs()
        overlaps = check_overlaps(registry, branches, prs)

    # Print inventory
    print_inventory(registry, overlaps, json_output=args.json)

    # Summary
    if not args.json:
        print("=" * 100)
        print(f"Total Strategies: {len(registry.list_strategies())}")
        if overlaps:
            print(f"Strategies with Overlaps: {len(overlaps)}")
        print("=" * 100)


if __name__ == "__main__":
    main()
