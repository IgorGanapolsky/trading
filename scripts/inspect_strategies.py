#!/usr/bin/env python3
"""
Strategy Inspector - View All Strategies and Their Status

This script inspects the repository and prints:
- All strategies currently implemented
- Their latest backtest date and key metrics
- Any branches or open PRs that touch the same components

Usage:
    python scripts/inspect_strategies.py
    python scripts/inspect_strategies.py --json
    python scripts/inspect_strategies.py --pr-check

Author: Trading System
Created: 2025-12-03
"""

import argparse
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.strategies.registry import StrategyStatus, get_registry, initialize_registry

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def get_git_branches_touching_file(filepath: str) -> list[str]:
    """Get branches that have modified a specific file."""
    try:
        result = subprocess.run(
            ["git", "log", "--all", "--format=%D", "--", filepath],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        branches = set()
        for line in result.stdout.strip().split("\n"):
            if line:
                for ref in line.split(","):
                    ref = ref.strip()
                    if "origin/" in ref:
                        branches.add(ref.split("origin/")[-1])
        return list(branches)[:5]  # Limit to 5 most relevant
    except Exception:
        return []


def get_open_prs() -> list[dict]:
    """Get open PRs from GitHub."""
    try:
        result = subprocess.run(
            ["gh", "pr", "list", "--json", "number,title,headRefName,updatedAt"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        return []
    except Exception:
        return []


def get_prs_touching_strategies() -> list[dict]:
    """Find PRs that touch strategy files."""
    prs = get_open_prs()
    strategy_prs = []

    for pr in prs:
        try:
            # Get files changed in PR
            result = subprocess.run(
                ["gh", "pr", "view", str(pr["number"]), "--json", "files"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                files = [f["path"] for f in data.get("files", [])]
                if any("strateg" in f.lower() for f in files):
                    pr["files"] = files
                    strategy_prs.append(pr)
        except Exception:
            continue

    return strategy_prs


def load_latest_backtest_metrics(strategy_name: str) -> dict | None:
    """Load the latest backtest metrics for a strategy."""
    metrics_file = Path(f"data/backtest_results/{strategy_name}_latest.json")
    if metrics_file.exists():
        with open(metrics_file) as f:
            return json.load(f)
    return None


def print_strategy_report():
    """Print a comprehensive strategy report."""
    initialize_registry()
    registry = get_registry()

    print("=" * 80)
    print("STRATEGY INSPECTOR REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()

    # Get all strategies
    strategies = registry.list_all()

    if not strategies:
        print(
            "No strategies registered. Run: python -c 'from src.strategies.registry import initialize_registry; initialize_registry()'"
        )
        return

    # Group by status
    by_status = {}
    for s in strategies:
        status = s.status.value
        if status not in by_status:
            by_status[status] = []
        by_status[status].append(s)

    # Print strategies by status
    status_order = ["core", "live_trading", "paper_trading", "experimental", "deprecated"]

    for status in status_order:
        if status not in by_status:
            continue

        status_strategies = by_status[status]
        print(f"\n{'=' * 40}")
        print(f"{status.upper()} ({len(status_strategies)} strategies)")
        print("=" * 40)

        for strat in status_strategies:
            print(f"\n  📊 {strat.name}")
            print(f"     Description: {strat.description[:60]}...")
            print(f"     Asset Class: {strat.asset_class.value}")
            print(f"     Source: {strat.source_file}")

            # Show metrics if available
            m = strat.metrics
            if m.backtest_date:
                print(f"     Last Backtest: {m.backtest_date}")
                print(
                    f"     Sharpe: {m.sharpe_ratio:.2f} | Win Rate: {m.win_rate:.1f}% | Avg Daily: ${m.avg_daily_pnl:.2f}"
                )
                print(f"     $100/Day Hit Rate: {m.hit_rate_100_day:.1f}%")
            else:
                print("     ⚠️  No backtest metrics available")

            # Show related branches
            if strat.source_file:
                branches = get_git_branches_touching_file(strat.source_file)
                if branches:
                    print(f"     Related Branches: {', '.join(branches[:3])}")

    # Show PRs touching strategies
    print("\n" + "=" * 80)
    print("OPEN PRs TOUCHING STRATEGY FILES")
    print("=" * 80)

    strategy_prs = get_prs_touching_strategies()
    if strategy_prs:
        for pr in strategy_prs:
            print(f"\n  PR #{pr['number']}: {pr['title']}")
            print(f"  Branch: {pr['headRefName']}")
            strategy_files = [f for f in pr.get("files", []) if "strateg" in f.lower()]
            if strategy_files:
                print(f"  Strategy Files: {', '.join(strategy_files[:3])}")
    else:
        print("\n  No open PRs touch strategy files.")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\n  Total Strategies: {len(strategies)}")
    for status, strats in by_status.items():
        print(f"    - {status}: {len(strats)}")

    # Check for strategies needing backtest
    needs_backtest = [s for s in strategies if not s.metrics.backtest_date]
    if needs_backtest:
        print(f"\n  ⚠️  {len(needs_backtest)} strategies need backtesting:")
        for s in needs_backtest:
            print(f"      - {s.name}")

    print()


def print_json_report():
    """Print strategy report as JSON."""
    initialize_registry()
    registry = get_registry()

    data = {
        "generated": datetime.now().isoformat(),
        "strategies": [s.to_dict() for s in registry.list_all()],
        "open_prs": get_prs_touching_strategies(),
        "summary": {
            "total": len(registry.list_all()),
            "by_status": {
                status.value: len(registry.list_by_status(status)) for status in StrategyStatus
            },
        },
    }

    print(json.dumps(data, indent=2))


def check_pr_duplicates(pr_title: str = "") -> bool:
    """
    Check if a new PR might duplicate existing work.

    Returns True if potential duplicate found.
    """
    strategy_prs = get_prs_touching_strategies()

    if not strategy_prs:
        print("No potential conflicts found.")
        return False

    print("⚠️  Existing PRs touch strategy code:")
    for pr in strategy_prs:
        print(f"  - PR #{pr['number']}: {pr['title']}")

    return len(strategy_prs) > 0


def main():
    parser = argparse.ArgumentParser(description="Inspect trading strategies")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--pr-check", action="store_true", help="Check for PR duplicates")

    args = parser.parse_args()

    if args.json:
        print_json_report()
    elif args.pr_check:
        has_conflicts = check_pr_duplicates()
        sys.exit(1 if has_conflicts else 0)
    else:
        print_strategy_report()


if __name__ == "__main__":
    main()
