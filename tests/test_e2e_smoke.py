"""End-to-end smoke tests verifying the trading funnel produces trades.

These tests ensure gates don't accidentally block all trades.

CRITICAL: After the Dec 11, 2025 incident where a syntax error was merged
and caused 0 trades to execute, these tests verify the trading funnel
actually produces trade requests when given valid buy signals.

Test Coverage:
1. test_funnel_produces_trade_with_buy_signal - Mock agents return BUY, verify trade executed
2. test_funnel_respects_sell_signal - Mock agents return SELL, verify no buy executed
3. test_gates_disabled_allows_passthrough - With gates off, signals flow through
4. test_no_silent_rejection - Verify trades aren't silently rejected without logging
"""

import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

# Mock problematic imports before importing our modules
sys.modules["yfinance"] = MagicMock()
sys.modules["ta"] = MagicMock()
sys.modules["alpaca"] = MagicMock()
sys.modules["alpaca.trading"] = MagicMock()
sys.modules["alpaca.trading.client"] = MagicMock()
sys.modules["alpaca.data"] = MagicMock()

# Now we can import pandas and our modules
import pandas as pd
from src.agents.momentum_agent import MomentumSignal
from src.orchestrator.main import TradingOrchestrator

# ============================================================================
# FIXTURES - Mock Components
# ============================================================================


@pytest.fixture
def mock_alpaca_executor():
    """Mock AlpacaExecutor for paper trading."""
    executor = MagicMock()
    executor.paper = True
    executor.account_equity = 100000.0
    executor.get_positions.return_value = []
    executor.sync_portfolio_state.return_value = None

    # Mock place_order to return a valid order
    def mock_place_order(*args, **kwargs):
        return {
            "id": "mock-order-123",
            "symbol": kwargs.get("symbol", "SPY"),
            "side": kwargs.get("side", "buy"),
            "filled_qty": 1.0,
            "notional": kwargs.get("notional", 10.0),
            "status": "filled",
        }

    executor.place_order = mock_place_order
    executor.set_stop_loss.return_value = {"id": "stop-123"}

    return executor


@pytest.fixture
def mock_market_data():
    """Mock market data with valid technical indicators."""
    # Create mock historical data
    idx = pd.date_range(end=datetime.today(), periods=100, freq="D")
    data = pd.DataFrame(
        {
            "Open": [100.0] * 100,
            "High": [102.0] * 100,
            "Low": [98.0] * 100,
            "Close": [101.0] * 100,
            "Volume": [1_000_000] * 100,
        },
        index=idx,
    )
    return data


@pytest.fixture
def mock_momentum_buy_signal():
    """Mock MomentumAgent.analyze() to return a deterministic BUY signal."""
    return MomentumSignal(
        is_buy=True,
        strength=0.75,
        indicators={
            "symbol": "SPY",
            "close": 100.0,
            "last_price": 100.0,
            "rsi": 55.0,
            "macd": 0.5,
            "macd_signal": 0.3,
            "macd_histogram": 0.2,
            "volume_ratio": 1.2,
            "sma_20": 99.0,
            "sma_50": 98.0,
            "momentum_strength": 0.75,
            "raw_score": 50.0,
        },
    )


@pytest.fixture
def mock_momentum_sell_signal():
    """Mock MomentumAgent.analyze() to return a deterministic SELL signal."""
    return MomentumSignal(
        is_buy=False,
        strength=0.25,
        indicators={
            "symbol": "SPY",
            "close": 100.0,
            "last_price": 100.0,
            "rsi": 75.0,  # Overbought
            "macd": -0.5,
            "macd_signal": -0.3,
            "macd_histogram": -0.2,
            "volume_ratio": 0.8,
            "sma_20": 101.0,
            "sma_50": 102.0,
            "momentum_strength": 0.25,
            "raw_score": -20.0,
        },
    )


@pytest.fixture
def mock_macro_bullish():
    """Mock MacroeconomicAgent.get_macro_context() to return BULLISH."""
    return {
        "state": "DOVISH",
        "reason": "Fed signaling rate cuts ahead",
        "confidence": 0.8,
        "retrieved_doc_count": 5,
    }


