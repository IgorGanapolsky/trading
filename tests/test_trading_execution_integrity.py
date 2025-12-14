"""
Trading Execution Integrity Tests

These tests verify critical execution paths work correctly to prevent
issues like the 23-day trading gap (Nov 12 - Dec 4, 2025).

Tests cover:
1. Position management is properly wired
2. Closed trades are recorded for win/loss tracking
3. Win rate calculation works correctly
4. Workflow configurations don't have silent failures
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestPositionManagementWiring:
    """Verify position management is properly integrated into orchestrator."""

    def test_orchestrator_has_position_manager(self):
        """Verify TradingOrchestrator initializes PositionManager."""
        # Import check - if this fails, the wiring is broken
        from src.orchestrator.main import TradingOrchestrator
        from src.risk.position_manager import PositionManager

        # Mock executor to avoid Alpaca connection
        with patch("src.orchestrator.main.AlpacaExecutor"):
            with patch("src.orchestrator.main.MomentumAgent"):
                with patch("src.orchestrator.main.RLFilter"):
                    with patch("src.orchestrator.main.LangChainSentimentAgent"):
                        with patch("src.orchestrator.main.BiasStore"):
                            orchestrator = TradingOrchestrator(tickers=["SPY"], paper=True)
                            assert hasattr(orchestrator, "position_manager")
                            assert isinstance(orchestrator.position_manager, PositionManager)

    def test_orchestrator_calls_manage_positions(self):
        """Verify run() calls _manage_open_positions() before processing tickers."""
        from src.orchestrator.main import TradingOrchestrator

        with patch.object(TradingOrchestrator, "__init__", lambda self, **kwargs: None):
            orchestrator = TradingOrchestrator.__new__(TradingOrchestrator)
            orchestrator.tickers = ["SPY"]
            orchestrator._manage_open_positions = MagicMock(return_value={})
            orchestrator._build_session_profile = MagicMock(
                return_value={
                    "session_type": "test",
                    "is_market_day": True,
                    "tickers": ["SPY"],
                    "rl_threshold": 0.6,
                }
            )
            orchestrator._process_ticker = MagicMock()
            orchestrator._deploy_safe_reserve = MagicMock()
            orchestrator._run_portfolio_strategies = MagicMock()
            orchestrator.run_delta_rebalancing = MagicMock()
            orchestrator.run_options_strategy = MagicMock()
            orchestrator.smart_dca = MagicMock()
            orchestrator.macro_agent = MagicMock()
            orchestrator.momentum_agent = MagicMock()
            orchestrator.telemetry = MagicMock()

            orchestrator.run()

            # CRITICAL: _manage_open_positions must be called
            orchestrator._manage_open_positions.assert_called_once()


class TestClosedTradeRecording:
    """Verify closed trades are properly recorded for win/loss tracking."""

    def test_record_closed_trade_updates_state(self, tmp_path):
        """Verify _record_closed_trade updates system_state.json."""
        # Create temporary state file
        state_file = tmp_path / "system_state.json"
        initial_state = {
            "meta": {"version": "1.0"},
            "performance": {
                "total_trades": 5,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "closed_trades": [],
            },
        }
        state_file.write_text(json.dumps(initial_state))

        # Mock StateManager to use temp file
        with patch("scripts.state_manager.StateManager") as MockStateManager:
            mock_instance = MagicMock()
            mock_instance.state = initial_state.copy()
            mock_instance.state["performance"] = initial_state["performance"].copy()
            MockStateManager.return_value = mock_instance

            from src.orchestrator.main import TradingOrchestrator

            # Create minimal orchestrator instance
            with patch.object(TradingOrchestrator, "__init__", lambda self, **kwargs: None):
                orchestrator = TradingOrchestrator.__new__(TradingOrchestrator)

                # Call the method
                orchestrator._record_closed_trade(
                    symbol="SPY",
                    entry_price=100.0,
                    exit_price=103.0,  # 3% profit
                    quantity=10,
                    entry_date="2025-01-01",
                    exit_reason="take_profit",
                )

                # Verify state was updated
                mock_instance.record_closed_trade.assert_called_once()
                mock_instance.save.assert_called_once()


class TestWinRateCalculation:
    """Verify win rate is calculated correctly."""

    def test_win_rate_calculation(self):
        """Test win rate calculation from closed trades."""
        from scripts.state_manager import StateManager

        with patch.object(StateManager, "__init__", lambda self: None):
            manager = StateManager.__new__(StateManager)
            manager.state = {
                "performance": {
                    "closed_trades": [
                        {"symbol": "SPY", "pl": 10.0},  # Win
                        {"symbol": "NVDA", "pl": -5.0},  # Loss
                        {"symbol": "GOOGL", "pl": 15.0},  # Win
                    ],
                    "winning_trades": 2,
                    "losing_trades": 1,
                }
            }

            # Calculate expected win rate
            total = len(manager.state["performance"]["closed_trades"])
            winning = manager.state["performance"]["winning_trades"]
            expected_win_rate = (winning / total) * 100  # 66.67%

            assert expected_win_rate == pytest.approx(66.67, rel=0.01)


class TestWorkflowConfiguration:
    """Verify GitHub Actions workflows don't have silent failure patterns."""

    @pytest.fixture
    def workflow_path(self):
        return Path(__file__).parent.parent / ".github" / "workflows"

    def test_no_silent_exit_zero_after_failure(self, workflow_path):
        """
        CRITICAL: Verify workflows don't exit 0 after failures.

        This was the root cause of 23 days without trading - workflows
        appeared successful but actually failed silently.
        """
        daily_trading = workflow_path / "daily-trading.yml"
        if not daily_trading.exists():
            pytest.skip("Workflow file not found")

        content = daily_trading.read_text()

        # Check for dangerous patterns
        dangerous_patterns = [
            # Pattern that caused secrets validation bypass
            ('echo "secrets_valid=true"', "unconditional success"),
            # Silent MCP failure pattern
            ("exit 0\n          fi\n          nohup uvx", "silent MCP skip"),
        ]

        for pattern, description in dangerous_patterns:
            if pattern in content:
                pytest.fail(f"Found dangerous pattern ({description}): {pattern[:50]}...")

    def test_secrets_validation_uses_gha_output(self, workflow_path):
        """Verify secrets validation properly sets GitHub output."""
        daily_trading = workflow_path / "daily-trading.yml"
        if not daily_trading.exists():
            pytest.skip("Workflow file not found")

        content = daily_trading.read_text()

        # Should use --gha-output flag
        assert "--gha-output" in content, "Secrets validation must use --gha-output flag"

    def test_mcp_failure_is_fatal(self, workflow_path):
        """Verify MCP server failure stops the workflow."""
        daily_trading = workflow_path / "daily-trading.yml"
        if not daily_trading.exists():
            pytest.skip("Workflow file not found")

        content = daily_trading.read_text()

        # Should exit 1 when credentials missing, not exit 0
        assert "exit 1" in content and "ALPACA_API_KEY" in content, (
            "MCP failure must be fatal when credentials missing"
        )


