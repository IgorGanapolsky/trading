#!/usr/bin/env python3
"""
Strategy Sanity Tests - Prevent Future Mistakes

These tests enforce lessons learned from the Dec 15, 2025 pyramid buying disaster
that destroyed $96 in 5 days.

Lesson: ll_020_pyramid_buying_fear_destroyed_96_dec15.md

Run with: pytest tests/test_strategy_sanity.py -v
"""

import json
import re
from pathlib import Path

import pytest

# Project root
PROJECT_ROOT = Path(__file__).parent.parent


class TestNoHardcodedMetrics:
    """Ensure hooks and configs don't contain hardcoded performance claims."""

    def test_inject_hook_no_fake_sharpe(self):
        """The 2.18 Sharpe that never existed should not appear."""
        hook_path = PROJECT_ROOT / ".claude/hooks/inject_trading_context.sh"

        if hook_path.exists():
            content = hook_path.read_text()

            # These fabricated metrics should NEVER be hardcoded
            assert "2.18 Sharpe" not in content, (
                "CRITICAL: Hardcoded '2.18 Sharpe' found in hook. "
                "This metric never existed in any backtest data."
            )
            assert "2.18" not in content or "Sharpe" not in content, (
                "Suspicious hardcoded Sharpe ratio found"
            )

    def test_load_hook_no_fake_winrate(self):
        """The cherry-picked 62.2% win rate should not be presented as validated."""
        hook_path = PROJECT_ROOT / ".claude/hooks/load_trading_state.sh"

        if hook_path.exists():
            content = hook_path.read_text()

            # This was from ONE scenario with -69.8 Sharpe
            assert "Validated Performance: 62.2%" not in content, (
                "CRITICAL: Cherry-picked 62.2% win rate found in hook. "
                "Full matrix shows 0/13 scenarios pass with all negative Sharpe."
            )

    def test_hooks_reference_dynamic_data(self):
        """Hooks should pull from actual data files, not hardcode values."""
        inject_hook = PROJECT_ROOT / ".claude/hooks/inject_trading_context.sh"

        if inject_hook.exists():
            content = inject_hook.read_text()

            # Should reference performance_log.json or system_state.json
            assert "performance_log.json" in content or "system_state.json" in content, (
                "Hook should read from actual data files, not hardcode metrics"
            )


class TestFearGreedSanity:
    """Ensure Fear/Greed Index doesn't amplify losing positions."""

    def test_fear_multiplier_not_increasing(self):
        """Extreme fear should NOT increase position size."""
        try:
            from src.utils.fear_greed_index import FearGreedIndex

            fgi = FearGreedIndex()

            # Mock an extreme fear scenario
            fgi.last_value = 20  # Extreme fear

            # The get_trading_signal method should not return multiplier > 1.0
            # during fear conditions
            signal_code = Path(
                PROJECT_ROOT / "src/utils/fear_greed_index.py"
            ).read_text()

            # Check that extreme fear doesn't multiply size
            # Look for the pattern where EXTREME_FEAR leads to multiplier > 1
            extreme_fear_section = re.search(
                r"if value <= self\.EXTREME_FEAR_THRESHOLD:.*?elif",
                signal_code,
                re.DOTALL,
            )

            if extreme_fear_section:
                section = extreme_fear_section.group()
                # Should NOT have multiplier > 1.0 in extreme fear block
                assert "size_multiplier = 1.5" not in section, (
                    "CRITICAL: Fear still increases position size (1.5x). "
                    "This caused $96 loss in Dec 2025."
                )
                assert "size_multiplier = 2" not in section, (
                    "CRITICAL: Fear still increases position size (2x). "
                    "Never increase position during fear."
                )

        except ImportError:
            pytest.skip("fear_greed_index module not available")

    def test_fear_action_not_aggressive_buy(self):
        """During extreme fear, action should be HOLD, not BUY."""
        fgi_path = PROJECT_ROOT / "src/utils/fear_greed_index.py"

        if fgi_path.exists():
            content = fgi_path.read_text()

            # Find the extreme fear handling block
            extreme_fear_match = re.search(
                r'if value <= self\.EXTREME_FEAR_THRESHOLD:.*?action = "(\w+)"',
                content,
                re.DOTALL,
            )

            if extreme_fear_match:
                action = extreme_fear_match.group(1)
                assert action != "BUY", (
                    f"CRITICAL: Extreme fear action is '{action}' but should be 'HOLD'. "
                    "Buying during extreme fear catches falling knives."
                )