# ============================================================================
# TEST ENVIRONMENT SETUP
# ============================================================================


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch, tmp_path):
    """Set up test environment with proper flags."""
    # Paper trading mode
    monkeypatch.setenv("PAPER_TRADING", "true")

    # Disable complex gates for smoke test (simplification mode)
    monkeypatch.setenv("RL_FILTER_ENABLED", "false")
    monkeypatch.setenv("LLM_SENTIMENT_ENABLED", "false")

    # Disable optional features that might fail in test
    monkeypatch.setenv("ENABLE_MENTAL_COACHING", "false")
    monkeypatch.setenv("ENABLE_BULL_BEAR_DEBATE", "false")
    monkeypatch.setenv("ENABLE_RAG_CONTEXT", "false")
    monkeypatch.setenv("ENABLE_INTROSPECTION", "false")
    monkeypatch.setenv("ENABLE_ASYNC_ANALYST", "false")
    monkeypatch.setenv("ENABLE_TRADE_VERIFICATION", "false")
    monkeypatch.setenv("ENABLE_THETA_AUTOMATION", "false")
    monkeypatch.setenv("ENABLE_IV_OPTIONS", "false")

    # Set daily investment
    monkeypatch.setenv("DAILY_INVESTMENT", "10")

    # Use temp directory for data files
    monkeypatch.setenv("BIAS_DATA_DIR", str(tmp_path / "bias"))

    # Ensure data directory exists
    (tmp_path / "bias").mkdir(parents=True, exist_ok=True)


# ============================================================================
# SMOKE TESTS
# ============================================================================


def test_funnel_produces_trade_with_buy_signal(
    monkeypatch,
    mock_alpaca_executor,
    mock_momentum_buy_signal,
    mock_macro_bullish,
    mock_market_data,
):
    """
    CRITICAL: Verify the trading funnel produces a trade when given a BUY signal.

    This test ensures that with:
    - A valid BUY signal from momentum
    - Gates disabled (simplification mode)
    - Paper trading enabled

    The system executes at least one trade through TradeGateway.

    If this test fails, it means gates are silently blocking all trades.
    """
    # Patch dependencies
    with (
        patch("src.orchestrator.main.MacroeconomicAgent") as MockMacro,
        patch("src.orchestrator.main.MomentumAgent") as MockMomentum,
        patch("src.orchestrator.main.AlpacaExecutor") as MockExecutor,
        patch("src.orchestrator.main.TradeGateway") as MockGateway,
        patch("src.utils.market_data.MarketDataFetcher") as MockMarketData,
    ):
        # Configure mocks
        mock_macro_instance = MockMacro.return_value
        mock_macro_instance.get_macro_context.return_value = mock_macro_bullish

        mock_momentum_instance = MockMomentum.return_value
        mock_momentum_instance.analyze.return_value = mock_momentum_buy_signal

        MockExecutor.return_value = mock_alpaca_executor

        # Mock TradeGateway to track calls
        mock_gateway_instance = MockGateway.return_value
        mock_gateway_instance.evaluate.return_value = MagicMock(
            approved=True,
            rejection_reasons=[],
            warnings=[],
            risk_score=0.1,
            adjusted_notional=10.0,
            request=MagicMock(symbol="SPY", side="buy", notional=10.0),
        )
        mock_gateway_instance.execute.return_value = {
            "id": "test-order-1",
            "symbol": "SPY",
            "filled_qty": 0.1,
            "status": "filled",
        }

        # Mock market data
        mock_market_data_instance = MockMarketData.return_value
        mock_market_data_instance.get_daily_bars.return_value = MagicMock(data=mock_market_data)

        # Create orchestrator and run
        orchestrator = TradingOrchestrator(tickers=["SPY"], paper=True)
        orchestrator.run()

        # CRITICAL ASSERTION: Verify TradeGateway.execute() was called
        assert mock_gateway_instance.execute.called, (
            "FAILED: TradeGateway.execute() was never called! "
            "This means the trading funnel is blocking all trades."
        )

        # Verify it was called at least once
        execute_call_count = mock_gateway_instance.execute.call_count
        assert execute_call_count > 0, (
            f"FAILED: TradeGateway.execute() called {execute_call_count} times "
            "(expected at least 1)"
        )

        # Verify evaluate was also called (gateway approval step)
        assert mock_gateway_instance.evaluate.called, (
            "FAILED: TradeGateway.evaluate() was never called! "
            "This means trades aren't even reaching the gateway."
        )

        print(f"✅ SUCCESS: Trading funnel produced {execute_call_count} trade(s)")


