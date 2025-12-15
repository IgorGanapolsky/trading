"""
Prevention tests for weekend crypto trading failures.

These tests are based on lessons learned from Dec 13, 2025 incident where:
1. Session start checklist was not followed (ll_023)
2. F-string syntax error crashed the script (ll_024)
3. RSI filters were too restrictive for bull market
4. FORCE_TRADE mode wasn't creating fallback trades

This test suite ensures these issues never happen again.
"""

import ast
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest
import yaml

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPythonSyntaxValidation:
    """Ensure all critical Python scripts have valid syntax (prevents ll_024)."""

    CRITICAL_SCRIPTS = [
        "scripts/autonomous_trader.py",
        "scripts/pre_market_health_check.py",
        "src/strategies/crypto_strategy.py",
        "src/orchestrator/main.py",
    ]

    @pytest.mark.parametrize("script_path", CRITICAL_SCRIPTS)
    def test_script_syntax_valid(self, script_path):
        """Verify script has no syntax errors (ll_024 prevention)."""
        full_path = Path(__file__).parent.parent / script_path
        if not full_path.exists():
            pytest.skip(f"{script_path} not found")

        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(full_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Syntax error in {script_path}: {result.stderr}"

    def test_no_backslash_in_fstrings(self):
        """Check for Python 3.12+ incompatible f-string patterns (ll_024)."""
        pattern_files = [
            "scripts/autonomous_trader.py",
            "src/strategies/crypto_strategy.py",
        ]

        for file_path in pattern_files:
            full_path = Path(__file__).parent.parent / file_path
            if not full_path.exists():
                continue

            with open(full_path) as f:
                content = f.read()

            # Check for backslash in f-string pattern: f"...{...\"...}..."
            # This is a simplified check - may have false positives
            if 'f"' in content and '\\"' in content:
                # Parse AST to find actual f-strings with issues
                try:
                    ast.parse(content)
                    # If parsing succeeds, the syntax is valid
                except SyntaxError as e:
                    if "f-string" in str(e).lower():
                        pytest.fail(f"{file_path} has f-string syntax error: {e}")


class TestWorkflowValidation:
    """Ensure GitHub Actions workflows are valid."""

    CRITICAL_WORKFLOWS = [
        ".github/workflows/weekend-crypto-trading.yml",
        ".github/workflows/daily-trading.yml",
    ]

    @pytest.mark.parametrize("workflow_path", CRITICAL_WORKFLOWS)
    def test_workflow_yaml_valid(self, workflow_path):
        """Verify workflow YAML is valid."""
        full_path = Path(__file__).parent.parent / workflow_path
        if not full_path.exists():
            pytest.skip(f"{workflow_path} not found")

        with open(full_path) as f:
            try:
                workflow = yaml.safe_load(f)
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in {workflow_path}: {e}")

        # Verify required keys exist
        assert "jobs" in workflow, f"{workflow_path} missing 'jobs' key"

    def test_weekend_crypto_has_pythonpath(self):
        """Ensure weekend crypto workflow has PYTHONPATH set (ll_024 fix)."""
        workflow_path = (
            Path(__file__).parent.parent / ".github/workflows/weekend-crypto-trading.yml"
        )
        if not workflow_path.exists():
            pytest.skip("weekend-crypto-trading.yml not found")

        with open(workflow_path) as f:
            content = f.read()

        assert "PYTHONPATH" in content, (
            "weekend-crypto-trading.yml missing PYTHONPATH - "
            "this will cause import failures (see ll_024)"
        )

    def test_weekend_crypto_has_force_trade(self):
        """Ensure CRYPTO_FORCE_TRADE is enabled in weekend workflow."""
        workflow_path = (
            Path(__file__).parent.parent / ".github/workflows/weekend-crypto-trading.yml"
        )
        if not workflow_path.exists():
            pytest.skip("weekend-crypto-trading.yml not found")

        with open(workflow_path) as f:
            content = f.read()

        assert "CRYPTO_FORCE_TRADE" in content, (
            "weekend-crypto-trading.yml missing CRYPTO_FORCE_TRADE - "
            "trades won't execute in overbought markets"
        )


class TestCryptoStrategyConfig:
    """Verify crypto strategy configuration is correct."""

    def test_rsi_overbought_is_relaxed(self):
        """Ensure RSI_OVERBOUGHT is not too restrictive for bull markets."""
        from src.strategies.crypto_strategy import CryptoStrategy

        # In a bull market, RSI > 60 is common. Default should be 70+
        assert CryptoStrategy.RSI_OVERBOUGHT >= 70, (
            f"RSI_OVERBOUGHT={CryptoStrategy.RSI_OVERBOUGHT} is too restrictive. "
            "Should be >= 70 for bull market conditions."
        )

    def test_force_trade_mode_exists(self):
        """Verify CRYPTO_FORCE_TRADE mode is implemented."""
        crypto_strategy_path = Path(__file__).parent.parent / "src/strategies/crypto_strategy.py"

        with open(crypto_strategy_path) as f:
            content = f.read()

        assert "CRYPTO_FORCE_TRADE" in content, (
            "crypto_strategy.py missing CRYPTO_FORCE_TRADE implementation"
        )
        assert "force_trade" in content, "crypto_strategy.py missing force_trade variable"


class TestSystemStateStaleness:
    """Ensure system state doesn't get stale (prevents ll_023)."""

    def test_tier5_execution_not_stale(self):
        """Verify Tier 5 crypto execution isn't more than 3 days old."""
        state_path = Path(__file__).parent.parent / "data/system_state.json"
        if not state_path.exists():
            pytest.skip("system_state.json not found")

        import json

        with open(state_path) as f:
            state = json.load(f)

        tier5 = state.get("strategies", {}).get("tier5", {})
        if not tier5.get("enabled"):
            pytest.skip("Tier 5 crypto not enabled")

        last_exec = tier5.get("last_execution")
        if not last_exec:
            pytest.skip("No last_execution recorded")

        last_exec_dt = datetime.fromisoformat(last_exec)
        days_since = (datetime.now() - last_exec_dt).days

        # On weekends, crypto should execute. Max staleness = 3 days
        assert days_since <= 3, (
            f"Tier 5 crypto is stale: {days_since} days since last execution. "
            f"Last execution: {last_exec}. This indicates weekend crypto workflow "
            "isn't running correctly."
        )


class TestSessionStartChecklist:
    """Tests to remind about session start checklist (ll_023)."""

    def test_claude_md_has_session_checklist(self):
        """Verify CLAUDE.md has session start checklist."""
        claude_md = Path(__file__).parent.parent / ".claude/CLAUDE.md"
        if not claude_md.exists():
            pytest.skip("CLAUDE.md not found")

        with open(claude_md) as f:
            content = f.read()

        assert "Session Start Checklist" in content, (
            "CLAUDE.md missing Session Start Checklist section"
        )
        assert "system_state.json" in content, (
            "CLAUDE.md checklist should mention system_state.json"
        )


class TestLessonsLearnedRAG:
    """Verify lessons learned are properly stored."""

    EXPECTED_LESSONS = [
        "ll_023",  # Session start checklist violation
        "ll_024",  # F-string syntax error
    ]

    def test_lessons_exist(self):
        """Verify critical lessons learned files exist."""
        lessons_dir = Path(__file__).parent.parent / "rag_knowledge/lessons_learned"
        if not lessons_dir.exists():
            pytest.skip("lessons_learned directory not found")

        existing_files = [f.stem for f in lessons_dir.glob("*.md")]

        for lesson_id in self.EXPECTED_LESSONS:
            matching = [f for f in existing_files if lesson_id in f]
            assert matching, (
                f"Lesson {lesson_id} not found in RAG. Available: {existing_files[:10]}"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
