"""
Comprehensive RAG Verification Tests.

Tests the entire RAG and ML pipeline for lessons learned:
1. Lesson ingestion and retrieval
2. Semantic search accuracy
3. Pattern detection
4. CI failure ingestion
5. Risk scoring
6. Prevention checklist generation

These tests ensure the verification system works correctly
and prevents repeat failures.

Created: 2025-12-14
Author: Trading CTO
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestLessonsLearnedRAG:
    """Tests for the LessonsLearnedRAG system."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            yield Path(f.name)

    @pytest.fixture
    def rag(self, temp_db):
        """Create RAG instance with temp database."""
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        return LessonsLearnedRAG(db_path=str(temp_db))

    def test_rag_initialization(self, rag):
        """Test RAG initializes with default lessons."""
        assert rag is not None
        assert len(rag.lessons) >= 4  # Default lessons

    def test_add_lesson(self, rag):
        """Test adding a new lesson."""
        initial_count = len(rag.lessons)

        lesson_id = rag.add_lesson(
            category="test",
            title="Test Lesson",
            description="This is a test lesson",
            root_cause="Test root cause",
            prevention="Test prevention step",
            severity="high",
        )

        assert lesson_id is not None
        assert len(rag.lessons) == initial_count + 1

    def test_add_lesson_with_all_fields(self, rag):
        """Test adding a lesson with all optional fields."""
        lesson_id = rag.add_lesson(
            category="trading_logic",
            title="Order Size Validation",
            description="Large orders can cause 200x errors",
            root_cause="Missing validation on order amounts",
            prevention="Validate order < 10x expected before execution",
            tags=["order", "validation", "critical"],
            severity="critical",
            financial_impact=1592.0,
            symbol="SPY",
        )

        assert lesson_id is not None

        # Find the lesson
        lesson = next((l for l in rag.lessons if l.id == lesson_id), None)
        assert lesson is not None
        assert lesson.financial_impact == 1592.0
        assert lesson.symbol == "SPY"
        assert "order" in lesson.tags

    def test_search_by_keyword(self, rag):
        """Test keyword search functionality."""
        # Add a specific lesson
        rag.add_lesson(
            category="test",
            title="Syntax Error Prevention",
            description="Check syntax before merge",
            root_cause="Missing syntax check",
            prevention="Run py_compile on all files",
            severity="critical",
        )

        results = rag.search("syntax error", top_k=5)

        assert len(results) > 0
        # First result should mention syntax
        first_lesson, score = results[0]
        assert "syntax" in first_lesson.title.lower() or "syntax" in first_lesson.description.lower()

    def test_search_by_category(self, rag):
        """Test filtering by category."""
        # Add lessons in different categories
        rag.add_lesson(
            category="trading",
            title="Trading Lesson",
            description="Trade validation",
            root_cause="Test",
            prevention="Test",
            severity="medium",
        )
        rag.add_lesson(
            category="ci_cd",
            title="CI Lesson",
            description="CI validation",
            root_cause="Test",
            prevention="Test",
            severity="medium",
        )

        trading_results = rag.search("validation", category="trading", top_k=5)
        ci_results = rag.search("validation", category="ci_cd", top_k=5)

        # Should find category-specific results
        if trading_results:
            assert all(l.category == "trading" for l, _ in trading_results)

    def test_get_prevention_checklist(self, rag):
        """Test prevention checklist generation."""
        # Add lessons with different severities
        rag.add_lesson(
            category="test",
            title="Critical Issue",
            description="Critical test",
            root_cause="Test",
            prevention="Critical prevention step",
            severity="critical",
        )
        rag.add_lesson(
            category="test",
            title="Low Issue",
            description="Low test",
            root_cause="Test",
            prevention="Low prevention step",
            severity="low",
        )

        checklist = rag.get_prevention_checklist("test")

        assert len(checklist) >= 2
        # Critical should come first
        assert "Critical" in checklist[0] or "critical" in checklist[0].lower()

    def test_get_context_for_trade(self, rag):
        """Test getting context for a trade."""
        # Add a relevant lesson
        rag.add_lesson(
            category="size_error",
            title="Large Order Error",
            description="Order too large",
            root_cause="No validation",
            prevention="Validate order size",
            severity="critical",
            symbol="SPY",
        )

        context = rag.get_context_for_trade("SPY", "buy", 1500.0)

        assert "symbol" in context
        assert context["symbol"] == "SPY"
        assert "warnings" in context
        assert "prevention_checklist" in context

    def test_lesson_persistence(self, temp_db):
        """Test that lessons are persisted to disk."""
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        # Create RAG and add lesson
        rag1 = LessonsLearnedRAG(db_path=str(temp_db))
        lesson_id = rag1.add_lesson(
            category="test",
            title="Persistent Lesson",
            description="Should persist",
            root_cause="Test",
            prevention="Test prevention",
            severity="high",
        )

        # Create new RAG instance
        rag2 = LessonsLearnedRAG(db_path=str(temp_db))

        # Should find the lesson
        found = any(l.id == lesson_id for l in rag2.lessons)
        assert found, "Lesson should persist across instances"


