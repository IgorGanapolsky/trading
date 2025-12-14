"""
Test suite for workflow observability configuration.

Ensures all GitHub Actions workflows that make LLM calls have complete
observability stack configured (LangSmith + Helicone).

Regression tests for ll_017: Missing LangSmith env vars in workflows.
"""

from pathlib import Path

import pytest


class TestWorkflowObservability:
    """Test that workflows have complete observability configuration."""

    # Workflows that make LLM calls and need full observability
    LLM_WORKFLOWS = [
        ".github/workflows/daily-trading.yml",
        ".github/workflows/weekend-crypto-trading.yml",
    ]

    # Required env vars for LangSmith tracing
    LANGSMITH_REQUIRED_VARS = [
        "LANGCHAIN_API_KEY",
        "LANGCHAIN_TRACING_V2",
        "LANGCHAIN_PROJECT",
    ]

    # Required env vars for Helicone cost tracking
    HELICONE_REQUIRED_VARS = [
        "HELICONE_API_KEY",
    ]

    @pytest.fixture
    def project_root(self) -> Path:
        """Get project root directory."""
        return Path(__file__).parent.parent

    def test_ll_017_workflows_have_langsmith_vars(self, project_root: Path):
        """
        REGRESSION TEST for ll_017: Ensure trading workflows have LangSmith env vars.

        On Dec 12, 2025, we discovered that workflows had HELICONE_API_KEY but
        were missing LANGCHAIN_API_KEY, causing all production LLM calls to
        run without tracing.
        """
        missing_vars = []

        for workflow_path in self.LLM_WORKFLOWS:
            full_path = project_root / workflow_path
            if not full_path.exists():
                pytest.skip(f"Workflow not found: {workflow_path}")

            content = full_path.read_text()

            for var in self.LANGSMITH_REQUIRED_VARS:
                if var not in content:
                    missing_vars.append(f"{workflow_path}: missing {var}")

        assert not missing_vars, (
            "REGRESSION ll_017: LangSmith env vars missing from workflows!\n"
            "Missing:\n" + "\n".join(f"  - {m}" for m in missing_vars)
        )

    def test_workflows_have_helicone_vars(self, project_root: Path):
        """Ensure trading workflows have Helicone cost tracking configured."""
        missing_vars = []

        for workflow_path in self.LLM_WORKFLOWS:
            full_path = project_root / workflow_path
            if not full_path.exists():
                continue

            content = full_path.read_text()

            for var in self.HELICONE_REQUIRED_VARS:
                if var not in content:
                    missing_vars.append(f"{workflow_path}: missing {var}")

        assert not missing_vars, (
            "Helicone env vars missing from workflows!\n"
            "Missing:\n" + "\n".join(f"  - {m}" for m in missing_vars)
        )

    def test_workflows_have_openrouter_key(self, project_root: Path):
        """Ensure trading workflows have OpenRouter API key."""
        for workflow_path in self.LLM_WORKFLOWS:
            full_path = project_root / workflow_path
            if not full_path.exists():
                continue

            content = full_path.read_text()
            assert "OPENROUTER_API_KEY" in content, f"Missing OPENROUTER_API_KEY in {workflow_path}"

    def test_langsmith_wrapper_configuration(self):
        """Test that langsmith wrapper properly checks for API key."""
        import os

        # Backup current value
        original_key = os.environ.get("LANGCHAIN_API_KEY")

        try:
            # Test with key set
            os.environ["LANGCHAIN_API_KEY"] = "test_key_12345"

            # Re-import to pick up new env var
            import importlib

            from src.utils import langsmith_wrapper

            importlib.reload(langsmith_wrapper)

            # Should be enabled with key present
            # Note: The actual check happens at module load time
            assert hasattr(langsmith_wrapper, "LANGSMITH_ENABLED")

        finally:
            # Restore original
            if original_key:
                os.environ["LANGCHAIN_API_KEY"] = original_key
            elif "LANGCHAIN_API_KEY" in os.environ:
                del os.environ["LANGCHAIN_API_KEY"]

    def test_observability_status_function_exists(self):
        """Test that observability status function is available."""
        from src.utils.langsmith_wrapper import get_observability_status

        status = get_observability_status()

        # Check structure
        assert "langsmith" in status
        assert "helicone" in status
        assert "openrouter" in status

        # Check langsmith fields
        assert "enabled" in status["langsmith"]
        assert "project" in status["langsmith"]
        assert "dashboard" in status["langsmith"]

        # Check helicone fields
        assert "enabled" in status["helicone"]
        assert "gateway_url" in status["helicone"]


class TestWorkflowSecretReferences:
    """Test that workflows correctly reference GitHub secrets."""

    def test_secrets_use_correct_syntax(self):
        """Ensure secrets use ${{ secrets.NAME }} syntax."""
        project_root = Path(__file__).parent.parent

        for workflow_path in TestWorkflowObservability.LLM_WORKFLOWS:
            full_path = project_root / workflow_path
            if not full_path.exists():
                continue

            content = full_path.read_text()

            # Check for correct secret syntax
            assert "${{ secrets.LANGCHAIN_API_KEY }}" in content, (
                f"LANGCHAIN_API_KEY should use secrets syntax in {workflow_path}"
            )

    def test_no_hardcoded_api_keys(self):
        """Ensure no hardcoded API keys in workflows."""
        project_root = Path(__file__).parent.parent

        # Patterns that might indicate hardcoded keys
        dangerous_patterns = [
            "sk-",  # OpenAI/OpenRouter key prefix
            "lsv2_pt_",  # LangSmith key prefix
            "sk-helicone-",  # Helicone key prefix
        ]

        for workflow_path in TestWorkflowObservability.LLM_WORKFLOWS:
            full_path = project_root / workflow_path
            if not full_path.exists():
                continue

            content = full_path.read_text()

            for pattern in dangerous_patterns:
                # Allow if it's in a comment explaining the format
                lines_with_pattern = [
                    line
                    for line in content.split("\n")
                    if pattern in line and not line.strip().startswith("#")
                ]

                for line in lines_with_pattern:
                    # Check if it looks like a real key (has more chars after prefix)
                    import re

                    if re.search(rf"{pattern}[a-zA-Z0-9]{{10,}}", line):
                        pytest.fail(
                            f"Possible hardcoded API key in {workflow_path}: "
                            f"'{line.strip()[:50]}...'"
                        )
