"""
ML-Powered Lesson Pattern Detector.

Uses machine learning to detect patterns in past failures and predict
future issues before they occur. Integrates with RAG to continuously
learn from new incidents.

Key Features:
1. Pattern recognition from past failures
2. Anomaly detection for new code changes
3. Risk scoring for PRs and commits
4. Automated prevention recommendations

Created: 2025-12-14
Author: Trading CTO
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


class FailureCategory(Enum):
    """Categories of failures detected in the system."""

    SYNTAX_ERROR = "syntax_error"
    IMPORT_ERROR = "import_error"
    TYPE_ERROR = "type_error"
    RUNTIME_ERROR = "runtime_error"
    TRADING_LOGIC = "trading_logic"
    DATA_QUALITY = "data_quality"
    CONFIGURATION = "configuration"
    DEPLOYMENT = "deployment"
    CI_CD = "ci_cd"
    SECURITY = "security"


class RiskLevel(Enum):
    """Risk levels for code changes."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class FailurePattern:
    """A detected failure pattern from historical data."""

    pattern_id: str
    category: FailureCategory
    signature: str  # Regex or keyword pattern
    occurrences: int
    last_seen: datetime
    files_affected: list[str]
    prevention: str
    risk_level: RiskLevel
    confidence: float  # 0.0 to 1.0


@dataclass
class RiskAssessment:
    """Risk assessment for a code change."""

    overall_risk: RiskLevel
    score: float  # 0.0 to 1.0 (higher = riskier)
    matched_patterns: list[FailurePattern]
    recommendations: list[str]
    warnings: list[str]
    files_at_risk: list[str]