def test_funnel_respects_sell_signal(
    monkeypatch,
    mock_alpaca_executor,
    mock_momentum_sell_signal,
    mock_macro_bullish,
    mock_market_data,
):
    """
    Verify the funnel correctly rejects when momentum returns SELL.

    This ensures Gate 1 (Momentum) is working properly.
    """
    with (
        patch("src.orchestrator.main.MacroeconomicAgent") as MockMacro,
        patch("src.orchestrator.main.MomentumAgent") as MockMomentum,
        patch("src.orchestrator.main.AlpacaExecutor") as MockExecutor,
        patch("src.orchestrator.main.TradeGateway") as MockGateway,
    ):
        # Configure mocks
        mock_macro_instance = MockMacro.return_value
        mock_macro_instance.get_macro_context.return_value = mock_macro_bullish

        mock_momentum_instance = MockMomentum.return_value
        mock_momentum_instance.analyze.return_value = mock_momentum_sell_signal

        MockExecutor.return_value = mock_alpaca_executor

        mock_gateway_instance = MockGateway.return_value

        # Create orchestrator and run
        orchestrator = TradingOrchestrator(tickers=["SPY"], paper=True)
        orchestrator.run()

        # ASSERTION: TradeGateway.execute() should NOT be called for SELL signal
        assert not mock_gateway_instance.execute.called, (
            "FAILED: TradeGateway.execute() was called despite SELL signal! "
            "Gate 1 (Momentum) is not filtering properly."
        )

        print("✅ SUCCESS: SELL signal correctly rejected at Gate 1")


def test_gates_disabled_allows_passthrough(
    monkeypatch,
    mock_alpaca_executor,
    mock_momentum_buy_signal,
    mock_macro_bullish,
    mock_market_data,
):
    """
    Verify that with all gates disabled (simplification mode),
    a BUY signal flows through to execution.

    This is the MINIMUM requirement - if this fails, the system is broken.
    """
    # Explicitly disable all gates
    monkeypatch.setenv("RL_FILTER_ENABLED", "false")
    monkeypatch.setenv("LLM_SENTIMENT_ENABLED", "false")

    with (
        patch("src.orchestrator.main.MacroeconomicAgent") as MockMacro,
        patch("src.orchestrator.main.MomentumAgent") as MockMomentum,
        patch("src.orchestrator.main.AlpacaExecutor") as MockExecutor,
        patch("src.orchestrator.main.TradeGateway") as MockGateway,
        patch("src.utils.market_data.MarketDataFetcher") as MockMarketData,
    ):
        # Configure mocks
        mock_macro_instance = MockMacro.return_value
        mock_macro_instance.get_macro_context.return_value = mock_macro_bullish

        mock_momentum_instance = MockMomentum.return_value
        mock_momentum_instance.analyze.return_value = mock_momentum_buy_signal

        MockExecutor.return_value = mock_alpaca_executor

        # Gateway approves everything
        mock_gateway_instance = MockGateway.return_value
        mock_gateway_instance.evaluate.return_value = MagicMock(
            approved=True,
            rejection_reasons=[],
            adjusted_notional=10.0,
            request=MagicMock(symbol="SPY", side="buy", notional=10.0),
        )
        mock_gateway_instance.execute.return_value = {
            "id": "test-order-gates-disabled",
            "symbol": "SPY",
            "filled_qty": 0.1,
            "status": "filled",
        }

        # Mock market data
        mock_market_data_instance = MockMarketData.return_value
        mock_market_data_instance.get_daily_bars.return_value = MagicMock(data=mock_market_data)

        # Create orchestrator and run
        orchestrator = TradingOrchestrator(tickers=["SPY"], paper=True)
        orchestrator.run()

        # CRITICAL: With gates disabled, execute MUST be called
        assert mock_gateway_instance.execute.called, (
            "CRITICAL FAILURE: Even with all gates disabled, no trades executed! "
            "This indicates a fundamental system failure."
        )

        print("✅ SUCCESS: BUY signal passed through with gates disabled")


