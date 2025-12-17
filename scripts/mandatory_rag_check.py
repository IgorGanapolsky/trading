#!/usr/bin/env python3
"""
Mandatory RAG Query Check - Prevents LL-035 pattern.

This script MUST be run before any significant changes to ensure
relevant lessons learned are consulted first.

Usage:
    python3 scripts/mandatory_rag_check.py "workflow failures"
    python3 scripts/mandatory_rag_check.py "crypto order fill"
    python3 scripts/mandatory_rag_check.py "import errors"

Created: Dec 15, 2025
Lesson: LL-035 - Failed to Use RAG Despite Building It
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def load_lessons_simple() -> list[dict]:
    """Load lessons using simple text search (no embeddings required)."""
    lessons_dir = PROJECT_ROOT / "rag_knowledge" / "lessons_learned"
    lessons = []

    if not lessons_dir.exists():
        print(f"WARNING: {lessons_dir} does not exist!")
        return lessons

    for md_file in lessons_dir.glob("*.md"):
        try:
            with open(md_file) as f:
                content = f.read()

            # Extract metadata
            lesson = {
                "id": md_file.stem,
                "path": str(md_file),
                "content": content,
                "title": "",
                "severity": "medium",
            }

            # Parse title
            for line in content.split("\n")[:10]:
                if line.startswith("# "):
                    lesson["title"] = line[2:].strip()
                    break
                elif line.startswith("**ID**"):
                    lesson["id"] = line.split(":")[-1].strip()

            # Parse severity
            if "CRITICAL" in content.upper():
                lesson["severity"] = "critical"
            elif "HIGH" in content.upper():
                lesson["severity"] = "high"

            lessons.append(lesson)
        except Exception as e:
            print(f"Warning: Could not load {md_file}: {e}")

    return lessons


def search_lessons(query: str, lessons: list[dict], top_k: int = 5) -> list[tuple]:
    """Simple keyword search over lessons."""
    query_terms = query.lower().split()
    scored_results = []

    for lesson in lessons:
        content_lower = lesson["content"].lower()
        title_lower = lesson.get("title", "").lower()

        # Score based on term matches
        score = 0
        for term in query_terms:
            # Title matches worth more
            if term in title_lower:
                score += 10
            # Content matches
            score += content_lower.count(term)

        # Boost critical lessons
        if lesson["severity"] == "critical":
            score *= 1.5
        elif lesson["severity"] == "high":
            score *= 1.2

        if score > 0:
            scored_results.append((lesson, score))

    # Sort by score descending
    scored_results.sort(key=lambda x: x[1], reverse=True)

    return scored_results[:top_k]


def main():
    parser = argparse.ArgumentParser(
        description="Query RAG lessons before making changes (prevents LL-035)"
    )
    parser.add_argument(
        "query",
        type=str,
        help="What you're trying to fix/change (e.g., 'workflow failures', 'crypto fills')",
    )
    parser.add_argument(
        "--top-k", type=int, default=5, help="Number of results to show"
    )
    parser.add_argument(
        "--require-ack",
        action="store_true",
        help="Require acknowledgment before proceeding",
    )

    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("MANDATORY RAG CHECK - Preventing LL-035 Pattern")
    print("=" * 70)
    print(f"\nQuery: {args.query}")
    print("-" * 70)

    # Load and search lessons
    lessons = load_lessons_simple()
    print(f"\nLoaded {len(lessons)} lessons from RAG knowledge base")

    if not lessons:
        print("\nERROR: No lessons found! RAG knowledge base may be missing.")
        print("  Expected location: rag_knowledge/lessons_learned/")
        sys.exit(1)

    results = search_lessons(args.query, lessons, args.top_k)

    if not results:
        print(f"\nNo relevant lessons found for: {args.query}")
        print("This may be a new issue type. Document it after resolution!")
    else:
        print(f"\nFound {len(results)} relevant lessons:\n")

        for i, (lesson, score) in enumerate(results, 1):
            severity_icon = {
                "critical": "🔴",
                "high": "🟠",
                "medium": "🟡",
            }.get(lesson["severity"], "⚪")

            print(f"{i}. {severity_icon} [{lesson['severity'].upper()}] {lesson['id']}")
            print(f"   Title: {lesson['title'][:60]}...")
            print(f"   File: {Path(lesson['path']).name}")
            print(f"   Relevance Score: {score:.1f}")
            print()

        # Show critical lessons' key points
        critical_lessons = [lesson for lesson, s in results if lesson["severity"] == "critical"]
        if critical_lessons:
            print("\n" + "=" * 70)
            print("CRITICAL LESSONS - READ THESE FIRST:")
            print("=" * 70)

            for lesson in critical_lessons[:2]:
                print(f"\n### {lesson['id']}: {lesson['title'][:50]}...")

                # Extract key sections
                content = lesson["content"]

                # Find Prevention or Fix sections
                for section in ["## Prevention", "## The Fix", "## Solution"]:
                    if section in content:
                        start = content.find(section)
                        end = content.find("\n## ", start + len(section))
                        if end == -1:
                            end = start + 500
                        snippet = content[start:end][:300]
                        print(f"\n{snippet.strip()}...")
                        break

    if args.require_ack:
        print("\n" + "=" * 70)
        print("ACKNOWLEDGMENT REQUIRED")
        print("=" * 70)
        print("\nBefore proceeding, confirm you have:")
        print("  [ ] Read the relevant lessons above")
        print("  [ ] Applied their prevention rules")
        print("  [ ] Considered if your change might repeat a past mistake")

        response = input("\nType 'READ' to acknowledge and proceed: ")
        if response.strip().upper() != "READ":
            print("\nAborted. Please read lessons before making changes.")
            sys.exit(1)

        print("\nAcknowledged. Proceeding...")

        # Create acknowledgment marker
        ack_file = PROJECT_ROOT / ".rag_query_acknowledged"
        with open(ack_file, "w") as f:
            f.write(f"Query: {args.query}\n")
            f.write(f"Time: {__import__('datetime').datetime.now().isoformat()}\n")
            f.write(f"Results: {len(results)} lessons reviewed\n")

    print("\n" + "=" * 70)
    print("RAG Check Complete")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
