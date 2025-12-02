#!/usr/bin/env python3
"""
Dependency Decision Logger - Learn from dependency management history

Logs all dependency decisions to build institutional knowledge.

Usage:
    # Add a decision
    python scripts/log_dependency_decision.py add \
        --package numpy \
        --version-after "2.0.0" \
        --change-type upgrade \
        --trigger conflict \
        --reason "Resolved pandas 2.3.3 compatibility" \
        --outcome success

    # Query package history
    python scripts/log_dependency_decision.py query --package numpy

    # Generate report
    python scripts/log_dependency_decision.py report

    # Get AI recommendations
    python scripts/log_dependency_decision.py recommend --package numpy
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

HISTORY_FILE = Path(__file__).parent.parent / ".claude" / "dependency-history.json"


def load_history() -> dict:
    """Load dependency history from JSON file"""
    if not HISTORY_FILE.exists():
        return {
            "schema_version": "1.0.0",
            "created": datetime.now().strftime("%Y-%m-%d"),
            "decisions": [],
            "statistics": {
                "total_decisions": 0,
                "successful_resolutions": 0,
                "failed_resolutions": 0,
                "rollbacks": 0,
                "conflicts_by_package": {},
                "strategy_success_rate": {},
            },
        }

    with open(HISTORY_FILE) as f:
        return json.load(f)


def save_history(history: dict):
    """Save dependency history to JSON file"""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def add_decision(args):
    """Add a new dependency decision to history"""
    history = load_history()

    decision = {
        "timestamp": datetime.now().isoformat(),
        "package": args.package,
        "version_before": args.version_before,
        "version_after": args.version_after,
        "change_type": args.change_type,
        "trigger": args.trigger,
        "reason": args.reason,
        "outcome": args.outcome,
        "strategy": args.strategy,
        "notes": args.notes,
    }

    history["decisions"].append(decision)

    # Update statistics
    stats = history["statistics"]
    stats["total_decisions"] += 1

    if args.outcome == "success":
        stats["successful_resolutions"] += 1
    elif args.outcome == "failure":
        stats["failed_resolutions"] += 1
    elif args.outcome == "rollback":
        stats["rollbacks"] += 1

    # Track conflicts by package
    if args.trigger == "conflict":
        pkg_conflicts = stats["conflicts_by_package"].get(args.package, 0)
        stats["conflicts_by_package"][args.package] = pkg_conflicts + 1

    # Track strategy success rate
    if args.strategy:
        strategy_stats = stats["strategy_success_rate"].get(
            args.strategy, {"success": 0, "failure": 0}
        )
        if args.outcome == "success":
            strategy_stats["success"] += 1
        elif args.outcome == "failure":
            strategy_stats["failure"] += 1
        stats["strategy_success_rate"][args.strategy] = strategy_stats

    save_history(history)

    print(f"✅ Decision logged for {args.package}")
    print(f"   Change: {args.version_before or 'new'} → {args.version_after}")
    print(f"   Outcome: {args.outcome}")


def query_package(args):
    """Query decision history for a specific package"""
    history = load_history()

    package_decisions = [d for d in history["decisions"] if d["package"] == args.package]

    if not package_decisions:
        print(f"📋 No decisions found for {args.package}")
        return

    print(f"📋 Decision History for {args.package} ({len(package_decisions)} decisions)\n")

    for i, decision in enumerate(package_decisions, 1):
        print(f"{i}. {decision['timestamp'][:10]}")
        print(f"   Change: {decision['version_before'] or 'new'} → {decision['version_after']}")
        print(f"   Type: {decision['change_type']} (Trigger: {decision['trigger']})")
        print(f"   Reason: {decision['reason']}")
        print(f"   Outcome: {decision['outcome']}")
        if decision.get("strategy"):
            print(f"   Strategy: {decision['strategy']}")
        print()


def generate_report(args):
    """Generate comprehensive dependency decision report"""
    history = load_history()
    stats = history["statistics"]

    print("=" * 70)
    print("📊 DEPENDENCY DECISION REPORT")
    print("=" * 70)
    print()

    print(f"Total Decisions: {stats['total_decisions']}")
    print(f"Successful: {stats['successful_resolutions']} ✅")
    print(f"Failed: {stats['failed_resolutions']} ❌")
    print(f"Rollbacks: {stats['rollbacks']} ⏪")

    if stats["total_decisions"] > 0:
        success_rate = (stats["successful_resolutions"] / stats["total_decisions"]) * 100
        print(f"Success Rate: {success_rate:.1f}%")

    print()

    # Top conflict packages
    if stats["conflicts_by_package"]:
        print("🔥 Top Conflict Packages:")
        conflicts = sorted(stats["conflicts_by_package"].items(), key=lambda x: x[1], reverse=True)
        for pkg, count in conflicts[:5]:
            print(f"   {pkg}: {count} conflicts")
        print()

    # Strategy success rates
    if stats["strategy_success_rate"]:
        print("📈 Strategy Success Rates:")
        for strategy, data in stats["strategy_success_rate"].items():
            total = data["success"] + data["failure"]
            rate = (data["success"] / total * 100) if total > 0 else 0
            print(f"   {strategy}: {rate:.1f}% ({data['success']}/{total})")
        print()

    print("=" * 70)


def recommend_strategy(args):
    """Recommend resolution strategy based on historical patterns"""
    history = load_history()

    package_decisions = [d for d in history["decisions"] if d["package"] == args.package]

    if not package_decisions:
        print(f"ℹ️  No historical data for {args.package}")
        print("   Recommended: Start with dependency upgrade (most common)")
        return

    # Find most successful strategy for this package
    strategies = {}
    for decision in package_decisions:
        if decision.get("strategy") and decision["outcome"] == "success":
            strategies[decision["strategy"]] = strategies.get(decision["strategy"], 0) + 1

    if strategies:
        best_strategy = max(strategies.items(), key=lambda x: x[1])
        print(f"🎯 Recommended strategy for {args.package}: {best_strategy[0]}")
        print(f"   (succeeded {best_strategy[1]} times in past)")
    else:
        print(f"ℹ️  No successful strategies recorded for {args.package}")

    # Show common triggers
    triggers = {}
    for decision in package_decisions:
        triggers[decision["trigger"]] = triggers.get(decision["trigger"], 0) + 1

    if triggers:
        print("\n📊 Common triggers:")
        for trigger, count in sorted(triggers.items(), key=lambda x: x[1], reverse=True):
            print(f"   {trigger}: {count} times")


def main():
    parser = argparse.ArgumentParser(description="Dependency Decision Logger")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Add decision
    add_parser = subparsers.add_parser("add", help="Add a decision")
    add_parser.add_argument("--package", required=True)
    add_parser.add_argument("--version-before", default=None)
    add_parser.add_argument("--version-after", required=True)
    add_parser.add_argument(
        "--change-type",
        required=True,
        choices=["install", "upgrade", "downgrade", "pin", "remove"],
    )
    add_parser.add_argument(
        "--trigger",
        required=True,
        choices=[
            "manual",
            "conflict",
            "security",
            "compatibility",
            "feature",
            "deprecation",
        ],
    )
    add_parser.add_argument("--reason", required=True)
    add_parser.add_argument(
        "--outcome",
        required=True,
        choices=["success", "failure", "rollback", "pending"],
    )
    add_parser.add_argument("--strategy", default=None)
    add_parser.add_argument("--notes", default=None)

    # Query package
    query_parser = subparsers.add_parser("query", help="Query package history")
    query_parser.add_argument("--package", required=True)

    # Generate report
    report_parser = subparsers.add_parser("report", help="Generate report")
    report_parser.add_argument("--format", default="text", choices=["text", "markdown", "json"])

    # Get recommendations
    recommend_parser = subparsers.add_parser("recommend", help="Get strategy recommendations")
    recommend_parser.add_argument("--package", required=True)

    args = parser.parse_args()

    if args.command == "add":
        add_decision(args)
    elif args.command == "query":
        query_package(args)
    elif args.command == "report":
        generate_report(args)
    elif args.command == "recommend":
        recommend_strategy(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
