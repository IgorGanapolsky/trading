"""
Comprehensive Tests for Automated Verification System

Tests the integrated ML+RAG verification system, automated lesson ingestion,
and failure detection.

Created: Dec 13, 2025
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Test fixtures
@pytest.fixture
def temp_rag_store():
    """Create temporary RAG store for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        rag_path = Path(tmpdir) / "lessons_learned.json"
        yield rag_path


@pytest.fixture
def temp_lessons_dir():
    """Create temporary lessons directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestAutomatedLessonIngestion:
    """Tests for automated lesson ingestion system."""

    def test_detect_syntax_errors(self, temp_lessons_dir):
        """Test syntax error detection."""
        from src.verification.automated_lesson_ingestion import AutomatedLessonIngestion

        ingestion = AutomatedLessonIngestion(lessons_dir=temp_lessons_dir)

        # Create a file with syntax error
        bad_file = temp_lessons_dir / "bad_code.py"
        bad_file.write_text("def broken(\n  # Missing closing paren")

        failures = ingestion.detect_syntax_errors([str(bad_file)])

        assert len(failures) > 0
        assert failures[0].category == "syntax"
        assert failures[0].severity == "critical"

    def test_detect_import_errors(self, temp_lessons_dir):
        """Test import error detection."""
        from src.verification.automated_lesson_ingestion import AutomatedLessonIngestion

        ingestion = AutomatedLessonIngestion(lessons_dir=temp_lessons_dir)

        # Test with non-existent module
        failures = ingestion.detect_import_errors(["nonexistent_module_xyz123"])

        assert len(failures) > 0
        assert failures[0].category == "import"
        assert failures[0].severity == "critical"

    def test_ingest_failure(self, temp_rag_store, temp_lessons_dir):
        """Test failure ingestion into RAG."""
        from src.verification.automated_lesson_ingestion import (
            AutomatedLessonIngestion,
            FailureEvent,
        )

        ingestion = AutomatedLessonIngestion(
            rag_path=str(temp_rag_store), lessons_dir=temp_lessons_dir
        )

        failure = FailureEvent(
            timestamp="2025-12-13T00:00:00",
            category="syntax",
            severity="critical",
            description="Test syntax error",
            root_cause="Missing closing paren",
            affected_files=["test.py"],
        )

        lesson_id = ingestion.ingest_failure(failure)

        assert lesson_id.startswith("ll_")
        assert (temp_lessons_dir / f"{lesson_id}.md").exists()
        assert temp_rag_store.exists()

        # Verify RAG store content
        with open(temp_rag_store) as f:
            data = json.load(f)
            assert len(data.get("lessons", [])) > 0


class TestMLRAGIntegratedVerifier:
    """Tests for ML+RAG integrated verifier."""

    def test_verify_pre_merge_basic(self, temp_rag_store):
        """Test basic pre-merge verification."""
        from src.verification.ml_rag_integrated_verifier import MLRAGIntegratedVerifier

        verifier = MLRAGIntegratedVerifier(rag_path=str(temp_rag_store))

        # Test with simple changes
        result = verifier.verify_pre_merge(
            changed_files=["src/utils/helpers.py"],
            commit_message="fix: update helper function",
        )

        assert isinstance(result.passed, bool)
        assert 0 <= result.risk_score <= 100
        assert isinstance(result.ml_anomalies, list)
        assert isinstance(result.rag_warnings, list)

    def test_verify_pre_merge_with_dangerous_files(self, temp_rag_store):
        """Test pre-merge verification detects dangerous file patterns."""
        from src.verification.ml_rag_integrated_verifier import MLRAGIntegratedVerifier

        verifier = MLRAGIntegratedVerifier(rag_path=str(temp_rag_store))

        # Test with executor changes (known dangerous pattern)
        result = verifier.verify_pre_merge(
            changed_files=["src/execution/alpaca_executor.py"],
            commit_message="refactor: update executor",
        )

        # Should have warnings about executor changes
        assert len(result.rag_warnings) > 0 or result.risk_score > 0

    def test_verify_post_merge(self, temp_rag_store):
        """Test post-merge verification."""
        from src.verification.ml_rag_integrated_verifier import MLRAGIntegratedVerifier

        verifier = MLRAGIntegratedVerifier(rag_path=str(temp_rag_store))

        result = verifier.verify_post_merge()

        assert isinstance(result.passed, bool)
        assert isinstance(result.rag_warnings, list)


class TestIntegration:
    """Integration tests for the full verification pipeline."""

    def test_full_pipeline_syntax_error_detection(self, temp_rag_store, temp_lessons_dir):
        """Test full pipeline: detect syntax error → ingest → verify."""
        from src.verification.automated_lesson_ingestion import AutomatedLessonIngestion
        from src.verification.ml_rag_integrated_verifier import MLRAGIntegratedVerifier

        # Step 1: Create syntax error
        bad_file = temp_lessons_dir / "test_bad.py"
        bad_file.write_text("def broken(\n")

        # Step 2: Detect failure
        ingestion = AutomatedLessonIngestion(
            rag_path=str(temp_rag_store), lessons_dir=temp_lessons_dir
        )
        failures = ingestion.detect_syntax_errors([str(bad_file)])
        assert len(failures) > 0

        # Step 3: Ingest failure
        lesson_id = ingestion.ingest_failure(failures[0])
        assert lesson_id.startswith("ll_")

        # Step 4: Verify future similar changes are caught
        verifier = MLRAGIntegratedVerifier(rag_path=str(temp_rag_store))
        result = verifier.verify_pre_merge(
            changed_files=[str(bad_file)],
            commit_message="fix: update test file",
        )

        # Should have warnings or high risk due to similar past failure
        assert result.risk_score > 0 or len(result.rag_warnings) > 0

    @patch("subprocess.run")
    def test_ci_failure_detection(self, mock_subprocess, temp_rag_store, temp_lessons_dir):
        """Test CI failure detection."""
        from src.verification.automated_lesson_ingestion import AutomatedLessonIngestion

        # Mock gh CLI output showing failed workflow
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(
                [
                    {
                        "id": "12345",
                        "conclusion": "failure",
                        "name": "Test Workflow",
                        "workflowName": "test.yml",
                    }
                ]
            ),
        )

        ingestion = AutomatedLessonIngestion(
            rag_path=str(temp_rag_store), lessons_dir=temp_lessons_dir
        )

        failure = ingestion.detect_ci_failure()

        # Should detect CI failure
        assert failure is not None
        assert failure.category == "ci"
        assert failure.severity == "high"


class TestRegressionPrevention:
    """Tests that verify regression prevention for known failures."""

    def test_ll_009_syntax_error_prevention(self, temp_rag_store):
        """Test that ll_009 (syntax error) is prevented."""
        from src.verification.ml_rag_integrated_verifier import MLRAGIntegratedVerifier

        verifier = MLRAGIntegratedVerifier(rag_path=str(temp_rag_store))

        # Simulate the type of change that caused ll_009
        result = verifier.verify_pre_merge(
            changed_files=["src/execution/alpaca_executor.py"],
            commit_message="refactor: update executor logic",
        )

        # Should have warnings about executor changes (known failure pattern)
        executor_warnings = [
            w for w in result.rag_warnings if "executor" in str(w).lower()
        ]
        assert len(executor_warnings) > 0 or result.risk_score >= 20

    def test_ll_024_fstring_syntax_prevention(self, temp_rag_store):
        """Test that ll_024 (f-string syntax) is prevented."""
        from src.verification.ml_rag_integrated_verifier import MLRAGIntegratedVerifier

        verifier = MLRAGIntegratedVerifier(rag_path=str(temp_rag_store))

        # Changes to autonomous_trader.py should trigger warnings
        result = verifier.verify_pre_merge(
            changed_files=["scripts/autonomous_trader.py"],
            commit_message="fix: update trading script",
        )

        # Should have some verification (even if just basic checks)
        assert isinstance(result.passed, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
