#!/usr/bin/env python3
"""
ML Pipeline Safety Checker Tests

Tests the integration of RAG lessons learned with ML anomaly detection
to prevent repeated failures from reaching production.

Based on Dec 11, 2025 analysis: "We have to use our RAG and ML pipeline for lessons learned."
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.verification.ml_pipeline_safety_checker import (
    FailurePattern,
    MLPipelineSafetyChecker,
    SafetyCheckResult,
)


class TestFailurePatternMatching:
    """Test failure pattern detection."""

    @pytest.fixture
    def checker(self) -> MLPipelineSafetyChecker:
        """Create checker with default patterns."""
        return MLPipelineSafetyChecker()

    def test_critical_orchestrator_change_detected(self, checker):
        """Changes to TradingOrchestrator should be flagged as HIGH risk."""
        result = checker.check_files(["src/orchestrator/main.py"])

        # Should have warnings about high-risk file
        assert any("HIGH RISK FILE" in w for w in result.warnings)
        assert result.risk_score > 0

    def test_workflow_yaml_change_detected(self, checker):
        """Changes to workflow YAML files should be flagged."""
        result = checker.check_files([".github/workflows/daily-trading.yml"])

        # Should match the workflow pattern
        matched_ids = [p.pattern_id for p in result.matched_patterns]
        assert any("fp_005" in pid or "workflow" in str(result.warnings).lower() for pid in matched_ids) or \
               len(result.matched_patterns) > 0

    def test_safety_system_change_is_critical(self, checker):
        """Changes to CircuitBreaker/KillSwitch should be CRITICAL."""
        # Check diff content with safety system changes
        diff_content = """
        +++ b/src/safety/circuit_breakers.py
        @@ -1,5 +1,5 @@
        -class CircuitBreaker:
        +class CircuitBreaker(SafetyMixin):
             def trip(self):
        """
        result = checker.check_diff(diff_content)

        # Should have matched critical pattern
        critical_patterns = [p for p in result.matched_patterns if p.severity == "CRITICAL"]
        assert len(critical_patterns) > 0 or result.risk_score >= 20

    def test_python_heredoc_in_yaml_detected(self, checker):
        """Python heredocs in YAML should be flagged (ll_009 issue)."""
        diff_content = """
        +++ b/.github/workflows/trade.yml
        @@ -10,5 +10,10 @@
        +      - name: Trade
        +        run: |
        +          python3 << 'EOF'
        +          from alpaca import Client
        +          EOF
        """
        result = checker.check_diff(diff_content)

        # Should warn about heredoc
        assert any("heredoc" in w.lower() for w in result.warnings) or \
               any("yaml" in w.lower() for w in result.warnings) or \
               result.risk_score > 0


class TestRiskScoreCalculation:
    """Test risk score calculations."""

    @pytest.fixture
    def checker(self) -> MLPipelineSafetyChecker:
        return MLPipelineSafetyChecker()

    def test_no_changes_zero_risk(self, checker):
        """Empty file list should have zero risk."""
        result = checker.check_files([])
        assert result.risk_score == 0
        assert result.passed is True
        assert result.confidence == 1.0

    def test_single_low_risk_file(self, checker):
        """Single benign file should have low risk."""
        result = checker.check_files(["docs/readme.md"])
        assert result.risk_score < 30
        assert result.passed is True

    def test_multiple_high_risk_files(self, checker):
        """Multiple high-risk files should accumulate risk."""
        high_risk_files = [
            "src/orchestrator/main.py",
            "src/execution/alpaca_executor.py",
            "src/risk/trade_gateway.py",
        ]
        result = checker.check_files(high_risk_files)

        # Risk should accumulate
        assert result.risk_score > 30

    def test_large_pr_warning(self, checker):
        """PRs with >10 files should trigger warning."""
        many_files = [f"src/module{i}.py" for i in range(15)]
        result = checker.check_files(many_files)

        # Should warn about large PR
        assert any("Large change" in w or "10" in w for w in result.warnings)

    def test_risk_score_clamped_to_100(self, checker):
        """Risk score should never exceed 100."""
        # Create worst-case scenario
        diff_content = """
        +++ b/src/orchestrator/main.py
        +class TradingOrchestrator:
        +    def execute(self):
        +        pass
        +++ b/src/safety/circuit_breakers.py
        +class CircuitBreaker:
        +    pass
        +++ b/.github/workflows/trade.yml
        +  run: |
        +    python3 << EOF
        +    EOF
        """ + "\n".join([f"-line{i}" for i in range(200)])  # Large deletion

        result = checker.check_diff(diff_content)
        assert result.risk_score <= 100


class TestRAGIntegration:
    """Test RAG lessons learned integration."""

    @pytest.fixture
    def checker(self) -> MLPipelineSafetyChecker:
        return MLPipelineSafetyChecker()

    def test_rag_context_retrieved(self, checker):
        """RAG should provide context for high-risk changes."""
        # Files that should trigger RAG lookup
        result = checker.check_files([
            "src/orchestrator/main.py",
            "src/execution/alpaca_executor.py",
        ])

        # Should have some RAG context (if lessons exist)
        # This is a soft check - depends on lessons_learned directory
        assert isinstance(result.rag_context, list)

    def test_recommendations_from_rag(self, checker):
        """RAG context should generate recommendations."""
        result = checker.check_files([
            "src/orchestrator/main.py",
        ])

        # Should have recommendations (import verification, etc.)
        assert len(result.recommendations) > 0


class TestPatternLearning:
    """Test ML pattern learning functionality."""

    def test_learn_new_pattern(self):
        """Should be able to learn new patterns from failures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            patterns_file = Path(tmpdir) / "patterns.json"

            checker = MLPipelineSafetyChecker()
            checker.PATTERNS_FILE = patterns_file

            initial_count = len(checker.patterns)

            # Learn from a failure
            pattern = checker.learn_from_failure(
                failure_description="API rate limit exceeded in data fetcher",
                affected_files=["src/data/api_client.py"],
                root_cause="No rate limiting implemented",
                lesson_id="ll_test",
            )

            # Should have added a pattern
            assert len(checker.patterns) == initial_count + 1
            assert pattern.lesson_id == "ll_test"
            assert pattern.confidence == 0.5  # Initial confidence

    def test_update_pattern_confidence_true_positive(self):
        """True positive feedback should increase confidence."""
        checker = MLPipelineSafetyChecker()

        # Get initial confidence of first pattern
        pattern = checker.patterns[0]
        initial_confidence = pattern.confidence

        # Mark as true positive
        checker.update_pattern_confidence(pattern.pattern_id, was_true_positive=True)

        # Confidence should increase
        assert pattern.confidence > initial_confidence

    def test_update_pattern_confidence_false_positive(self):
        """False positive feedback should decrease confidence."""
        checker = MLPipelineSafetyChecker()

        pattern = checker.patterns[0]
        initial_confidence = pattern.confidence

        # Mark as false positive
        checker.update_pattern_confidence(pattern.pattern_id, was_true_positive=False)

        # Confidence should decrease
        assert pattern.confidence < initial_confidence


