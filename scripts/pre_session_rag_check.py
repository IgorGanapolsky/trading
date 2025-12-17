#!/usr/bin/env python3
"""
Pre-Session RAG Check - Query lessons learned before trading.

This script MUST run before any trading session to:
1. Query for recent CRITICAL operational failures
2. Display warnings about relevant lessons
3. Block trading if there are unresolved CRITICAL issues

Why this exists (LL-035, Dec 15, 2025):
- We had 60 lessons learned but WEREN'T USING THEM
- Same failures kept repeating because AI didn't read lessons
- This script forces lessons to be read at session start

Usage:
    python3 scripts/pre_session_rag_check.py

    # Block if CRITICAL lessons found:
    python3 scripts/pre_session_rag_check.py --block-on-critical
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def check_recent_critical_lessons(days_back: int = 7) -> list[dict]:
    """
    Check for CRITICAL lessons learned in the past N days.

    Returns:
        List of critical lessons with metadata
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
            content_lower = content.lower()

            # Check if CRITICAL severity
            is_critical = (
                "severity**: critical" in content_lower or
                "severity: critical" in content_lower or
                "**severity**: critical" in content_lower
            )

            if not is_critical:
                continue

            # Try to extract date from content
            lesson_date = None
            for line in content.split("\n"):
                if "date" in line.lower() and "2025" in line:
                    # Try to parse date
                    import re
                    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", line)
                    if date_match:
                        try:
                            lesson_date = datetime.strptime(date_match.group(1), "%Y-%m-%d")
                        except ValueError:
                            pass
                    break

            # Also check file modification time
            file_mtime = datetime.fromtimestamp(lesson_file.stat().st_mtime)

            # Use whichever date is available
            effective_date = lesson_date or file_mtime

            # Extract title/summary
            title = lesson_file.stem
            for line in content.split("\n")[:5]:
                if line.startswith("# "):
                    title = line[2:].strip()
                    break

            critical_lessons.append({
                "file": lesson_file.name,
                "title": title,
                "date": effective_date,
                "is_recent": effective_date >= cutoff_date,
                "content_preview": content[:500],
            })

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
        from src.rag.lessons_search import LessonsSearch

        search = LessonsSearch()
        stats = search.get_stats()
        logger.info(f"RAG Stats: {stats['total_chunks']} chunks, {stats['total_files']} files")

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
            results = search.query(query, top_k=3)
            all_results.extend([{
                "lesson_file": r.lesson_file,
                "section_title": r.section_title,
                "score": r.score,
                "content_preview": r.content[:300],
            } for r in results if r.score > 0.3])

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


def main():
    parser = argparse.ArgumentParser(description="Pre-session RAG check")
    parser.add_argument(
        "--block-on-critical",
        action="store_true",
        help="Exit with error code if CRITICAL lessons found in last 7 days"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Days to look back for recent lessons (default: 7)"
    )
    args = parser.parse_args()

    print("=" * 70)
    print("🔍 PRE-SESSION RAG CHECK - Learning from past mistakes")
    print("=" * 70)
    print()

    has_critical_recent = False

    # 1. Check for CRITICAL lessons (direct file search)
    print("📚 Checking for CRITICAL lessons learned...")
    critical_lessons = check_recent_critical_lessons(days_back=args.days)

    if critical_lessons:
        print(f"\n🚨 Found {len(critical_lessons)} CRITICAL lessons!")
        print("-" * 50)

        for lesson in critical_lessons:
            age_str = "RECENT" if lesson["is_recent"] else "older"
            print(f"\n📖 {lesson['title']}")
            print(f"   File: {lesson['file']}")
            print(f"   Date: {lesson['date'].strftime('%Y-%m-%d')} ({age_str})")

            if lesson["is_recent"]:
                has_critical_recent = True
                print("   ⚠️  THIS IS A RECENT CRITICAL FAILURE - READ IT!")

        print()
    else:
        print("   ✅ No CRITICAL lessons found")

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

    # 3. Summary
    print("\n" + "=" * 70)
    if has_critical_recent:
        print("🚨 CRITICAL RECENT FAILURES DETECTED!")
        print("   Review these lessons before trading to avoid repeating mistakes.")

        if args.block_on_critical:
            print("\n❌ BLOCKING: --block-on-critical flag set")
            print("   Fix the issues or acknowledge before proceeding.")
            sys.exit(1)
        else:
            print("\n⚠️  WARNING: Trading will proceed but you should review lessons!")
    else:
        print("✅ No recent CRITICAL failures - clear to proceed")

    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