def test_no_silent_rejection(
    monkeypatch,
    mock_alpaca_executor,
    mock_momentum_buy_signal,
    mock_macro_bullish,
    caplog,
):
    """
    Verify that if a trade is rejected, it's logged (not silent).

    Silent rejections are dangerous - they make debugging impossible.
    """
    with (
        patch("src.orchestrator.main.MacroeconomicAgent") as MockMacro,
        patch("src.orchestrator.main.MomentumAgent") as MockMomentum,
        patch("src.orchestrator.main.AlpacaExecutor") as MockExecutor,
        patch("src.orchestrator.main.TradeGateway") as MockGateway,
    ):
        # Configure mocks
        mock_macro_instance = MockMacro.return_value
        mock_macro_instance.get_macro_context.return_value = mock_macro_bullish

        mock_momentum_instance = MockMomentum.return_value
        mock_momentum_instance.analyze.return_value = mock_momentum_buy_signal

        MockExecutor.return_value = mock_alpaca_executor

        # Gateway REJECTS the trade
        from src.risk.trade_gateway import RejectionReason

        mock_gateway_instance = MockGateway.return_value
        mock_gateway_instance.evaluate.return_value = MagicMock(
            approved=False,
            rejection_reasons=[RejectionReason.MINIMUM_BATCH_NOT_MET],
            warnings=["Accumulating toward batch threshold"],
            request=MagicMock(symbol="SPY", side="buy", notional=10.0),
        )

        # Create orchestrator and run
        orchestrator = TradingOrchestrator(tickers=["SPY"], paper=True)
        orchestrator.run()

        # Verify execute was NOT called (trade rejected)
        assert not mock_gateway_instance.execute.called, "Trade should have been rejected"

        # CRITICAL: Verify rejection was LOGGED
        log_text = caplog.text.lower()
        assert any(keyword in log_text for keyword in ["reject", "blocked", "skip", "warning"]), (
            "FAILED: Trade was rejected but no rejection logged! "
            "Silent rejections make debugging impossible."
        )

        print("✅ SUCCESS: Rejection was properly logged")


def test_orchestrator_runs_without_exceptions(
    monkeypatch,
    mock_alpaca_executor,
    mock_momentum_buy_signal,
    mock_macro_bullish,
):
    """
    Basic smoke test: Verify orchestrator.run() completes without exceptions.

    This is the absolute minimum - system must not crash.
    """
    with (
        patch("src.orchestrator.main.MacroeconomicAgent") as MockMacro,
        patch("src.orchestrator.main.MomentumAgent") as MockMomentum,
        patch("src.orchestrator.main.AlpacaExecutor") as MockExecutor,
        patch("src.orchestrator.main.TradeGateway"),
    ):
        # Configure mocks
        mock_macro_instance = MockMacro.return_value
        mock_macro_instance.get_macro_context.return_value = mock_macro_bullish

        mock_momentum_instance = MockMomentum.return_value
        mock_momentum_instance.analyze.return_value = mock_momentum_buy_signal

        MockExecutor.return_value = mock_alpaca_executor

        # Create orchestrator and run (should not raise)
        try:
            orchestrator = TradingOrchestrator(tickers=["SPY"], paper=True)
            orchestrator.run()
            print("✅ SUCCESS: Orchestrator ran without exceptions")
        except Exception as e:
            pytest.fail(f"FAILED: Orchestrator raised exception: {e}")


# ============================================================================
# INTEGRATION TEST (if Alpaca credentials available)
# ============================================================================


@pytest.mark.skipif(
    not os.getenv("ALPACA_API_KEY") or not os.getenv("ALPACA_SECRET_KEY"),
    reason="Alpaca credentials not available",
)
def test_real_alpaca_integration_smoke(monkeypatch):
    """
    Integration test with real Alpaca API (paper trading).

    Only runs if ALPACA_API_KEY and ALPACA_SECRET_KEY are set.

    This verifies the entire system works end-to-end with real APIs.
    """
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("RL_FILTER_ENABLED", "false")
    monkeypatch.setenv("LLM_SENTIMENT_ENABLED", "false")
    monkeypatch.setenv("DAILY_INVESTMENT", "10")

    try:
        orchestrator = TradingOrchestrator(tickers=["SPY"], paper=True)
        orchestrator.run()
        print("✅ SUCCESS: Real Alpaca integration test passed")
    except Exception as e:
        pytest.fail(f"Integration test failed: {e}")
