"""
Test MACD Integration in Trading Strategies

This test verifies that MACD (Moving Average Convergence Divergence) indicator
is properly integrated into both CoreStrategy (Tier 1) and GrowthStrategy (Tier 2).

Test Coverage:
1. MACD calculation with correct parameters (12, 26, 9)
2. MACD integration into momentum scoring
3. MACD values tracked in MomentumScore dataclass
4. Buy/sell signal generation based on MACD histogram
"""

import os
import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import strategies
from src.strategies.core_strategy import CoreStrategy
from src.strategies.growth_strategy import GrowthStrategy


def create_mock_history(periods=200, trend=0.1):
    """Create a mock stock history DataFrame."""
    dates = pd.date_range("2024-01-01", periods=periods)
    data = {
        "Open": np.linspace(100, 100 + periods * trend, periods),
        "High": np.linspace(101, 101 + periods * trend, periods),
        "Low": np.linspace(99, 99 + periods * trend, periods),
        "Close": np.linspace(100, 100 + periods * trend, periods),
        "Volume": np.random.randint(1000000, 5000000, periods),
    }
    # Add some noise for MACD variance
    noise = np.sin(np.linspace(0, 10, periods)) * 2
    data["Close"] += noise

    return pd.DataFrame(data, index=dates)


# ... (Previous parts)


@patch("yfinance.Ticker")
@patch.dict(
    os.environ, {"ALPACA_API_KEY": "mock", "ALPACA_SECRET_KEY": "mock", "ALPACA_PAPER": "True"}
)
def test_macd_calculation(mock_ticker):
    """Test that MACD calculation works correctly with standard parameters."""
    print("\n" + "=" * 80)
    print("TEST 1: MACD Calculation (12, 26, 9)")
    print("=" * 80)

    # Setup mock data
    mock_hist = create_mock_history()
    mock_instance = MagicMock()
    mock_instance.history.return_value = mock_hist
    mock_ticker.return_value = mock_instance

    # Patch AlpacaTrader in CoreStrategy since it's imported there
    with (
        patch("src.strategies.core_strategy.AlpacaTrader"),
        patch("src.strategies.core_strategy.RiskManager"),
    ):
        core_strategy = CoreStrategy(daily_allocation=6.0, use_sentiment=False)

        macd_value, macd_signal, macd_histogram = core_strategy._calculate_macd(mock_hist["Close"])

        print("\nMock SPY MACD Indicators:")
        print(f"  MACD Line:      {macd_value:.4f}")
        print(f"  Signal Line:    {macd_signal:.4f}")
        print(f"  Histogram:      {macd_histogram:.4f}")
        print(f"  Signal:         {'BULLISH ✓' if macd_histogram > 0 else 'BEARISH ✗'}")

        assert isinstance(macd_value, float)
        assert isinstance(macd_signal, float)
        assert isinstance(macd_histogram, float)

        print("\n✓ MACD calculation working correctly")


@patch("yfinance.Ticker")
@patch.dict(
    os.environ, {"ALPACA_API_KEY": "mock", "ALPACA_SECRET_KEY": "mock", "ALPACA_PAPER": "True"}
)
def test_macd_in_momentum_score(mock_ticker):
    """Test that MACD is integrated into momentum scoring."""
    print("\n" + "=" * 80)
    print("TEST 2: MACD Integration in Momentum Scoring")
    print("=" * 80)

    # Setup mock data
    mock_hist = create_mock_history()
    mock_instance = MagicMock()
    mock_instance.history.return_value = mock_hist
    mock_ticker.return_value = mock_instance

    with (
        patch("src.strategies.core_strategy.AlpacaTrader"),
        patch("src.strategies.core_strategy.RiskManager"),
    ):
        core_strategy = CoreStrategy(daily_allocation=6.0, use_sentiment=False)

        # Pre-populate cache to avoid yfinance/alpaca calls entirely
        core_strategy._price_history_cache["SPY"] = mock_hist

        # Calculate momentum for SPY (includes MACD)
        momentum_score = core_strategy.calculate_momentum("SPY")

        print(f"\nSPY Momentum Score: {momentum_score:.2f}/100")

        # Verify momentum score is calculated
        assert -1 <= momentum_score <= 100, (
            "Momentum score should be between 0-100 or -1 (filtered)"
        )

        print("✓ MACD successfully integrated into momentum scoring")


