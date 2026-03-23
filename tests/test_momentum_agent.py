from src.agents.momentum_agent import MomentumAgent, MomentumSignal


def test_momentum_agent_initialization():
    """MomentumAgent is retained only as a neutral compatibility stub."""
    agent = MomentumAgent()
    assert agent._min_score == 0.0
    assert hasattr(agent, "rag")
    assert not hasattr(agent, "_strategy")


def test_momentum_agent_configure_regime():
    """Regime configuration is a no-op once MomentumStrategy is removed."""
    agent = MomentumAgent()
    result = agent.configure_regime({"macd_threshold": 1.5, "rsi_overbought": 50.0})
    assert result is None
    assert not hasattr(agent, "_strategy")


def test_momentum_agent_analyze_mock(monkeypatch):
    """Neutral stub must stay non-buying even when market data would be bullish."""
    agent = MomentumAgent()

    # Mock RAG to avoid slow queries
    monkeypatch.setattr(agent.rag, "query", lambda *args, **kwargs: [])

    signal = agent.analyze("SPY")

    assert isinstance(signal, MomentumSignal)
    assert signal.indicators["symbol"] == "SPY"
    assert signal.indicators["note"] == "momentum_strategy_removed"
    assert signal.is_buy is False
    assert signal.strength == 0.0
