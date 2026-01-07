"""
Tests for VIX Circuit Breaker Module.

This module tests the critical risk management component that monitors VIX
and triggers automatic position reductions during volatility spikes.

Critical for Phil Town Rule #1: Don't lose money.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from src.risk.vix_circuit_breaker import (
    VIXCircuitBreaker,
    AlertLevel,
    VIXStatus,
    DeRiskAction,
    check_vix_before_trade,
    get_vix_circuit_breaker,
)


class TestAlertLevelDetermination:
    """Test alert level determination based on VIX levels and spikes."""

    def test_normal_vix_level(self):
        """VIX < 15 should be NORMAL."""
        breaker = VIXCircuitBreaker()
        level = breaker._determine_alert_level(12.0, 0.0)
        assert level == AlertLevel.NORMAL

    def test_elevated_vix_level(self):
        """VIX 15-20 should be ELEVATED."""
        breaker = VIXCircuitBreaker()
        level = breaker._determine_alert_level(17.0, 0.0)
        assert level == AlertLevel.ELEVATED

    def test_high_vix_level(self):
        """VIX 20-25 should be HIGH."""
        breaker = VIXCircuitBreaker()
        level = breaker._determine_alert_level(22.0, 0.0)
        assert level == AlertLevel.HIGH

    def test_very_high_vix_level(self):
        """VIX 25-30 should be VERY_HIGH."""
        breaker = VIXCircuitBreaker()
        level = breaker._determine_alert_level(27.0, 0.0)
        assert level == AlertLevel.VERY_HIGH

    def test_extreme_vix_level(self):
        """VIX >= 30 should be EXTREME."""
        breaker = VIXCircuitBreaker()
        level = breaker._determine_alert_level(35.0, 0.0)
        assert level == AlertLevel.EXTREME

    def test_spike_alert_overrides_level(self):
        """Intraday spike >= 20% should trigger VERY_HIGH regardless of level."""
        breaker = VIXCircuitBreaker()
        # VIX at 18 (normally ELEVATED) but with 25% spike
        level = breaker._determine_alert_level(18.0, 0.25)
        assert level == AlertLevel.VERY_HIGH

    def test_emergency_spike_triggers_extreme(self):
        """Intraday spike >= 30% should trigger EXTREME."""
        breaker = VIXCircuitBreaker()
        level = breaker._determine_alert_level(18.0, 0.35)
        assert level == AlertLevel.EXTREME

    def test_crisis_spike_triggers_spike_level(self):
        """Intraday spike >= 50% should trigger SPIKE (highest alert)."""
        breaker = VIXCircuitBreaker()
        level = breaker._determine_alert_level(20.0, 0.55)
        assert level == AlertLevel.SPIKE


class TestPositionSizing:
    """Test position sizing multipliers based on alert level."""

    def test_normal_allows_full_position(self):
        """Normal VIX allows 100% position size."""
        breaker = VIXCircuitBreaker()
        assert breaker.SIZE_MULTIPLIERS[AlertLevel.NORMAL] == 1.0

    def test_elevated_reduces_to_80_percent(self):
        """Elevated VIX reduces new positions to 80%."""
        breaker = VIXCircuitBreaker()
        assert breaker.SIZE_MULTIPLIERS[AlertLevel.ELEVATED] == 0.8

    def test_high_reduces_to_50_percent(self):
        """High VIX reduces new positions to 50%."""
        breaker = VIXCircuitBreaker()
        assert breaker.SIZE_MULTIPLIERS[AlertLevel.HIGH] == 0.5

    def test_very_high_reduces_to_25_percent(self):
        """Very high VIX reduces new positions to 25%."""
        breaker = VIXCircuitBreaker()
        assert breaker.SIZE_MULTIPLIERS[AlertLevel.VERY_HIGH] == 0.25

    def test_extreme_blocks_new_positions(self):
        """Extreme VIX blocks all new positions (0%)."""
        breaker = VIXCircuitBreaker()
        assert breaker.SIZE_MULTIPLIERS[AlertLevel.EXTREME] == 0.0

    def test_spike_blocks_new_positions(self):
        """Spike alert blocks all new positions (0%)."""
        breaker = VIXCircuitBreaker()
        assert breaker.SIZE_MULTIPLIERS[AlertLevel.SPIKE] == 0.0


class TestReductionTargets:
    """Test position reduction targets for existing positions."""

    def test_normal_no_reduction(self):
        """Normal VIX doesn't require position reduction."""
        breaker = VIXCircuitBreaker()
        assert breaker.REDUCTION_TARGETS[AlertLevel.NORMAL] == 0.0

    def test_high_no_reduction(self):
        """High VIX only restricts new positions, no reduction."""
        breaker = VIXCircuitBreaker()
        assert breaker.REDUCTION_TARGETS[AlertLevel.HIGH] == 0.0

    def test_very_high_reduces_25_percent(self):
        """Very high VIX reduces existing positions by 25%."""
        breaker = VIXCircuitBreaker()
        assert breaker.REDUCTION_TARGETS[AlertLevel.VERY_HIGH] == 0.25

    def test_extreme_reduces_50_percent(self):
        """Extreme VIX reduces existing positions by 50%."""
        breaker = VIXCircuitBreaker()
        assert breaker.REDUCTION_TARGETS[AlertLevel.EXTREME] == 0.50

    def test_spike_reduces_50_percent(self):
        """Spike alert reduces existing positions by 50%."""
        breaker = VIXCircuitBreaker()
        assert breaker.REDUCTION_TARGETS[AlertLevel.SPIKE] == 0.50


