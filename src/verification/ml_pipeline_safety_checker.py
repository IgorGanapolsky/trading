#!/usr/bin/env python3
"""
ML Pipeline Safety Checker

Integrates RAG lessons learned with ML anomaly detection to prevent
repeated failures before they reach production.

Key Features:
1. Queries RAG for similar past failures before any merge
2. Uses ML pattern matching to detect high-risk changes
3. Provides confidence scores for merge decisions
4. Learns from new failures to improve future detection

Based on Dec 11, 2025 analysis: "We have to use our RAG and ML pipeline for lessons learned."

Usage:
    python -m src.verification.ml_pipeline_safety_checker --diff "path/to/diff"
    python -m src.verification.ml_pipeline_safety_checker --files "src/orchestrator/main.py"
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class FailurePattern:
    """A learned failure pattern from lessons learned."""

    pattern_id: str
    regex: str
    lesson_id: str
    severity: str
    description: str
    confidence: float
    times_triggered: int = 0
    false_positive_rate: float = 0.0


@dataclass
class SafetyCheckResult:
    """Result of ML pipeline safety check."""

    passed: bool
    confidence: float  # 0.0 to 1.0
    risk_score: float  # 0.0 to 100.0
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    matched_patterns: list[FailurePattern] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    rag_context: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "confidence": self.confidence,
            "risk_score": self.risk_score,
            "blockers": self.blockers,
            "warnings": self.warnings,
            "matched_patterns": [
                {
                    "pattern_id": p.pattern_id,
                    "lesson_id": p.lesson_id,
                    "severity": p.severity,
                    "description": p.description,
                    "confidence": p.confidence,
                }
                for p in self.matched_patterns
            ],
            "recommendations": self.recommendations,
            "rag_context": self.rag_context,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }


class MLPipelineSafetyChecker:
    """
    ML-powered safety checker that learns from past failures.

    Integrates:
    - RAG lessons learned database
    - ML anomaly detection patterns
    - Statistical pattern matching
    - Confidence-weighted decision making
    """

    LESSONS_DIR = Path("rag_knowledge/lessons_learned")
    PATTERNS_FILE = Path("data/ml_models/failure_patterns.json")

    # Default failure patterns (learned from ll_009, ll_013)
    DEFAULT_PATTERNS = [
        FailurePattern(
            pattern_id="fp_001",
            regex=r"from\s+[\w.]+\s+import\s+\*",
            lesson_id="ll_009",
            severity="MEDIUM",
            description="Wildcard import - may cause import errors",
            confidence=0.6,
        ),
        FailurePattern(
            pattern_id="fp_002",
            regex=r"class\s+TradingOrchestrator",
            lesson_id="ll_009",
            severity="HIGH",
            description="Core orchestrator modified - verify imports",
            confidence=0.8,
        ),
        FailurePattern(
            pattern_id="fp_003",
            regex=r"def\s+(execute|submit_order|trade)",
            lesson_id="ll_009",
            severity="HIGH",
            description="Trading execution function changed",
            confidence=0.7,
        ),
        FailurePattern(
            pattern_id="fp_004",
            regex=r"(CircuitBreaker|KillSwitch|RiskManager)",
            lesson_id="ll_013",
            severity="CRITICAL",
            description="Safety system modified - review carefully",
            confidence=0.9,
        ),
        FailurePattern(
            pattern_id="fp_005",
            regex=r"\.github/workflows/.*\.yml",
            lesson_id="ll_009",
            severity="HIGH",
            description="CI workflow modified - verify YAML syntax",
            confidence=0.85,
        ),
        FailurePattern(
            pattern_id="fp_006",
            regex=r"run:\s*\|[\s\S]*?python3?\s*<<",
            lesson_id="ll_009",
            severity="HIGH",
            description="Python heredoc in YAML - verify indentation",
            confidence=0.9,
        ),
        FailurePattern(
            pattern_id="fp_007",
            regex=r"except\s*:",
            lesson_id="ll_013",
            severity="MEDIUM",
            description="Bare except clause - may hide errors",
            confidence=0.65,
        ),
        FailurePattern(
            pattern_id="fp_008",
            regex=r"(sharpe|volatility).*=.*0",
            lesson_id="ll_sharpe",
            severity="HIGH",
            description="Sharpe/volatility may have division by zero",
            confidence=0.75,
        ),
    ]

    def __init__(self):
        self.patterns = self._load_patterns()
        self.lessons = self._load_lessons()

    def _load_patterns(self) -> list[FailurePattern]:
        """Load failure patterns from disk or use defaults."""
        if self.PATTERNS_FILE.exists():
            try:
                with open(self.PATTERNS_FILE) as f:
                    data = json.load(f)
                    return [FailurePattern(**p) for p in data.get("patterns", [])]
            except Exception as e:
                logger.warning(f"Failed to load patterns: {e}")
        return self.DEFAULT_PATTERNS.copy()

    def _save_patterns(self) -> None:
        """Save learned patterns to disk."""
        self.PATTERNS_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "patterns": [
                {
                    "pattern_id": p.pattern_id,
                    "regex": p.regex,
                    "lesson_id": p.lesson_id,
                    "severity": p.severity,
                    "description": p.description,
                    "confidence": p.confidence,
                    "times_triggered": p.times_triggered,
                    "false_positive_rate": p.false_positive_rate,
                }
                for p in self.patterns
            ],
            "last_updated": datetime.utcnow().isoformat() + "Z",
        }
        with open(self.PATTERNS_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def _load_lessons(self) -> list[dict[str, Any]]:
        """Load lessons learned from RAG knowledge base."""
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
                "root_cause": self._extract_section(content, "Root Cause"),
                "prevention": self._extract_section(content, "Prevention"),
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

    def _extract_section(self, content: str, section: str) -> str:
        """Extract a section's content from markdown."""
        pattern = rf"## {section}\s*\n([\s\S]*?)(?=\n## |\Z)"
        match = re.search(pattern, content)
        return match.group(1).strip() if match else ""

    def check_files(self, files: list[str]) -> SafetyCheckResult:
        """Check a list of files for safety issues."""
        result = SafetyCheckResult(passed=True, confidence=1.0, risk_score=0.0)

        for file_path in files:
            # Check file against patterns
            for pattern in self.patterns:
                if re.search(pattern.regex, file_path):
                    result.matched_patterns.append(pattern)
                    pattern.times_triggered += 1

                    if pattern.severity == "CRITICAL":
                        result.blockers.append(
                            f"CRITICAL: {file_path} matches {pattern.description} "
                            f"(lesson: {pattern.lesson_id}, confidence: {pattern.confidence:.0%})"
                        )
                        result.passed = False
                        result.risk_score += 30 * pattern.confidence
                    elif pattern.severity == "HIGH":
                        result.warnings.append(
                            f"HIGH: {file_path} matches {pattern.description} "
                            f"(lesson: {pattern.lesson_id})"
                        )
                        result.risk_score += 20 * pattern.confidence
                    else:
                        result.warnings.append(
                            f"{pattern.severity}: {file_path} - {pattern.description}"
                        )
                        result.risk_score += 10 * pattern.confidence

            # Check for high-risk file modifications
            high_risk_files = [
                "src/orchestrator/main.py",
                "src/execution/alpaca_executor.py",
                "src/risk/trade_gateway.py",
                "src/safety/circuit_breakers.py",
            ]
            if file_path in high_risk_files:
                result.warnings.append(f"HIGH RISK FILE: {file_path}")
                result.recommendations.append(
                    f'Run: python3 -c "from {file_path.replace("/", ".").replace(".py", "")} import *"'
                )
                result.risk_score += 15

        # Query RAG for similar issues
        rag_context = self._query_rag_for_context(files)
        result.rag_context = rag_context

        # Add RAG-based recommendations
        for context in rag_context:
            if context.get("prevention"):
                result.recommendations.append(
                    f"From {context['id']}: {context['prevention'][:100]}..."
                )

        # Calculate confidence based on pattern matches
        if result.matched_patterns:
            avg_confidence = sum(p.confidence for p in result.matched_patterns) / len(
                result.matched_patterns
            )
            result.confidence = 1.0 - (
                avg_confidence * 0.5
            )  # Higher match = lower confidence in safety

        # Clamp risk score
        result.risk_score = min(100.0, result.risk_score)

        # File count warning (ll_009)
        if len(files) > 10:
            result.warnings.append(f"Large change: {len(files)} files (threshold: 10 from ll_009)")
            result.recommendations.append("Consider splitting into smaller PRs")

        return result

    def check_diff(self, diff_content: str) -> SafetyCheckResult:
        """Check a diff for safety issues."""
        result = SafetyCheckResult(passed=True, confidence=1.0, risk_score=0.0)

        # Extract files from diff
        file_patterns = re.findall(r"(?:^|\n)(?:\+\+\+|---)\s+[ab]/(.+)", diff_content)
        files = list(set(file_patterns))

        # First check the files
        file_result = self.check_files(files)
        result.warnings.extend(file_result.warnings)
        result.blockers.extend(file_result.blockers)
        result.matched_patterns.extend(file_result.matched_patterns)
        result.recommendations.extend(file_result.recommendations)
        result.rag_context.extend(file_result.rag_context)
        result.risk_score += file_result.risk_score

        if file_result.blockers:
            result.passed = False

        # Check diff content against patterns
        for pattern in self.patterns:
            matches = re.findall(pattern.regex, diff_content)
            if matches:
                # Don't double-count file path matches
                for match in matches:
                    if match not in files:
                        if pattern not in result.matched_patterns:
                            result.matched_patterns.append(pattern)
                            pattern.times_triggered += 1

                        if pattern.severity == "CRITICAL":
                            result.warnings.append(
                                f"DIFF PATTERN: {pattern.description} (lesson: {pattern.lesson_id})"
                            )
                            result.risk_score += 25 * pattern.confidence
                        elif pattern.severity == "HIGH":
                            result.warnings.append(f"DIFF PATTERN: {pattern.description}")
                            result.risk_score += 15 * pattern.confidence

        # Check for large deletions
        deletions = len(re.findall(r"^-[^-]", diff_content, re.MULTILINE))
        if deletions > 100:
            result.warnings.append(f"Large deletion: {deletions} lines (review for regressions)")
            result.risk_score += 10

        # Check for YAML heredoc issues (ll_009 specific)
        if re.search(r"\.yml|\.yaml", str(files)):
            # Check for Python code in heredocs without proper indentation
            heredoc_pattern = r"run:\s*\|[\s\S]*?python3?\s*<<\s*['\"]?(\w+)['\"]?"
            if re.search(heredoc_pattern, diff_content):
                result.warnings.append(
                    "YAML heredoc with Python detected - verify indentation (ll_009)"
                )
                result.recommendations.append(
                    "Ensure Python code inside heredocs is properly indented"
                )
                result.risk_score += 20

        # Update confidence
        if result.matched_patterns:
            avg_confidence = sum(p.confidence for p in result.matched_patterns) / len(
                result.matched_patterns
            )
            result.confidence = 1.0 - (avg_confidence * 0.5)

        # Clamp risk score
        result.risk_score = min(100.0, result.risk_score)

        # Save updated pattern statistics
        self._save_patterns()

        return result

    def _query_rag_for_context(self, files: list[str]) -> list[dict[str, Any]]:
        """Query RAG for relevant lessons based on files being changed."""
        relevant_lessons = []

        # Keywords to look for based on file paths
        keywords = set()
        for file_path in files:
            parts = file_path.replace("/", " ").replace("_", " ").replace(".py", "").split()
            keywords.update(parts)

        # Also add common risk keywords
        risk_keywords = {"trading", "execution", "order", "safety", "circuit", "risk"}
        keywords.update(risk_keywords)

        for lesson in self.lessons:
            # Check if lesson is relevant
            lesson_text = (lesson["content"] + " " + " ".join(lesson["tags"])).lower()
            matches = sum(1 for kw in keywords if kw.lower() in lesson_text)

            if matches >= 2 or lesson["severity"] == "CRITICAL":
                relevant_lessons.append(
                    {
                        "id": lesson["id"],
                        "file": lesson["file"],
                        "severity": lesson["severity"],
                        "category": lesson["category"],
                        "prevention": lesson["prevention"],
                        "relevance_score": matches,
                    }
                )

        # Sort by relevance and severity
        relevant_lessons.sort(
            key=lambda x: (x["severity"] == "CRITICAL", x["relevance_score"]),
            reverse=True,
        )

        return relevant_lessons[:5]  # Return top 5 most relevant

    def learn_from_failure(
        self,
        failure_description: str,
        affected_files: list[str],
        root_cause: str,
        lesson_id: str = None,
    ) -> FailurePattern:
        """Learn a new pattern from a failure."""
        # Generate pattern ID
        pattern_id = f"fp_{len(self.patterns) + 1:03d}"

        # Try to extract a regex pattern from affected files
        if affected_files:
            # Use the first file as a pattern template
            regex = re.escape(affected_files[0])
            # Make it more general
            regex = regex.replace(r"\.py", r"\.py")
        else:
            # Use keywords from description
            words = re.findall(r"\b\w{4,}\b", failure_description.lower())
            regex = "|".join(words[:3]) if words else "unknown"

        new_pattern = FailurePattern(
            pattern_id=pattern_id,
            regex=regex,
            lesson_id=lesson_id or "ll_new",
            severity="HIGH",
            description=failure_description[:100],
            confidence=0.5,  # Start with moderate confidence
        )

        self.patterns.append(new_pattern)
        self._save_patterns()

        logger.info(f"Learned new pattern: {pattern_id} - {failure_description[:50]}")
        return new_pattern

    def update_pattern_confidence(self, pattern_id: str, was_true_positive: bool) -> None:
        """Update pattern confidence based on feedback."""
        for pattern in self.patterns:
            if pattern.pattern_id == pattern_id:
                # Bayesian-like update
                if was_true_positive:
                    pattern.confidence = min(0.99, pattern.confidence * 1.1)
                    pattern.false_positive_rate *= 0.9
                else:
                    pattern.confidence *= 0.9
                    pattern.false_positive_rate = min(0.5, pattern.false_positive_rate + 0.1)

                self._save_patterns()
                break


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ML Pipeline Safety Checker")
    parser.add_argument(
        "--files",
        type=str,
        nargs="+",
        help="List of files to check",
    )
    parser.add_argument(
        "--diff",
        type=str,
        help="Path to diff file or '-' for stdin",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    parser.add_argument(
        "--learn",
        type=str,
        help="Learn from a new failure (provide description)",
    )
    parser.add_argument(
        "--affected-files",
        type=str,
        nargs="*",
        help="Files affected by failure (with --learn)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    checker = MLPipelineSafetyChecker()

    if args.learn:
        pattern = checker.learn_from_failure(
            failure_description=args.learn,
            affected_files=args.affected_files or [],
            root_cause=args.learn,
        )
        print(f"Learned new pattern: {pattern.pattern_id}")
        print(f"  Regex: {pattern.regex}")
        print(f"  Description: {pattern.description}")
        return 0

    if args.files:
        result = checker.check_files(args.files)
    elif args.diff:
        if args.diff == "-":
            diff_content = sys.stdin.read()
        else:
            diff_content = Path(args.diff).read_text()
        result = checker.check_diff(diff_content)
    else:
        print("Provide --files or --diff")
        return 1

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print("=" * 60)
        print("ML PIPELINE SAFETY CHECK RESULT")
        print("=" * 60)

        if result.passed:
            print(
                f"\n[PASSED] Confidence: {result.confidence:.0%}, Risk: {result.risk_score:.0f}/100\n"
            )
        else:
            print(
                f"\n[BLOCKED] Confidence: {result.confidence:.0%}, Risk: {result.risk_score:.0f}/100\n"
            )

        if result.blockers:
            print("BLOCKERS:")
            for blocker in result.blockers:
                print(f"  [X] {blocker}")
            print()

        if result.warnings:
            print("WARNINGS:")
            for warning in result.warnings:
                print(f"  [!] {warning}")
            print()

        if result.matched_patterns:
            print("MATCHED PATTERNS:")
            for pattern in result.matched_patterns:
                print(f"  [{pattern.severity}] {pattern.pattern_id}: {pattern.description}")
                print(f"       Lesson: {pattern.lesson_id}, Confidence: {pattern.confidence:.0%}")
            print()

        if result.rag_context:
            print("RAG CONTEXT (Related Lessons):")
            for ctx in result.rag_context:
                print(f"  [i] {ctx['id']} ({ctx['severity']}): {ctx.get('category', 'N/A')}")
            print()

        if result.recommendations:
            print("RECOMMENDATIONS:")
            for rec in result.recommendations:
                print(f"  -> {rec}")

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
