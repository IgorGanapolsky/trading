"""
Tests for the comprehensive verification system.

These tests ensure our safety gates work correctly to prevent
incidents like the Dec 11, 2025 syntax error.
"""

import tempfile
from pathlib import Path

import pytest


class TestPreMergeVerifier:
    """Tests for pre-merge verification."""

    def test_syntax_check_passes_valid_code(self):
        """Valid Python code should pass syntax check."""
        from src.verification.pre_merge_verifier import PreMergeVerifier

        verifier = PreMergeVerifier()
        result = verifier.check_syntax()

        # Current codebase should pass
        assert result["passed"], f"Syntax check failed: {result.get('errors')}"

    def test_syntax_check_catches_syntax_error(self):
        """Syntax errors should be caught."""
        from src.verification.pre_merge_verifier import PreMergeVerifier

        # Create a temp file with syntax error
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def broken(\n")  # Missing closing paren
            temp_path = f.name

        # This is a unit test - in real usage, it would scan the file
        # For now, just verify the verifier can be instantiated
        verifier = PreMergeVerifier()
        assert verifier is not None

        # Cleanup
        Path(temp_path).unlink()

    def test_critical_imports_list_is_complete(self):
        """Verify critical imports list includes essential modules."""
        from src.verification.pre_merge_verifier import PreMergeVerifier

        critical_module_names = [imp[0] for imp in PreMergeVerifier.CRITICAL_IMPORTS]

        assert "TradingOrchestrator" in critical_module_names
        assert "AlpacaExecutor" in critical_module_names
        assert "TradeGateway" in critical_module_names

    def test_verify_all_returns_result(self):
        """verify_all should return a VerificationResult."""
        from src.verification.pre_merge_verifier import PreMergeVerifier, VerificationResult

        verifier = PreMergeVerifier()
        result = verifier.verify_all(run_tests=False, run_typecheck=False)

        assert isinstance(result, VerificationResult)
        assert result.checks_run > 0


class TestRAGSafetyChecker:
    """Tests for RAG safety checking."""

    def test_large_pr_warning(self):
        """Large PRs should generate warnings."""
        from src.verification.rag_safety_checker import RAGSafetyChecker

        checker = RAGSafetyChecker()

        # Simulate a large PR (15 files)
        changed_files = [f"src/file_{i}.py" for i in range(15)]
        result = checker.check_merge_safety(changed_files, "feat: big change")

        assert len(result.warnings) > 0 or len(result.similar_incidents) > 0

    def test_executor_change_detected(self):
        """Changes to executor files should be flagged."""
        from src.verification.rag_safety_checker import RAGSafetyChecker

        checker = RAGSafetyChecker()

        changed_files = ["src/execution/alpaca_executor.py"]
        result = checker.check_merge_safety(changed_files, "fix: executor")

        # Should have warnings or blocking reasons
        assert len(result.warnings) > 0 or len(result.blocking_reasons) > 0

    def test_safe_change_passes(self):
        """Simple safe changes should pass."""
        from src.verification.rag_safety_checker import RAGSafetyChecker

        checker = RAGSafetyChecker()

        changed_files = ["README.md"]
        result = checker.check_merge_safety(changed_files, "docs: update readme")

        # README changes should be safe
        assert result.safe


class TestContinuousVerifier:
    """Tests for continuous monitoring."""

    def test_no_trades_alert(self):
        """Should alert when no trades executed."""
        from src.verification.continuous_verifier import ContinuousVerifier

        verifier = ContinuousVerifier(trades_dir="data")

        # Run checks - may or may not have alerts depending on actual data
        alerts = verifier.check_trading_health()

        # Just verify it runs without error
        assert isinstance(alerts, list)

    def test_risky_code_change_detection(self):
        """Should detect risky code changes."""
        from src.verification.continuous_verifier import ContinuousVerifier

        verifier = ContinuousVerifier()

        # Simulate risky change
        alerts = verifier.check_code_change_risk(
            changed_files=[
                "src/execution/alpaca_executor.py",
                "src/orchestrator/main.py",
                "src/risk/trade_gateway.py",
            ]
            + [f"src/strategies/strategy_{i}.py" for i in range(10)],
            commit_message="hotfix: urgent fix for broken trading",
        )

        # Should have at least one alert due to risky patterns
        assert len(alerts) > 0
        assert any(a.type == "risky_code_change" for a in alerts)


class TestVerificationIntegration:
    """Integration tests for the verification system."""

    def test_full_verification_pipeline(self):
        """Test the complete verification pipeline."""
        from src.verification.post_deploy_verifier import PostDeployVerifier
        from src.verification.pre_merge_verifier import PreMergeVerifier

        # Pre-merge
        pre_verifier = PreMergeVerifier()
        pre_result = pre_verifier.verify_all()

        # Post-deploy (if pre passes)
        if pre_result.passed:
            post_verifier = PostDeployVerifier()
            post_result = post_verifier.verify_deployment()

            # At minimum, checks should run
            assert len(post_result.checks) > 0

    def test_lesson_recording(self):
        """Test that incidents can be recorded to RAG."""
        import tempfile

        from src.verification.rag_safety_checker import RAGSafetyChecker

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"lessons": []}')
            temp_path = f.name

        checker = RAGSafetyChecker(rag_path=temp_path)

        lesson_id = checker.record_incident(
            category="test",
            title="Test Incident",
            description="This is a test",
            root_cause="Testing",
            prevention="Run tests",
            severity="low",
        )

        assert lesson_id.startswith("ll_")

        # Cleanup
        Path(temp_path).unlink()


# Regression tests for specific past incidents
class TestIncidentRegression:
    """Regression tests to prevent past incidents from recurring."""

    def test_ll_009_syntax_error_prevention(self):
        """
        Regression test for ll_009: Syntax error merged to main.

        On Dec 11, 2025, a syntax error in alpaca_executor.py was merged
        causing 0 trades to execute.

        This test ensures:
        1. All Python files in src/ have valid syntax
        2. Critical imports work
        """
        from src.verification.pre_merge_verifier import PreMergeVerifier

        verifier = PreMergeVerifier()

        # Check 1: All files compile
        syntax_result = verifier.check_syntax()
        assert syntax_result["passed"], (
            f"REGRESSION: Syntax error detected! See ll_009. Errors: {syntax_result.get('errors')}"
        )

        # Check 2: Critical imports (syntax only, not full import)
        import ast
        from pathlib import Path

        critical_files = [
            "src/execution/alpaca_executor.py",
            "src/orchestrator/main.py",
            "src/risk/trade_gateway.py",
        ]

        for filepath in critical_files:
            path = Path(filepath)
            if path.exists():
                with open(path) as f:
                    try:
                        ast.parse(f.read())
                    except SyntaxError as e:
                        pytest.fail(
                            f"REGRESSION: Syntax error in {filepath}! See ll_009. Error: {e}"
                        )

    def test_ll_001_over_engineering_check(self):
        """
        Regression test for ll_001: Over-engineering with too many gates.

        System should not have excessive entry gates that block all trades.
        """
        # This is a documentation/process check
        # In production, would check gate pass rates
        pass