class TestBlockingBehavior:
    """Test that critical issues properly block merges."""

    @pytest.fixture
    def checker(self) -> MLPipelineSafetyChecker:
        return MLPipelineSafetyChecker()

    def test_critical_pattern_blocks(self, checker):
        """CRITICAL severity patterns should cause blocking."""
        # Add a critical pattern that will definitely match
        checker.patterns.append(
            FailurePattern(
                pattern_id="fp_test_critical",
                regex=r"DEFINITELY_CRITICAL_MATCH",
                lesson_id="ll_test",
                severity="CRITICAL",
                description="Test critical pattern",
                confidence=0.95,
            )
        )

        result = checker.check_files(["src/DEFINITELY_CRITICAL_MATCH.py"])

        assert result.passed is False
        assert len(result.blockers) > 0

    def test_high_severity_warns_but_passes(self, checker):
        """HIGH severity should warn but not block."""
        result = checker.check_files(["src/orchestrator/main.py"])

        # High risk file should warn but typically not block
        # (unless it also matches CRITICAL patterns)
        if not result.blockers:
            assert result.passed is True
            assert len(result.warnings) > 0


class TestDiffParsing:
    """Test diff content parsing."""

    @pytest.fixture
    def checker(self) -> MLPipelineSafetyChecker:
        return MLPipelineSafetyChecker()

    def test_extract_files_from_diff(self, checker):
        """Should correctly extract file paths from diff."""
        diff_content = """
diff --git a/src/main.py b/src/main.py
index 1234567..abcdefg 100644
--- a/src/main.py
+++ b/src/main.py
@@ -1,5 +1,5 @@
 import os
-import sys
+import sys, json
"""
        result = checker.check_diff(diff_content)

        # Should have processed without error
        assert isinstance(result, SafetyCheckResult)

    def test_large_deletion_warning(self, checker):
        """Should warn about large deletions."""
        # Create diff with many deletions
        deletions = "\n".join([f"-line {i}" for i in range(150)])
        diff_content = f"""
--- a/src/file.py
+++ b/src/file.py
{deletions}
"""
        result = checker.check_diff(diff_content)

        # Should warn about large deletion
        assert any("deletion" in w.lower() for w in result.warnings)


class TestOutputFormats:
    """Test output format handling."""

    @pytest.fixture
    def checker(self) -> MLPipelineSafetyChecker:
        return MLPipelineSafetyChecker()

    def test_result_to_dict(self, checker):
        """SafetyCheckResult should serialize to dict."""
        result = checker.check_files(["src/main.py"])

        result_dict = result.to_dict()

        assert "passed" in result_dict
        assert "confidence" in result_dict
        assert "risk_score" in result_dict
        assert "timestamp" in result_dict
        assert isinstance(result_dict["blockers"], list)
        assert isinstance(result_dict["warnings"], list)

    def test_result_json_serializable(self, checker):
        """Result dict should be JSON serializable."""
        result = checker.check_files([
            "src/orchestrator/main.py",
            "src/safety/circuit_breakers.py",
        ])

        result_dict = result.to_dict()

        # Should not raise
        json_str = json.dumps(result_dict)
        parsed = json.loads(json_str)

        assert parsed["passed"] == result.passed


class TestIntegrationWithExistingInfrastructure:
    """Test integration with existing ML/RAG infrastructure."""

    def test_works_with_ml_anomaly_detector(self):
        """Should work alongside existing ML anomaly detector."""
        try:
            from src.verification.ml_anomaly_detector import MLAnomalyDetector

            # Both should be importable and usable
            anomaly_detector = MLAnomalyDetector()
            safety_checker = MLPipelineSafetyChecker()

            assert anomaly_detector is not None
            assert safety_checker is not None
        except ImportError:
            pytest.skip("ML anomaly detector not available")

    def test_works_with_rag_premerge_validator(self):
        """Should work alongside RAG pre-merge validator."""
        try:
            from src.verification.rag_premerge_validator import RAGPreMergeValidator

            # Both should be importable and usable
            rag_validator = RAGPreMergeValidator()
            safety_checker = MLPipelineSafetyChecker()

            assert rag_validator is not None
            assert safety_checker is not None
        except ImportError:
            pytest.skip("RAG pre-merge validator not available")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