class TestTradeAllowance:
    """Test should_allow_trade function with various VIX conditions."""

    @patch.object(VIXCircuitBreaker, '_fetch_vix_data')
    def test_allows_trade_in_normal_conditions(self, mock_fetch):
        """Trade allowed with full size in normal VIX conditions."""
        mock_fetch.return_value = {
            "current": 12.0,
            "previous_close": 12.0,
            "vvix": None
        }
        breaker = VIXCircuitBreaker()
        allowed, reason, adjusted = breaker.should_allow_trade("SPY", 1000.0)

        assert allowed is True
        assert adjusted == 1000.0
        assert "normal" in reason.lower()

    @patch.object(VIXCircuitBreaker, '_fetch_vix_data')
    def test_blocks_trade_in_extreme_conditions(self, mock_fetch):
        """Trade blocked when VIX is extreme."""
        mock_fetch.return_value = {
            "current": 35.0,
            "previous_close": 30.0,
            "vvix": None
        }
        breaker = VIXCircuitBreaker()
        allowed, reason, adjusted = breaker.should_allow_trade("NVDA", 500.0)

        assert allowed is False
        assert adjusted == 0.0
        assert "no new positions" in reason.lower()

    @patch.object(VIXCircuitBreaker, '_fetch_vix_data')
    def test_reduces_trade_size_in_elevated_conditions(self, mock_fetch):
        """Trade size reduced in elevated VIX conditions."""
        mock_fetch.return_value = {
            "current": 17.0,
            "previous_close": 17.0,
            "vvix": None
        }
        breaker = VIXCircuitBreaker()
        allowed, reason, adjusted = breaker.should_allow_trade("AAPL", 1000.0)

        assert allowed is True
        # Elevated = 80% multiplier
        assert adjusted == 800.0


class TestDeRiskingPriority:
    """Test position reduction priority ordering."""

    def test_speculative_stocks_reduce_first(self):
        """High-beta speculative stocks should have priority 1."""
        breaker = VIXCircuitBreaker()
        position = {"symbol": "NVDA", "qty": 10, "unrealized_plpc": 0.05}
        priority = breaker._get_reduction_priority("NVDA", position)
        assert priority == 1

    def test_growth_stocks_reduce_second(self):
        """Growth stocks should have priority 2."""
        breaker = VIXCircuitBreaker()
        position = {"symbol": "GOOGL", "qty": 5, "unrealized_plpc": 0.03}
        priority = breaker._get_reduction_priority("GOOGL", position)
        assert priority == 2

    def test_high_gain_positions_reduce_third(self):
        """Positions with >10% gain should have priority 3."""
        breaker = VIXCircuitBreaker()
        position = {"symbol": "XYZ", "qty": 20, "unrealized_plpc": 0.15}
        priority = breaker._get_reduction_priority("XYZ", position)
        assert priority == 3

    def test_core_etfs_reduce_last(self):
        """Core ETFs (SPY, QQQ, VOO) should reduce last (priority 5)."""
        breaker = VIXCircuitBreaker()
        for symbol in ["SPY", "QQQ", "VOO", "VTI"]:
            position = {"symbol": symbol, "qty": 10, "unrealized_plpc": 0.02}
            priority = breaker._get_reduction_priority(symbol, position)
            assert priority == 5, f"{symbol} should have priority 5"


