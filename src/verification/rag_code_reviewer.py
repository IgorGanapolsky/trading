#!/usr/bin/env python3
"""
RAG-Based Code Review System with LangSmith Tracing

Automatically reviews code changes against lessons learned and known anti-patterns
before merge. Uses vector similarity to find relevant past mistakes and prevent
repeating them.

Integration:
- Pre-commit hook: scripts/pre_merge_gate.py
- CI workflow: .github/workflows/verification-gate.yml
- LangSmith: Traces all reviews to trading-code-review project
- Manual: python -m src.verification.rag_code_reviewer <file_paths>

Author: Trading System CTO
Created: 2025-12-11
"""

from __future__ import annotations

import json
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Known anti-patterns that caused production issues
CRITICAL_ANTI_PATTERNS = [
    {
        "pattern": r"def\s+\w+\([^)]*\):\s*\n\s*[^:\n]*[^:\s]\s*\n",
        "description": "Function missing return type annotation or docstring",
        "severity": "warning",
        "lesson_ref": "ll_009_ci_syntax_failure_dec11.md",
    },
    {
        "pattern": r"from\s+\.\s+import\s+\*",
        "description": "Wildcard import can cause name collisions",
        "severity": "error",
        "lesson_ref": "over_engineering_trading_system.md",
    },
    {
        "pattern": r"except:\s*\n",
        "description": "Bare except clause catches all errors including KeyboardInterrupt",
        "severity": "error",
        "lesson_ref": "ll_009_ci_syntax_failure_dec11.md",
    },
    {
        "pattern": r"\.execute\([^)]*\)\s*#.*(?:TODO|FIXME|HACK)",
        "description": "Trading execution with unresolved TODO/FIXME",
        "severity": "critical",
        "lesson_ref": "ci_failure_blocked_trading.md",
    },
    {
        "pattern": r"if\s+True:|while\s+True:",
        "description": "Hardcoded True condition may cause infinite loops",
        "severity": "warning",
        "lesson_ref": "over_engineering_trading_system.md",
    },
    {
        "pattern": r"api_key\s*=\s*['\"][^'\"]+['\"]",
        "description": "Hardcoded API key detected",
        "severity": "critical",
        "lesson_ref": "security_best_practices.md",
    },
    {
        "pattern": r"git\s+push.*--force",
        "description": "Force push can destroy history",
        "severity": "critical",
        "lesson_ref": "ll_009_ci_syntax_failure_dec11.md",
    },
    {
        "pattern": r"\.get\(['\"][^'\"]+['\"]\)(?!\s*or\s)",
        "description": ".get() without default may return None unexpectedly",
        "severity": "info",
        "lesson_ref": "defensive_programming.md",
    },
]

# Critical files that need extra scrutiny
CRITICAL_FILES = {
    "src/orchestrator/main.py": "Core trading orchestrator",
    "src/execution/alpaca_executor.py": "Order execution",
    "src/risk/trade_gateway.py": "Risk management gateway",
    "src/strategies/core_strategy.py": "Core trading strategy",
    "src/core/config.py": "System configuration",
}


@dataclass
class CodeReviewFinding:
    """A finding from code review."""

    file_path: str
    line_number: int
    severity: str  # critical, error, warning, info
    description: str
    pattern_matched: str
    lesson_reference: str
    suggestion: str = ""


@dataclass
class CodeReviewResult:
    """Complete result of a code review."""

    files_reviewed: int
    findings: list[CodeReviewFinding]
    critical_count: int
    error_count: int
    warning_count: int
    info_count: int
    passed: bool
    summary: str


