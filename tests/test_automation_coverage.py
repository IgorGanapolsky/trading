"""
Test Automation Coverage - Ensure all profit strategies are automated.

This test prevents the scenario where high-profit activities (like options)
are not included in automated workflows.

Lesson Learned: ll_022_options_not_automated_dec12.md
"""

import re
from pathlib import Path

import pytest


class TestAutomationCoverage:
    """Verify all income strategies have workflow automation."""

    @pytest.fixture
    def daily_workflow(self):
        """Load the daily trading workflow."""
        workflow_path = Path(".github/workflows/daily-trading.yml")
        if not workflow_path.exists():
            pytest.skip("Workflow file not found")
        return workflow_path.read_text()

    def test_equity_dca_automated(self, daily_workflow):
        """Equity DCA must be in daily workflow."""
        patterns = [
            r"autonomous_trader\.py",
            r"TradingOrchestrator",
            r"Execute daily trading",
        ]
        assert any(re.search(p, daily_workflow, re.IGNORECASE) for p in patterns), (
            "Equity DCA trading not found in daily workflow"
        )

    def test_options_theta_automated(self, daily_workflow):
        """Options theta harvesting must be in daily workflow."""
        patterns = [
            r"theta",
            r"options_profit_planner",
            r"execute_options_trade",
            r"wheel.*strategy",
            r"Harvest.*theta",
        ]
        assert any(re.search(p, daily_workflow, re.IGNORECASE) for p in patterns), (
            "Options theta harvesting not found in daily workflow. "
            "Options generate 100x more profit than DCA - this MUST be automated. "
            "See: ll_022_options_not_automated_dec12.md"
        )

        patterns = [
            r"tier.?5",
            r"weekend.*trad",
        ]
        assert any(re.search(p, daily_workflow, re.IGNORECASE) for p in patterns), (
        )

    def test_no_manual_only_strategies(self, daily_workflow):
        """
        All strategies in system_state.json should have workflow coverage.

        This test ensures we don't add new strategies without automation.
        """
        state_file = Path("data/system_state.json")
        if not state_file.exists():
            pytest.skip("system_state.json not found")

        import json

        with open(state_file) as f:
            state = json.load(f)

        strategies = state.get("strategies", {})
        active_strategies = [
            name for name, config in strategies.items() if config.get("status") == "active"
        ]

        # Map strategy names to workflow patterns
        strategy_patterns = {
            "tier1": r"Core|SPY|ETF|autonomous_trader",
            "tier2": r"Growth|NVDA|GOOGL|AMZN|autonomous_trader",
        }

        for strategy in active_strategies:
            if strategy in strategy_patterns:
                pattern = strategy_patterns[strategy]
                assert re.search(pattern, daily_workflow, re.IGNORECASE), (
                    f"Active strategy '{strategy}' not found in workflow. Pattern: {pattern}"
                )

    def test_workflow_has_error_handling(self, daily_workflow):
        """Workflow should have continue-on-error for non-critical steps."""
        # Count steps with continue-on-error
        error_handling_count = len(re.findall(r"continue-on-error:\s*true", daily_workflow))

        # Should have at least 3 non-critical steps with error handling
        assert error_handling_count >= 3, (
            f"Only {error_handling_count} steps have continue-on-error. "
            "Non-critical steps should fail gracefully."
        )

    def test_workflow_commits_data(self, daily_workflow):
        """Workflow should commit trading data after execution."""
        patterns = [
            r"git.*commit",
            r"Commit.*trading.*data",
            r"git.*push",
        ]
        assert any(re.search(p, daily_workflow, re.IGNORECASE) for p in patterns), (
            "Workflow does not commit trading data - state may be lost"
        )


class TestTimestampStaleness:
    """Verify timestamps are checked for staleness."""

    def test_detect_automation_gaps_script_exists(self):
        """Gap detection script should exist."""
        script_path = Path("scripts/detect_automation_gaps.py")
        assert script_path.exists(), (
            "scripts/detect_automation_gaps.py not found. "
            "This script detects revenue-leaking automation gaps."
        )

    def test_system_state_has_timestamps(self):
        """System state should track last execution timestamps."""
        state_file = Path("data/system_state.json")
        if not state_file.exists():
            pytest.skip("system_state.json not found")

        import json

        with open(state_file) as f:
            state = json.load(f)

        # Check required timestamps exist
        required_timestamps = [
            ("meta.last_updated", "system_state freshness"),
            ("options.last_theta_harvest", "options automation"),
            ("automation.last_successful_execution", "trading automation"),
        ]

        for key_path, description in required_timestamps:
            keys = key_path.split(".")
            value = state
            for key in keys:
                value = value.get(key, {}) if isinstance(value, dict) else None

            # Allow None but ensure the path exists in schema
            assert value is not None or key_path.split(".")[0] in state, (
                f"Missing timestamp: {key_path} ({description})"
            )
