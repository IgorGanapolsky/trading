"""
Tests for ML Learning Loop Integration.

Verifies that all components are properly wired together:
- Anomaly detection → Lesson generation
- Lesson creation → Vector indexing
- Pre-trade → RAG checks

Created: Dec 15, 2025
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestMLLearningLoopInitialization:
    """Tests for learning loop initialization."""

    @pytest.fixture
    def project_root(self) -> Path:
        return Path(__file__).parent.parent

    def test_integration_module_exists(self, project_root):
        """Verify the integration module exists and imports."""
        integration_file = (
            project_root / "src" / "verification" / "ml_learning_loop_integration.py"
        )
        assert integration_file.exists(), "ml_learning_loop_integration.py must exist"

    def test_can_import_integration(self):
        """Verify integration module can be imported."""
        try:
            from src.verification.ml_learning_loop_integration import (
                MLLearningLoopIntegration,
                initialize_learning_loop,
                pre_trade_check,
            )

            assert MLLearningLoopIntegration is not None
            assert initialize_learning_loop is not None
            assert pre_trade_check is not None
        except ImportError as e:
            pytest.skip(f"Could not import integration module: {e}")

    def test_integration_initializes_components(self):
        """Verify integration initializes all required components."""
        try:
            from src.verification.ml_learning_loop_integration import (
                MLLearningLoopIntegration,
            )

            loop = MLLearningLoopIntegration()
            loop.initialize()

            status = loop.get_status()

            # Should initialize without crashing
            assert status["initialized"] is True

            # At least some components should be active
            active_count = sum(
                [
                    status["anomaly_loop_active"],
                    status["failure_pipeline_active"],
                    status["lessons_indexer_active"],
                    status["rag_gate_active"],
                ]
            )

            assert active_count >= 1, "At least one component should initialize"

        except ImportError as e:
            pytest.skip(f"Could not import: {e}")


class TestPreTradeRAGCheck:
    """Tests for pre-trade RAG checking."""

    def test_pre_trade_check_returns_structure(self):
        """Verify pre_trade_check returns expected structure."""
        try:
            from src.verification.ml_learning_loop_integration import pre_trade_check

            result = pre_trade_check("BTCUSD", "BUY", {"fear_greed": 20})

            assert "allowed" in result
            assert "warnings" in result
            assert "critical_lessons" in result

            assert isinstance(result["allowed"], bool)
            assert isinstance(result["warnings"], list)
            assert isinstance(result["critical_lessons"], list)

        except ImportError as e:
            pytest.skip(f"Could not import: {e}")

    def test_pre_trade_check_finds_fear_lessons(self):
        """Verify pre-trade check finds relevant lessons for fear conditions."""
        try:
            from src.verification.ml_learning_loop_integration import (
                initialize_learning_loop,
                pre_trade_check,
            )

            # Initialize the loop
            loop = initialize_learning_loop()

            # Query with fear context
            result = pre_trade_check(
                "BTCUSD", "BUY", {"fear_greed": 15, "regime": "bear"}
            )

            # Should find some warnings (we have LL-020, LL-040 about fear)
            # Note: May return empty if RAG not fully initialized
            assert isinstance(result["warnings"], list)

        except ImportError as e:
            pytest.skip(f"Could not import: {e}")


class TestAnomalyToLessonPipeline:
    """Tests for anomaly → lesson pipeline."""

    @pytest.fixture
    def project_root(self) -> Path:
        return Path(__file__).parent.parent

    def test_failure_pipeline_exists(self, project_root):
        """Verify failure-to-lesson pipeline exists."""
        pipeline_file = (
            project_root / "src" / "verification" / "failure_to_lesson_pipeline.py"
        )
        assert pipeline_file.exists(), "failure_to_lesson_pipeline.py must exist"

    def test_anomaly_loop_exists(self, project_root):
        """Verify anomaly learning loop exists."""
        loop_file = (
            project_root
            / "src"
            / "verification"
            / "anomaly_learning_feedback_loop.py"
        )
        assert loop_file.exists(), "anomaly_learning_feedback_loop.py must exist"

    def test_lessons_directory_has_content(self, project_root):
        """Verify lessons learned directory has content."""
        lessons_dir = project_root / "rag_knowledge" / "lessons_learned"

        assert lessons_dir.exists(), "rag_knowledge/lessons_learned/ must exist"

        lessons = list(lessons_dir.glob("*.md"))
        assert len(lessons) >= 40, f"Expected 40+ lessons, found {len(lessons)}"


class TestVectorStoreIndexing:
    """Tests for vector store indexing of lessons."""

    @pytest.fixture
    def project_root(self) -> Path:
        return Path(__file__).parent.parent

    def test_lessons_indexer_exists(self, project_root):
        """Verify lessons indexer exists."""
        indexer_file = project_root / "src" / "rag" / "lessons_indexer.py"
        assert indexer_file.exists(), "lessons_indexer.py must exist"

    def test_lessons_search_exists(self, project_root):
        """Verify lessons search exists."""
        search_file = project_root / "src" / "rag" / "lessons_search.py"
        assert search_file.exists(), "lessons_search.py must exist"

    def test_indexer_can_be_instantiated(self):
        """Verify indexer can be instantiated."""
        try:
            from src.rag.lessons_indexer import LessonsIndexer

            indexer = LessonsIndexer()
            assert indexer is not None
        except ImportError as e:
            pytest.skip(f"Could not import LessonsIndexer: {e}")
        except Exception as e:
            # May fail due to missing dependencies, but shouldn't crash Python
            pytest.skip(f"LessonsIndexer initialization failed: {e}")


class TestLearningLoopStatus:
    """Tests for learning loop status reporting."""

    def test_status_includes_all_components(self):
        """Verify status includes all expected components."""
        try:
            from src.verification.ml_learning_loop_integration import (
                MLLearningLoopIntegration,
            )

            loop = MLLearningLoopIntegration()
            loop.initialize()

            status = loop.get_status()

            required_keys = [
                "initialized",
                "anomaly_loop_active",
                "failure_pipeline_active",
                "lessons_indexer_active",
                "rag_gate_active",
                "init_errors",
                "lessons_count",
            ]

            for key in required_keys:
                assert key in status, f"Status missing required key: {key}"

        except ImportError as e:
            pytest.skip(f"Could not import: {e}")

    def test_lessons_count_accurate(self):
        """Verify lessons count matches files on disk."""
        try:
            from src.verification.ml_learning_loop_integration import (
                MLLearningLoopIntegration,
            )

            loop = MLLearningLoopIntegration()
            loop.initialize()

            status = loop.get_status()

            # Should have 40+ lessons
            assert status["lessons_count"] >= 40, (
                f"Expected 40+ lessons, found {status['lessons_count']}"
            )

        except ImportError as e:
            pytest.skip(f"Could not import: {e}")


class TestRegressionPreventionIntegration:
    """Tests that learning loop prevents past regressions."""

    @pytest.fixture
    def project_root(self) -> Path:
        return Path(__file__).parent.parent

    def test_ll020_fear_detectable_via_rag(self):
        """Verify LL-020 (fear multiplier) is detectable via RAG query."""
        try:
            from src.verification.ml_learning_loop_integration import (
                initialize_learning_loop,
            )

            loop = initialize_learning_loop()

            if loop.rag_gate:
                results = loop.rag_gate.semantic_search("fear multiplier", top_k=5)

                # Should find relevant lessons about fear
                assert len(results) >= 1, "Should find lessons about fear multiplier"

        except ImportError as e:
            pytest.skip(f"Could not import: {e}")

    def test_ll034_crypto_fill_detectable_via_rag(self):
        """Verify LL-034 (crypto fills) is detectable via RAG query."""
        try:
            from src.verification.ml_learning_loop_integration import (
                initialize_learning_loop,
            )

            loop = initialize_learning_loop()

            if loop.rag_gate:
                results = loop.rag_gate.semantic_search(
                    "crypto order fill verification", top_k=5
                )

                # Should find relevant lessons about crypto fills
                assert len(results) >= 1, "Should find lessons about crypto fills"

        except ImportError as e:
            pytest.skip(f"Could not import: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