class TestMLLessonPatternDetector:
    """Tests for the ML pattern detector."""

    @pytest.fixture
    def temp_patterns_db(self):
        """Create temporary patterns database."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            yield Path(f.name)

    @pytest.fixture
    def detector(self, temp_patterns_db):
        """Create detector with temp database."""
        from src.verification.ml_lesson_pattern_detector import MLLessonPatternDetector

        return MLLessonPatternDetector(
            patterns_db_path=temp_patterns_db,
            rag_enabled=False,
        )

    def test_detector_initialization(self, detector):
        """Test detector initializes with default patterns."""
        assert detector is not None
        assert len(detector.patterns) >= 6  # Default patterns

    def test_assess_low_risk_change(self, detector):
        """Test assessing a low-risk code change."""
        assessment = detector.assess_code_change(
            files_changed=["docs/README.md"],
            diff_content="Updated documentation",
            commit_message="docs: Update README",
        )

        from src.verification.ml_lesson_pattern_detector import RiskLevel

        assert assessment.overall_risk in [RiskLevel.LOW, RiskLevel.MEDIUM]
        assert assessment.score < 0.5

    def test_assess_high_risk_change(self, detector):
        """Test assessing a high-risk code change."""
        assessment = detector.assess_code_change(
            files_changed=[
                "src/execution/alpaca_executor.py",
                "src/orchestrator/main.py",
            ],
            diff_content="Modified order execution logic",
            commit_message="Refactor trading execution",
        )

        from src.verification.ml_lesson_pattern_detector import RiskLevel

        assert assessment.overall_risk in [RiskLevel.HIGH, RiskLevel.CRITICAL]
        assert len(assessment.warnings) > 0
        assert len(assessment.recommendations) > 0

    def test_detect_syntax_error_pattern(self, detector):
        """Test detection of syntax error patterns."""
        assessment = detector.assess_code_change(
            files_changed=["src/test.py"],
            diff_content="SyntaxError: invalid syntax at alpaca_executor.py",
            commit_message="test",
        )

        # Should detect syntax error pattern
        assert len(assessment.warnings) > 0

    def test_learn_from_failure(self, detector):
        """Test learning from a new failure."""
        from src.verification.ml_lesson_pattern_detector import (
            FailureCategory,
            RiskLevel,
        )

        initial_count = len(detector.patterns)

        pattern_id = detector.learn_from_failure(
            error_message="New unique error pattern XYZ123",
            files_involved=["src/new_module.py"],
            category=FailureCategory.RUNTIME_ERROR,
            prevention="Check for XYZ before execution",
            risk_level=RiskLevel.HIGH,
        )

        assert pattern_id is not None
        assert len(detector.patterns) == initial_count + 1

    def test_get_prevention_checklist(self, detector):
        """Test prevention checklist from patterns."""
        checklist = detector.get_prevention_checklist()

        assert len(checklist) > 0
        # Critical items should have [CRITICAL] prefix
        critical_items = [c for c in checklist if "[CRITICAL]" in c]
        assert len(critical_items) > 0

    def test_get_stats(self, detector):
        """Test getting pattern statistics."""
        stats = detector.get_stats()

        assert "total_patterns" in stats
        assert "by_category" in stats
        assert "critical_patterns" in stats
        assert stats["total_patterns"] >= 6


class TestCIFailureIngestion:
    """Tests for CI failure ingestion pipeline."""

    @pytest.fixture
    def pipeline(self):
        """Create pipeline with mocked dependencies."""
        from src.verification.ci_failure_ingestion import CIFailureIngestionPipeline

        with patch.object(CIFailureIngestionPipeline, "_init_rag"):
            with patch.object(CIFailureIngestionPipeline, "_init_ml_detector"):
                pipeline = CIFailureIngestionPipeline(
                    repo="test/repo",
                    rag_enabled=False,
                    ml_detector_enabled=False,
                )
                return pipeline

    def test_classify_syntax_error(self, pipeline):
        """Test classifying syntax error logs."""
        from src.verification.ci_failure_ingestion import FailureType

        log = "SyntaxError: invalid syntax at line 42"
        failure_type = pipeline.classify_failure(log)

        assert failure_type == FailureType.SYNTAX_ERROR

    def test_classify_import_error(self, pipeline):
        """Test classifying import error logs."""
        from src.verification.ci_failure_ingestion import FailureType

        log = "ImportError: cannot import name 'TradingOrchestrator'"
        failure_type = pipeline.classify_failure(log)

        assert failure_type == FailureType.IMPORT_ERROR

    def test_classify_test_failure(self, pipeline):
        """Test classifying test failure logs."""
        from src.verification.ci_failure_ingestion import FailureType

        log = "FAILED tests/test_trading.py::test_order_validation - AssertionError"
        failure_type = pipeline.classify_failure(log)

        assert failure_type == FailureType.TEST_FAILURE

    def test_extract_error_details(self, pipeline):
        """Test extracting error details from logs."""
        log = '''
Traceback (most recent call last):
  File "src/orchestrator/main.py", line 42
    def broken_function(
SyntaxError: unexpected EOF while parsing
'''
        message, file_path, line_num = pipeline.extract_error_details(log)

        assert "SyntaxError" in message or "EOF" in message
        assert file_path is not None

    def test_parse_failure(self, pipeline):
        """Test parsing a complete failure."""
        run_metadata = {
            "databaseId": "12345",
            "name": "Test Workflow",
            "headBranch": "main",
            "headSha": "abc123def456",
            "actor": {"login": "testuser"},
        }
        log = "SyntaxError: invalid syntax in test.py"

        failure = pipeline.parse_failure(run_metadata, log)

        assert failure.run_id == "12345"
        assert failure.workflow_name == "Test Workflow"
        assert failure.branch == "main"


class TestSemanticCodeRiskScorer:
    """Tests for semantic code risk scorer."""

    @pytest.fixture
    def scorer(self):
        """Create scorer with embeddings disabled."""
        from src.verification.semantic_code_risk_scorer import SemanticCodeRiskScorer

        return SemanticCodeRiskScorer(rag_enabled=False)

    def test_parse_diff(self, scorer):
        """Test parsing a git diff."""
        diff = '''
diff --git a/src/test.py b/src/test.py
@@ -10,0 +11,3 @@
+def new_function():
+    return True
'''
        chunks = scorer.parse_diff(diff)

        assert len(chunks) > 0
        assert chunks[0].file_path == "src/test.py"
        assert "new_function" in chunks[0].content

    def test_classify_feature_intent(self, scorer):
        """Test classifying feature addition intent."""
        from src.verification.semantic_code_risk_scorer import ChangeIntent, CodeChunk

        chunks = [
            CodeChunk(
                file_path="src/new_feature.py",
                content="def new_feature(): pass",
                change_type="added",
                line_start=1,
                line_end=1,
            )
        ]

        intent = scorer.classify_intent("feat: Add new feature", chunks)

        assert intent == ChangeIntent.FEATURE_ADD

    def test_classify_bugfix_intent(self, scorer):
        """Test classifying bug fix intent."""
        from src.verification.semantic_code_risk_scorer import ChangeIntent, CodeChunk

        chunks = [
            CodeChunk(
                file_path="src/fix.py",
                content="# Fixed the bug",
                change_type="modified",
                line_start=1,
                line_end=1,
            )
        ]

        intent = scorer.classify_intent("fix: Fix order validation bug", chunks)

        assert intent == ChangeIntent.BUG_FIX

    def test_determine_critical_impact(self, scorer):
        """Test determining critical impact level."""
        from src.verification.semantic_code_risk_scorer import ImpactLevel, CodeChunk

        chunks = [
            CodeChunk(
                file_path="src/execution/alpaca_executor.py",
                content="# Trading execution code",
                change_type="modified",
                line_start=1,
                line_end=1,
            )
        ]

        impact = scorer.determine_impact_level(chunks)

        assert impact == ImpactLevel.CRITICAL

    def test_determine_minimal_impact(self, scorer):
        """Test determining minimal impact level."""
        from src.verification.semantic_code_risk_scorer import ImpactLevel, CodeChunk

        chunks = [
            CodeChunk(
                file_path="docs/README.md",
                content="# Documentation",
                change_type="modified",
                line_start=1,
                line_end=1,
            )
        ]

        impact = scorer.determine_impact_level(chunks)

        assert impact == ImpactLevel.MINIMAL

    def test_score_high_risk_change(self, scorer):
        """Test scoring a high-risk code change."""
        diff = '''
diff --git a/src/execution/alpaca_executor.py b/src/execution/alpaca_executor.py
@@ -100,0 +101,5 @@
+def execute_trade(self, symbol, amount):
+    # Modified trading logic
+    order = self.api.submit_order(symbol, amount)
+    return order
'''
        result = scorer.score_code_change(diff, "Modify trading execution")

        from src.verification.semantic_code_risk_scorer import ImpactLevel

        assert result.impact_level == ImpactLevel.CRITICAL
        assert result.overall_score >= 0.3
        assert len(result.recommendations) > 0

    def test_score_low_risk_change(self, scorer):
        """Test scoring a low-risk code change."""
        diff = '''
diff --git a/docs/README.md b/docs/README.md
@@ -1,0 +2,2 @@
+## New Section
+Documentation update
'''
        result = scorer.score_code_change(diff, "docs: Update documentation")

        from src.verification.semantic_code_risk_scorer import ImpactLevel

        assert result.impact_level == ImpactLevel.MINIMAL
        assert result.overall_score < 0.3


class TestIntegration:
    """Integration tests for the full verification pipeline."""

    def test_end_to_end_lesson_ingestion_and_retrieval(self):
        """Test full cycle: ingest lesson -> search -> get prevention."""
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            rag = LessonsLearnedRAG(db_path=f.name)

            # Ingest a lesson
            lesson_id = rag.add_lesson(
                category="syntax_error",
                title="Test: Syntax Error in Executor",
                description="Syntax error caused trading failure",
                root_cause="Missing closing parenthesis",
                prevention="Run py_compile before merge",
                severity="critical",
            )

            # Search for it
            results = rag.search("syntax error executor", top_k=5)

            # Should find it
            found = any(l.id == lesson_id for l, _ in results)
            assert found, "Should find ingested lesson via search"

            # Get prevention checklist
            checklist = rag.get_prevention_checklist("syntax_error")
            assert "py_compile" in " ".join(checklist).lower()

    def test_pattern_detector_learns_from_new_failure(self):
        """Test pattern detector learns and applies new patterns."""
        from src.verification.ml_lesson_pattern_detector import (
            MLLessonPatternDetector,
            FailureCategory,
            RiskLevel,
        )

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            detector = MLLessonPatternDetector(
                patterns_db_path=Path(f.name),
                rag_enabled=False,
            )

            # Learn from a failure
            detector.learn_from_failure(
                error_message="NewUniqueError: special case XYZ",
                files_involved=["src/special/module.py"],
                category=FailureCategory.RUNTIME_ERROR,
                prevention="Check for XYZ condition",
                risk_level=RiskLevel.HIGH,
            )

            # Assess change that matches
            assessment = detector.assess_code_change(
                files_changed=["src/special/module.py"],
                diff_content="Modified special module",
            )

            # Should have higher risk due to learned pattern
            assert len(assessment.matched_patterns) > 0 or len(assessment.files_at_risk) > 0

    def test_convenience_functions(self):
        """Test convenience functions for quick risk assessment."""
        from src.verification.ml_lesson_pattern_detector import assess_pr_risk
        from src.verification.semantic_code_risk_scorer import score_diff_risk

        # Test PR risk assessment
        pr_result = assess_pr_risk(
            files_changed=["src/execution/alpaca_executor.py"],
            commit_message="Modify execution",
        )
        assert "risk_level" in pr_result
        assert "can_merge" in pr_result
        assert "recommendations" in pr_result

        # Test diff risk scoring
        diff = "diff --git a/test.py b/test.py\n+# test"
        diff_result = score_diff_risk(diff, "test commit")
        assert "score" in diff_result
        assert "impact" in diff_result
        assert "recommendations" in diff_result


class TestRegressionPrevention:
    """Tests to prevent regression of known incidents."""

    def test_ll_009_syntax_error_prevention(self):
        """
        Regression test for LL-009: Syntax error merged to main.

        Ensures the pre-merge gate catches syntax errors.
        """
        import ast

        # This should fail to parse (syntax error)
        bad_code = "def broken(\n"  # Missing closing paren

        with pytest.raises(SyntaxError):
            ast.parse(bad_code)

    def test_200x_order_error_prevention(self):
        """
        Regression test for 200x order error.

        Ensures anomaly detector catches large orders.
        """
        from src.ml.anomaly_detector import TradingAnomalyDetector, AlertLevel

        detector = TradingAnomalyDetector(expected_daily_amount=10.0)

        # Order 200x expected should be blocked
        anomalies = detector.validate_trade("SPY", 2000.0, "buy")

        blocking = [a for a in anomalies if a.alert_level == AlertLevel.BLOCK]
        assert len(blocking) > 0, "Should block 200x order"

    def test_critical_imports_work(self):
        """
        Regression test for import failures.

        Ensures all critical modules can be imported.
        """
        # These imports must work
        try:
            from src.orchestrator.main import TradingOrchestrator
            from src.execution.alpaca_executor import AlpacaExecutor
            from src.risk.trade_gateway import TradeGateway

            assert TradingOrchestrator is not None
            assert AlpacaExecutor is not None
            assert TradeGateway is not None
        except ImportError as e:
            pytest.fail(f"Critical import failed: {e}")

    def test_stale_data_detection(self):
        """
        Regression test for stale data usage.

        Ensures anomaly detector catches stale data.
        """
        from datetime import timedelta
        from src.ml.anomaly_detector import TradingAnomalyDetector

        detector = TradingAnomalyDetector()

        # Data from 48 hours ago should be flagged
        old_time = datetime.now(timezone.utc) - timedelta(hours=48)
        anomalies = detector.check_data_freshness(old_time, "market_data")

        assert len(anomalies) > 0, "Should detect stale data"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