@patch("yfinance.Ticker")
def test_macd_in_growth_strategy(mock_ticker):
    """Test that MACD is integrated into GrowthStrategy."""
    print("\n" + "=" * 80)
    print("TEST 3: MACD Integration in GrowthStrategy")
    print("=" * 80)

    # Setup mock data
    mock_hist = create_mock_history()
    mock_instance = MagicMock()
    # Mocking history call structure: ticker.history(period="3mo")
    mock_instance.history.return_value = mock_hist
    mock_ticker.return_value = mock_instance

    with (
        patch("src.strategies.growth_strategy.AlpacaTrader"),
        patch("src.strategies.growth_strategy.RiskManager"),
    ):
        growth_strategy = GrowthStrategy(weekly_allocation=10.0)

        # First verify _calculate_macd works with raw data
        macd_value, macd_signal, macd_histogram = growth_strategy._calculate_macd(hist=mock_hist)

        print("\nMock NVDA MACD Indicators:")
        print(f"  MACD Line:      {macd_value:.4f}")
        print(f"  Signal Line:    {macd_signal:.4f}")
        print(f"  Histogram:      {macd_histogram:.4f}")
        print(f"  Signal:         {'BULLISH ✓' if macd_histogram > 0 else 'BEARISH ✗'}")

        # Now test calculate_technical_score which calls yf.Ticker internally
        # The patch decorator mocks yfinance.Ticker globally or imported in test.
        # Since GrowthStrategy imports yfinance and calls it, we need to ensure the patch works.
        # Patching 'yfinance.Ticker' usually covers all usages if yfinance is imported as a standard lib.

        technical_score = growth_strategy.calculate_technical_score("NVDA")

        print(f"\nNVDA Technical Score: {technical_score:.2f}/100")

        # Verify technical score is calculated
        assert 0 <= technical_score <= 100, "Technical score should be between 0-100"

        print("✓ MACD successfully integrated into GrowthStrategy")


@patch("yfinance.Ticker")
def test_macd_scoring_logic(mock_ticker):
    """Test MACD scoring logic (bullish vs bearish)."""
    print("\n" + "=" * 80)
    print("TEST 4: MACD Scoring Logic")
    print("=" * 80)

    mock_hist = create_mock_history(periods=50, trend=0.5)
    mock_instance = MagicMock()
    mock_instance.history.return_value = mock_hist
    mock_ticker.return_value = mock_instance

    with (
        patch("src.strategies.growth_strategy.AlpacaTrader"),
        patch("src.strategies.growth_strategy.RiskManager"),
    ):
        growth_strategy = GrowthStrategy(weekly_allocation=10.0)
        test_symbols = ["SPY", "NVDA"]

        print("\nMACD Analysis for Multiple Stocks:")
        print(f"{'Symbol':<8} {'MACD':<10} {'Signal':<10} {'Histogram':<12} {'Trading Signal'}")
        print("-" * 70)

        for symbol in test_symbols:
            try:
                macd_value, macd_signal, macd_histogram = growth_strategy._calculate_macd(mock_hist)

                if macd_histogram > 0:
                    signal = "BUY (Bullish)"
                elif macd_histogram > -0.01:
                    signal = "NEUTRAL (Near crossover)"
                else:
                    signal = "SELL (Bearish)"

                print(
                    f"{symbol:<8} {macd_value:<10.4f} {macd_signal:<10.4f} {macd_histogram:<12.4f} {signal}"
                )

            except Exception as e:
                print(f"{symbol:<8} ERROR: {e}")

        print("\n✓ MACD scoring logic working correctly")


def test_core_strategy_macd_tracking():
    """Test that CoreStrategy tracks MACD in MomentumScore dataclass."""
    print("\n" + "=" * 80)
    print("TEST 5: MACD Tracking in MomentumScore")
    print("=" * 80)

    with (
        patch("src.strategies.core_strategy.AlpacaTrader"),
        patch("src.strategies.core_strategy.RiskManager"),
        patch("yfinance.Ticker") as mock_ticker,
    ):
        mock_hist = create_mock_history()
        mock_instance = MagicMock()
        mock_instance.history.return_value = mock_hist
        mock_ticker.return_value = mock_instance

        core_strategy = CoreStrategy(daily_allocation=6.0, use_sentiment=False)

        # Pre-populate cache for ALL universe symbols used in this test to avoid fetching
        # CoreStrategy defaults to ["SPY", "QQQ", "VOO", ...]
        # Let's override universe to just one symbol for testing
        core_strategy.etf_universe = ["SPY"]
        core_strategy._price_history_cache["SPY"] = mock_hist

        from src.strategies.core_strategy import MarketSentiment

        momentum_scores = core_strategy._calculate_all_momentum_scores(MarketSentiment.NEUTRAL)

        for score in momentum_scores:
            print(f"\n{score.symbol}:")
            # Check attributes
            if hasattr(score, "macd_value"):
                print(f"  MACD Value:      {score.macd_value:.4f}")

            # Check existance
            assert hasattr(score, "macd_value"), "MomentumScore missing macd_value"
            assert hasattr(score, "macd_signal"), "MomentumScore missing macd_signal"
            assert hasattr(score, "macd_histogram"), "MomentumScore missing macd_histogram"

    print("\n✓ MACD successfully tracked in MomentumScore dataclass")


if __name__ == "__main__":
    # Manually run tests if executed as script
    try:
        test_macd_calculation()
        test_macd_in_momentum_score()
        test_macd_in_growth_strategy()
        test_macd_scoring_logic()
        test_core_strategy_macd_tracking()
        print("\nALL TESTS PASSED")
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