class TestCheckAndAct:
    """Test the check_and_act method that generates de-risk actions."""

    @patch.object(VIXCircuitBreaker, '_fetch_vix_data')
    def test_no_actions_in_normal_conditions(self, mock_fetch):
        """No de-risk actions needed when VIX is normal."""
        mock_fetch.return_value = {
            "current": 12.0,
            "previous_close": 12.0,
            "vvix": None
        }
        breaker = VIXCircuitBreaker(enable_auto_reduce=False)
        positions = [
            {"symbol": "SPY", "qty": 10, "market_value": 5000}
        ]

        actions = breaker.check_and_act(positions)
        assert len(actions) == 0

    @patch.object(VIXCircuitBreaker, '_fetch_vix_data')
    def test_generates_reduction_actions_in_extreme(self, mock_fetch):
        """De-risk actions generated when VIX is extreme."""
        mock_fetch.return_value = {
            "current": 35.0,
            "previous_close": 30.0,
            "vvix": None
        }
        breaker = VIXCircuitBreaker(enable_auto_reduce=False)
        positions = [
            {"symbol": "NVDA", "qty": 100, "market_value": 10000},
            {"symbol": "SPY", "qty": 50, "market_value": 25000},
        ]

        actions = breaker.check_and_act(positions)
        assert len(actions) == 2

        # All should be "reduce" actions
        for action in actions:
            assert action.action == "reduce"
            # 50% reduction target in extreme
            assert action.target_qty == action.current_qty * 0.5


class TestVIXStatusDataclass:
    """Test VIXStatus dataclass methods."""

    def test_to_dict_method(self):
        """VIXStatus.to_dict() should return proper dictionary."""
        status = VIXStatus(
            current_level=25.0,
            previous_close=20.0,
            intraday_change_pct=25.0,
            alert_level=AlertLevel.VERY_HIGH,
            position_multiplier=0.25,
            new_position_allowed=True,
            reduction_target_pct=0.25,
            message="VIX elevated",
            timestamp=datetime(2026, 1, 7, 10, 30, 0),
            vvix_level=120.0,
        )

        d = status.to_dict()

        assert d["vix_current"] == 25.0
        assert d["vix_prev_close"] == 20.0
        assert d["intraday_change_pct"] == 25.0
        assert d["alert_level"] == "very_high"
        assert d["position_multiplier"] == 0.25
        assert d["new_position_allowed"] is True
        assert d["reduction_target_pct"] == 0.25
        assert d["vvix_level"] == 120.0


class TestCaching:
    """Test VIX status caching behavior."""

    @patch.object(VIXCircuitBreaker, '_fetch_vix_data')
    def test_uses_cache_within_interval(self, mock_fetch):
        """Should use cached status within check interval."""
        mock_fetch.return_value = {
            "current": 15.0,
            "previous_close": 15.0,
            "vvix": None
        }
        breaker = VIXCircuitBreaker(check_interval_seconds=300)

        # First call fetches data
        status1 = breaker.get_current_status()
        call_count_1 = mock_fetch.call_count

        # Second call should use cache
        status2 = breaker.get_current_status()
        call_count_2 = mock_fetch.call_count

        assert call_count_1 == 1
        assert call_count_2 == 1  # No additional fetch
        assert status1.current_level == status2.current_level

    @patch.object(VIXCircuitBreaker, '_fetch_vix_data')
    def test_force_refresh_bypasses_cache(self, mock_fetch):
        """force_refresh=True should bypass cache."""
        mock_fetch.return_value = {
            "current": 15.0,
            "previous_close": 15.0,
            "vvix": None
        }
        breaker = VIXCircuitBreaker(check_interval_seconds=300)

        # First call
        breaker.get_current_status()
        call_count_1 = mock_fetch.call_count

        # Second call with force_refresh
        breaker.get_current_status(force_refresh=True)
        call_count_2 = mock_fetch.call_count

        assert call_count_2 == call_count_1 + 1


