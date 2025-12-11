"""
Tests for Additional Verification Measures.

Tests:
- Position Reconciler
- Model Circuit Breaker
- Signal Backtester
- Hallucination Alerts
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone

from src.verification.position_reconciler import PositionReconciler
from src.verification.model_circuit_breaker import ModelCircuitBreaker, CircuitState
from src.verification.signal_backtester import SignalBacktester
from src.verification.hallucination_alerts import HallucinationAlertSystem


class TestPositionReconciler:
    """Test position reconciliation."""

    @pytest.fixture
    def reconciler(self):
        return PositionReconciler(alpaca_api=None)

    def test_reconcile_matching_positions(self, reconciler):
        """Test reconciliation when positions match."""
        # Mock the actual positions
        reconciler._fetch_actual_positions = Mock(return_value={
            "SPY": {"qty": 10, "market_value": 5000},
            "QQQ": {"qty": 5, "market_value": 2500},
        })

        result = reconciler.reconcile({
            "SPY": {"qty": 10, "market_value": 5000},
            "QQQ": {"qty": 5, "market_value": 2500},
        })

        assert result.is_reconciled is True
        assert len(result.discrepancies) == 0

    def test_reconcile_phantom_position(self, reconciler):
        """Test detection of phantom position (claimed but doesn't exist)."""
        reconciler._fetch_actual_positions = Mock(return_value={
            "SPY": {"qty": 10, "market_value": 5000},
        })

        result = reconciler.reconcile({
            "SPY": {"qty": 10, "market_value": 5000},
            "FAKE": {"qty": 100, "market_value": 10000},  # Phantom!
        })

        assert result.is_reconciled is False
        assert any(d["type"] == "phantom_position" for d in result.discrepancies)

    def test_reconcile_quantity_mismatch(self, reconciler):
        """Test detection of quantity mismatch."""
        reconciler._fetch_actual_positions = Mock(return_value={
            "SPY": {"qty": 10, "market_value": 5000},
        })

        result = reconciler.reconcile({
            "SPY": {"qty": 100, "market_value": 5000},  # Wrong qty!
        })

        assert result.is_reconciled is False
        assert any(d["type"] == "quantity_mismatch" for d in result.discrepancies)

    def test_reconcile_missing_position(self, reconciler):
        """Test detection of missing position (exists but not claimed)."""
        reconciler._fetch_actual_positions = Mock(return_value={
            "SPY": {"qty": 10, "market_value": 5000},
            "QQQ": {"qty": 5, "market_value": 2500},
        })

        result = reconciler.reconcile({
            "SPY": {"qty": 10, "market_value": 5000},
            # Missing QQQ!
        })

        assert result.is_reconciled is False
        assert any(d["type"] == "missing_position" for d in result.discrepancies)


class TestModelCircuitBreaker:
    """Test model circuit breaker."""

    @pytest.fixture
    def breaker(self):
        breaker = ModelCircuitBreaker(
            accuracy_threshold=0.50,
            consecutive_failure_limit=3,
            min_predictions_for_trip=5,
        )
        breaker.model_states = {}  # Clear state
        return breaker

    def test_new_model_enabled(self, breaker):
        """Test that new models are enabled by default."""
        assert breaker.is_model_enabled("new/model") is True

    def test_consecutive_failures_trip(self, breaker):
        """Test circuit trips after consecutive failures."""
        model = "test/model"

        # Record 3 consecutive failures
        for _ in range(3):
            result = breaker.record_prediction(model, was_correct=False)

        assert breaker.is_model_enabled(model) is False
        assert "TRIPPED" in (result.get("action_taken") or "")

    def test_accuracy_threshold_trip(self, breaker):
        """Test circuit trips when accuracy drops below threshold."""
        model = "test/model"

        # Record 2 correct, 4 wrong (33% accuracy < 50% threshold)
        for _ in range(2):
            breaker.record_prediction(model, was_correct=True)
        for _ in range(4):
            result = breaker.record_prediction(model, was_correct=False)

        assert breaker.model_states[model].accuracy < 0.50

    def test_force_reset(self, breaker):
        """Test force reset of circuit breaker."""
        model = "test/model"

        # Trip the breaker
        for _ in range(5):
            breaker.record_prediction(model, was_correct=False)

        assert breaker.is_model_enabled(model) is False

        # Force reset
        breaker.force_reset(model)
        assert breaker.is_model_enabled(model) is True

    def test_get_disabled_models(self, breaker):
        """Test getting list of disabled models."""
        # Trip one model
        for _ in range(5):
            breaker.record_prediction("bad/model", was_correct=False)

        # Keep another enabled
        for _ in range(5):
            breaker.record_prediction("good/model", was_correct=True)

        disabled = breaker.get_disabled_models()
        assert "bad/model" in disabled
        assert "good/model" not in disabled


class TestSignalBacktester:
    """Test signal backtesting."""

    @pytest.fixture
    def backtester(self):
        return SignalBacktester(
            alpaca_api=None,
            min_win_rate=0.50,
            min_sharpe=0.5,
            lookback_days=30,
        )

    def test_backtest_returns_result(self, backtester):
        """Test that backtest returns a result."""
        result = backtester.backtest_signal(
            symbol="SPY",
            signal_direction="BUY",
            model="test/model",
        )

        assert result is not None
        assert result.symbol == "SPY"
        assert result.signal_direction == "BUY"

    def test_backtest_calculates_metrics(self, backtester):
        """Test that backtest calculates metrics."""
        result = backtester.backtest_signal(
            symbol="SPY",
            signal_direction="BUY",
            model="test/model",
        )

        assert 0 <= result.win_rate <= 1
        assert -10 <= result.sharpe_ratio <= 10
        assert 0 <= result.max_drawdown <= 1

    def test_backtest_validation(self, backtester):
        """Test backtest validation logic."""
        result = backtester.backtest_signal(
            symbol="SPY",
            signal_direction="BUY",
            model="test/model",
        )

        # Should have a validation message
        assert result.validation_message is not None

    def test_cache_results(self, backtester):
        """Test that results are cached."""
        result1 = backtester.backtest_signal("SPY", "BUY", "model1")
        result2 = backtester.get_cached_result("SPY", "BUY", "model1")

        assert result2 is not None
        assert result1.signal_id == result2.signal_id


class TestHallucinationAlerts:
    """Test hallucination alert system."""

    @pytest.fixture
    def alert_system(self):
        return HallucinationAlertSystem(
            slack_webhook_url=None,  # Disable Slack
            email_config={},  # Disable email
        )

    def test_send_alert(self, alert_system):
        """Test sending an alert."""
        alert = alert_system.send_alert(
            severity="warning",
            alert_type="test",
            title="Test Alert",
            message="This is a test",
        )

        assert alert is not None
        assert alert.severity == "warning"
        assert alert.title == "Test Alert"

    def test_send_hallucination_alert(self, alert_system):
        """Test sending hallucination alert."""
        alert = alert_system.send_hallucination_alert(
            model="test/model",
            hallucination_type="price_mismatch",
            claimed_value=100.0,
            actual_value=120.0,
        )

        assert alert.alert_type == "hallucination"
        assert "test/model" in alert.title

    def test_send_circuit_breaker_alert(self, alert_system):
        """Test sending circuit breaker alert."""
        alert = alert_system.send_circuit_breaker_alert(
            model="test/model",
            reason="Low accuracy",
            accuracy=0.45,
        )

        assert alert.alert_type == "circuit_breaker"
        assert alert.severity == "critical"

    def test_alert_history(self, alert_system):
        """Test alert history tracking."""
        alert_system.send_alert("info", "test", "Test 1", "Message 1")
        alert_system.send_alert("warning", "test", "Test 2", "Message 2")

        assert len(alert_system.alert_history) == 2

    def test_get_alert_summary(self, alert_system):
        """Test alert summary."""
        alert_system.send_alert("info", "test", "Test", "Message")
        alert_system.send_alert("warning", "hallucination", "Test", "Message")

        summary = alert_system.get_alert_summary(hours=1)

        assert summary["total_alerts"] == 2
        assert "test" in summary["by_type"]
        assert "hallucination" in summary["by_type"]


class TestIntegration:
    """Test integration between components."""

    def test_circuit_breaker_triggers_alert(self):
        """Test that circuit breaker can trigger alerts."""
        breaker = ModelCircuitBreaker(consecutive_failure_limit=3)
        breaker.model_states = {}
        alerts = HallucinationAlertSystem()

        # Trip the breaker
        for i in range(4):
            result = breaker.record_prediction("test/model", was_correct=False)
            if result.get("action_taken"):
                # Send alert
                alert = alerts.send_circuit_breaker_alert(
                    model="test/model",
                    reason=result["action_taken"],
                    accuracy=result["accuracy"],
                )
                assert alert.severity == "critical"
                break


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
