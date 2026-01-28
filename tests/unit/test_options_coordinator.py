"""Tests for options_coordinator.py - Gate 6 & 7 Options Strategy.

This module tests the options strategy coordination that handles:
- Gate 6: Phil Town Rule #1 Options Strategy
- Gate 7: IV-Aware Options Execution
- Options risk monitoring

CRITICAL for trade execution path.
"""

import pytest
from unittest.mock import MagicMock, patch
import os

from src.orchestrator.options_coordinator import OptionsStrategyCoordinator


class TestOptionsStrategyCoordinator:
    """Tests for OptionsStrategyCoordinator class."""

    @pytest.fixture
    def mock_executor(self):
        """Create mock AlpacaExecutor."""
        return MagicMock()

    @pytest.fixture
    def mock_risk_monitor(self):
        """Create mock OptionsRiskMonitor."""
        mock = MagicMock()
        mock.run_risk_check.return_value = {
            "positions_checked": 3,
            "stop_loss_exits": [],
            "delta_analysis": {"rebalance_needed": False},
        }
        return mock

    @pytest.fixture
    def mock_telemetry(self):
        """Create mock OrchestratorTelemetry."""
        return MagicMock()

    @pytest.fixture
    def coordinator(self, mock_executor, mock_risk_monitor, mock_telemetry):
        """Create coordinator with mocked dependencies."""
        return OptionsStrategyCoordinator(
            executor=mock_executor,
            options_risk_monitor=mock_risk_monitor,
            telemetry=mock_telemetry,
            paper=True,
        )

    def test_creates_coordinator(self, coordinator):
        """Should create coordinator with dependencies."""
        assert coordinator.paper is True
        assert coordinator.executor is not None
        assert coordinator.options_risk_monitor is not None
        assert coordinator.telemetry is not None


class TestRunOptionsRiskCheck:
    """Tests for run_options_risk_check method."""

    @pytest.fixture
    def mock_executor(self):
        return MagicMock()

    @pytest.fixture
    def mock_risk_monitor(self):
        mock = MagicMock()
        mock.run_risk_check.return_value = {
            "positions_checked": 2,
            "stop_loss_exits": [],
            "delta_analysis": {"rebalance_needed": False, "net_delta": 15},
        }
        return mock

    @pytest.fixture
    def mock_telemetry(self):
        return MagicMock()

    @pytest.fixture
    def coordinator(self, mock_executor, mock_risk_monitor, mock_telemetry):
        return OptionsStrategyCoordinator(
            executor=mock_executor,
            options_risk_monitor=mock_risk_monitor,
            telemetry=mock_telemetry,
            paper=True,
        )

    def test_runs_risk_check(self, coordinator, mock_risk_monitor):
        """Should run options risk check."""
        result = coordinator.run_options_risk_check()
        assert result["positions_checked"] == 2
        mock_risk_monitor.run_risk_check.assert_called_once()

    def test_passes_option_prices(self, coordinator, mock_risk_monitor):
        """Should pass option prices to risk monitor."""
        prices = {"SPY260227P00660000": 2.50}
        coordinator.run_options_risk_check(option_prices=prices)
        mock_risk_monitor.run_risk_check.assert_called_with(
            current_prices=prices, executor=coordinator.executor
        )

    def test_records_telemetry(self, coordinator, mock_telemetry):
        """Should record telemetry event."""
        coordinator.run_options_risk_check()
        mock_telemetry.record.assert_called_once()
        call_kwargs = mock_telemetry.record.call_args.kwargs
        assert call_kwargs["event_type"] == "options.risk_check"
        assert call_kwargs["status"] == "completed"

    def test_handles_exception(self, coordinator, mock_risk_monitor):
        """Should handle and return errors gracefully."""
        mock_risk_monitor.run_risk_check.side_effect = Exception("API Error")
        result = coordinator.run_options_risk_check()
        assert "error" in result
        assert "API Error" in result["error"]


class TestRunOptionsStrategy:
    """Tests for run_options_strategy (Gate 6) method."""

    @pytest.fixture
    def mock_executor(self):
        return MagicMock()

    @pytest.fixture
    def mock_risk_monitor(self):
        return MagicMock()

    @pytest.fixture
    def mock_telemetry(self):
        return MagicMock()

    @pytest.fixture
    def coordinator(self, mock_executor, mock_risk_monitor, mock_telemetry):
        return OptionsStrategyCoordinator(
            executor=mock_executor,
            options_risk_monitor=mock_risk_monitor,
            telemetry=mock_telemetry,
            paper=True,
        )

    def test_disabled_when_env_false(self, coordinator):
        """Should be disabled when ENABLE_THETA_AUTOMATION is false."""
        with patch.dict(os.environ, {"ENABLE_THETA_AUTOMATION": "false"}):
            result = coordinator.run_options_strategy()
            assert result["action"] == "disabled"
            assert "ENABLE_THETA_AUTOMATION" in result["reason"]


class TestPaperMode:
    """Tests for paper trading mode."""

    def test_paper_mode_true(self):
        """Should set paper mode to True."""
        coordinator = OptionsStrategyCoordinator(
            executor=MagicMock(),
            options_risk_monitor=MagicMock(),
            telemetry=MagicMock(),
            paper=True,
        )
        assert coordinator.paper is True

    def test_paper_mode_false(self):
        """Should set paper mode to False for live trading."""
        coordinator = OptionsStrategyCoordinator(
            executor=MagicMock(),
            options_risk_monitor=MagicMock(),
            telemetry=MagicMock(),
            paper=False,
        )
        assert coordinator.paper is False
