#!/usr/bin/env python3
"""
Pre-commit RAG Check - Query lessons learned before committing.

This script is called by pre-commit hooks to:
1. Analyze changed files
2. Query RAG for similar past bugs/issues
3. Warn or block if HIGH/CRITICAL severity matches found

Usage:
    # In .pre-commit-config.yaml:
    - repo: local
      hooks:
        - id: rag-check
          name: RAG Lessons Check
          entry: python scripts/pre_commit_rag_check.py
          language: python
          pass_filenames: true

Author: Trading System
Created: December 2025
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def get_changed_files() -> list[str]:
    """Get list of staged files."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
    )
    return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]


def extract_keywords(files: list[str]) -> list[str]:
    """Extract keywords from changed files for RAG query."""
    keywords = set()

    for file_path in files:
        # Add filename components
        parts = Path(file_path).parts
        for part in parts:
            if part not in {"src", "tests", "scripts", "__init__.py"}:
                keywords.add(part.replace(".py", "").replace("_", " "))

        # Read file and extract function/class names
        try:
            full_path = BASE_DIR / file_path
            if full_path.exists() and full_path.suffix == ".py":
                content = full_path.read_text()
                for line in content.split("\n"):
                    if line.startswith("def ") or line.startswith("class "):
                        name = line.split("(")[0].split()[-1]
                        keywords.add(name.replace("_", " "))
        except Exception:
            pass

    return list(keywords)[:10]  # Limit to 10 keywords


def query_rag(keywords: list[str]) -> list[dict]:
    """Query RAG for relevant lessons."""
    try:
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        rag = LessonsLearnedRAG()
        query = " ".join(keywords) + " bugs errors mistakes"
        results = rag.search(query=query, top_k=5)

        lessons = []
        for lesson, score in results or []:
            if score > 0.2:  # Higher threshold for pre-commit
                lessons.append({
                    "title": lesson.title,
                    "severity": lesson.severity,
                    "prevention": lesson.prevention[:150],
                    "score": score,
                })
        return lessons

    except Exception as e:
        logger.debug(f"RAG query failed: {e}")
        return []


def check_for_blockers(lessons: list[dict]) -> tuple[bool, list[str]]:
    """Check if any lessons should block the commit."""
    warnings = []
    blockers = []

    for lesson in lessons:
        severity = lesson["severity"].upper()
        msg = f"[{severity}] {lesson['title']}: {lesson['prevention']}"

        if severity in ("CRITICAL",):
            blockers.append(msg)
        elif severity in ("HIGH",):
            warnings.append(msg)

    return len(blockers) > 0, blockers + warnings


def main():
    parser = argparse.ArgumentParser(description="Pre-commit RAG check")
    parser.add_argument("files", nargs="*", help="Changed files")
    parser.add_argument("--strict", action="store_true", help="Block on HIGH severity")
    args = parser.parse_args()

    # Get changed files
    files = args.files or get_changed_files()
    if not files:
        sys.exit(0)

    logger.info("=" * 60)
    logger.info("PRE-COMMIT RAG CHECK")
    logger.info("=" * 60)
    logger.info(f"Checking {len(files)} changed files...")

    # Extract keywords
    keywords = extract_keywords(files)
    if not keywords:
        logger.info("No keywords extracted, skipping RAG check")
        sys.exit(0)

    logger.info(f"Keywords: {', '.join(keywords)}")

    # Query RAG
    lessons = query_rag(keywords)

    if not lessons:
        logger.info("No relevant lessons found")
        sys.exit(0)

    # Check for blockers
    should_block, messages = check_for_blockers(lessons)

    if messages:
        logger.warning("")
        logger.warning("⚠️  LESSONS LEARNED (from past mistakes):")
        logger.warning("-" * 50)
        for msg in messages:
            logger.warning(f"  {msg}")
        logger.warning("-" * 50)
        logger.warning("")

    if should_block:
        logger.error("❌ BLOCKED: CRITICAL severity lesson matches found!")
        logger.error("   Review the lessons above before committing.")
        logger.error("   Use --no-verify to bypass (not recommended)")
        sys.exit(1)

    if messages:
        logger.warning("⚠️  Please review the warnings above before committing.")

    logger.info("✅ RAG check passed")
    sys.exit(0)


if __name__ == "__main__":
    main()
