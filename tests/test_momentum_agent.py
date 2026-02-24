from src.agents.momentum_agent import MomentumAgent, MomentumSignal


def test_momentum_agent_initialization():
    """Test agent initialization."""
    agent = MomentumAgent()
    assert agent._min_score == 0.0
    assert agent._strategy.name == "momentum_strategy"


def test_momentum_agent_configure_regime():
    """Test regime configuration overrides."""
    agent = MomentumAgent()
    agent.configure_regime({"macd_threshold": 1.5, "rsi_overbought": 50.0})

    assert agent._strategy.MACD_THRESHOLD == 1.5
    assert agent._strategy.RSI_OVERBOUGHT == 50.0


def test_momentum_agent_analyze_mock(monkeypatch):
    """Test analyze with mocked data fetching."""
    agent = MomentumAgent()

    # Mock yfinance_wrapper Ticker
    class MockTicker:
        def __init__(self, ticker):
            self.ticker = ticker

        def history(self, period="60d"):
            import pandas as pd
            import numpy as np

            dates = pd.date_range(start="2023-01-01", periods=100)
            prices = np.linspace(100, 150, 100)
            return pd.DataFrame(
                {
                    "Open": prices * 0.99,
                    "High": prices * 1.01,
                    "Low": prices * 0.98,
                    "Close": prices,
                    "Volume": [1000] * 100,
                },
                index=dates,
            )

    from src.utils import yfinance_wrapper

    monkeypatch.setattr(yfinance_wrapper, "Ticker", MockTicker)

    # Mock RAG to avoid slow queries
    monkeypatch.setattr(agent.rag, "query", lambda *args, **kwargs: [])

    signal = agent.analyze("SPY")

    assert isinstance(signal, MomentumSignal)
    assert signal.indicators["symbol"] == "SPY"
    assert signal.is_buy is True
    assert signal.strength > 0