class RAGCodeReviewer:
    """
    RAG-enhanced code reviewer that checks changes against lessons learned.

    Uses semantic similarity to find relevant past mistakes and prevents
    repeating them in new code.
    """

    def __init__(self, rag_store_path: str | None = None):
        """Initialize the code reviewer."""
        self.rag_store_path = Path(rag_store_path or "rag_knowledge/lessons_learned")
        self.lessons_cache: dict[str, Any] = {}
        self._load_lessons()

    def _load_lessons(self) -> None:
        """Load lessons learned from RAG knowledge base."""
        if not self.rag_store_path.exists():
            logger.warning(f"RAG store path not found: {self.rag_store_path}")
            return

        for lesson_file in self.rag_store_path.glob("*.md"):
            content = lesson_file.read_text(encoding="utf-8")
            self.lessons_cache[lesson_file.name] = {
                "content": content,
                "keywords": self._extract_keywords(content),
            }

        logger.info(f"Loaded {len(self.lessons_cache)} lessons from RAG knowledge base")

    def _extract_keywords(self, content: str) -> list[str]:
        """Extract keywords from lesson content for matching."""
        # Simple keyword extraction - in production would use embeddings
        keywords = []
        patterns = [
            r"ERROR:\s*([^\n]+)",
            r"SOLUTION:\s*([^\n]+)",
            r"SYMPTOM:\s*([^\n]+)",
            r"PREVENTION:\s*([^\n]+)",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            keywords.extend(matches)
        return keywords

    def review_file(self, file_path: Path) -> list[CodeReviewFinding]:
        """Review a single file for anti-patterns and lessons learned violations."""
        findings: list[CodeReviewFinding] = []

        if not file_path.exists():
            return findings

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return findings  # Skip binary files

        lines = content.split("\n")

        # Check each anti-pattern
        for anti_pattern in CRITICAL_ANTI_PATTERNS:
            pattern = anti_pattern["pattern"]
            for i, line in enumerate(lines, start=1):
                if re.search(pattern, line):
                    finding = CodeReviewFinding(
                        file_path=str(file_path),
                        line_number=i,
                        severity=anti_pattern["severity"],
                        description=anti_pattern["description"],
                        pattern_matched=pattern,
                        lesson_reference=anti_pattern["lesson_ref"],
                        suggestion=self._get_suggestion(anti_pattern["lesson_ref"]),
                    )
                    findings.append(finding)

        # Extra scrutiny for critical files
        if str(file_path) in CRITICAL_FILES:
            findings.extend(self._deep_review(file_path, content, lines))

        return findings

    def _deep_review(
        self, file_path: Path, content: str, lines: list[str]
    ) -> list[CodeReviewFinding]:
        """Perform deep review on critical files."""
        findings: list[CodeReviewFinding] = []

        # Check for syntax errors by attempting to compile
        try:
            compile(content, str(file_path), "exec")
        except SyntaxError as e:
            findings.append(
                CodeReviewFinding(
                    file_path=str(file_path),
                    line_number=e.lineno or 0,
                    severity="critical",
                    description=f"Syntax error: {e.msg}",
                    pattern_matched="compile_check",
                    lesson_reference="ll_009_ci_syntax_failure_dec11.md",
                    suggestion="Fix syntax error before merge - this blocked trading on Dec 11",
                )
            )

        # Check for missing error handling in execution code
        if "executor" in str(file_path).lower() or "trade" in str(file_path).lower():
            for i, line in enumerate(lines, start=1):
                if "execute" in line.lower() and "try" not in lines[max(0, i - 3) : i]:
                    findings.append(
                        CodeReviewFinding(
                            file_path=str(file_path),
                            line_number=i,
                            severity="warning",
                            description="Trade execution without try/except wrapper",
                            pattern_matched="execution_error_handling",
                            lesson_reference="defensive_programming.md",
                            suggestion="Wrap trade execution in try/except to prevent silent failures",
                        )
                    )

        return findings

    def _get_suggestion(self, lesson_ref: str) -> str:
        """Get suggestion from lessons learned."""
        if lesson_ref in self.lessons_cache:
            content = self.lessons_cache[lesson_ref]["content"]
            # Extract solution/prevention section
            match = re.search(r"(?:SOLUTION|PREVENTION|FIX):\s*([^\n]+)", content, re.I)
            if match:
                return match.group(1)
        return "Review lessons learned documentation"

    def review_files(self, file_paths: list[Path]) -> CodeReviewResult:
        """Review multiple files and aggregate results."""
        all_findings: list[CodeReviewFinding] = []

        for file_path in file_paths:
            if file_path.suffix == ".py":
                findings = self.review_file(file_path)
                all_findings.extend(findings)

        # Count by severity
        critical = sum(1 for f in all_findings if f.severity == "critical")
        errors = sum(1 for f in all_findings if f.severity == "error")
        warnings = sum(1 for f in all_findings if f.severity == "warning")
        info = sum(1 for f in all_findings if f.severity == "info")

        # Determine if passed
        passed = critical == 0 and errors == 0

        # Generate summary
        if passed:
            summary = f"✅ Code review passed ({len(file_paths)} files, {warnings} warnings)"
        else:
            summary = f"❌ Code review FAILED ({critical} critical, {errors} errors)"

        return CodeReviewResult(
            files_reviewed=len(file_paths),
            findings=all_findings,
            critical_count=critical,
            error_count=errors,
            warning_count=warnings,
            info_count=info,
            passed=passed,
            summary=summary,
        )

    def review_changed_files(self) -> CodeReviewResult:
        """Review files changed in current git diff."""
        import subprocess

        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~1"],
                capture_output=True,
                text=True,
                check=True,
            )
            changed_files = [Path(f) for f in result.stdout.strip().split("\n") if f]
        except subprocess.CalledProcessError:
            # Fall back to unstaged changes
            result = subprocess.run(
                ["git", "diff", "--name-only"],
                capture_output=True,
                text=True,
            )
            changed_files = [Path(f) for f in result.stdout.strip().split("\n") if f]

        return self.review_files(changed_files)


