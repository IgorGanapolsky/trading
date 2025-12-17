#!/usr/bin/env python3
"""
RAG Pre-Merge Validator

Queries the lessons learned database before merges to prevent repeated failures.
Integrates with ML pipeline for pattern detection.

Usage:
    python -m src.verification.rag_premerge_validator --diff "path/to/diff"
    python -m src.verification.rag_premerge_validator --files "src/orchestrator/main.py"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class LessonMatch:
    """A match between a change and a lesson learned."""

    lesson_id: str
    lesson_file: str
    match_reason: str
    severity: str
    confidence: float  # 0.0 to 1.0


@dataclass
class ValidationResult:
    """Result of RAG pre-merge validation."""

    passed: bool
    warnings: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    lesson_matches: list[LessonMatch] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "warnings": self.warnings,
            "blockers": self.blockers,
            "lesson_matches": [
                {
                    "lesson_id": m.lesson_id,
                    "lesson_file": m.lesson_file,
                    "match_reason": m.match_reason,
                    "severity": m.severity,
                    "confidence": m.confidence,
                }
                for m in self.lesson_matches
            ],
            "recommendations": self.recommendations,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }


class RAGPreMergeValidator:
    """Validates changes against RAG lessons learned database."""

    LESSONS_DIR = Path("rag_knowledge/lessons_learned")

    # Known failure patterns from lessons learned
    FAILURE_PATTERNS = [
        {
            "pattern": r"(import|from)\s+.*\s+import",
            "lesson_id": "ll_009",
            "reason": "Import structure change - verify syntax",
            "severity": "MEDIUM",
        },
        {
            "pattern": r"def\s+(execute|trade|submit_order)",
            "lesson_id": "ll_009",
            "reason": "Trading execution function changed",
            "severity": "HIGH",
        },
        {
            "pattern": r"class\s+TradingOrchestrator",
            "lesson_id": "ll_009",
            "reason": "Core orchestrator modified - run full import test",
            "severity": "CRITICAL",
        },
        {
            "pattern": r"(CircuitBreaker|KillSwitch|RiskManager)",
            "lesson_id": "ll_013",
            "reason": "Safety system modified",
            "severity": "CRITICAL",
        },
        {
            "pattern": r"\.github/workflows/.*\.yml",
            "lesson_id": "ll_009",
            "reason": "CI workflow modified - verify YAML syntax",
            "severity": "HIGH",
        },
    ]

    # High-risk file patterns
    HIGH_RISK_FILES = [
        "src/orchestrator/main.py",
        "src/execution/alpaca_executor.py",
        "src/risk/trade_gateway.py",
        "src/safety/circuit_breakers.py",
        "src/safety/kill_switch.py",
    ]

    def __init__(self):
        self.lessons = self._load_lessons()

    def _load_lessons(self) -> list[dict[str, Any]]:
        """Load all lessons learned files."""
        lessons = []
        if not self.LESSONS_DIR.exists():
            return lessons

        for md_file in self.LESSONS_DIR.glob("*.md"):
            content = md_file.read_text()
            lesson = {
                "file": md_file.name,
                "content": content,
                "id": self._extract_field(content, "ID"),
                "severity": self._extract_field(content, "Severity"),
                "category": self._extract_field(content, "Category"),
                "tags": self._extract_tags(content),
            }
            lessons.append(lesson)

        return lessons

    def _extract_field(self, content: str, field: str) -> str:
        """Extract a field value from markdown content."""
        match = re.search(rf"\*\*{field}\*\*:\s*(.+)", content)
        return match.group(1).strip() if match else "unknown"

    def _extract_tags(self, content: str) -> list[str]:
        """Extract tags from markdown content."""
        match = re.search(r"## Tags\s*\n\s*(#[\w\s#-]+)", content)
        if match:
            return [t.strip() for t in match.group(1).split("#") if t.strip()]
        return []

    def validate_files(self, files: list[str]) -> ValidationResult:
        """Validate a list of changed files."""
        result = ValidationResult(passed=True)

        for file_path in files:
            # Check against high-risk files
            if file_path in self.HIGH_RISK_FILES:
                result.warnings.append(f"HIGH RISK: {file_path} is a critical system file")
                result.recommendations.append(
                    f'Run: python3 -c "from {file_path.replace("/", ".").replace(".py", "")} import *"'
                )

            # Check against failure patterns
            for pattern_info in self.FAILURE_PATTERNS:
                if re.search(pattern_info["pattern"], file_path):
                    match = LessonMatch(
                        lesson_id=pattern_info["lesson_id"],
                        lesson_file=f"{pattern_info['lesson_id']}_*.md",
                        match_reason=pattern_info["reason"],
                        severity=pattern_info["severity"],
                        confidence=0.7,
                    )
                    result.lesson_matches.append(match)

                    if pattern_info["severity"] == "CRITICAL":
                        result.blockers.append(
                            f"CRITICAL: {file_path} - {pattern_info['reason']} (see {pattern_info['lesson_id']})"
                        )
                        result.passed = False
                    else:
                        result.warnings.append(
                            f"{pattern_info['severity']}: {file_path} - {pattern_info['reason']}"
                        )

        # Check file count (ll_009 lesson)
        if len(files) > 10:
            result.warnings.append(
                f"Large PR: {len(files)} files changed (> 10 threshold from ll_009)"
            )
            result.recommendations.append("Consider splitting into smaller PRs")

        return result

    def validate_diff(self, diff_content: str) -> ValidationResult:
        """Validate a diff string."""
        result = ValidationResult(passed=True)

        # Extract changed files from diff
        file_patterns = re.findall(r"(?:^|\n)(?:\+\+\+|---)\s+[ab]/(.+)", diff_content)
        files = list(set(file_patterns))

        # Validate files
        file_result = self.validate_files(files)
        result.warnings.extend(file_result.warnings)
        result.blockers.extend(file_result.blockers)
        result.lesson_matches.extend(file_result.lesson_matches)
        result.recommendations.extend(file_result.recommendations)

        if file_result.blockers:
            result.passed = False

        # Check diff content against patterns
        for pattern_info in self.FAILURE_PATTERNS:
            if re.search(pattern_info["pattern"], diff_content):
                match = LessonMatch(
                    lesson_id=pattern_info["lesson_id"],
                    lesson_file=f"{pattern_info['lesson_id']}_*.md",
                    match_reason=pattern_info["reason"],
                    severity=pattern_info["severity"],
                    confidence=0.8,
                )
                result.lesson_matches.append(match)

                if pattern_info["severity"] == "CRITICAL":
                    result.warnings.append(
                        f"PATTERN MATCH: {pattern_info['reason']} ({pattern_info['lesson_id']})"
                    )

        # Check for large deletions (ll_009 lesson)
        deletions = len(re.findall(r"^-[^-]", diff_content, re.MULTILINE))
        if deletions > 100:
            result.warnings.append(
                f"Large deletion: {deletions} lines removed (review for regressions)"
            )

        return result

    def query_lessons(self, keywords: list[str]) -> list[dict[str, Any]]:
        """Query lessons learned by keywords."""
        matches = []

        for lesson in self.lessons:
            # Check tags
            for keyword in keywords:
                if keyword.lower() in [t.lower() for t in lesson["tags"]]:
                    matches.append(lesson)
                    break
                # Check content
                if keyword.lower() in lesson["content"].lower():
                    matches.append(lesson)
                    break

        return matches


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RAG Pre-Merge Validator")
    parser.add_argument(
        "--files",
        type=str,
        nargs="+",
        help="List of changed files to validate",
    )
    parser.add_argument(
        "--diff",
        type=str,
        help="Path to diff file or '-' for stdin",
    )
    parser.add_argument(
        "--query",
        type=str,
        nargs="+",
        help="Query lessons learned by keywords",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    validator = RAGPreMergeValidator()

    if args.query:
        lessons = validator.query_lessons(args.query)
        if args.json:
            print(
                json.dumps(
                    [
                        {"file": lesson["file"], "id": lesson["id"], "severity": lesson["severity"]}
                        for lesson in lessons
                    ],
                    indent=2,
                )
            )
        else:
            print(f"Found {len(lessons)} matching lessons:")
            for lesson in lessons:
                print(f"  - {lesson['file']} ({lesson['severity']})")
        return

    if args.files:
        result = validator.validate_files(args.files)
    elif args.diff:
        if args.diff == "-":
            diff_content = sys.stdin.read()
        else:
            diff_content = Path(args.diff).read_text()
        result = validator.validate_diff(diff_content)
    else:
        print("Provide --files or --diff")
        sys.exit(1)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print("=" * 60)
        print("RAG PRE-MERGE VALIDATION RESULT")
        print("=" * 60)

        if result.passed:
            print("\n✅ PASSED\n")
        else:
            print("\n❌ BLOCKED\n")

        if result.blockers:
            print("BLOCKERS:")
            for blocker in result.blockers:
                print(f"  ❌ {blocker}")
            print()

        if result.warnings:
            print("WARNINGS:")
            for warning in result.warnings:
                print(f"  ⚠️  {warning}")
            print()

        if result.lesson_matches:
            print("RELATED LESSONS:")
            for match in result.lesson_matches:
                print(f"  📚 {match.lesson_id}: {match.match_reason}")
            print()

        if result.recommendations:
            print("RECOMMENDATIONS:")
            for rec in result.recommendations:
                print(f"  💡 {rec}")

    sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
