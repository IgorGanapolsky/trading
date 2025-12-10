#!/usr/bin/env python3
"""
Branch & Strategy Analysis Dashboard

Analyzes current branches, open PRs, and strategy registry to provide visibility
into what work is in progress and prevent duplicate efforts.

This script helps answer:
1. What branches exist and what are they working on?
2. What strategies are implemented vs. in development?
3. Are multiple people/branches working on the same thing?
4. What's the latest backtest status for each strategy?

Author: Trading System
Created: 2025-12-03
"""

import json
import logging
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from strategies.strategy_registry import StrategyRegistry, StrategyStatus

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def run_command(cmd: list[str]) -> str | None:
    """Run a shell command and return output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {' '.join(cmd)}\n{e.stderr}")
        return None


def get_git_branches() -> dict:
    """Get all git branches with metadata."""
    output = run_command(["git", "branch", "-a", "-v"])
    if not output:
        return {}

    branches = {}
    for line in output.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Parse branch info
        is_current = line.startswith("*")
        line = line.lstrip("* ")

        parts = line.split()
        if len(parts) < 2:
            continue

        branch_name = parts[0]
        commit_hash = parts[1]

        branches[branch_name] = {
            "is_current": is_current,
            "commit_hash": commit_hash,
            "commit_msg": " ".join(parts[2:]) if len(parts) > 2 else "",
        }

    return branches


def get_open_prs() -> list[dict]:
    """Get open pull requests from GitHub."""
    output = run_command(
        [
            "gh",
            "pr",
            "list",
            "--state",
            "open",
            "--json",
            "number,title,author,headRefName,createdAt,updatedAt",
            "--limit",
            "50",
        ]
    )

    if not output:
        return []

    try:
        return json.loads(output)
    except json.JSONDecodeError:
        logger.error("Failed to parse PR JSON")
        return []


def get_recent_commits(branch: str = "main", limit: int = 10) -> list[dict]:
    """Get recent commits on a branch."""
    output = run_command(["git", "log", branch, "--oneline", f"-{limit}"])

    if not output:
        return []

    commits = []
    for line in output.split("\n"):
        if not line.strip():
            continue

        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            commits.append({"hash": parts[0], "message": parts[1]})

    return commits


def analyze_branch_activity() -> dict:
    """Analyze which areas of code each branch is touching."""
    branches = get_git_branches()
    branch_analysis = {}

    for branch_name in branches:
        if "remotes/origin/" not in branch_name or branch_name.endswith("/main"):
            continue

        # Get files changed in this branch vs main
        output = run_command(["git", "diff", "--name-only", "origin/main", branch_name])

        if not output:
            continue

        files_changed = output.split("\n")

        # Categorize changes
        categories = defaultdict(list)
        for file in files_changed:
            if not file:
                continue

            if file.startswith("src/strategies/"):
                categories["strategies"].append(file)
            elif file.startswith("src/backtesting/"):
                categories["backtesting"].append(file)
            elif file.startswith("src/risk/"):
                categories["risk"].append(file)
            elif file.startswith("src/orchestrator/"):
                categories["orchestrator"].append(file)
            elif file.startswith("tests/"):
                categories["tests"].append(file)
            elif file.startswith("docs/"):
                categories["docs"].append(file)
            else:
                categories["other"].append(file)

        branch_analysis[branch_name] = {
            "files_changed": len(files_changed),
            "categories": dict(categories),
        }

    return branch_analysis


def find_potential_conflicts(
    branch_analysis: dict, strategy_registry: StrategyRegistry
) -> list[dict]:
    """Find potential conflicts or duplicate work."""
    conflicts = []

    # Check for multiple branches touching same strategy files
    strategy_files = defaultdict(list)
    for branch, info in branch_analysis.items():
        for file in info["categories"].get("strategies", []):
            strategy_files[file].append(branch)

    for file, branches in strategy_files.items():
        if len(branches) > 1:
            conflicts.append(
                {
                    "type": "file_conflict",
                    "severity": "medium",
                    "message": f"Multiple branches editing {file}",
                    "branches": branches,
                }
            )

    # Check for strategies in development that might overlap
    strategies_in_dev = strategy_registry.find_by_status(StrategyStatus.DEVELOPMENT)
    strategy_types = defaultdict(list)
    for strategy in strategies_in_dev:
        strategy_types[strategy.strategy_type].append(strategy)

    for strategy_type, strategies in strategy_types.items():
        if len(strategies) > 1:
            conflicts.append(
                {
                    "type": "duplicate_strategy_type",
                    "severity": "low",
                    "message": f"Multiple {strategy_type.value} strategies in development",
                    "strategies": [s.name for s in strategies],
                }
            )

    return conflicts


def generate_dashboard_report() -> str:
    """Generate comprehensive dashboard report."""
    lines = []

    lines.append("=" * 100)
    lines.append("BRANCH & STRATEGY ANALYSIS DASHBOARD")
    lines.append("=" * 100)
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # Git Branches
    lines.append("=" * 100)
    lines.append("ACTIVE BRANCHES")
    lines.append("=" * 100)
    branches = get_git_branches()
    remote_branches = [b for b in branches if "remotes/origin/" in b and not b.endswith("/main")]
    lines.append(f"Total branches: {len(remote_branches)}")
    lines.append("")

    for branch in sorted(remote_branches)[:20]:  # Show top 20
        info = branches[branch]
        clean_name = branch.replace("remotes/origin/", "")
        lines.append(f"  • {clean_name}")
        lines.append(f"    Commit: {info['commit_hash']} - {info['commit_msg'][:80]}")

    if len(remote_branches) > 20:
        lines.append(f"\n  ... and {len(remote_branches) - 20} more branches")

    lines.append("")

    # Open PRs
    lines.append("=" * 100)
    lines.append("OPEN PULL REQUESTS")
    lines.append("=" * 100)
    prs = get_open_prs()
    lines.append(f"Total open PRs: {len(prs)}")
    lines.append("")

    for pr in prs[:10]:  # Show top 10
        lines.append(f"  • PR #{pr['number']}: {pr['title']}")
        lines.append(f"    Branch: {pr['headRefName']}")
        lines.append(f"    Author: {pr['author']['login']}")
        lines.append(f"    Updated: {pr['updatedAt'][:10]}")
        lines.append("")

    if len(prs) > 10:
        lines.append(f"  ... and {len(prs) - 10} more PRs")

    lines.append("")

    # Strategy Registry
    lines.append("=" * 100)
    lines.append("STRATEGY REGISTRY STATUS")
    lines.append("=" * 100)
    registry = StrategyRegistry()

    by_status = defaultdict(list)
    for strategy in registry.strategies.values():
        by_status[strategy.status].append(strategy)

    for status in StrategyStatus:
        strategies = by_status.get(status, [])
        if strategies:
            lines.append(f"\n{status.value.upper()}: {len(strategies)}")
            for s in strategies:
                metrics_str = ""
                if s.backtest_metrics:
                    m = s.backtest_metrics
                    metrics_str = f" | Sharpe: {m.sharpe_ratio:.2f}, WR: {m.win_rate_pct:.1f}%, P&L: ${m.avg_daily_pnl:.2f}/day"

                branch_str = f" [Branch: {s.branch}]" if s.branch else ""
                pr_str = f" [PR #{s.pr_number}]" if s.pr_number else ""

                lines.append(f"  • {s.name}{branch_str}{pr_str}{metrics_str}")

    lines.append("")

    # Branch Activity Analysis
    lines.append("=" * 100)
    lines.append("BRANCH ACTIVITY ANALYSIS")
    lines.append("=" * 100)
    branch_analysis = analyze_branch_activity()

    if branch_analysis:
        lines.append(f"Analyzing {len(branch_analysis)} active development branches...")
        lines.append("")

        for branch, info in list(branch_analysis.items())[:10]:
            clean_name = branch.replace("remotes/origin/", "")
            lines.append(f"  • {clean_name}")
            lines.append(f"    Files changed: {info['files_changed']}")
            for category, files in info["categories"].items():
                lines.append(f"      - {category}: {len(files)} files")
    else:
        lines.append("No active development branches detected")

    lines.append("")

    # Potential Conflicts
    lines.append("=" * 100)
    lines.append("POTENTIAL CONFLICTS & DUPLICATE WORK")
    lines.append("=" * 100)
    conflicts = find_potential_conflicts(branch_analysis, registry)

    if conflicts:
        for conflict in conflicts:
            severity_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
            emoji = severity_emoji.get(conflict["severity"], "•")
            lines.append(f"{emoji} {conflict['message']}")
            if "branches" in conflict:
                for branch in conflict["branches"]:
                    clean_name = branch.replace("remotes/origin/", "")
                    lines.append(f"    - {clean_name}")
            if "strategies" in conflict:
                for strategy in conflict["strategies"]:
                    lines.append(f"    - {strategy}")
            lines.append("")
    else:
        lines.append("✅ No conflicts detected - good job coordinating!")

    lines.append("")

    # Best Performing Strategies
    lines.append("=" * 100)
    lines.append("TOP PERFORMING STRATEGIES")
    lines.append("=" * 100)

    best_sharpe = registry.get_best_by_metric("sharpe_ratio")
    best_pnl = registry.get_best_by_metric("avg_daily_pnl")
    best_win_rate = registry.get_best_by_metric("win_rate_pct")

    if best_sharpe and best_sharpe.backtest_metrics:
        m = best_sharpe.backtest_metrics
        lines.append(f"🏆 Best Sharpe: {best_sharpe.name}")
        lines.append(
            f"   Sharpe: {m.sharpe_ratio:.2f}, Return: {m.total_return_pct:.1f}%, Drawdown: {m.max_drawdown_pct:.1f}%"
        )
        lines.append(f"   Backtest: {m.start_date} to {m.end_date}")
        lines.append("")

    if best_pnl and best_pnl.backtest_metrics:
        m = best_pnl.backtest_metrics
        lines.append(f"💰 Best Daily P&L: {best_pnl.name}")
        lines.append(f"   Daily P&L: ${m.avg_daily_pnl:.2f}, Win Rate: {m.win_rate_pct:.1f}%")
        lines.append(f"   Total Trades: {m.total_trades}")
        lines.append("")

    if best_win_rate and best_win_rate.backtest_metrics:
        m = best_win_rate.backtest_metrics
        lines.append(f"🎯 Best Win Rate: {best_win_rate.name}")
        lines.append(f"   Win Rate: {m.win_rate_pct:.1f}%, Sharpe: {m.sharpe_ratio:.2f}")
        lines.append("")

    # Recommendations
    lines.append("=" * 100)
    lines.append("RECOMMENDATIONS")
    lines.append("=" * 100)

    # Check if we should focus on improving existing vs adding new
    strategies_in_dev = len(by_status.get(StrategyStatus.DEVELOPMENT, []))
    strategies_backtested = len(by_status.get(StrategyStatus.BACKTESTED, []))
    strategies_live = len(by_status.get(StrategyStatus.LIVE, []))

    if strategies_in_dev > 3:
        lines.append(
            "⚠️  Many strategies in development - consider finishing some before starting new ones"
        )

    if strategies_backtested > strategies_live + 1:
        lines.append(
            "💡 Multiple backtested strategies ready - consider deploying best one to paper/live"
        )

    if best_sharpe and best_sharpe.backtest_metrics:
        if best_sharpe.backtest_metrics.sharpe_ratio > 2.0:
            lines.append(
                f"✅ {best_sharpe.name} has excellent Sharpe ({best_sharpe.backtest_metrics.sharpe_ratio:.2f}) - strong candidate for live deployment"
            )

    if len(conflicts) > 0:
        lines.append(f"⚠️  {len(conflicts)} potential conflicts detected - review before merging")

    lines.append("")
    lines.append("=" * 100)

    return "\n".join(lines)


def main():
    """Main entry point."""
    print("\nGenerating branch & strategy analysis dashboard...\n")

    report = generate_dashboard_report()
    print(report)

    # Save to file
    output_file = Path("reports/branch_strategy_analysis.txt")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        f.write(report)

    print(f"\nReport saved to: {output_file}")


if __name__ == "__main__":
    main()
