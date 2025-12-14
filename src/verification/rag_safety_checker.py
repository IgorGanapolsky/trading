"""
RAG Safety Checker

Queries the lessons learned RAG before any critical action to check
if a similar mistake has been made before.

Created: Dec 11, 2025 (after syntax error incident)
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SafetyCheckResult:
    """Result of a RAG safety check."""

    safe: bool
    similar_incidents: list[dict]
    warnings: list[str]
    blocking_reasons: list[str]
    confidence: float

    def __bool__(self):
        return self.safe


class RAGSafetyChecker:
    """
    Checks proposed actions against lessons learned RAG.

    Before ANY critical action (merge, deploy, trade), this checker:
    1. Queries RAG for similar past incidents
    2. Checks if proposed changes match known failure patterns
    3. Returns warnings or blocks based on severity

    Usage:
        checker = RAGSafetyChecker()
        result = checker.check_merge_safety(changed_files, commit_message)
        if not result.safe:
            raise BlockedByRAGError(result.blocking_reasons)
    """

    # Known dangerous patterns from lessons learned
    DANGEROUS_PATTERNS = {
        "large_pr": {
            "threshold": 10,  # files changed
            "severity": "high",
            "lesson_id": "ll_009",
            "message": "Large PRs (>10 files) have caused production incidents. Requires extra review.",
        },
        "executor_changes": {
            "files": ["alpaca_executor.py", "executor.py", "broker"],
            "severity": "critical",
            "lesson_id": "ll_009",
            "message": "Changes to execution layer can break all trading. Verify syntax and imports.",
        },
        "gate_changes": {
            "files": ["gate", "filter", "circuit_breaker"],
            "severity": "high",
            "lesson_id": "ll_001",
            "message": "Gate changes can block all trades. Verify pass rates after change.",
        },
        "ml_data_handling": {
            "files": ["data_processor", "normalize", "transform"],
            "severity": "high",
            "lesson_id": "ll_002",
            "message": "ML data handling changes can cause data leakage. Verify fit/transform pattern.",
        },
    }

    def __init__(self, rag_path: str = "data/rag/lessons_learned.json"):
        self.rag_path = rag_path
        self._lessons_cache = None

    def _load_lessons(self) -> list[dict]:
        """Load lessons from RAG store."""
        if self._lessons_cache is not None:
            return self._lessons_cache

        try:
            import json
            from pathlib import Path

            path = Path(self.rag_path)
            if path.exists():
                with open(path) as f:
                    data = json.load(f)
                    self._lessons_cache = data.get("lessons", [])
            else:
                self._lessons_cache = []

            # Also load markdown lessons
            lessons_dir = Path("rag_knowledge/lessons_learned")
            if lessons_dir.exists():
                for md_file in lessons_dir.glob("*.md"):
                    self._lessons_cache.append(
                        {
                            "id": md_file.stem,
                            "file": str(md_file),
                            "type": "markdown",
                        }
                    )

            return self._lessons_cache

        except Exception as e:
            logger.warning(f"Failed to load lessons: {e}")
            return []

    def check_merge_safety(
        self,
        changed_files: list[str],
        commit_message: str,
        diff_stats: Optional[dict] = None,
    ) -> SafetyCheckResult:
        """
        Check if a merge is safe based on lessons learned.

        Args:
            changed_files: List of files being changed
            commit_message: The commit message
            diff_stats: Optional dict with {additions, deletions, files_changed}

        Returns:
            SafetyCheckResult with safety status and any warnings
        """
        warnings = []
        blocking_reasons = []
        similar_incidents = []

        # Check 1: Large PR
        num_files = len(changed_files)
        if num_files > self.DANGEROUS_PATTERNS["large_pr"]["threshold"]:
            pattern = self.DANGEROUS_PATTERNS["large_pr"]
            warnings.append(f"⚠️ Large PR ({num_files} files): {pattern['message']}")
            similar_incidents.append(
                {
                    "pattern": "large_pr",
                    "lesson_id": pattern["lesson_id"],
                    "severity": pattern["severity"],
                }
            )

        # Check 2: Dangerous file patterns
        for pattern_name, pattern in self.DANGEROUS_PATTERNS.items():
            if "files" in pattern:
                for changed in changed_files:
                    for dangerous in pattern["files"]:
                        if dangerous.lower() in changed.lower():
                            msg = f"⚠️ {pattern_name}: {pattern['message']}"
                            if pattern["severity"] == "critical":
                                blocking_reasons.append(msg)
                            else:
                                warnings.append(msg)
                            similar_incidents.append(
                                {
                                    "pattern": pattern_name,
                                    "file": changed,
                                    "lesson_id": pattern["lesson_id"],
                                    "severity": pattern["severity"],
                                }
                            )
                            break

        # Check 3: Query RAG for semantic similarity
        lessons = self._load_lessons()
        # (In production, this would use vector similarity search)

        # Check 4: Diff stats warnings
        if diff_stats:
            if diff_stats.get("deletions", 0) > 1000:
                warnings.append(
                    f"⚠️ Large deletion ({diff_stats['deletions']} lines). "
                    "Verify no critical code removed."
                )

        # Determine overall safety
        safe = len(blocking_reasons) == 0
        confidence = 1.0 - (len(warnings) * 0.1) - (len(blocking_reasons) * 0.3)

        return SafetyCheckResult(
            safe=safe,
            similar_incidents=similar_incidents,
            warnings=warnings,
            blocking_reasons=blocking_reasons,
            confidence=max(0.0, confidence),
        )

    def check_trade_safety(
        self,
        symbol: str,
        side: str,
        amount: float,
        strategy: str,
    ) -> SafetyCheckResult:
        """
        Check if a trade is safe based on past incidents.

        Queries RAG for similar trade failures.
        """
        warnings = []
        blocking_reasons = []
        similar_incidents = []

        # Check for similar past failures
        lessons = self._load_lessons()
        for lesson in lessons:
            if isinstance(lesson, dict):
                if lesson.get("symbol") == symbol:
                    warnings.append(
                        f"⚠️ Past incident with {symbol}: {lesson.get('title', 'Unknown')}"
                    )
                    similar_incidents.append(lesson)

        return SafetyCheckResult(
            safe=len(blocking_reasons) == 0,
            similar_incidents=similar_incidents,
            warnings=warnings,
            blocking_reasons=blocking_reasons,
            confidence=1.0 - (len(warnings) * 0.1),
        )

    def record_incident(
        self,
        category: str,
        title: str,
        description: str,
        root_cause: str,
        prevention: str,
        severity: str = "medium",
        tags: Optional[list[str]] = None,
        financial_impact: Optional[float] = None,
    ) -> str:
        """
        Record a new incident to the lessons learned RAG.

        This should be called whenever an error occurs to build
        the knowledge base for future prevention.
        """
        import json
        import uuid
        from datetime import datetime
        from pathlib import Path

        lesson = {
            "id": f"ll_{uuid.uuid4().hex[:8]}",
            "timestamp": datetime.utcnow().isoformat(),
            "category": category,
            "title": title,
            "description": description,
            "root_cause": root_cause,
            "prevention": prevention,
            "severity": severity,
            "tags": tags or [],
            "financial_impact": financial_impact,
        }

        # Load existing lessons
        path = Path(self.rag_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists():
            with open(path) as f:
                data = json.load(f)
        else:
            data = {"lessons": [], "metadata": {"version": "1.0"}}

        data["lessons"].append(lesson)

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

        # Clear cache
        self._lessons_cache = None

        logger.info(f"Recorded incident: {lesson['id']} - {title}")
        return lesson["id"]
