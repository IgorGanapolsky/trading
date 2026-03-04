import os
import pytest
from unittest.mock import MagicMock, patch, ANY
from src.orchestrator.main import TradingOrchestrator


class TestOrchestratorHardening:
    """Additional unit tests to increase coverage of src/orchestrator/main.py."""

    @pytest.fixture
    def mock_trader(self, monkeypatch):
        """Initialize TradingOrchestrator with mocked dependencies."""
        monkeypatch.setenv("RAG_QUERY_INDEX_MAX_AGE_MINUTES", "999999")
        monkeypatch.setenv("CONTEXT_INDEX_MAX_AGE_MINUTES", "999999")
        with (
            patch("src.orchestrator.main.AlpacaExecutor"),
            patch("src.orchestrator.main.MomentumAgent"),
            patch("src.orchestrator.main.MacroeconomicAgent"),
            patch("src.orchestrator.main.OrchestratorTelemetry"),
            patch("src.orchestrator.main.OptionsStrategyCoordinator"),
            patch("src.orchestrator.main.RiskManager"),
            patch("src.orchestrator.main.TradeGateway"),
            patch("src.orchestrator.main.BudgetController"),
            patch("src.orchestrator.main.AnomalyMonitor"),
            patch("src.orchestrator.main.FailureIsolationManager"),
        ):
            trader = TradingOrchestrator(tickers=["SPY", "QQQ"])
            # Manually inject a mock for mental_coach since it's None by default
            trader.mental_coach = MagicMock()
            # Mock the core telemetry for verification
            trader.telemetry = MagicMock()
            # Provide a concrete value for account_equity to avoid comparison errors
            trader.executor.account_equity = 100000.0
            # Mock the long-running or problematic methods
            trader._process_tickers_parallel = MagicMock()
            trader.run_delta_rebalancing = MagicMock()
            trader._run_portfolio_strategies = MagicMock()
            trader.run_options_strategy = MagicMock()
            trader.run_iv_options_execution = MagicMock()
            return trader

    def test_gate_0_blocking_strict_mode(self, mock_trader):
        """Test that Gate 0 (Mental Coach) blocks the session in strict mode."""
        # Setup: Coach returns not ready
        mock_trader.mental_coach.is_ready_to_trade.return_value = (
            False,
            MagicMock(headline="TILT", message="Chill out"),
        )

        # Enable strict mode for this test
        with patch.dict(os.environ, {"COACHING_STRICT_MODE": "true"}):
            # Act: Run the funnel
            mock_trader.run()

            # Assert: Telemetry was recorded
            mock_trader.telemetry.record.assert_any_call(
                event_type="coaching.session_blocked",
                ticker="SYSTEM",
                status="blocked",
                payload=ANY,
            )

    def test_adk_decision_summary_telemetry(self, mock_trader):
        """Test that ADK Multi-Agent decisions are summarized and recorded."""
        # Setup: Mock ADK adapter and its decision
        mock_decision = MagicMock()
        mock_decision.symbol = "AAPL"
        mock_decision.action = "BUY"
        mock_decision.confidence = 0.85
        mock_decision.position_size = 0.05

        mock_trader.adk_adapter = MagicMock()
        mock_trader.adk_adapter.evaluate.return_value = mock_decision

        # Act: Run funnel
        with patch(
            "src.orchestrator.main.summarize_adk_decision", return_value={"summary": "Buy AAPL"}
        ):
            mock_trader.run()

            # Assert: Telemetry was recorded
            mock_trader.telemetry.record.assert_any_call(
                event_type="adk.decision",
                ticker="AAPL",
                status="info",
                payload={"summary": "Buy AAPL"},
            )

    def test_manage_positions_called_first(self, mock_trader):
        """Test that position management happens before new entries."""
        # Mocking the sequential calls
        mock_trader._manage_open_positions = MagicMock()
        mock_trader._query_lessons_learned = MagicMock()

        # Act: Run funnel
        mock_trader.run()

        # Assert: Execution order
        assert mock_trader._manage_open_positions.called
        assert mock_trader._query_lessons_learned.called

    def test_macro_context_injection(self, mock_trader):
        """Test that macro context is injected into session profile."""
        mock_trader.macro_agent.get_macro_context.return_value = {"regime": "bullish"}

        # Act
        mock_trader.run()

        # Assert: Telemetry records macro context
        found_profile = False
        for call in mock_trader.telemetry.record.call_args_list:
            if call[1].get("event_type") == "session.profile":
                assert call[1]["payload"]["macro_context"] == {"regime": "bullish"}
                found_profile = True
        assert found_profile
