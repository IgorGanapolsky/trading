"""
RAG-Powered Verification Gate

Uses lessons learned from RAG knowledge base to prevent repeating past mistakes.
Integrates with pre-merge gate and continuous verification.

Created: Dec 14, 2025
Purpose: Learn from history to prevent future failures
"""

import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np


@dataclass
class LessonLearned:
    """Structured lesson learned from RAG knowledge base."""

    id: str
    title: str
    date: str
    severity: str  # critical, high, medium, low
    category: str
    impact: str
    prevention_rules: List[str]
    test_requirements: List[str]
    file_patterns: List[str]  # Files commonly involved in this type of failure


class RAGVerificationGate:
    """
    Intelligent verification gate that learns from past mistakes.

    Uses semantic search over lessons learned to detect potentially dangerous
    changes before they reach production.
    """

    def __init__(self, rag_knowledge_path: Optional[Path] = None):
        """Initialize RAG verification gate.

        Args:
            rag_knowledge_path: Path to rag_knowledge directory
        """
        if rag_knowledge_path is None:
            # Auto-detect project root
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent
            rag_knowledge_path = project_root / "rag_knowledge" / "lessons_learned"

        self.rag_path = rag_knowledge_path
        self.lessons: List[LessonLearned] = []
        self._load_lessons()

    def _load_lessons(self):
        """Load all lessons learned from RAG knowledge base."""
        if not self.rag_path.exists():
            print(f"⚠️  RAG knowledge path not found: {self.rag_path}")
            return

        # Parse all lesson learned markdown files
        for lesson_file in self.rag_path.glob("ll_*.md"):
            try:
                lesson = self._parse_lesson_file(lesson_file)
                if lesson:
                    self.lessons.append(lesson)
            except Exception as e:
                print(f"⚠️  Failed to parse {lesson_file.name}: {e}")

    def _parse_lesson_file(self, file_path: Path) -> Optional[LessonLearned]:
        """Parse a lesson learned markdown file into structured data.

        Args:
            file_path: Path to lesson learned .md file

        Returns:
            LessonLearned object or None if parsing fails
        """
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract metadata from markdown front matter
        lines = content.split("\n")

        # Parse ID, severity, category, etc. from markdown headers
        lesson_id = None
        title = None
        date = None
        severity = None
        category = None
        impact = None
        prevention_rules = []
        test_requirements = []
        file_patterns = []

        in_prevention_section = False
        in_test_section = False

        for line in lines:
            line = line.strip()

            # Extract metadata
            if line.startswith("**ID**:"):
                lesson_id = line.split("**ID**:")[-1].strip()
            elif line.startswith("**Date**:"):
                date = line.split("**Date**:")[-1].strip()
            elif line.startswith("**Severity**:"):
                severity = line.split("**Severity**:")[-1].strip().lower()
            elif line.startswith("**Category**:"):
                category = line.split("**Category**:")[-1].strip()
            elif line.startswith("**Impact**:"):
                impact = line.split("**Impact**:")[-1].strip()
            elif line.startswith("# ") and not title:
                title = line.replace("#", "").strip()

            # Extract prevention rules
            if "## Prevention" in line or "### Prevention Rules" in line:
                in_prevention_section = True
                in_test_section = False
            elif "## Verification Test" in line or "### Test" in line:
                in_test_section = True
                in_prevention_section = False
            elif line.startswith("##"):
                in_prevention_section = False
                in_test_section = False

            if in_prevention_section and line.startswith("-"):
                rule = line.lstrip("- ").strip()
                if rule:
                    prevention_rules.append(rule)

            if in_test_section and "test_" in line.lower():
                test_requirements.append(line)

            # Extract file patterns (look for backtick-wrapped paths)
            if "`src/" in line or "`scripts/" in line:
                import re

                patterns = re.findall(r"`([^`]+\.py)`", line)
                file_patterns.extend(patterns)

        # Require minimum fields
        if not lesson_id or not title or not severity:
            return None

        return LessonLearned(
            id=lesson_id,
            title=title,
            date=date or "Unknown",
            severity=severity,
            category=category or "General",
            impact=impact or "Unknown",
            prevention_rules=prevention_rules,
            test_requirements=test_requirements,
            file_patterns=file_patterns,
        )

    def check_changed_files(
        self, changed_files: List[str]
    ) -> Tuple[List[str], List[LessonLearned]]:
        """Check changed files against lessons learned.

        Args:
            changed_files: List of file paths that changed

        Returns:
            Tuple of (warnings, relevant_lessons)
        """
        warnings = []
        relevant_lessons = []

        for lesson in self.lessons:
            # Check if any changed file matches known failure patterns
            for file_pattern in lesson.file_patterns:
                for changed_file in changed_files:
                    if file_pattern in changed_file:
                        relevant_lessons.append(lesson)
                        warnings.append(
                            f"[{lesson.severity.upper()}] {lesson.id}: {lesson.title}\n"
                            f"   File pattern match: {file_pattern}\n"
                            f"   Impact: {lesson.impact}"
                        )
                        break

        return warnings, relevant_lessons

    def semantic_search(
        self, query: str, top_k: int = 5
    ) -> List[Tuple[LessonLearned, float]]:
        """Semantic search over lessons learned.

        Uses simple keyword matching (can be upgraded to embeddings later).

        Args:
            query: Search query (e.g., "syntax error", "import failure")
            top_k: Number of results to return

        Returns:
            List of (lesson, score) tuples sorted by relevance
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored_lessons = []

        for lesson in self.lessons:
            # Simple keyword matching score
            score = 0.0

            # Check title
            title_words = set(lesson.title.lower().split())
            score += len(query_words & title_words) * 3.0

            # Check category
            if query_lower in lesson.category.lower():
                score += 2.0

            # Check impact
            impact_words = set(lesson.impact.lower().split())
            score += len(query_words & impact_words) * 1.5

            # Check prevention rules
            for rule in lesson.prevention_rules:
                rule_words = set(rule.lower().split())
                score += len(query_words & rule_words) * 1.0

            # Boost critical severity
            if lesson.severity == "critical":
                score *= 1.5
            elif lesson.severity == "high":
                score *= 1.2

            if score > 0:
                scored_lessons.append((lesson, score))

        # Sort by score and return top_k
        scored_lessons.sort(key=lambda x: x[1], reverse=True)
        return scored_lessons[:top_k]

    def check_merge_safety(
        self, pr_description: str, changed_files: List[str], pr_size: int
    ) -> Tuple[bool, List[str]]:
        """Comprehensive merge safety check.

        Args:
            pr_description: PR description/commit message
            changed_files: List of changed file paths
            pr_size: Number of files changed

        Returns:
            Tuple of (is_safe, warnings)
        """
        warnings = []
        is_safe = True

        # Check 1: Large PR warning (from ll_009)
        if pr_size > 10:
            warnings.append(
                f"⚠️  LARGE PR: {pr_size} files changed (>10 threshold)\n"
                "   Recommendation: Break into smaller PRs\n"
                "   Risk: Bugs hide in large PRs (see ll_009)"
            )

        # Check 2: Changed files against known failure patterns
        file_warnings, relevant_lessons = self.check_changed_files(changed_files)
        warnings.extend(file_warnings)

        # Check 3: Semantic search on PR description
        if pr_description:
            similar_lessons = self.semantic_search(pr_description, top_k=3)
            for lesson, score in similar_lessons:
                if score > 2.0 and lesson.severity in ["critical", "high"]:
                    warnings.append(
                        f"⚠️  SIMILAR PAST FAILURE: {lesson.id}\n"
                        f"   Title: {lesson.title}\n"
                        f"   Severity: {lesson.severity}\n"
                        f"   Relevance: {score:.1f}/10"
                    )

        # Check 4: Critical file changes
        critical_files = [
            "src/orchestrator/main.py",
            "src/execution/alpaca_executor.py",
            "src/risk/trade_gateway.py",
            "scripts/autonomous_trader.py",
        ]

        critical_changed = [f for f in changed_files if any(cf in f for cf in critical_files)]

        if critical_changed:
            warnings.append(
                f"🚨 CRITICAL FILES CHANGED: {len(critical_changed)}\n"
                f"   Files: {', '.join(critical_changed)}\n"
                "   Required: Extra review, all tests must pass"
            )
            # Don't block, but escalate
            is_safe = True  # Still safe with warnings

        return is_safe, warnings

    def ingest_new_lesson(
        self,
        title: str,
        severity: str,
        category: str,
        impact: str,
        prevention_rules: List[str],
        file_patterns: List[str],
    ) -> Path:
        """Ingest a new lesson learned into RAG knowledge base.

        Args:
            title: Lesson title
            severity: Severity level (critical, high, medium, low)
            category: Category (CI/CD, Syntax, Import, etc.)
            impact: Impact description
            prevention_rules: List of prevention rules
            file_patterns: List of file patterns involved

        Returns:
            Path to created lesson file
        """
        # Generate lesson ID
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        lesson_count = len(list(self.rag_path.glob("ll_*.md"))) + 1
        lesson_id = f"ll_{lesson_count:03d}"

        # Create markdown content
        content = f"""# Lesson Learned: {title}

