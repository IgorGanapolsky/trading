#!/usr/bin/env python3
"""
Pre-Session RAG Check - Query lessons learned before trading.

This script MUST run before any trading session to:
1. Query for recent CRITICAL and HIGH severity operational failures
2. Display warnings about relevant lessons
3. BLOCK trading if there are unresolved CRITICAL or HIGH issues

Why this exists (LL-035, Dec 15, 2025):
- We had 60 lessons learned but WEREN'T USING THEM
- Same failures kept repeating because AI didn't read lessons
- This script forces lessons to be read at session start

BLOCKING BEHAVIOR (DEFAULT):
- ALWAYS blocks on recent CRITICAL lessons
- ALWAYS blocks on recent HIGH severity lessons
- Use --allow-warnings to permit HIGH but still block on CRITICAL
- Use --no-block to override (NOT RECOMMENDED)

Usage:
    # Default - blocks on CRITICAL and HIGH:
    python3 scripts/pre_session_rag_check.py

    # Allow HIGH severity, block only CRITICAL:
    python3 scripts/pre_session_rag_check.py --allow-warnings

    # Check last 14 days:
    python3 scripts/pre_session_rag_check.py --days 14

    # Override blocking (NOT RECOMMENDED):
    python3 scripts/pre_session_rag_check.py --no-block

Exit Codes:
    0 - No blocking issues found (safe to proceed)
    1 - CRITICAL or HIGH issues found (trading blocked)
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from src.utils.staleness_guard import check_context_freshness

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
TRUTHY = {"1", "true", "yes", "on"}


def _extract_severity(content: str) -> str | None:
    normalized = re.sub(r"[*_`]", "", content)
    match = re.search(r"\bseverity\b\s*:\s*(critical|high|medium|low)\b", normalized, flags=re.I)
    if not match:
        return None
    return match.group(1).upper()


def _parse_lesson_date(value: str) -> datetime | None:
    text = re.sub(r"[*_`]", "", (value or "")).strip()
    if not text:
        return None
    patterns = (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%B %d, %Y",
        "%b %d, %Y",
        "%B %d %Y",
        "%b %d %Y",
    )
    for fmt in patterns:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    iso_match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if iso_match:
        try:
            return datetime.strptime(iso_match.group(0), "%Y-%m-%d")
        except ValueError:
            return None
    return None


def check_recent_critical_lessons(days_back: int = 7, include_high: bool = False) -> list[dict]:
    """
    Check for CRITICAL (and optionally HIGH) severity lessons learned in the past N days.

    Args:
        days_back: How many days to look back
        include_high: If True, also check for HIGH severity lessons

    Returns:
        List of critical/high lessons with metadata
    """
    lessons_dir = Path("rag_knowledge/lessons_learned")
    if not lessons_dir.exists():
        logger.warning("No lessons_learned directory found")
        return []

    critical_lessons = []
    cutoff_date = datetime.now() - timedelta(days=days_back)

    for lesson_file in lessons_dir.glob("*.md"):
        try:
            content = lesson_file.read_text()

            severity = _extract_severity(content)
            is_critical = severity == "CRITICAL"
            is_high = include_high and severity == "HIGH"

            if not (is_critical or is_high):
                continue

            severity_level = "CRITICAL" if is_critical else "HIGH"

            # Try to extract date from content
            lesson_date = None
            for line in content.split("\n"):
                if "date" not in line.lower():
                    continue
                after_colon = line.split(":", 1)[1] if ":" in line else line
                parsed = _parse_lesson_date(after_colon)
                if parsed:
                    lesson_date = parsed
                    break

            # Also check file modification time as fallback
            file_mtime = datetime.fromtimestamp(lesson_file.stat().st_mtime)

            # PRIORITY: Use lesson content date if found, otherwise file mtime
            # This prevents RAG rebuilds from making old lessons appear "recent"
            effective_date = lesson_date if lesson_date else file_mtime

            # Extract title/summary
            title = lesson_file.stem
            for line in content.split("\n")[:5]:
                if line.startswith("# "):
                    title = line[2:].strip()
                    break

            critical_lessons.append(
                {
                    "file": lesson_file.name,
                    "title": title,
                    "date": effective_date,
                    "is_recent": effective_date >= cutoff_date,
                    "severity": severity_level,
                    "content_preview": content[:500],
                }
            )

        except Exception as e:
            logger.warning(f"Error reading {lesson_file}: {e}")

    # Sort by date (most recent first)
    critical_lessons.sort(key=lambda x: x["date"], reverse=True)

    return critical_lessons


def query_rag_for_operational_failures() -> list[dict]:
    """
    Use semantic search to find operational failure lessons.

    Returns:
        List of relevant lessons from semantic search
    """
    try:
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        rag = LessonsLearnedRAG()
        lesson_count = len(rag.lessons)
        logger.info(
            "RAG Stats: %s lessons loaded (source=%s)",
            lesson_count,
            rag.last_source or "unknown",
        )

        # Key queries for operational failures
        queries = [
            "operational failure critical catastrophe",
            "trade blocked error failure",
            "blind trading equity zero account",
            "options not closing buy to close",
            "API failure connection error",
        ]

        all_results = []
        for query in queries:
            results = rag.query(query, top_k=3)
            all_results.extend(
                [
                    {
                        "lesson_file": r.get("file", "unknown"),
                        "section_title": r.get("title", r.get("id", "unknown")),
                        "score": r.get("score", 0.0),
                        "content_preview": (r.get("snippet") or r.get("content") or "")[:300],
                    }
                    for r in results
                    if (r.get("score", 0.0) or 0.0) > 0.3
                ]
            )

        # Deduplicate by lesson file
        seen = set()
        unique = []
        for r in all_results:
            if r["lesson_file"] not in seen:
                seen.add(r["lesson_file"])
                unique.append(r)

        return sorted(unique, key=lambda x: x["score"], reverse=True)[:10]

    except ImportError as e:
        logger.warning(f"RAG not available: {e}")
        return []
    except Exception as e:
        logger.error(f"RAG query failed: {e}")
        return []


def attempt_context_refresh() -> bool:
    """Refresh local context indexes once before hard-failing freshness checks."""
    env = os.environ.copy()
    if "RAG_WRITE_PROFILE" not in env:
        env["RAG_WRITE_PROFILE"] = (
            "repo" if env.get("CI", "").strip().lower() in TRUTHY else "local"
        )

    commands = [
        ["python3", "scripts/build_rag_query_index.py"],
        ["python3", "scripts/build_context_engine_index.py", "--project-root", "."],
    ]
    for cmd in commands:
        try:
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        except OSError as exc:
            logger.warning("Failed to execute %s: %s", " ".join(cmd), exc)
            return False
        if result.returncode != 0:
            logger.warning("Context refresh step failed: %s", " ".join(cmd))
            logger.warning(result.stderr.strip() or result.stdout.strip())
            return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Pre-session RAG check")
    parser.add_argument(
        "--allow-warnings",
        action="store_true",
        help="Allow HIGH severity lessons but still block on CRITICAL (default: block on both)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Days to look back for recent lessons (default: 7)",
    )
    parser.add_argument(
        "--no-block",
        action="store_true",
        help="Don't block on any lessons, just warn (NOT RECOMMENDED)",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("🔍 PRE-SESSION RAG CHECK - Learning from past mistakes")
    print("=" * 70)
    print()

    if "RAG_WRITE_PROFILE" not in os.environ and os.getenv("CI", "").strip().lower() not in TRUTHY:
        os.environ["RAG_WRITE_PROFILE"] = "local"

    has_critical_recent = False
    has_high_recent = False
    stale_context_block = False
    context_block_reasons: list[str] = []

    # 0. Freshness SLO check for deterministic RAG/context state
    print("⏱️  Verifying context freshness SLOs...")
    context = check_context_freshness(is_market_day=True)
    auto_refresh = os.getenv("PRE_SESSION_AUTO_REFRESH_CONTEXT", "true").strip().lower() in TRUTHY
    if context.is_stale:
        print(f"   ❌ {context.reason}")
        for source in context.sources:
            freshness = "STALE" if source.is_stale else "fresh"
            print(
                f"   - {source.source}: {freshness} | "
                f"last_sync={source.last_sync or 'unknown'} | "
                f"age={source.age_minutes:.1f}m | max_age={source.max_age_minutes:.1f}m"
            )
        if auto_refresh:
            print("   🔄 Attempting automatic context refresh...")
            if attempt_context_refresh():
                context = check_context_freshness(is_market_day=True)
                if context.is_stale:
                    print(f"   ❌ Refresh completed but context still stale: {context.reason}")
                else:
                    print("   ✅ Refresh completed and context freshness SLOs now pass")
            else:
                print("   ❌ Automatic context refresh failed")
        if context.blocking and not args.no_block:
            stale_context_block = True
            context_block_reasons.append(context.reason)
    else:
        print("   ✅ Context freshness SLOs satisfied")

    # 1. Check for CRITICAL and HIGH lessons (direct file search)
    # If --allow-warnings, only check CRITICAL. Otherwise check both.
    check_high = not args.allow_warnings
    severity_desc = "CRITICAL and HIGH" if check_high else "CRITICAL"
    print(f"📚 Checking for {severity_desc} lessons learned...")

    all_lessons = check_recent_critical_lessons(days_back=args.days, include_high=check_high)

    # Separate by severity
    critical_lessons = [lesson for lesson in all_lessons if lesson["severity"] == "CRITICAL"]
    high_lessons = [lesson for lesson in all_lessons if lesson["severity"] == "HIGH"]

    if critical_lessons:
        print(f"\n🚨 Found {len(critical_lessons)} CRITICAL lessons!")
        print("-" * 50)

        for lesson in critical_lessons:
            age_str = "RECENT" if lesson["is_recent"] else "older"
            print(f"\n📖 [{lesson['severity']}] {lesson['title']}")
            print(f"   File: {lesson['file']}")
            print(f"   Date: {lesson['date'].strftime('%Y-%m-%d')} ({age_str})")

            if lesson["is_recent"]:
                has_critical_recent = True
                print("   🚫 THIS IS A RECENT CRITICAL FAILURE - MUST READ!")

        print()
    else:
        print("   ✅ No CRITICAL lessons found")

    if high_lessons:
        print(f"\n⚠️  Found {len(high_lessons)} HIGH severity lessons!")
        print("-" * 50)

        for lesson in high_lessons:
            age_str = "RECENT" if lesson["is_recent"] else "older"
            print(f"\n📖 [{lesson['severity']}] {lesson['title']}")
            print(f"   File: {lesson['file']}")
            print(f"   Date: {lesson['date'].strftime('%Y-%m-%d')} ({age_str})")

            if lesson["is_recent"]:
                has_high_recent = True
                print("   ⚠️  THIS IS A RECENT HIGH-SEVERITY ISSUE - REVIEW IT!")

        print()
    elif check_high:
        print("   ✅ No HIGH severity lessons found")

    # 2. Semantic search for operational failures
    print("\n📊 Running semantic search for operational failure patterns...")
    rag_results = query_rag_for_operational_failures()

    if rag_results:
        print(f"\n📖 Found {len(rag_results)} relevant lessons via semantic search:")
        print("-" * 50)

        for i, result in enumerate(rag_results[:5], 1):
            print(f"\n{i}. {result['lesson_file']} (score: {result['score']:.2f})")
            print(f"   Section: {result['section_title']}")
            print(f"   Preview: {result['content_preview'][:100]}...")
    else:
        print("   No additional lessons found via semantic search")

    # 3. Summary and blocking logic
    print("\n" + "=" * 70)

    should_block = False
    block_reason = []

    # Determine if we should block
    if has_critical_recent:
        should_block = True
        block_reason.append("CRITICAL recent failures detected")

    if has_high_recent and not args.allow_warnings:
        should_block = True
        block_reason.append("HIGH severity recent issues detected")

    if stale_context_block:
        should_block = True
        block_reason.extend(context_block_reasons)

    # Apply --no-block override
    if args.no_block:
        should_block = False

    # Display summary
    if has_critical_recent or has_high_recent or stale_context_block:
        if has_critical_recent:
            print("🚨 CRITICAL RECENT FAILURES DETECTED!")
        if has_high_recent:
            print("⚠️  HIGH SEVERITY RECENT ISSUES DETECTED!")
        if stale_context_block:
            print("⛔ CONTEXT FRESHNESS SLO FAILED!")

        print("   Review these lessons before trading to avoid repeating mistakes.")

        if should_block:
            print("\n❌ BLOCKING EXECUTION")
            for reason in block_reason:
                print(f"   - {reason}")
            print("\n   Options:")
            print("   1. Review and fix the issues")
            print("   2. Use --allow-warnings to permit HIGH severity but block CRITICAL")
            print("   3. Use --no-block to override (NOT RECOMMENDED)")
            print("=" * 70)
            sys.exit(1)
        else:
            if args.no_block:
                print("\n⚠️  WARNING: --no-block flag set, proceeding anyway (NOT RECOMMENDED)")
            elif args.allow_warnings:
                print("\n⚠️  WARNING: --allow-warnings flag set, allowing HIGH severity issues")
                if has_critical_recent:
                    print("   But CRITICAL issues were found - this should NOT happen!")
            print("=" * 70)
            return 0
    else:
        print("✅ No recent CRITICAL or HIGH severity failures - clear to proceed")
        print("=" * 70)
        return 0


if __name__ == "__main__":
    sys.exit(main())