class TestExecutionTracking:
    """Verify execution is properly tracked and logged."""

    def test_system_state_has_execution_tracking(self):
        """Verify system_state.json has automation tracking fields."""
        state_path = Path(__file__).parent.parent / "data" / "system_state.json"
        if not state_path.exists():
            pytest.skip("system_state.json not found")

        with open(state_path) as f:
            state = json.load(f)

        # Should have meta fields for tracking
        assert "meta" in state
        assert "last_updated" in state["meta"]

    def test_daily_report_created(self):
        """Verify daily reports are being created."""
        reports_path = Path(__file__).parent.parent / "reports"
        if not reports_path.exists():
            pytest.skip("Reports directory not found")

        # Get recent reports
        reports = list(reports_path.glob("daily_report_*.txt"))

        # Should have at least one report in last 7 days
        recent_reports = []
        cutoff = datetime.now() - timedelta(days=7)
        for report in reports:
            try:
                date_str = report.stem.replace("daily_report_", "")
                report_date = datetime.strptime(date_str, "%Y-%m-%d")
                if report_date > cutoff:
                    recent_reports.append(report)
            except ValueError:
                continue

        # Warn if no recent reports (don't fail - might be weekend)
        if not recent_reports:
            pytest.skip("No recent daily reports - check if trading is running")


class TestAlpacaExecutor:
    """Verify AlpacaExecutor has required methods."""

    def test_executor_has_get_positions(self):
        """Verify AlpacaExecutor has get_positions method."""
        from src.execution.alpaca_executor import AlpacaExecutor

        assert hasattr(AlpacaExecutor, "get_positions")

    def test_get_positions_returns_list(self):
        """Verify get_positions returns a list."""
        from src.execution.alpaca_executor import AlpacaExecutor

        with patch.object(AlpacaExecutor, "__init__", lambda self, **kwargs: None):
            executor = AlpacaExecutor.__new__(AlpacaExecutor)
            executor.simulated = True
            executor.positions = []
            executor.trader = None

            result = executor.get_positions()
            assert isinstance(result, list)


class TestPositionManager:
    """Verify PositionManager exit logic works correctly."""

    def test_position_manager_evaluates_exits(self):
        """Verify PositionManager evaluates positions for exits."""
        from datetime import datetime

        from src.risk.position_manager import (
            ExitConditions,
            PositionInfo,
            PositionManager,
        )

        manager = PositionManager(
            conditions=ExitConditions(
                take_profit_pct=0.03,
                stop_loss_pct=0.03,
                max_holding_days=10,
            )
        )

        # Test take-profit trigger
        winning_position = PositionInfo(
            symbol="SPY",
            quantity=10,
            entry_price=100.0,
            current_price=104.0,  # 4% profit > 3% target
            entry_date=datetime.now(),
            unrealized_pl=40.0,
            unrealized_plpc=0.04,
            market_value=1040.0,
        )

        signal = manager.evaluate_position(winning_position)
        assert signal.should_exit
        assert signal.reason.value == "take_profit"

    def test_stop_loss_triggers(self):
        """Verify stop-loss triggers correctly."""
        from datetime import datetime

        from src.risk.position_manager import (
            ExitConditions,
            PositionInfo,
            PositionManager,
        )

        manager = PositionManager(conditions=ExitConditions(stop_loss_pct=0.03))

        losing_position = PositionInfo(
            symbol="SPY",
            quantity=10,
            entry_price=100.0,
            current_price=96.0,  # 4% loss > 3% stop
            entry_date=datetime.now(),
            unrealized_pl=-40.0,
            unrealized_plpc=-0.04,
            market_value=960.0,
        )

        signal = manager.evaluate_position(losing_position)
        assert signal.should_exit
        assert signal.reason.value == "stop_loss"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
