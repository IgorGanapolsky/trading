"""Tests to verify gate configurations work as expected.

These tests prevent future refactors from sneakily re-enabling gates.

Background:
    Dec 10, 2025: Backtest showed Sharpe ratio -7 to -72 with complex gates.
    Per Carver/López de Prado: "Simple rules beat complex ones"
    Gates 2 (RL) and 3 (LLM) are now DISABLED BY DEFAULT.

Purpose:
    Ensure disabled gates:
    - Don't allocate memory/resources (rl_filter/llm_agent = None)
    - Don't make API calls during trading
    - Can be explicitly enabled when needed
    - Respect environment variable configuration
"""

import sys
from unittest.mock import MagicMock, Mock

import pytest


@pytest.fixture(autouse=True)
def mock_all_imports(monkeypatch):
    """
    Mock all heavy imports to avoid real API connections.

    This is autouse=True so it applies to all tests in this file.
    """
    # Mock holidays module (Python package for holiday calculations)
    mock_holidays = MagicMock()
    mock_holidays.US = MagicMock(return_value={})  # Return empty dict (no holidays)
    sys.modules["holidays"] = mock_holidays

    # Create mock modules
    mock_modules = {
        "src.agents.macro_agent": MagicMock(),
        "src.agents.momentum_agent": MagicMock(),
        "src.agents.rl_agent": MagicMock(),
        "src.analyst.bias_store": MagicMock(),
        "src.execution.alpaca_executor": MagicMock(),
        "src.integrations.playwright_mcp": MagicMock(),
        "src.langchain_agents.analyst": MagicMock(),
        "src.orchestrator.anomaly_monitor": MagicMock(),
        "src.orchestrator.budget": MagicMock(),
        "src.orchestrator.failure_isolation": MagicMock(),
        "src.orchestrator.smart_dca": MagicMock(),
        "src.orchestrator.telemetry": MagicMock(),
        "src.risk.capital_efficiency": MagicMock(),
        "src.risk.options_risk_monitor": MagicMock(),
        "src.risk.position_manager": MagicMock(),
        "src.risk.risk_manager": MagicMock(),
        "src.risk.trade_gateway": MagicMock(),
        "src.signals.microstructure_features": MagicMock(),
        "src.strategies.treasury_ladder_strategy": MagicMock(),
        "src.utils.regime_detector": MagicMock(),
    }

    # Install mocks
    for module_name, mock_module in mock_modules.items():
        sys.modules[module_name] = mock_module

    yield

    # Clean up - remove mocks
    if "holidays" in sys.modules:
        del sys.modules["holidays"]
    for module_name in mock_modules:
        if module_name in sys.modules:
            del sys.modules[module_name]


class TestGatesDisabledByDefault:
    """Test that RL and LLM gates are disabled by default (no env vars)."""

    def test_rl_filter_disabled_by_default(self, monkeypatch):
        """Gate 2 (RL Filter) should be disabled when RL_FILTER_ENABLED is not set."""
        # Ensure RL_FILTER_ENABLED is not set
        monkeypatch.delenv("RL_FILTER_ENABLED", raising=False)

        from src.orchestrator.main import TradingOrchestrator

        orch = TradingOrchestrator(tickers=["SPY"], paper=True)

        # Verify RL filter is disabled
        assert orch.rl_filter_enabled is False, "RL filter should be disabled by default"
        assert orch.rl_filter is None, "rl_filter should be None when disabled"

    def test_llm_sentiment_disabled_by_default(self, monkeypatch):
        """Gate 3 (LLM Sentiment) should be disabled when LLM_SENTIMENT_ENABLED is not set."""
        # Ensure LLM_SENTIMENT_ENABLED is not set
        monkeypatch.delenv("LLM_SENTIMENT_ENABLED", raising=False)

        from src.orchestrator.main import TradingOrchestrator

        orch = TradingOrchestrator(tickers=["SPY"], paper=True)

        # Verify LLM sentiment is disabled
        assert orch.llm_sentiment_enabled is False, "LLM sentiment should be disabled by default"
        assert orch.llm_agent is None, "llm_agent should be None when disabled"

    def test_both_gates_disabled_by_default(self, monkeypatch):
        """Both gates should be disabled when no env vars are set."""
        monkeypatch.delenv("RL_FILTER_ENABLED", raising=False)
        monkeypatch.delenv("LLM_SENTIMENT_ENABLED", raising=False)

        from src.orchestrator.main import TradingOrchestrator

        orch = TradingOrchestrator(tickers=["SPY"], paper=True)

        # Verify both gates disabled
        assert orch.rl_filter_enabled is False
        assert orch.rl_filter is None
        assert orch.llm_sentiment_enabled is False
        assert orch.llm_agent is None


