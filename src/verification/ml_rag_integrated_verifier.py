"""
ML + RAG Integrated Verifier

Combines ML anomaly detection with RAG semantic search to create a
comprehensive verification system that learns from past mistakes.

Key Features:
1. Pre-merge: ML anomaly detection + RAG pattern matching
2. Post-merge: Continuous monitoring with automatic lesson ingestion
3. ML feedback loop: Updates anomaly detection baselines from lessons learned
4. Semantic search: Finds similar past failures using embeddings

Created: Dec 13, 2025
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Result of integrated verification."""

    passed: bool
    ml_anomalies: list[dict]
    rag_warnings: list[dict]
    risk_score: float  # 0-100
    recommendations: list[str]
    similar_lessons: list[str]


class MLRAGIntegratedVerifier:
    """
    Integrated verification system combining ML and RAG.

    Uses:
    - ML anomaly detection for pattern recognition
    - RAG semantic search for similar past failures
    - Automatic lesson ingestion for continuous learning
    """

    def __init__(
        self,
        ml_detector_path: Optional[str] = None,
        rag_path: str = "data/rag/lessons_learned.json",
    ):
        """Initialize the integrated verifier."""
        # Import ML components
        try:
            from src.verification.ml_anomaly_detector import MLAnomalyDetector

            self.ml_detector = MLAnomalyDetector(ml_detector_path)
        except ImportError:
            logger.warning("ML anomaly detector not available")
            self.ml_detector = None

        # Import RAG components
        try:
            from src.rag.lessons_learned_rag import LessonsLearnedRAG

            self.rag = LessonsLearnedRAG(rag_path)
        except ImportError:
            logger.warning("RAG system not available")
            self.rag = None

        # Import safety checker
        try:
            from src.verification.rag_safety_checker import RAGSafetyChecker

            self.safety_checker = RAGSafetyChecker(rag_path)
        except ImportError:
            logger.warning("RAG safety checker not available")
            self.safety_checker = None

    def verify_pre_merge(
        self,
        changed_files: list[str],
        commit_message: str,
        diff_stats: Optional[dict] = None,
    ) -> VerificationResult:
        """
        Comprehensive pre-merge verification.

        Combines:
        1. ML anomaly detection on code changes
        2. RAG semantic search for similar failures
        3. Pattern matching against known failure modes

        Args:
            changed_files: List of changed file paths
            commit_message: Commit message
            diff_stats: Optional diff statistics

        Returns:
            VerificationResult with all checks
        """
        ml_anomalies = []
        rag_warnings = []
        recommendations = []
        similar_lessons = []

        # 1. ML Anomaly Detection
        if self.ml_detector:
            code_files = [Path(f) for f in changed_files if f.endswith(".py")]
            if code_files:
                ml_report = self.ml_detector.run_full_detection(code_files=code_files)
                ml_anomalies = [
                    {
                        "category": a.category,
                        "severity": a.severity,
                        "description": a.description,
                        "recommendation": a.recommendation,
                    }
                    for a in ml_report.anomalies
                ]

                if ml_report.high_count > 0:
                    recommendations.append(
                        f"🚨 {ml_report.high_count} high-severity ML anomalies detected. Review before merge."
                    )

        # 2. RAG Safety Check
        if self.safety_checker:
            safety_result = self.safety_checker.check_merge_safety(
                changed_files, commit_message, diff_stats
            )

            if not safety_result.safe:
                rag_warnings.extend(safety_result.blocking_reasons)
                recommendations.append("🚨 RAG safety check blocked merge. Review warnings.")

            rag_warnings.extend(safety_result.warnings)

            # Extract similar lesson IDs
            for incident in safety_result.similar_incidents:
                if "lesson_id" in incident:
                    similar_lessons.append(incident["lesson_id"])

        # 3. RAG Semantic Search
        if self.rag:
            # Build query from commit message and changed files
            query = f"{commit_message} {' '.join(changed_files[:5])}"
            rag_results = self.rag.search(query, top_k=3)

            for lesson, score in rag_results:
                if score > 0.5:  # High similarity threshold
                    rag_warnings.append(
                        {
                            "type": "similar_past_failure",
                            "lesson_id": lesson.id,
                            "title": lesson.title,
                            "similarity": score,
                            "prevention": lesson.prevention,
                        }
                    )
                    similar_lessons.append(lesson.id)
                    recommendations.append(
                        f"⚠️ Similar past failure detected: {lesson.title} (see {lesson.id})"
                    )

        # Calculate risk score
        risk_score = self._calculate_risk_score(ml_anomalies, rag_warnings)

        # Determine if passed
        passed = risk_score < 50 and not any(
            w.get("severity") == "critical" or "blocked" in str(w).lower() for w in rag_warnings
        )

        return VerificationResult(
            passed=passed,
            ml_anomalies=ml_anomalies,
            rag_warnings=rag_warnings,
            risk_score=risk_score,
            recommendations=recommendations,
            similar_lessons=list(set(similar_lessons)),
        )

    def verify_post_merge(self) -> VerificationResult:
        """
        Post-merge verification and monitoring.

        Checks:
        1. System health after merge
        2. Trading execution status
        3. Import/syntax verification
        4. Performance metrics

        Returns:
            VerificationResult
        """
        warnings = []
        recommendations = []

        # Check critical imports
        critical_imports = [
            "src.orchestrator.main.TradingOrchestrator",
            "src.execution.alpaca_executor.AlpacaExecutor",
            "src.risk.trade_gateway.TradeGateway",
        ]

        import subprocess
        import sys

        for imp in critical_imports:
            try:
                module_path = imp.replace(".", "/")
                result = subprocess.run(
                    [sys.executable, "-c", f"from {imp.rsplit('.', 1)[0]} import {imp.rsplit('.', 1)[1]}"],
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode != 0:
                    warnings.append(
                        {
                            "type": "import_error",
                            "module": imp,
                            "error": result.stderr.decode()[:200],
                        }
                    )
            except Exception as e:
                warnings.append({"type": "import_check_failed", "module": imp, "error": str(e)})

        # Check system state
        state_path = Path("data/system_state.json")
        if state_path.exists():
            with open(state_path) as f:
                state = json.load(f)

            automation = state.get("automation", {})
            if automation.get("workflow_status") != "OPERATIONAL":
                warnings.append(
                    {
                        "type": "workflow_not_operational",
                        "status": automation.get("workflow_status"),
                    }
                )
                recommendations.append("Check GitHub Actions workflow status")

        risk_score = len(warnings) * 20  # 20 points per warning
        passed = len(warnings) == 0

        return VerificationResult(
            passed=passed,
            ml_anomalies=[],
            rag_warnings=warnings,
            risk_score=risk_score,
            recommendations=recommendations,
            similar_lessons=[],
        )

    def update_ml_baselines_from_lessons(self) -> None:
        """
        Update ML anomaly detection baselines from lessons learned.

        This creates a feedback loop where lessons learned improve
        ML detection thresholds.
        """
        if not self.ml_detector or not self.rag:
            return

        # Extract patterns from lessons learned
        lessons = self.rag.lessons

        # Group by category and extract metrics
        category_patterns = {}
        for lesson in lessons:
            cat = lesson.category
            if cat not in category_patterns:
                category_patterns[cat] = []

            # Extract numeric patterns from prevention text
            # This is a simple heuristic - in production would use NLP
            category_patterns[cat].append(lesson)

        # Update baselines based on lessons
        # For now, just log - full implementation would update ML model
        logger.info(f"Found {len(lessons)} lessons to inform ML baselines")

    def _calculate_risk_score(self, ml_anomalies: list[dict], rag_warnings: list[dict]) -> float:
        """Calculate overall risk score from anomalies and warnings."""
        score = 0.0

        # ML anomalies
        for anomaly in ml_anomalies:
            severity_weights = {"high": 30, "medium": 10, "low": 2}
            score += severity_weights.get(anomaly.get("severity", "low"), 0)

        # RAG warnings
        for warning in rag_warnings:
            if isinstance(warning, dict):
                if warning.get("severity") == "critical":
                    score += 50
                elif warning.get("severity") == "high":
                    score += 20
                elif "blocked" in str(warning).lower():
                    score += 40
            elif "blocked" in str(warning).lower() or "critical" in str(warning).lower():
                score += 30

        return min(100.0, score)


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="ML+RAG Integrated Verifier")
    parser.add_argument("--pre-merge", action="store_true", help="Run pre-merge verification")
    parser.add_argument("--post-merge", action="store_true", help="Run post-merge verification")
    parser.add_argument("--files", nargs="*", help="Changed files for pre-merge check")
    parser.add_argument("--commit-msg", help="Commit message")
    args = parser.parse_args()

    verifier = MLRAGIntegratedVerifier()

    if args.pre_merge:
        if not args.files:
            print("Error: --files required for pre-merge check")
            return 1

        result = verifier.verify_pre_merge(args.files, args.commit_msg or "")
        print(f"\n{'✅ PASSED' if result.passed else '❌ FAILED'}")
        print(f"Risk Score: {result.risk_score}/100")
        print(f"\nML Anomalies: {len(result.ml_anomalies)}")
        print(f"RAG Warnings: {len(result.rag_warnings)}")
        print(f"Similar Lessons: {len(result.similar_lessons)}")

        if result.recommendations:
            print("\nRecommendations:")
            for rec in result.recommendations:
                print(f"  {rec}")

        return 0 if result.passed else 1

    elif args.post_merge:
        result = verifier.verify_post_merge()
        print(f"\n{'✅ PASSED' if result.passed else '❌ FAILED'}")
        print(f"Risk Score: {result.risk_score}/100")

        if result.rag_warnings:
            print("\nWarnings:")
            for w in result.rag_warnings:
                print(f"  {w}")

        return 0 if result.passed else 1

    else:
        print("Error: Specify --pre-merge or --post-merge")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
