import pytest
import pandas as pd
import numpy as np
from src.strategies.momentum_strategy import MomentumStrategy
from src.strategies.core_strategy import Signal


@pytest.fixture
def mock_market_data():
    """Generate mock market data for testing."""
    np.random.seed(42)
    dates = pd.date_range(start="2023-01-01", periods=100)
    # Generate an upward-trending price series with slight acceleration for positive MACD
    prices = np.linspace(100, 150, 100)
    prices[-20:] += np.linspace(0, 3, 20)
    data = pd.DataFrame(
        {
            "Open": prices * 0.99,
            "High": prices * 1.01,
            "Low": prices * 0.98,
            "Close": prices,
            "Volume": np.random.randint(1000000, 5000000, 100),
        },
        index=dates,
    )
    return {"SPY": data}


def test_momentum_strategy_initialization():
    """Test strategy initialization and config."""
    strategy = MomentumStrategy(universe=["SPY"], paper=True)
    assert strategy.name == "momentum_strategy"
    assert strategy.universe == ["SPY"]
    assert strategy.paper is True

    config = strategy.get_config()
    assert config["thresholds"]["macd"] == 0.0
    assert config["thresholds"]["rsi_overbought"] == 85.0


def test_momentum_strategy_generate_signals(mock_market_data):
    """Test signal generation logic."""
    strategy = MomentumStrategy(universe=["SPY"])
    signals = strategy.generate_signals(mock_market_data)

    assert len(signals) == 1
    signal = signals[0]
    assert isinstance(signal, Signal)
    assert signal.symbol == "SPY"
    # Should be a "buy" given the upward trend
    assert signal.action == "buy"
    assert signal.strength > 0
    assert signal.price > 0
    assert signal.stop_loss < signal.price
    assert signal.take_profit > signal.price
    assert "Strong momentum" in signal.rationale


def test_momentum_strategy_insufficient_data():
    """Test handling of insufficient data."""
    strategy = MomentumStrategy(universe=["SPY"])
    short_data = {"SPY": pd.DataFrame({"Close": [100.0] * 5})}
    signals = strategy.generate_signals(short_data)
    assert len(signals) == 0


def test_momentum_strategy_overbought_filter():
    """Test RSI overbought filter."""
    strategy = MomentumStrategy(universe=["SPY"], config={"rsi_overbought": 30.0})
    # Mock data with prices that will likely yield RSI > 30
    dates = pd.date_range(start="2023-01-01", periods=100)
    prices = np.linspace(100, 200, 100)
    data = pd.DataFrame(
        {
            "Open": prices * 0.99,
            "High": prices * 1.01,
            "Low": prices * 0.98,
            "Close": prices,
            "Volume": [1000000] * 100,
        },
        index=dates,
    )

    signals = strategy.generate_signals({"SPY": data})
    assert len(signals) == 1
    # Should be "hold" because RSI is likely over the 30.0 threshold
    assert signals[0].action == "hold"
    assert "RSI" in signals[0].rationale