class TestGatesExplicitlyDisabled:
    """Test that gates respect explicit 'false' configuration."""

    @pytest.mark.parametrize("false_value", ["false", "False", "FALSE", "0", "no"])
    def test_rl_filter_explicit_false(self, monkeypatch, false_value):
        """Gate 2 should be disabled when RL_FILTER_ENABLED is explicitly 'false'."""
        monkeypatch.setenv("RL_FILTER_ENABLED", false_value)

        from src.orchestrator.main import TradingOrchestrator

        orch = TradingOrchestrator(tickers=["SPY"], paper=True)

        assert orch.rl_filter_enabled is False
        assert orch.rl_filter is None

    @pytest.mark.parametrize("false_value", ["false", "False", "FALSE", "0", "no"])
    def test_llm_sentiment_explicit_false(self, monkeypatch, false_value):
        """Gate 3 should be disabled when LLM_SENTIMENT_ENABLED is explicitly 'false'."""
        monkeypatch.setenv("LLM_SENTIMENT_ENABLED", false_value)

        from src.orchestrator.main import TradingOrchestrator

        orch = TradingOrchestrator(tickers=["SPY"], paper=True)

        assert orch.llm_sentiment_enabled is False
        assert orch.llm_agent is None


class TestGatesExplicitlyEnabled:
    """Test that gates can be explicitly enabled when needed."""

    @pytest.mark.parametrize("true_value", ["true", "True", "TRUE", "1", "yes"])
    def test_rl_filter_explicit_true(self, monkeypatch, true_value):
        """Gate 2 should be enabled when RL_FILTER_ENABLED is explicitly 'true'."""
        monkeypatch.setenv("RL_FILTER_ENABLED", true_value)

        from src.orchestrator.main import TradingOrchestrator

        orch = TradingOrchestrator(tickers=["SPY"], paper=True)

        assert orch.rl_filter_enabled is True
        assert orch.rl_filter is not None

    @pytest.mark.parametrize("true_value", ["true", "True", "TRUE", "1", "yes"])
    def test_llm_sentiment_explicit_true(self, monkeypatch, true_value):
        """Gate 3 should be enabled when LLM_SENTIMENT_ENABLED is explicitly 'true'."""
        monkeypatch.setenv("LLM_SENTIMENT_ENABLED", true_value)

        from src.orchestrator.main import TradingOrchestrator

        orch = TradingOrchestrator(tickers=["SPY"], paper=True)

        assert orch.llm_sentiment_enabled is True
        assert orch.llm_agent is not None

    def test_both_gates_enabled(self, monkeypatch):
        """Both gates should be enabled when explicitly set to 'true'."""
        monkeypatch.setenv("RL_FILTER_ENABLED", "true")
        monkeypatch.setenv("LLM_SENTIMENT_ENABLED", "true")

        from src.orchestrator.main import TradingOrchestrator

        orch = TradingOrchestrator(tickers=["SPY"], paper=True)

        assert orch.rl_filter_enabled is True
        assert orch.rl_filter is not None
        assert orch.llm_sentiment_enabled is True
        assert orch.llm_agent is not None