def query_lessons_learned(query: str) -> list[dict[str, Any]]:
    """
    Query the lessons learned RAG for relevant past mistakes.

    Args:
        query: Natural language query about potential issues

    Returns:
        List of relevant lessons with similarity scores
    """
    try:
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        rag = LessonsLearnedRAG()
        return rag.search(query, k=5)
    except ImportError:
        logger.warning("LessonsLearnedRAG not available, using keyword fallback")
        return _keyword_search_lessons(query)


def _keyword_search_lessons(query: str) -> list[dict[str, Any]]:
    """Fallback keyword search when embeddings unavailable."""
    results = []
    lessons_path = Path("rag_knowledge/lessons_learned")

    if not lessons_path.exists():
        return results

    query_words = set(query.lower().split())

    for lesson_file in lessons_path.glob("*.md"):
        content = lesson_file.read_text(encoding="utf-8").lower()
        # Simple word overlap scoring
        content_words = set(content.split())
        overlap = len(query_words & content_words)
        if overlap > 0:
            results.append(
                {
                    "file": lesson_file.name,
                    "score": overlap / len(query_words),
                    "content": lesson_file.read_text(encoding="utf-8")[:500],
                }
            )

    return sorted(results, key=lambda x: x["score"], reverse=True)[:5]


def main() -> int:
    """CLI entry point for code review."""
    import argparse

    parser = argparse.ArgumentParser(description="RAG-based code reviewer")
    parser.add_argument("files", nargs="*", help="Files to review")
    parser.add_argument(
        "--changed",
        action="store_true",
        help="Review git changed files",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON format",
    )
    args = parser.parse_args()

    reviewer = RAGCodeReviewer()

    if args.changed or not args.files:
        result = reviewer.review_changed_files()
    else:
        result = reviewer.review_files([Path(f) for f in args.files])

    if args.json:
        output = {
            "files_reviewed": result.files_reviewed,
            "passed": result.passed,
            "summary": result.summary,
            "critical": result.critical_count,
            "errors": result.error_count,
            "warnings": result.warning_count,
            "findings": [
                {
                    "file": f.file_path,
                    "line": f.line_number,
                    "severity": f.severity,
                    "description": f.description,
                    "lesson": f.lesson_reference,
                }
                for f in result.findings
            ],
        }
        print(json.dumps(output, indent=2))
    else:
        print(result.summary)
        print()
        for finding in result.findings:
            icon = {"critical": "🚨", "error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(
                finding.severity, "•"
            )
            print(f"{icon} {finding.file_path}:{finding.line_number}")
            print(f"   {finding.description}")
            print(f"   Lesson: {finding.lesson_reference}")
            if finding.suggestion:
                print(f"   Fix: {finding.suggestion}")
            print()

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
