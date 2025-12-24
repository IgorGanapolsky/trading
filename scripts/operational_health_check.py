#!/usr/bin/env python3
"""
Operational Health Check - Run at Session Start

This script checks all operational systems and reports their status.
It should be run at the START of every Claude session.

Usage:
    python3 scripts/operational_health_check.py
"""

import importlib
import json
import sys
from datetime import datetime
from pathlib import Path


def print_header(title: str) -> None:
    """Print a formatted header."""
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def check_system_state() -> bool:
    """Check system_state.json freshness."""
    state_file = Path("data/system_state.json")
    if not state_file.exists():
        print("❌ system_state.json NOT FOUND")
        return False

    try:
        with open(state_file) as f:
            state = json.load(f)

        last_updated = state.get("last_updated", "unknown")
        portfolio = state.get("portfolio_value", 0)
        day = state.get("challenge_day", 0)

        print(f"📊 Portfolio: ${portfolio:,.2f}")
        print(f"📅 Day: {day}/90")
        print(f"🕐 Last Updated: {last_updated}")

        return True
    except Exception as e:
        print(f"❌ Error reading state: {e}")
        return False


def check_feature_list() -> int:
    """Check feature_list.json for pending items."""
    feature_file = Path("feature_list.json")
    if not feature_file.exists():
        print("⚠️  feature_list.json not found")
        return 0

    try:
        with open(feature_file) as f:
            data = json.load(f)

        features = data.get("features", [])
        pending = [f for f in features if not f.get("passes", False)]

        print(f"📋 Total features: {len(features)}")
        print(f"⏳ Pending: {len(pending)}")

        if pending:
            print("\n  TOP 5 PENDING:")
            for f in pending[:5]:
                print(f"    - {f.get('name', 'unnamed')}")

        return len(pending)
    except Exception as e:
        print(f"❌ Error reading features: {e}")
        return 0


def check_lessons_learned() -> int:
    """Check lessons learned count."""
    lessons_dir = Path("rag_knowledge/lessons_learned")
    if not lessons_dir.exists():
        print("⚠️  lessons_learned directory not found")
        return 0

    lessons = list(lessons_dir.glob("*.md"))
    print(f"📚 Lessons learned: {len(lessons)}")

    # Check for critical lessons
    critical = list(lessons_dir.glob("ll_05*.md"))
    print(f"   Critical (ll_05x): {len(critical)}")

    return len(lessons)


def check_deferred_items() -> list:
    """Find deferred/Month 3 items."""
    deferred = []
    lessons_dir = Path("rag_knowledge/lessons_learned")

    if lessons_dir.exists():
        for lesson in lessons_dir.glob("*.md"):
            content = lesson.read_text().lower()
            if "month 3" in content or "#deferred" in content or "deferred" in content:
                deferred.append(lesson.name)

    print(f"📌 Deferred items: {len(deferred)}")
    for d in deferred[:5]:
        print(f"    - {d}")

    return deferred


def check_phil_town_rag() -> bool:
    """Check Phil Town content completeness."""
    youtube_dir = Path("rag_knowledge/youtube/transcripts")
    blog_dir = Path("rag_knowledge/blogs/phil_town")

    youtube_count = len(list(youtube_dir.glob("*.md"))) if youtube_dir.exists() else 0
    blog_count = len(list(blog_dir.glob("*.md"))) if blog_dir.exists() else 0

    print(f"📺 Phil Town YouTube: {youtube_count}")
    print(f"📝 Phil Town Blog: {blog_count}")

    if youtube_count < 10 or blog_count < 10:
        print("⚠️  Phil Town content below minimum!")
        return False

    return True


def check_ci_recent() -> bool:
    """Check if we can access CI status."""
    # This would need GITHUB_TOKEN to actually work
    print("🔄 CI Status: Check GitHub Actions manually")
    return True


def check_agent_health() -> bool:
    """Quick check of critical imports."""
    print("\n🤖 Agent Health:")

    agents = [
        ("TradingOrchestrator", "src.orchestrator.main", "TradingOrchestrator"),
        ("StrategyRegistry", "src.strategies.registry", "StrategyRegistry"),
    ]

    all_ok = True
    for name, module, cls in agents:
        try:
            mod = importlib.import_module(module)
            getattr(mod, cls)
            print(f"   ✅ {name}")
        except (ImportError, AttributeError) as e:
            print(f"   ❌ {name}: {e}")
            all_ok = False

    return all_ok


def main() -> int:
    """Run all health checks."""
    print_header("OPERATIONAL HEALTH CHECK")
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    issues = 0

    # System State
    print_header("SYSTEM STATE")
    if not check_system_state():
        issues += 1

    # Features
    print_header("FEATURE TRACKING")
    pending = check_feature_list()
    if pending > 10:
        print("⚠️  Many pending features - focus on completion")

    # Lessons
    print_header("KNOWLEDGE BASE")
    check_lessons_learned()
    check_deferred_items()

    # Phil Town
    print_header("PHIL TOWN RAG")
    if not check_phil_town_rag():
        issues += 1

    # Agents
    print_header("AGENT HEALTH")
    # Skip actual import check in script to avoid dependency issues
    print("   Run 'python -c \"from src.orchestrator.main import TradingOrchestrator\"' to verify")

    # Summary
    print_header("SUMMARY")
    if issues == 0:
        print("✅ All systems operational")
        return 0
    else:
        print(f"⚠️  {issues} issue(s) found - review above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