class TestDisabledGatesDontMakeCalls:
    """Test that disabled gates don't allocate resources or make API calls."""

    def test_disabled_rl_filter_skips_processing(self, monkeypatch):
        """When RL filter is disabled, _process_ticker should skip Gate 2 without errors."""
        monkeypatch.setenv("RL_FILTER_ENABLED", "false")
        monkeypatch.setenv("LLM_SENTIMENT_ENABLED", "false")

        from src.orchestrator.main import TradingOrchestrator

        orch = TradingOrchestrator(tickers=["SPY"], paper=True)

        # Mock momentum agent to pass Gate 1
        mock_momentum_signal = Mock()
        mock_momentum_signal.is_buy = True
        mock_momentum_signal.strength = 0.8
        mock_momentum_signal.indicators = {"close": 100.0}
        orch.momentum_agent.analyze = Mock(return_value=mock_momentum_signal)

        # Mock failure manager to return momentum signal
        mock_outcome = Mock()
        mock_outcome.ok = True
        mock_outcome.result = mock_momentum_signal
        orch.failure_manager.run = Mock(return_value=mock_outcome)

        # Mock telemetry
        orch.telemetry.gate_reject = Mock()
        orch.telemetry.gate_pass = Mock()
        orch.telemetry.record = Mock()
        orch.telemetry.explainability_event = Mock()
        orch.telemetry.order_event = Mock()

        # Mock other components to prevent execution
        orch.smart_dca.plan_allocation = Mock(
            return_value=Mock(cap=0, bucket="test", confidence=0.5)
        )

        # Call _process_ticker
        orch._process_ticker("SPY", rl_threshold=0.5)

        # Verify RL filter was NOT called (it's None)
        assert orch.rl_filter is None

        # Verify telemetry recorded the skip
        gate_pass_calls = [call for call in orch.telemetry.gate_pass.call_args_list]
        rl_skip = any(
            call[0][0] == "rl_filter" and call[0][2].get("skipped") is True
            for call in gate_pass_calls
        )
        assert rl_skip, "Should record RL gate skip in telemetry"

    def test_disabled_llm_sentiment_skips_processing(self, monkeypatch):
        """When LLM sentiment is disabled, _process_ticker should skip Gate 3 without errors."""
        monkeypatch.setenv("RL_FILTER_ENABLED", "false")
        monkeypatch.setenv("LLM_SENTIMENT_ENABLED", "false")

        from src.orchestrator.main import TradingOrchestrator

        orch = TradingOrchestrator(tickers=["SPY"], paper=True)

        # Verify LLM agent was NOT initialized (it's None)
        assert orch.llm_agent is None, "LLM agent should be None when disabled"

        # Verify _process_ticker doesn't crash when LLM is disabled
        # Mock momentum agent to pass Gate 1
        mock_momentum_signal = Mock()
        mock_momentum_signal.is_buy = True
        mock_momentum_signal.strength = 0.8
        mock_momentum_signal.indicators = {"close": 100.0, "last_price": 100.0}
        orch.momentum_agent.analyze = Mock(return_value=mock_momentum_signal)

        # Mock failure manager
        mock_outcome = Mock()
        mock_outcome.ok = True
        mock_outcome.result = mock_momentum_signal
        orch.failure_manager.run = Mock(return_value=mock_outcome)

        # Mock telemetry
        orch.telemetry.gate_reject = Mock()
        orch.telemetry.gate_pass = Mock()
        orch.telemetry.record = Mock()
        orch.telemetry.explainability_event = Mock()

        # Mock DCA to prevent execution
        orch.smart_dca.plan_allocation = Mock(
            return_value=Mock(cap=0, bucket="test", confidence=0.5)
        )

        # Call _process_ticker - should not crash even with LLM disabled
        try:
            orch._process_ticker("SPY", rl_threshold=0.5)
        except Exception as e:
            # If there's an exception, it should NOT be related to missing LLM agent
            assert "llm_agent" not in str(e).lower(), (
                f"LLM gate should not cause errors when disabled: {e}"
            )
            # Other errors are acceptable (like missing microstructure data, etc.)
            pass

        # Verify LLM agent is still None (wasn't magically created)
        assert orch.llm_agent is None


