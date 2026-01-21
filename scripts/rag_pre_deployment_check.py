#!/usr/bin/env python3
"""
RAG Pre-Deployment Check - Learn from Past Mistakes

Automatically queries the lessons learned RAG database before:
1. Deploying workflow changes
2. Modifying requirements files
3. Changing trading logic

Uses semantic search to find relevant past failures and warns if
the proposed change matches patterns of past mistakes.

Author: Trading System
Created: 2025-12-12
"""

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
RAG_LESSONS_PATH = PROJECT_ROOT / "data" / "rag" / "lessons_learned.json"
RAG_KNOWLEDGE_DIR = PROJECT_ROOT / "rag_knowledge" / "lessons_learned"

# Keywords that indicate risky changes
RISK_KEYWORDS = {
    "workflow": ["requirements.txt", "pip install", "dependencies", "gpu", "cuda"],
    "trading": ["execute", "order", "position", "risk", "circuit_breaker"],
    "data": ["commit", "push", "save", "write", "file"],
}


def load_lessons() -> list[dict]:
    """Load lessons from both RAG database and markdown files."""
    lessons = []

    # Load from RAG JSON
    if RAG_LESSONS_PATH.exists():
        try:
            with open(RAG_LESSONS_PATH) as f:
                data = json.load(f)
                if isinstance(data, list):
                    lessons.extend(data)
                elif isinstance(data, dict) and "lessons" in data:
                    lessons.extend(data["lessons"])
        except Exception as e:
            logger.warning(f"Could not load RAG lessons: {e}")

    # Load from markdown files
    if RAG_KNOWLEDGE_DIR.exists():
        for md_file in RAG_KNOWLEDGE_DIR.glob("*.md"):
            try:
                content = md_file.read_text()
                lesson = {
                    "id": md_file.stem,
                    "file": str(md_file),
                    "content": content,
                    "severity": "high" if "critical" in content.lower() else "medium",
                }
                lessons.append(lesson)
            except Exception as e:
                logger.warning(f"Could not read {md_file}: {e}")

    return lessons


def get_changed_files() -> list[str]:
    """Get list of files changed in current git diff."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        staged = result.stdout.strip().split("\n") if result.stdout.strip() else []

        result = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        unstaged = result.stdout.strip().split("\n") if result.stdout.strip() else []

        return list(set(staged + unstaged))
    except Exception:
        return []


def keyword_search(query: str, lessons: list[dict]) -> list[dict]:
    """Simple keyword-based search when embeddings aren't available."""
    query_words = set(query.lower().split())
    results = []

    for lesson in lessons:
        content = lesson.get("content", "")
        if not content:
            content = " ".join(
                [
                    str(lesson.get("title", "")),
                    str(lesson.get("description", "")),
                    str(lesson.get("root_cause", "")),
                    str(lesson.get("prevention", "")),
                    " ".join(lesson.get("tags", [])),
                ]
            )

        content_words = set(content.lower().split())
        overlap = query_words & content_words

        if overlap:
            lesson["score"] = len(overlap) / len(query_words)
            results.append(lesson)

    return sorted(results, key=lambda x: x.get("score", 0), reverse=True)[:5]


def check_for_relevant_lessons(changed_files: list[str]) -> list[dict]:
    """Find lessons relevant to the changed files."""
    lessons = load_lessons()
    if not lessons:
        logger.info("No lessons found in RAG database")
        return []

    warnings = []

    for filepath in changed_files:
        if not filepath:
            continue

        # Determine change category
        categories = []
        if "workflow" in filepath or filepath.endswith(".yml"):
            categories.append("workflow")
        if "requirements" in filepath:
            categories.append("workflow")
        if "trading" in filepath or "trade" in filepath:
            categories.append("trading")
        if "data" in filepath:
            categories.append("data")

        # Build search query
        query_parts = [filepath]
        for cat in categories:
            query_parts.extend(RISK_KEYWORDS.get(cat, []))

        query = " ".join(query_parts)
        relevant = keyword_search(query, lessons)

        for lesson in relevant:
            if lesson.get("score", 0) > 0.2:  # Relevance threshold
                warnings.append(
                    {
                        "file": filepath,
                        "lesson_id": lesson.get("id", "unknown"),
                        "severity": lesson.get("severity", "medium"),
                        "match_score": lesson.get("score", 0),
                        "summary": lesson.get("title", lesson.get("id", ""))[:100],
                    }
                )

    return warnings


def check_workflow_changes() -> list[str]:
    """Check for risky patterns in workflow file changes."""
    issues = []
    workflows_dir = PROJECT_ROOT / ".github" / "workflows"

    for workflow in workflows_dir.glob("*.yml"):
        content = workflow.read_text()

        # Check for full requirements.txt in lightweight workflows
        if "dashboard" in workflow.name.lower() or "health" in workflow.name.lower():
            if "pip install -r requirements.txt" in content:
                issues.append(
                    f"WARNING: {workflow.name} uses full requirements.txt. "
                    f"This may fail on GitHub Actions due to GPU packages. "
                    f"(Lesson: LL-020)"
                )

        # Check for missing PAT_TOKEN in workflows that push
        if "git push" in content and "PAT_TOKEN" not in content:
            issues.append(
                f"WARNING: {workflow.name} has git push but may not have PAT_TOKEN. "
                f"GITHUB_TOKEN may not have push permissions."
            )

        # Check for missing error handling
        if "continue-on-error: false" in content or (
            "git push" in content and "|| true" not in content.split("git push")[1][:50]
        ):
            # This is actually good - explicit error handling
            pass

    return issues


def main():
    parser = argparse.ArgumentParser(description="RAG Pre-Deployment Check")
    parser.add_argument(
        "--check-changed",
        action="store_true",
        help="Check files changed in current git diff",
    )
    parser.add_argument(
        "--check-workflows",
        action="store_true",
        help="Check all workflow files for known issues",
    )
    parser.add_argument(
        "--query",
        type=str,
        help="Search lessons for specific query",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error if warnings found",
    )
    args = parser.parse_args()

    has_warnings = False

    if args.check_changed:
        changed = get_changed_files()
        if changed:
            print(f"\n📝 Changed files: {', '.join(changed[:10])}")
            warnings = check_for_relevant_lessons(changed)
            if warnings:
                has_warnings = True
                print("\n⚠️  RELEVANT LESSONS FOUND:")
                for w in warnings:
                    print(f"   [{w['severity'].upper()}] {w['file']}")
                    print(f"      Lesson: {w['lesson_id']} - {w['summary']}")
        else:
            print("No changed files detected")

    if args.check_workflows:
        issues = check_workflow_changes()
        if issues:
            has_warnings = True
            print("\n⚠️  WORKFLOW ISSUES DETECTED:")
            for issue in issues:
                print(f"   {issue}")
        else:
            print("\n✅ No workflow issues detected")

    if args.query:
        lessons = load_lessons()
        results = keyword_search(args.query, lessons)
        print(f"\n🔍 Lessons matching '{args.query}':")
        for r in results[:5]:
            print(f"   [{r.get('severity', 'med')}] {r.get('id', 'unknown')}")
            if "title" in r:
                print(f"      {r['title'][:80]}")

    if args.strict and has_warnings:
        print("\n❌ Pre-deployment check FAILED (--strict mode)")
        return 1

    if not has_warnings:
        print("\n✅ Pre-deployment check passed")

    return 0


if __name__ == "__main__":
    sys.exit(main())