class TestFailSafeVIXFetch:
    """Test that VIX fetch failures don't create false safety signals."""

    @patch.object(VIXCircuitBreaker, '_fetch_vix_data')
    def test_raises_error_on_fetch_failure(self, mock_fetch):
        """VIX fetch failure should raise error, not return false safety."""
        mock_fetch.side_effect = RuntimeError("Cannot fetch VIX data")
        breaker = VIXCircuitBreaker()

        with pytest.raises(RuntimeError) as exc_info:
            breaker.get_current_status(force_refresh=True)

        assert "Cannot fetch VIX data" in str(exc_info.value)


class TestGlobalInstance:
    """Test singleton pattern for circuit breaker."""

    def test_get_vix_circuit_breaker_returns_instance(self):
        """get_vix_circuit_breaker should return a VIXCircuitBreaker instance."""
        # Reset singleton for test isolation
        import src.risk.vix_circuit_breaker as module
        module._circuit_breaker = None

        breaker = get_vix_circuit_breaker(paper_mode=True)
        assert isinstance(breaker, VIXCircuitBreaker)
        assert breaker.paper_mode is True


class TestConvenienceFunction:
    """Test the check_vix_before_trade convenience function."""

    @patch('src.risk.vix_circuit_breaker.get_vix_circuit_breaker')
    def test_convenience_function_calls_breaker(self, mock_get):
        """check_vix_before_trade should use global breaker."""
        mock_breaker = MagicMock()
        mock_breaker.should_allow_trade.return_value = (True, "OK", 500.0)
        mock_get.return_value = mock_breaker

        allowed, reason, adjusted = check_vix_before_trade("AAPL", 500.0)

        mock_breaker.should_allow_trade.assert_called_once_with("AAPL", 500.0)
        assert allowed is True
        assert adjusted == 500.0


class TestMessageGeneration:
    """Test human-readable message generation."""

    def test_normal_message(self):
        """Normal VIX should generate calm message."""
        breaker = VIXCircuitBreaker()
        msg = breaker._generate_message(AlertLevel.NORMAL, 12.0, 0.0)
        assert "calm" in msg.lower()
        assert "12.0" in msg

    def test_extreme_message(self):
        """Extreme VIX should generate urgent message."""
        breaker = VIXCircuitBreaker()
        msg = breaker._generate_message(AlertLevel.EXTREME, 35.0, 0.0)
        assert "EXTREME" in msg
        assert "50%" in msg

    def test_spike_message(self):
        """Spike alert should generate emergency message."""
        breaker = VIXCircuitBreaker()
        msg = breaker._generate_message(AlertLevel.SPIKE, 25.0, 0.55)
        assert "SPIKE" in msg
        assert "Emergency" in msg


# Integration test for full workflow
class TestIntegrationWorkflow:
    """Integration tests for complete circuit breaker workflow."""

    @patch.object(VIXCircuitBreaker, '_fetch_vix_data')
    def test_full_de_risk_workflow(self, mock_fetch):
        """Test complete workflow: detect spike -> generate actions."""
        # Simulate 40% VIX spike (crisis level)
        mock_fetch.return_value = {
            "current": 28.0,
            "previous_close": 20.0,  # 40% increase
            "vvix": 130.0
        }

        breaker = VIXCircuitBreaker(enable_auto_reduce=False, paper_mode=True)

        # Get status
        status = breaker.get_current_status(force_refresh=True)

        # Should be at least EXTREME due to 40% spike
        assert status.alert_level in [AlertLevel.EXTREME, AlertLevel.SPIKE]
        assert status.new_position_allowed is False
        assert status.reduction_target_pct >= 0.50

        # Generate de-risk actions
        positions = [
            {"symbol": "NVDA", "qty": 100, "market_value": 10000, "unrealized_plpc": 0.05},
            {"symbol": "TSLA", "qty": 50, "market_value": 12500, "unrealized_plpc": -0.02},
            {"symbol": "SPY", "qty": 200, "market_value": 100000, "unrealized_plpc": 0.03},
        ]

        actions = breaker.check_and_act(positions)

        # Should generate actions for all positions
        assert len(actions) == 3

        # Speculative stocks (NVDA, TSLA) should have higher priority
        priorities = {a.symbol: a.priority for a in actions}
        assert priorities["NVDA"] < priorities["SPY"]  # NVDA before SPY
        assert priorities["TSLA"] < priorities["SPY"]  # TSLA before SPY