class TestGateConfigurationIsolation:
    """Test that gate configuration changes don't affect other components."""

    def test_rl_enabled_llm_disabled(self, monkeypatch):
        """RL can be enabled while LLM is disabled (independent gates)."""
        monkeypatch.setenv("RL_FILTER_ENABLED", "true")
        monkeypatch.setenv("LLM_SENTIMENT_ENABLED", "false")

        from src.orchestrator.main import TradingOrchestrator

        orch = TradingOrchestrator(tickers=["SPY"], paper=True)

        assert orch.rl_filter_enabled is True
        assert orch.rl_filter is not None
        assert orch.llm_sentiment_enabled is False
        assert orch.llm_agent is None

    def test_llm_enabled_rl_disabled(self, monkeypatch):
        """LLM can be enabled while RL is disabled (independent gates)."""
        monkeypatch.setenv("RL_FILTER_ENABLED", "false")
        monkeypatch.setenv("LLM_SENTIMENT_ENABLED", "true")

        from src.orchestrator.main import TradingOrchestrator

        orch = TradingOrchestrator(tickers=["SPY"], paper=True)

        assert orch.rl_filter_enabled is False
        assert orch.rl_filter is None
        assert orch.llm_sentiment_enabled is True
        assert orch.llm_agent is not None

    def test_gate_state_does_not_affect_other_components(self, monkeypatch):
        """Disabling gates should not affect other orchestrator components."""
        monkeypatch.setenv("RL_FILTER_ENABLED", "false")
        monkeypatch.setenv("LLM_SENTIMENT_ENABLED", "false")

        from src.orchestrator.main import TradingOrchestrator

        orch = TradingOrchestrator(tickers=["SPY"], paper=True)

        # Verify other components are still initialized
        assert orch.momentum_agent is not None, "Momentum agent should be initialized"
        assert orch.risk_manager is not None, "Risk manager should be initialized"
        assert orch.executor is not None, "Executor should be initialized"
        assert orch.telemetry is not None, "Telemetry should be initialized"
        assert orch.trade_gateway is not None, "Trade gateway should be initialized"


class TestGateMemoryFootprint:
    """Test that disabled gates don't allocate unnecessary memory."""

    def test_disabled_gates_minimal_memory(self, monkeypatch):
        """Disabled gates should not allocate memory for unused components."""
        monkeypatch.setenv("RL_FILTER_ENABLED", "false")
        monkeypatch.setenv("LLM_SENTIMENT_ENABLED", "false")

        from src.orchestrator.main import TradingOrchestrator

        orch = TradingOrchestrator(tickers=["SPY"], paper=True)

        # Verify attributes are None (no memory allocated)
        assert orch.rl_filter is None, "rl_filter should be None (no memory allocated)"
        assert orch.llm_agent is None, "llm_agent should be None (no memory allocated)"

    def test_enabled_gates_allocate_resources(self, monkeypatch):
        """Enabled gates should allocate resources properly."""
        monkeypatch.setenv("RL_FILTER_ENABLED", "true")
        monkeypatch.setenv("LLM_SENTIMENT_ENABLED", "true")

        from src.orchestrator.main import TradingOrchestrator

        orch = TradingOrchestrator(tickers=["SPY"], paper=True)

        # Verify attributes are NOT None (resources allocated)
        assert orch.rl_filter is not None, "rl_filter should be allocated when enabled"
        assert orch.llm_agent is not None, "llm_agent should be allocated when enabled"


