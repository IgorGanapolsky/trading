"""
ML Learning Loop Integration - Wires Together ALL Verification Systems

This module connects:
1. Anomaly detectors → Failure-to-lesson pipeline
2. Lessons → Vector store indexing
3. Pre-trade → RAG checks
4. Post-trade → Learning feedback

CRITICAL: Call `initialize_learning_loop()` at orchestrator startup!

Created: Dec 15, 2025
Lesson: LL-041 - Comprehensive Regression Tests
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAG_DIR = PROJECT_ROOT / "rag_knowledge" / "lessons_learned"


class MLLearningLoopIntegration:
    """
    Central integration point for the ML learning loop.

    Connects:
    - AnomalyLearningLoop (recurrence tracking)
    - FailureToLessonPipeline (lesson generation)
    - LessonsIndexer (vector store)
    - Pre-trade RAG checks
    """

    def __init__(self):
        self.initialized = False
        self.anomaly_loop = None
        self.failure_pipeline = None
        self.lessons_indexer = None
        self.rag_gate = None
        self._init_errors: list[str] = []

    def initialize(self) -> bool:
        """Initialize all components of the learning loop."""
        logger.info("Initializing ML Learning Loop Integration...")

        # 1. Initialize Anomaly Learning Loop
        try:
            from src.verification.anomaly_learning_feedback_loop import (
                AnomalyLearningLoop,
            )

            self.anomaly_loop = AnomalyLearningLoop()
            logger.info("  ✓ AnomalyLearningLoop initialized")
        except Exception as e:
            self._init_errors.append(f"AnomalyLearningLoop: {e}")
            logger.warning(f"  ✗ AnomalyLearningLoop failed: {e}")

        # 2. Initialize Failure-to-Lesson Pipeline
        try:
            from src.verification.failure_to_lesson_pipeline import (
                FailureToLessonPipeline,
            )

            self.failure_pipeline = FailureToLessonPipeline()
            logger.info("  ✓ FailureToLessonPipeline initialized")
        except Exception as e:
            self._init_errors.append(f"FailureToLessonPipeline: {e}")
            logger.warning(f"  ✗ FailureToLessonPipeline failed: {e}")

        # 3. Initialize Lessons Indexer (vector store)
        try:
            from src.rag.lessons_indexer import LessonsIndexer

            self.lessons_indexer = LessonsIndexer()
            logger.info("  ✓ LessonsIndexer initialized")
        except Exception as e:
            self._init_errors.append(f"LessonsIndexer: {e}")
            logger.warning(f"  ✗ LessonsIndexer failed: {e}")

        # 4. Initialize RAG Verification Gate
        try:
            from src.verification.rag_verification_gate import RAGVerificationGate

            self.rag_gate = RAGVerificationGate()
            logger.info("  ✓ RAGVerificationGate initialized")
        except Exception as e:
            self._init_errors.append(f"RAGVerificationGate: {e}")
            logger.warning(f"  ✗ RAGVerificationGate failed: {e}")

        # 5. Wire up integrations
        self._wire_anomaly_to_lesson()
        self._wire_lesson_to_indexer()

        self.initialized = True
        success_count = 4 - len(self._init_errors)
        logger.info(
            f"ML Learning Loop Integration complete: {success_count}/4 components active"
        )

        return len(self._init_errors) == 0

    def _wire_anomaly_to_lesson(self):
        """Wire anomaly detection to lesson generation."""
        if self.anomaly_loop and self.failure_pipeline:
            # Patch the anomaly loop to create lessons
            original_process = self.anomaly_loop.process_anomaly

            def enhanced_process(anomaly: dict) -> dict:
                result = original_process(anomaly)

                # If this is a new pattern, create a lesson
                if result.get("is_new_pattern", False):
                    try:
                        lesson = self.failure_pipeline.create_lesson_from_anomaly(
                            anomaly
                        )
                        result["lesson_created"] = lesson
                        logger.info(
                            f"Auto-created lesson from anomaly: {anomaly.get('anomaly_id')}"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to create lesson from anomaly: {e}")

                return result

            self.anomaly_loop.process_anomaly = enhanced_process
            logger.info("  ✓ Wired anomaly detection → lesson generation")

    def _wire_lesson_to_indexer(self):
        """Wire lesson creation to vector store indexing."""
        if self.failure_pipeline and self.lessons_indexer:
            # Patch the lesson pipeline to index new lessons
            original_create = getattr(
                self.failure_pipeline, "create_lesson_from_anomaly", None
            )
            if original_create:
                def enhanced_create(anomaly: dict) -> str:
                    lesson_path = original_create(anomaly)

                    # Index the new lesson
                    if lesson_path and Path(lesson_path).exists():
                        try:
                            self.lessons_indexer.index_single_lesson(lesson_path)
                            logger.info(f"Auto-indexed new lesson: {lesson_path}")
                        except Exception as e:
                            logger.warning(f"Failed to index lesson: {e}")

                    return lesson_path

                self.failure_pipeline.create_lesson_from_anomaly = enhanced_create
                logger.info("  ✓ Wired lesson creation → vector indexing")

    def index_all_lessons(self) -> int:
        """Index all existing lessons into vector store."""
        if not self.lessons_indexer:
            logger.warning("LessonsIndexer not available - skipping indexing")
            return 0

        try:
            count = self.lessons_indexer.index_all_lessons()
            logger.info(f"Indexed {count} lessons into vector store")
            return count
        except Exception as e:
            logger.warning(f"Failed to index lessons: {e}")
            return 0

    def process_anomaly(self, anomaly: dict) -> dict:
        """Process an anomaly through the full learning loop."""
        if not self.anomaly_loop:
            logger.warning("AnomalyLearningLoop not available")
            return {"error": "Learning loop not initialized"}

        return self.anomaly_loop.process_anomaly(anomaly)

    def query_lessons_before_trade(
        self, symbol: str, action: str, context: dict | None = None
    ) -> list[dict]:
        """
        Query RAG for relevant lessons before executing a trade.

        Returns list of relevant lessons that should be reviewed.
        """
        if not self.rag_gate:
            return []

        query = f"{action} {symbol}"
        if context:
            if context.get("fear_greed"):
                query += f" fear greed {context['fear_greed']}"
            if context.get("regime"):
                query += f" {context['regime']} market"

        try:
            results = self.rag_gate.semantic_search(query, top_k=3)
            warnings = []

            for lesson, score in results:
                if score > 0.5:  # Relevance threshold
                    warnings.append(
                        {
                            "lesson_id": lesson.id,
                            "title": lesson.title,
                            "severity": lesson.severity,
                            "relevance_score": score,
                            "summary": getattr(lesson, "summary", "")[:200],
                        }
                    )

            if warnings:
                logger.info(
                    f"Pre-trade RAG check for {symbol}: {len(warnings)} relevant lessons"
                )

            return warnings
        except Exception as e:
            logger.warning(f"Pre-trade RAG check failed: {e}")
            return []

    def record_trade_outcome(
        self, trade_id: str, symbol: str, outcome: str, pnl: float
    ):
        """
        Record trade outcome for learning feedback.

        If outcome was negative and we had warnings, this is a missed prevention.
        If outcome was positive despite warnings, lessons may need updating.
        """
        # TODO: Implement trade outcome tracking
        # This would update lesson effectiveness scores
        pass

    def get_status(self) -> dict[str, Any]:
        """Get status of all learning loop components."""
        return {
            "initialized": self.initialized,
            "anomaly_loop_active": self.anomaly_loop is not None,
            "failure_pipeline_active": self.failure_pipeline is not None,
            "lessons_indexer_active": self.lessons_indexer is not None,
            "rag_gate_active": self.rag_gate is not None,
            "init_errors": self._init_errors,
            "lessons_count": len(list(RAG_DIR.glob("*.md"))) if RAG_DIR.exists() else 0,
        }


# Global instance
_learning_loop: MLLearningLoopIntegration | None = None


def initialize_learning_loop() -> MLLearningLoopIntegration:
    """Initialize and return the global learning loop instance."""
    global _learning_loop

    if _learning_loop is None:
        _learning_loop = MLLearningLoopIntegration()
        _learning_loop.initialize()

        # Index all existing lessons on first init
        _learning_loop.index_all_lessons()

    return _learning_loop


def get_learning_loop() -> MLLearningLoopIntegration | None:
    """Get the global learning loop instance (may be None if not initialized)."""
    return _learning_loop


def pre_trade_check(symbol: str, action: str, context: dict | None = None) -> dict:
    """
    Convenience function for pre-trade RAG check.

    Returns:
        {
            "allowed": bool,
            "warnings": list[dict],
            "critical_lessons": list[str]
        }
    """
    loop = get_learning_loop()
    if not loop:
        return {"allowed": True, "warnings": [], "critical_lessons": []}

    warnings = loop.query_lessons_before_trade(symbol, action, context)

    critical = [w for w in warnings if w.get("severity") == "critical"]

    return {
        "allowed": len(critical) == 0,  # Block if critical lessons found
        "warnings": warnings,
        "critical_lessons": [c["lesson_id"] for c in critical],
    }


if __name__ == "__main__":
    # Test the integration
    logging.basicConfig(level=logging.INFO)

    loop = initialize_learning_loop()
    print("\nML Learning Loop Status:")
    for key, value in loop.get_status().items():
        print(f"  {key}: {value}")

    # Test pre-trade check
    print("\nTesting pre-trade check for BTCUSD BUY during fear...")
    result = pre_trade_check("BTCUSD", "BUY", {"fear_greed": 20, "regime": "bear"})
    print(f"  Allowed: {result['allowed']}")
    print(f"  Warnings: {len(result['warnings'])}")
    for w in result["warnings"][:3]:
        print(f"    - [{w['severity']}] {w['lesson_id']}: {w['title'][:50]}...")