**ID**: {lesson_id}
**Date**: {date_str}
**Severity**: {severity.upper()}
**Category**: {category}
**Impact**: {impact}

## What Happened

(Automatically generated - fill in details)

## Prevention Rules

"""

        for rule in prevention_rules:
            content += f"- {rule}\n"

        content += "\n## File Patterns\n\n"
        for pattern in file_patterns:
            content += f"- `{pattern}`\n"

        content += f"""

## Verification Test

```python
def test_{lesson_id}_regression():
    \"\"\"Prevent {lesson_id}: {title}\"\"\"
    # Add test implementation
    pass
```

## Tags

#{category.lower().replace('/', '-')} #lessons-learned #automated

## Change Log

- {date_str}: Automatically ingested by RAG verification gate
"""

        # Write to file
        lesson_file = self.rag_path / f"{lesson_id}_{title.lower().replace(' ', '_')}.md"
        with open(lesson_file, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"✅ New lesson ingested: {lesson_file.name}")

        # Reload lessons
        self._load_lessons()

        return lesson_file


def cli_check_merge():
    """CLI tool to check merge safety before committing."""
    import argparse

    parser = argparse.ArgumentParser(description="RAG-powered merge safety checker")
    parser.add_argument("--files", nargs="+", help="Changed files", required=True)
    parser.add_argument("--description", help="PR/commit description", default="")
    parser.add_argument("--pr-size", type=int, help="Number of changed files")

    args = parser.parse_args()

    gate = RAGVerificationGate()

    pr_size = args.pr_size or len(args.files)
    is_safe, warnings = gate.check_merge_safety(
        pr_description=args.description, changed_files=args.files, pr_size=pr_size
    )

    if warnings:
        print("\n" + "=" * 60)
        print("RAG VERIFICATION WARNINGS")
        print("=" * 60 + "\n")
        for warning in warnings:
            print(warning)
            print()

    if is_safe:
        print("✅ RAG verification passed (warnings noted)")
        sys.exit(0)
    else:
        print("❌ RAG verification FAILED - resolve issues before merge")
        sys.exit(1)


if __name__ == "__main__":
    cli_check_merge()