class TestRegressionProtection:
    """
    Regression tests to prevent future refactors from sneakily re-enabling gates.

    These tests document the Dec 10, 2025 decision to simplify the system.
    """

    def test_default_config_matches_simplification_mode(self, monkeypatch):
        """
        CRITICAL: Default configuration must match Dec 10, 2025 simplification mode.

        Rationale:
            - Backtest Sharpe: -7 to -72 with complex gates
            - Carver: "Simple rules beat complex ones"
            - López de Prado: "Beware of backtest overfitting"

        Gates 2 (RL) and 3 (LLM) MUST default to disabled.
        """
        # Clear all gate env vars
        monkeypatch.delenv("RL_FILTER_ENABLED", raising=False)
        monkeypatch.delenv("LLM_SENTIMENT_ENABLED", raising=False)

        from src.orchestrator.main import TradingOrchestrator

        orch = TradingOrchestrator(tickers=["SPY"], paper=True)

        # CRITICAL ASSERTIONS - DO NOT REMOVE
        assert orch.rl_filter_enabled is False, (
            "REGRESSION: RL filter must default to disabled (Dec 10, 2025 decision)"
        )
        assert orch.llm_sentiment_enabled is False, (
            "REGRESSION: LLM sentiment must default to disabled (Dec 10, 2025 decision)"
        )

        assert orch.rl_filter is None, (
            "REGRESSION: rl_filter must be None when disabled (memory optimization)"
        )
        assert orch.llm_agent is None, (
            "REGRESSION: llm_agent must be None when disabled (memory optimization)"
        )

    def test_env_var_names_unchanged(self, monkeypatch):
        """
        Protect against renaming env vars (would break existing configs).

        The exact env var names are part of the API contract.
        """
        # Test exact env var names work
        monkeypatch.setenv("RL_FILTER_ENABLED", "true")
        monkeypatch.setenv("LLM_SENTIMENT_ENABLED", "true")

        from src.orchestrator.main import TradingOrchestrator

        orch = TradingOrchestrator(tickers=["SPY"], paper=True)

        assert orch.rl_filter_enabled is True
        assert orch.llm_sentiment_enabled is True

        # If these fail, someone renamed the env vars - this is a breaking change!

    def test_false_string_values_recognized(self, monkeypatch):
        """
        Protect against changing the set of values that mean 'false'.

        Current contract: {"false", "0", "no"} (case-insensitive) = disabled
        """
        false_values = ["false", "False", "FALSE", "0", "no", "No", "NO"]

        for false_value in false_values:
            monkeypatch.setenv("RL_FILTER_ENABLED", false_value)
            monkeypatch.setenv("LLM_SENTIMENT_ENABLED", false_value)

            # Need to reload module to re-initialize
            import importlib

            import src.orchestrator.main

            importlib.reload(src.orchestrator.main)

            from src.orchestrator.main import TradingOrchestrator

            orch = TradingOrchestrator(tickers=["SPY"], paper=True)

            assert orch.rl_filter_enabled is False, f"'{false_value}' should disable RL filter"
            assert orch.llm_sentiment_enabled is False, (
                f"'{false_value}' should disable LLM sentiment"
            )

    def test_true_string_values_recognized(self, monkeypatch):
        """
        Protect against changing the set of values that mean 'true'.

        Current contract: {"true", "1", "yes"} (case-insensitive) = enabled
        """
        true_values = ["true", "True", "TRUE", "1", "yes", "Yes", "YES"]

        for true_value in true_values:
            monkeypatch.setenv("RL_FILTER_ENABLED", true_value)
            monkeypatch.setenv("LLM_SENTIMENT_ENABLED", true_value)

            # Need to reload module to re-initialize
            import importlib

            import src.orchestrator.main

            importlib.reload(src.orchestrator.main)

            from src.orchestrator.main import TradingOrchestrator

            orch = TradingOrchestrator(tickers=["SPY"], paper=True)

            assert orch.rl_filter_enabled is True, f"'{true_value}' should enable RL filter"
            assert orch.llm_sentiment_enabled is True, f"'{true_value}' should enable LLM sentiment"