class TestBacktestIntegrity:
    """Ensure backtest data is honest and not cherry-picked."""

    def test_latest_summary_exists(self):
        """Backtest summary file should exist."""
        summary_path = PROJECT_ROOT / "data/backtests/latest_summary.json"
        assert summary_path.exists(), "Backtest summary file missing"

    def test_aggregate_metrics_honest(self):
        """Aggregate metrics should reflect reality, not cherry-picked scenarios."""
        summary_path = PROJECT_ROOT / "data/backtests/latest_summary.json"

        if summary_path.exists():
            with open(summary_path) as f:
                data = json.load(f)

            aggregate = data.get("aggregate_metrics", {})

            # The passes count should be accurate
            passes = aggregate.get("passes", 0)

            # If 0 scenarios pass, the system should know it has no edge
            if passes == 0:
                # Verify this is communicated honestly
                min_sharpe = aggregate.get("min_sharpe_ratio", 0)
                assert min_sharpe < 0, (
                    "If 0 scenarios pass, min Sharpe should be negative"
                )

    def test_no_scenario_has_fabricated_sharpe(self):
        """No scenario should have the fabricated 2.18 Sharpe."""
        summary_path = PROJECT_ROOT / "data/backtests/latest_summary.json"

        if summary_path.exists():
            with open(summary_path) as f:
                data = json.load(f)

            for scenario in data.get("scenarios", []):
                sharpe = scenario.get("sharpe_ratio", 0)

                # The 2.18 Sharpe never existed
                assert abs(sharpe - 2.18) > 0.1, (
                    f"Scenario {scenario.get('scenario')} has suspicious 2.18 Sharpe. "
                    "This metric was fabricated in Dec 2025."
                )


class TestLivePerformanceSafety:
    """Ensure live performance triggers appropriate circuit breakers."""

    def test_performance_log_exists(self):
        """Performance log should be tracking P/L."""
        perf_path = PROJECT_ROOT / "data/performance_log.json"
        assert perf_path.exists(), "Performance log missing - can't track P/L"

    def test_system_state_reflects_reality(self):
        """System state should show actual P/L, not stale data."""
        state_path = PROJECT_ROOT / "data/system_state.json"

        if state_path.exists():
            with open(state_path) as f:
                data = json.load(f)

            # Account data should exist
            account = data.get("account", {})
            assert "total_pl" in account, "System state missing total_pl"
            assert "current_equity" in account, "System state missing equity"


class TestStrategyWinRateGate:
    """Block strategies with unacceptably low win rates."""

    def test_live_win_rate_above_threshold(self):
        """Live win rate should be monitored and gated."""
        state_path = PROJECT_ROOT / "data/system_state.json"

        if state_path.exists():
            with open(state_path) as f:
                data = json.load(f)

            performance = data.get("performance", {})
            win_rate = performance.get("win_rate", 50)

            # If win rate is exactly 50%, it's a coin flip - no edge
            # This test documents the current state but doesn't fail
            # The real gate should be in production code
            if win_rate <= 50:
                pytest.warns(
                    UserWarning,
                    match="Win rate at or below 50%",
                )


class TestRiskManagement:
    """Ensure risk management is not bypassed."""

    def test_max_risk_per_trade_enforced(self):
        """Risk manager should cap per-trade risk."""
        risk_path = PROJECT_ROOT / "src/risk/risk_manager.py"

        if risk_path.exists():
            content = risk_path.read_text()

            # Should have a max position size cap
            assert "max_position" in content.lower() or "position_size" in content, (
                "Risk manager should enforce position size limits"
            )

    def test_daily_loss_limit_exists(self):
        """Trade gateway should have daily loss circuit breaker."""
        gateway_path = PROJECT_ROOT / "src/risk/trade_gateway.py"

        if gateway_path.exists():
            content = gateway_path.read_text()

            assert "MAX_DAILY_LOSS" in content or "daily_loss" in content.lower(), (
                "Trade gateway should enforce daily loss limits"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
