"""
Configuration Consistency Test Suite.

Ensures critical configuration values are consistent across the codebase.
Prevents silent drift like the LL_047 incident (LangSmith project name mismatch).

Run with: pytest tests/test_config_consistency.py -v
"""

import os
import re
from pathlib import Path

import pytest


class TestConfigurationConsistency:
    """Tests for configuration consistency across the codebase."""

    PROJECT_ROOT = Path(__file__).parent.parent

    # =========================================================================
    # LL_047: LangSmith Project Name Consistency
    # =========================================================================

    EXPECTED_LANGSMITH_PROJECT = "igor-trading-system"
    LANGSMITH_CONFIG_FILES = [
        ".github/workflows/daily-trading.yml",
        ".github/workflows/weekend-crypto-trading.yml",
        ".github/workflows/rl-training-continuous.yml",
        ".github/workflows/model-training.yml",
        ".github/workflows/combined-trading.yml",
        ".env.example",
        "src/utils/langsmith_wrapper.py",
        "scripts/rl_training_orchestrator.py",
    ]

    def test_ll_047_langsmith_project_name_unified(self):
        """
        REGRESSION LL_047: All LangSmith project names must be 'igor-trading-system'.

        On Dec 15, 2025, traces were going to 'trading-system' while the dashboard
        showed 'igor-trading-system', making the dashboard appear broken.
        """
        mismatches = []
        pattern = r"LANGCHAIN_PROJECT[=:]\s*['\"]([^'\"]+)['\"]"

        for filepath in self.LANGSMITH_CONFIG_FILES:
            full_path = self.PROJECT_ROOT / filepath
            if not full_path.exists():
                continue

            content = full_path.read_text()
            matches = re.findall(pattern, content)

            for match in matches:
                if match != self.EXPECTED_LANGSMITH_PROJECT:
                    mismatches.append(f"{filepath}: '{match}'")

        assert not mismatches, (
            f"REGRESSION LL_047: LangSmith project name inconsistency!\n"
            f"Expected: '{self.EXPECTED_LANGSMITH_PROJECT}'\n"
            f"Found: {mismatches}"
        )

    # =========================================================================
    # LL_017: LangSmith Environment Variables Present
    # =========================================================================

    REQUIRED_LANGSMITH_VARS = [
        "LANGCHAIN_API_KEY",
        "LANGCHAIN_TRACING_V2",
        "LANGCHAIN_PROJECT",
    ]

    TRADING_WORKFLOWS = [
        ".github/workflows/daily-trading.yml",
        ".github/workflows/weekend-crypto-trading.yml",
    ]

    def test_ll_017_workflows_have_all_langsmith_vars(self):
        """
        REGRESSION LL_017: Trading workflows must have all LangSmith env vars.

        On Dec 12, 2025, workflows had HELICONE but were missing LANGCHAIN vars,
        causing blind production execution without observability.
        """
        missing = []

        for workflow in self.TRADING_WORKFLOWS:
            workflow_path = self.PROJECT_ROOT / workflow
            if not workflow_path.exists():
                continue

            content = workflow_path.read_text()

            for var in self.REQUIRED_LANGSMITH_VARS:
                if var not in content:
                    missing.append(f"{workflow}: missing {var}")

        assert not missing, (
            f"REGRESSION LL_017: Incomplete observability configuration!\n"
            f"Missing: {missing}"
        )

    # =========================================================================
    # Safety: Paper Trading Mode
    # =========================================================================

    def test_paper_trading_mode_in_workflows(self):
        """Ensure all trading workflows use PAPER_TRADING=true."""
        for workflow in self.TRADING_WORKFLOWS:
            workflow_path = self.PROJECT_ROOT / workflow
            if not workflow_path.exists():
                continue

            content = workflow_path.read_text()

            # Check that PAPER_TRADING is set to true
            assert "PAPER_TRADING" in content, f"{workflow} missing PAPER_TRADING"

            # Ensure it's not set to false
            if re.search(r"PAPER_TRADING[=:]\s*['\"]?false", content, re.IGNORECASE):
                pytest.fail(f"DANGER: {workflow} has PAPER_TRADING=false!")

    # =========================================================================
    # Security: No Secrets in Code
    # =========================================================================

    FORBIDDEN_PATTERNS = [
        (r"ghp_[A-Za-z0-9]{36}", "GitHub PAT token"),
        (r"sk-[A-Za-z0-9]{48}", "OpenAI API key"),
        (r"AKIA[A-Z0-9]{16}", "AWS Access Key"),
    ]

    def test_no_hardcoded_secrets(self):
        """Ensure no API keys or tokens are hardcoded in source files."""
        violations = []

        for py_file in self.PROJECT_ROOT.rglob("*.py"):
            if ".git" in str(py_file):
                continue
            if "test_config_consistency.py" in str(py_file):
                continue  # Skip this test file

            try:
                content = py_file.read_text()
            except Exception:
                continue

            for pattern, name in self.FORBIDDEN_PATTERNS:
                if re.search(pattern, content):
                    violations.append(f"{py_file}: contains {name}")

        assert not violations, (
            f"SECURITY: Hardcoded secrets detected!\n"
            f"Violations: {violations}"
        )

    # =========================================================================
    # Consistency: Single Source of Truth
    # =========================================================================

    def test_daily_investment_default_consistent(self):
        """Ensure DAILY_INVESTMENT defaults are consistent across workflows."""
        defaults = {}
        pattern = r"DAILY_INVESTMENT.*\|\|\s*['\"]?([0-9.]+)"

        for workflow in self.PROJECT_ROOT.glob(".github/workflows/*.yml"):
            content = workflow.read_text()
            matches = re.findall(pattern, content)
            for match in matches:
                if workflow.name not in defaults:
                    defaults[workflow.name] = set()
                defaults[workflow.name].add(match)

        # All workflows should use the same default
        all_values = set()
        for values in defaults.values():
            all_values.update(values)

        if len(all_values) > 1:
            pytest.fail(
                f"DAILY_INVESTMENT defaults inconsistent: {defaults}\n"
                f"All values: {all_values}"
            )


class TestObservabilityHealth:
    """Tests for observability system health."""

    def test_langsmith_env_vars_structure(self):
        """Verify LangSmith env vars have correct structure in .env.example."""
        env_example = Path(".env.example")
        if not env_example.exists():
            pytest.skip(".env.example not found")

        content = env_example.read_text()

        # Should have all three LangSmith vars
        assert "LANGCHAIN_API_KEY" in content
        assert "LANGCHAIN_PROJECT" in content
        assert "LANGCHAIN_TRACING_V2" in content

    def test_observability_tracer_imports(self):
        """Verify langsmith_tracer module is importable."""
        try:
            from src.observability.langsmith_tracer import LangSmithTracer, get_tracer
            assert LangSmithTracer is not None
            assert get_tracer is not None
        except ImportError as e:
            pytest.fail(f"Failed to import langsmith_tracer: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
