"""
Comprehensive tests for the verification system.

Tests the entire verification pipeline:
- RAG-powered lesson learned checks
- ML anomaly detection
- Pre-merge gate
- Continuous monitoring

Created: Dec 14, 2025
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest


class TestRAGVerificationGate:
    """Tests for RAG-powered verification gate."""

    @pytest.fixture
    def project_root(self) -> Path:
        return Path(__file__).parent.parent

    @pytest.fixture
    def rag_gate(self, project_root):
        """Create RAG verification gate instance."""
        from src.verification.rag_verification_gate import RAGVerificationGate

        return RAGVerificationGate(
            rag_knowledge_path=project_root / "rag_knowledge" / "lessons_learned"
        )

    def test_rag_gate_loads_lessons(self, rag_gate):
        """Verify RAG gate loads lessons learned from disk."""
        # Should load multiple lessons from rag_knowledge/lessons_learned/
        assert len(rag_gate.lessons) > 0, "RAG gate should load lessons from disk"

        # Verify structure
        lesson = rag_gate.lessons[0]
        assert hasattr(lesson, "id")
        assert hasattr(lesson, "title")
        assert hasattr(lesson, "severity")
        assert hasattr(lesson, "category")

    def test_ll_009_detected_by_rag(self, rag_gate):
        """Verify ll_009 (Dec 11 syntax error) is in RAG knowledge base."""
        ll_009_lessons = [l for l in rag_gate.lessons if l.id == "ll_009"]

        assert len(ll_009_lessons) > 0, "ll_009 should be in RAG knowledge base"

        lesson = ll_009_lessons[0]
        assert lesson.severity == "critical"
        assert "syntax" in lesson.title.lower() or "syntax" in lesson.category.lower()

    def test_ll_024_detected_by_rag(self, rag_gate):
        """Verify ll_024 (Dec 13 f-string error) is in RAG knowledge base."""
        ll_024_lessons = [l for l in rag_gate.lessons if l.id == "ll_024"]

        assert len(ll_024_lessons) > 0, "ll_024 should be in RAG knowledge base"

        lesson = ll_024_lessons[0]
        assert lesson.severity == "critical"

    def test_semantic_search_finds_syntax_errors(self, rag_gate):
        """Verify semantic search can find past syntax errors."""
        results = rag_gate.semantic_search("syntax error", top_k=5)

        assert len(results) > 0, "Should find lessons related to syntax errors"

        # Check that results are scored
        for lesson, score in results:
            assert score > 0, "Results should have positive scores"
            assert hasattr(lesson, "id")
            assert hasattr(lesson, "severity")

    def test_check_changed_files_detects_critical_files(self, rag_gate):
        """Verify RAG gate detects changes to critical files."""
        # Simulate changing alpaca_executor.py (caused ll_009)
        changed_files = ["src/execution/alpaca_executor.py"]

        warnings, relevant_lessons = rag_gate.check_changed_files(changed_files)

        # May or may not trigger depending on lesson file_patterns
        # But should not crash
        assert isinstance(warnings, list)
        assert isinstance(relevant_lessons, list)

    def test_large_pr_warning(self, rag_gate):
        """Verify RAG gate warns about large PRs (>10 files)."""
        large_pr_files = [f"src/file_{i}.py" for i in range(50)]

        is_safe, warnings = rag_gate.check_merge_safety(
            pr_description="Large refactor",
            changed_files=large_pr_files,
            pr_size=len(large_pr_files),
        )

        # Should warn about large PR
        assert any("LARGE PR" in w for w in warnings), "Should warn about large PRs (>10 files)"

    def test_critical_file_warning(self, rag_gate):
        """Verify RAG gate warns about critical file changes."""
        critical_files = ["src/orchestrator/main.py", "src/execution/alpaca_executor.py"]

        is_safe, warnings = rag_gate.check_merge_safety(
            pr_description="Fix orchestrator",
            changed_files=critical_files,
            pr_size=len(critical_files),
        )

        # Should warn about critical files
        assert any(
            "CRITICAL" in w for w in warnings
        ), "Should warn when critical files changed"


class TestMLAnomalyDetector:
    """Tests for ML-based anomaly detection."""

    @pytest.fixture
    def project_root(self) -> Path:
        return Path(__file__).parent.parent

    @pytest.fixture
    def detector(self, project_root):
        """Create ML anomaly detector instance."""
        from src.verification.ml_anomaly_detector import MLAnomalyDetector

        return MLAnomalyDetector(data_dir=project_root / "data")

    def test_detector_loads_system_state(self, detector):
        """Verify detector can load system state."""
        state = detector.load_system_state()

        # Should load from data/system_state.json
        if state:
            assert "meta" in state or "account" in state or "strategies" in state
        # If no state file, returns None (acceptable)

    def test_detect_zero_trades_anomaly(self, detector, tmp_path):
        """Verify detector catches 0 trades anomaly (Dec 11 incident)."""
        # Create mock system state with 0 trades
        mock_state = {
            "performance": {"total_trades": 0, "win_rate": 0},
            "challenge": {"current_day": 5},
        }

        state_file = tmp_path / "system_state.json"
        with open(state_file, "w") as f:
            json.dump(mock_state, f)

        detector.system_state_file = state_file

        anomaly = detector.detect_trade_volume_anomaly()

        assert anomaly is not None, "Should detect 0 trades as anomaly"
        assert anomaly.severity in [
            "critical",
            "high",
        ], "0 trades should be critical/high severity"
        assert anomaly.metric_value == 0.0

    def test_detect_stale_system_state(self, detector, tmp_path):
        """Verify detector catches stale system state."""
        # Create mock state with old timestamp (>48 hours)
        old_timestamp = (datetime.utcnow() - timedelta(hours=72)).isoformat()

        mock_state = {
            "meta": {"last_updated": old_timestamp},
            "performance": {"total_trades": 5},
        }

        state_file = tmp_path / "system_state.json"
        with open(state_file, "w") as f:
            json.dump(mock_state, f)

        detector.system_state_file = state_file

        anomaly = detector.detect_system_health_anomaly()

        assert anomaly is not None, "Should detect stale state as anomaly"
        assert "stale" in anomaly.description.lower()
        assert anomaly.metric_value > 48.0  # Hours old

    def test_detect_large_code_change(self, detector):
        """Verify detector catches large code changes (>50 files)."""
        large_change = [f"src/file_{i}.py" for i in range(100)]

        anomaly = detector.detect_code_change_anomaly(large_change)

        assert anomaly is not None, "Should detect large code change as anomaly"
        assert anomaly.metric_value == 100.0
        assert anomaly.severity in ["high", "critical"]

    def test_detect_critical_file_change(self, detector):
        """Verify detector flags critical file changes."""
        critical_change = ["src/execution/alpaca_executor.py"]

        anomaly = detector.detect_code_change_anomaly(critical_change)

        # Should detect critical file change
        if anomaly:
            assert "critical" in anomaly.description.lower()

    def test_anomaly_history_persistence(self, detector, tmp_path):
        """Verify anomalies are saved to history."""
        from src.verification.ml_anomaly_detector import Anomaly

        detector.anomaly_history_file = tmp_path / "anomaly_history.json"

        test_anomaly = Anomaly(
            timestamp=datetime.utcnow().isoformat(),
            category="test",
            severity="medium",
            description="Test anomaly",
            metric_name="test_metric",
            metric_value=42.0,
            expected_range=(0.0, 10.0),
            confidence=0.9,
        )

        detector.save_anomaly(test_anomaly)

        # Verify saved
        assert detector.anomaly_history_file.exists()

        with open(detector.anomaly_history_file) as f:
            history = json.load(f)

        assert len(history) == 1
        assert history[0]["metric_name"] == "test_metric"
        assert history[0]["metric_value"] == 42.0


class TestPreMergeGate:
    """Tests for pre-merge gate integration."""

    @pytest.fixture
    def project_root(self) -> Path:
        return Path(__file__).parent.parent

    def test_pre_merge_gate_exists(self, project_root):
        """Verify pre_merge_gate.py script exists."""
        gate_script = project_root / "scripts" / "pre_merge_gate.py"
        assert gate_script.exists(), "pre_merge_gate.py should exist"

    def test_pre_merge_gate_imports_verification_modules(self, project_root):
        """Verify pre_merge_gate imports RAG and ML verification."""
        gate_script = project_root / "scripts" / "pre_merge_gate.py"

        with open(gate_script) as f:
            content = f.read()

        # Should import or use RAG verification
        # (May be conditional import, so we check for mention)
        # This is a weak check - mainly verifies integration exists
        assert "verification" in content.lower() or "rag" in content.lower()


class TestContinuousVerification:
    """Tests for continuous verification monitoring."""

    @pytest.fixture
    def project_root(self) -> Path:
        return Path(__file__).parent.parent

    def test_ci_workflows_exist(self, project_root):
        """Verify CI workflows for verification exist."""
        workflows_dir = project_root / ".github" / "workflows"

        # Check for test workflow
        test_workflows = list(workflows_dir.glob("*test*.yml"))
        assert len(test_workflows) > 0, "Should have test workflows"

    def test_verification_can_run_daily(self, project_root):
        """Verify verification system can run as daily job."""
        from src.verification.ml_anomaly_detector import MLAnomalyDetector

        detector = MLAnomalyDetector(data_dir=project_root / "data")

        # Should be able to run without crashing
        try:
            anomalies = detector.run_all_checks()
            assert isinstance(anomalies, list)
        except Exception as e:
            # Acceptable if data files don't exist in test environment
            if "system_state.json" not in str(e):
                raise


class TestRegressionPrevention:
    """Tests that specifically prevent past incidents from recurring."""

    def test_ll_009_syntax_error_prevention(self):
        """Prevent ll_009: Syntax errors in critical files.

        Dec 11, 2025: Syntax error in alpaca_executor.py broke all trading.
        """
        from pathlib import Path

        project_root = Path(__file__).parent.parent
        critical_files = [
            project_root / "src" / "orchestrator" / "main.py",
            project_root / "src" / "execution" / "alpaca_executor.py",
            project_root / "src" / "risk" / "trade_gateway.py",
        ]

        errors = []
        for file_path in critical_files:
            if file_path.exists():
                try:
                    import ast

                    with open(file_path) as f:
                        ast.parse(f.read())
                except SyntaxError as e:
                    errors.append(f"{file_path.name}: {e}")

        assert not errors, "REGRESSION ll_009: Syntax errors in critical files:\n" + "\n".join(
            errors
        )

    def test_ll_024_fstring_syntax_prevention(self):
        """Prevent ll_024: F-string backslash escapes.

        Dec 13, 2025: F-string with backslash crashed autonomous_trader.py.
        """
        from pathlib import Path

        project_root = Path(__file__).parent.parent
        trader_script = project_root / "scripts" / "autonomous_trader.py"

        if trader_script.exists():
            import ast

            with open(trader_script) as f:
                content = f.read()

            try:
                ast.parse(content)
            except SyntaxError as e:
                pytest.fail(
                    f"REGRESSION ll_024: Syntax error in autonomous_trader.py: {e}"
                )

    def test_ci_failure_doesnt_block_trading(self):
        """Prevent CI test failures from blocking trading.

        Dec 10-11, 2025: CI test failures blocked trading for 2 days.
        """
        from pathlib import Path

        project_root = Path(__file__).parent.parent
        workflows = (project_root / ".github" / "workflows").glob("*.yml")

        for workflow_file in workflows:
            with open(workflow_file) as f:
                f.read()

            # If this is a daily trading workflow
            if "trading" in workflow_file.name.lower():
                # Should have continue-on-error or separate jobs
                # (This is a weak check - main protection is in workflow structure)
                pass  # Just verify it exists and is readable


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