class MLLessonPatternDetector:
    """
    ML-powered detector for failure patterns.

    Uses historical lessons learned to:
    1. Extract common failure patterns
    2. Score new code changes for risk
    3. Recommend preventive measures
    4. Alert on high-risk changes

    Integration:
    - Pre-merge gate: Scores PRs before merge
    - CI/CD: Flags risky commits
    - RAG: Ingests new failures automatically
    """

    PATTERNS_DB_PATH = Path("data/ml/failure_patterns.json")

    # High-risk file patterns (from historical data)
    HIGH_RISK_FILES = [
        r"src/execution/.*\.py",  # Trade execution
        r"src/risk/.*\.py",  # Risk management
        r"src/orchestrator/main\.py",  # Main trading logic
        r"scripts/autonomous_trader\.py",  # Autonomous trading
        r"\.github/workflows/.*\.yml",  # CI/CD
    ]

    # Error signature patterns (extracted from logs)
    ERROR_SIGNATURES = {
        "syntax_error": [
            r"SyntaxError:",
            r"invalid syntax",
            r"unexpected EOF",
            r"f-string:.*invalid",
        ],
        "import_error": [
            r"ImportError:",
            r"ModuleNotFoundError:",
            r"cannot import name",
            r"No module named",
        ],
        "type_error": [
            r"TypeError:",
            r"expected .* got",
            r"missing \d+ required",
            r"unexpected keyword argument",
        ],
        "runtime_error": [
            r"RuntimeError:",
            r"AttributeError:",
            r"KeyError:",
            r"IndexError:",
        ],
        "trading_logic": [
            r"200x error",
            r"position size",
            r"order amount",
            r"budget exceeded",
            r"max risk",
        ],
        "data_quality": [
            r"stale data",
            r"missing data",
            r"NaN",
            r"null pointer",
            r"empty response",
        ],
    }

    def __init__(
        self,
        patterns_db_path: Optional[Path] = None,
        rag_enabled: bool = True,
    ):
        """
        Initialize the pattern detector.

        Args:
            patterns_db_path: Path to patterns database
            rag_enabled: Whether to query RAG for additional patterns
        """
        self.patterns_db_path = patterns_db_path or self.PATTERNS_DB_PATH
        self.patterns: list[FailurePattern] = []
        self.rag_enabled = rag_enabled
        self.rag = None

        # Load existing patterns
        self._load_patterns()

        # Initialize RAG if enabled
        if rag_enabled:
            self._init_rag()

    def _init_rag(self) -> None:
        """Initialize RAG connection."""
        try:
            from src.rag.lessons_learned_rag import LessonsLearnedRAG

            self.rag = LessonsLearnedRAG()
            logger.info("RAG integration enabled")
        except Exception as e:
            logger.warning(f"Could not initialize RAG: {e}")
            self.rag = None

    def _load_patterns(self) -> None:
        """Load patterns from database."""
        if self.patterns_db_path.exists():
            try:
                with open(self.patterns_db_path) as f:
                    data = json.load(f)
                self.patterns = [
                    FailurePattern(
                        pattern_id=p["pattern_id"],
                        category=FailureCategory(p["category"]),
                        signature=p["signature"],
                        occurrences=p["occurrences"],
                        last_seen=datetime.fromisoformat(p["last_seen"]),
                        files_affected=p["files_affected"],
                        prevention=p["prevention"],
                        risk_level=RiskLevel(p["risk_level"]),
                        confidence=p["confidence"],
                    )
                    for p in data
                ]
                logger.info(f"Loaded {len(self.patterns)} failure patterns")
            except Exception as e:
                logger.warning(f"Could not load patterns: {e}")
                self._initialize_default_patterns()
        else:
            self._initialize_default_patterns()

    def _save_patterns(self) -> None:
        """Save patterns to database."""
        self.patterns_db_path.parent.mkdir(parents=True, exist_ok=True)
        data = [
            {
                "pattern_id": p.pattern_id,
                "category": p.category.value,
                "signature": p.signature,
                "occurrences": p.occurrences,
                "last_seen": p.last_seen.isoformat(),
                "files_affected": p.files_affected,
                "prevention": p.prevention,
                "risk_level": p.risk_level.value,
                "confidence": p.confidence,
            }
            for p in self.patterns
        ]
        with open(self.patterns_db_path, "w") as f:
            json.dump(data, f, indent=2)

    def _initialize_default_patterns(self) -> None:
        """Initialize default patterns from known incidents."""
        default_patterns = [
            FailurePattern(
                pattern_id="PAT-001",
                category=FailureCategory.SYNTAX_ERROR,
                signature=r"SyntaxError:.*alpaca_executor",
                occurrences=1,
                last_seen=datetime(2025, 12, 11, tzinfo=timezone.utc),
                files_affected=["src/execution/alpaca_executor.py"],
                prevention="Run python3 -m py_compile on all changed files before merge",
                risk_level=RiskLevel.CRITICAL,
                confidence=0.95,
            ),
            FailurePattern(
                pattern_id="PAT-002",
                category=FailureCategory.TRADING_LOGIC,
                signature=r"200x.*error|position.*size.*10x",
                occurrences=1,
                last_seen=datetime(2025, 11, 3, tzinfo=timezone.utc),
                files_affected=["scripts/autonomous_trader.py"],
                prevention="Validate order amount < 10x expected daily budget before execution",
                risk_level=RiskLevel.CRITICAL,
                confidence=0.90,
            ),
            FailurePattern(
                pattern_id="PAT-003",
                category=FailureCategory.IMPORT_ERROR,
                signature=r"cannot import name.*TradingOrchestrator",
                occurrences=2,
                last_seen=datetime(2025, 12, 11, tzinfo=timezone.utc),
                files_affected=["src/orchestrator/main.py"],
                prevention="Verify critical imports after any change to orchestrator",
                risk_level=RiskLevel.CRITICAL,
                confidence=0.88,
            ),
            FailurePattern(
                pattern_id="PAT-004",
                category=FailureCategory.CI_CD,
                signature=r"workflow.*failed|CI.*blocked",
                occurrences=3,
                last_seen=datetime(2025, 12, 11, tzinfo=timezone.utc),
                files_affected=[".github/workflows/*.yml"],
                prevention="Require CI to pass before merge (branch protection)",
                risk_level=RiskLevel.HIGH,
                confidence=0.85,
            ),
            FailurePattern(
                pattern_id="PAT-005",
                category=FailureCategory.DATA_QUALITY,
                signature=r"stale.*data|data.*old|freshness",
                occurrences=2,
                last_seen=datetime(2025, 11, 4, tzinfo=timezone.utc),
                files_affected=["src/data/*.py"],
                prevention="Verify data timestamp < 5 minutes before trading",
                risk_level=RiskLevel.HIGH,
                confidence=0.82,
            ),
            FailurePattern(
                pattern_id="PAT-006",
                category=FailureCategory.CONFIGURATION,
                signature=r"missing.*env|environment.*variable|API.*key",
                occurrences=2,
                last_seen=datetime(2025, 12, 12, tzinfo=timezone.utc),
                files_affected=["config/*.py", "src/**/*.py"],
                prevention="Check all required env vars are set before deployment",
                risk_level=RiskLevel.MEDIUM,
                confidence=0.78,
            ),
        ]

        self.patterns = default_patterns
        self._save_patterns()
        logger.info(f"Initialized {len(default_patterns)} default failure patterns")

    def assess_code_change(
        self,
        files_changed: list[str],
        diff_content: Optional[str] = None,
        commit_message: Optional[str] = None,
    ) -> RiskAssessment:
        """
        Assess the risk of a code change.

        Args:
            files_changed: List of changed file paths
            diff_content: Optional git diff content
            commit_message: Optional commit message

        Returns:
            RiskAssessment with overall risk and recommendations
        """
        matched_patterns: list[FailurePattern] = []
        warnings: list[str] = []
        recommendations: list[str] = []
        files_at_risk: list[str] = []

        # 1. Check if files match high-risk patterns
        for file_path in files_changed:
            for risk_pattern in self.HIGH_RISK_FILES:
                if re.match(risk_pattern, file_path):
                    files_at_risk.append(file_path)
                    warnings.append(f"High-risk file changed: {file_path}")

        # 2. Check against known failure patterns
        content_to_check = (diff_content or "") + (commit_message or "")
        for pattern in self.patterns:
            if re.search(pattern.signature, content_to_check, re.IGNORECASE):
                matched_patterns.append(pattern)
                warnings.append(f"Matches failure pattern: {pattern.pattern_id}")
                recommendations.append(pattern.prevention)

            # Also check by files affected
            for file_path in files_changed:
                for affected in pattern.files_affected:
                    if re.match(affected.replace("*", ".*"), file_path):
                        if pattern not in matched_patterns:
                            matched_patterns.append(pattern)
                            warnings.append(
                                f"File {file_path} associated with pattern: {pattern.pattern_id}"
                            )
                            recommendations.append(pattern.prevention)

        # 3. Check error signatures in diff content
        if diff_content:
            for category, signatures in self.ERROR_SIGNATURES.items():
                for sig in signatures:
                    if re.search(sig, diff_content, re.IGNORECASE):
                        warnings.append(f"Potential {category} detected in diff")

        # 4. Query RAG for additional context
        if self.rag and diff_content:
            try:
                rag_results = self.rag.search(diff_content[:500], top_k=3)
                for lesson, score in rag_results:
                    if score > 0.5:
                        recommendations.append(f"[RAG] {lesson.prevention}")
            except Exception as e:
                logger.warning(f"RAG query failed: {e}")

        # 5. Calculate overall risk score
        score = self._calculate_risk_score(
            files_at_risk=files_at_risk,
            matched_patterns=matched_patterns,
            num_files=len(files_changed),
        )

        # Determine risk level
        if score >= 0.8 or any(p.risk_level == RiskLevel.CRITICAL for p in matched_patterns):
            overall_risk = RiskLevel.CRITICAL
        elif score >= 0.6 or any(p.risk_level == RiskLevel.HIGH for p in matched_patterns):
            overall_risk = RiskLevel.HIGH
        elif score >= 0.3:
            overall_risk = RiskLevel.MEDIUM
        else:
            overall_risk = RiskLevel.LOW

        # Add default recommendations based on risk
        if overall_risk in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
            recommendations.insert(0, "Run pre_merge_gate.py before merge")
            recommendations.insert(1, "Verify all critical imports work")
            if len(files_changed) > 10:
                recommendations.insert(2, "Consider breaking into smaller PRs")

        return RiskAssessment(
            overall_risk=overall_risk,
            score=score,
            matched_patterns=matched_patterns,
            recommendations=list(dict.fromkeys(recommendations)),  # Deduplicate
            warnings=warnings,
            files_at_risk=files_at_risk,
        )

    def _calculate_risk_score(
        self,
        files_at_risk: list[str],
        matched_patterns: list[FailurePattern],
        num_files: int,
    ) -> float:
        """Calculate a risk score between 0.0 and 1.0."""
        score = 0.0

        # Risk from high-risk files (max 0.3)
        score += min(0.3, len(files_at_risk) * 0.1)

        # Risk from matched patterns (max 0.4)
        pattern_risk = sum(
            p.confidence * (0.2 if p.risk_level == RiskLevel.CRITICAL else 0.1)
            for p in matched_patterns
        )
        score += min(0.4, pattern_risk)

        # Risk from number of files changed (max 0.2)
        if num_files > 50:
            score += 0.2
        elif num_files > 20:
            score += 0.15
        elif num_files > 10:
            score += 0.1
        elif num_files > 5:
            score += 0.05

        # Additional risk factors (max 0.1)
        if any(p.category == FailureCategory.TRADING_LOGIC for p in matched_patterns):
            score += 0.05
        if any(p.category == FailureCategory.CI_CD for p in matched_patterns):
            score += 0.05

        return min(1.0, score)

    def learn_from_failure(
        self,
        error_message: str,
        files_involved: list[str],
        category: FailureCategory,
        prevention: str,
        risk_level: RiskLevel = RiskLevel.HIGH,
    ) -> str:
        """
        Learn from a new failure and create a pattern.

        Args:
            error_message: The error message or description
            files_involved: Files that were involved
            category: Category of the failure
            prevention: How to prevent in future
            risk_level: Severity of the issue

        Returns:
            Pattern ID of the new/updated pattern
        """
        # Generate signature from error message
        signature = self._extract_signature(error_message)

        # Check if similar pattern exists
        for pattern in self.patterns:
            if pattern.signature == signature or any(
                f in pattern.files_affected for f in files_involved
            ):
                # Update existing pattern
                pattern.occurrences += 1
                pattern.last_seen = datetime.now(timezone.utc)
                pattern.files_affected = list(
                    set(pattern.files_affected + files_involved)
                )
                if risk_level.value == "critical":
                    pattern.risk_level = risk_level
                self._save_patterns()
                logger.info(f"Updated pattern: {pattern.pattern_id}")
                return pattern.pattern_id

        # Create new pattern
        pattern_id = f"PAT-{len(self.patterns) + 1:03d}"
        new_pattern = FailurePattern(
            pattern_id=pattern_id,
            category=category,
            signature=signature,
            occurrences=1,
            last_seen=datetime.now(timezone.utc),
            files_affected=files_involved,
            prevention=prevention,
            risk_level=risk_level,
            confidence=0.70,  # Start with moderate confidence
        )

        self.patterns.append(new_pattern)
        self._save_patterns()

        # Also ingest to RAG if available
        if self.rag:
            try:
                self.rag.add_lesson(
                    category=category.value,
                    title=f"Failure Pattern: {pattern_id}",
                    description=error_message,
                    root_cause=f"Pattern detected from error: {signature}",
                    prevention=prevention,
                    severity="high" if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL] else "medium",
                    tags=["auto-detected", "ml-pattern"],
                )
            except Exception as e:
                logger.warning(f"Could not ingest to RAG: {e}")

        logger.info(f"Created new pattern: {pattern_id}")
        return pattern_id

    def _extract_signature(self, error_message: str) -> str:
        """Extract a regex signature from an error message."""
        # Remove specific values and create a pattern
        signature = error_message

        # Replace specific numbers with regex
        signature = re.sub(r"\b\d+\b", r"\\d+", signature)

        # Replace file paths with patterns
        signature = re.sub(r"/[\w/]+\.py", r".*\\.py", signature)

        # Escape special regex characters (except those we added)
        signature = re.sub(r"([^\w\s\\.*+?])", r"\\\1", signature)

        # Limit length
        if len(signature) > 100:
            signature = signature[:100]

        return signature

    def get_prevention_checklist(
        self,
        category: Optional[FailureCategory] = None,
    ) -> list[str]:
        """Get prevention checklist from learned patterns."""
        patterns = self.patterns
        if category:
            patterns = [p for p in patterns if p.category == category]

        # Sort by risk level and occurrences
        risk_order = {
            RiskLevel.CRITICAL: 0,
            RiskLevel.HIGH: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.LOW: 3,
        }
        patterns = sorted(
            patterns,
            key=lambda p: (risk_order[p.risk_level], -p.occurrences),
        )

        checklist = []
        seen = set()
        for pattern in patterns:
            if pattern.prevention not in seen:
                prefix = "[CRITICAL] " if pattern.risk_level == RiskLevel.CRITICAL else ""
                checklist.append(f"{prefix}{pattern.prevention}")
                seen.add(pattern.prevention)

        return checklist

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about learned patterns."""
        category_counts = Counter(p.category.value for p in self.patterns)
        risk_counts = Counter(p.risk_level.value for p in self.patterns)

        return {
            "total_patterns": len(self.patterns),
            "by_category": dict(category_counts),
            "by_risk_level": dict(risk_counts),
            "total_occurrences": sum(p.occurrences for p in self.patterns),
            "critical_patterns": sum(
                1 for p in self.patterns if p.risk_level == RiskLevel.CRITICAL
            ),
            "rag_enabled": self.rag is not None,
        }


def assess_pr_risk(
    files_changed: list[str],
    diff_content: Optional[str] = None,
    commit_message: Optional[str] = None,
) -> dict[str, Any]:
    """
    Convenience function to assess PR risk.

    Returns dict with:
    - risk_level: str
    - score: float
    - can_merge: bool
    - warnings: list[str]
    - recommendations: list[str]
    """
    detector = MLLessonPatternDetector()
    assessment = detector.assess_code_change(
        files_changed=files_changed,
        diff_content=diff_content,
        commit_message=commit_message,
    )

    return {
        "risk_level": assessment.overall_risk.value,
        "score": assessment.score,
        "can_merge": assessment.overall_risk != RiskLevel.CRITICAL,
        "warnings": assessment.warnings,
        "recommendations": assessment.recommendations,
        "files_at_risk": assessment.files_at_risk,
        "matched_patterns": [p.pattern_id for p in assessment.matched_patterns],
    }


if __name__ == "__main__":
    """Demo the ML pattern detector."""
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("ML LESSON PATTERN DETECTOR DEMO")
    print("=" * 80)

    detector = MLLessonPatternDetector()

    # Show stats
    stats = detector.get_stats()
    print(f"\nLoaded Patterns: {stats['total_patterns']}")
    print(f"Critical: {stats['critical_patterns']}")
    print(f"By Category: {stats['by_category']}")

    # Demo risk assessment
    print("\n" + "=" * 80)
    print("RISK ASSESSMENT: Large PR touching trading logic")
    print("=" * 80)

    assessment = detector.assess_code_change(
        files_changed=[
            "src/execution/alpaca_executor.py",
            "src/orchestrator/main.py",
            "src/risk/trade_gateway.py",
        ],
        diff_content="Modified order validation logic",
        commit_message="Refactor trading execution",
    )

    print(f"\nOverall Risk: {assessment.overall_risk.value.upper()}")
    print(f"Score: {assessment.score:.2f}")
    print(f"\nFiles at Risk: {assessment.files_at_risk}")
    print(f"\nWarnings:")
    for w in assessment.warnings:
        print(f"  - {w}")
    print(f"\nRecommendations:")
    for r in assessment.recommendations:
        print(f"  - {r}")

    # Prevention checklist
    print("\n" + "=" * 80)
    print("PREVENTION CHECKLIST")
    print("=" * 80)

    checklist = detector.get_prevention_checklist()
    for i, item in enumerate(checklist, 1):
        print(f"  {i}. {item}")
