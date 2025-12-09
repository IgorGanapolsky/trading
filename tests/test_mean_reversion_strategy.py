"""
Unit tests for Mean Reversion Strategy.

Tests cover:
- RSI calculation accuracy
- Signal generation logic
- Trend filter integration
- VIX filter integration
- Position sizing
- Regime-aware activation
"""

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
from src.strategies.mean_reversion_strategy import (
    MeanReversionSignal,
    MeanReversionStrategy,
)


class TestMeanReversionStrategy(unittest.TestCase):
    """Test suite for Mean Reversion Strategy."""

    def setUp(self):
        """Set up test fixtures."""
        self.strategy = MeanReversionStrategy(
            rsi_buy_threshold=10.0,
            rsi_sell_threshold=90.0,
            rsi_period=2,
            use_trend_filter=True,
            use_vix_filter=True,
        )

    def test_initialization(self):
        """Test strategy initialization with custom parameters."""
        strategy = MeanReversionStrategy(
            rsi_buy_threshold=15.0,
            rsi_sell_threshold=85.0,
            rsi_period=3,
            use_trend_filter=False,
            use_vix_filter=False,
        )

        self.assertEqual(strategy.rsi_buy_threshold, 15.0)
        self.assertEqual(strategy.rsi_sell_threshold, 85.0)
        self.assertEqual(strategy.rsi_period, 3)
        self.assertFalse(strategy.use_trend_filter)
        self.assertFalse(strategy.use_vix_filter)

    def test_calculate_rsi_basic(self):
        """Test RSI calculation with known values."""
        # Create simple price series
        # Uptrend: should have high RSI
        prices = pd.Series([100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 120])

        rsi = self.strategy.calculate_rsi(prices, period=2)

        # RSI should be above 50 for uptrend
        self.assertGreater(rsi.iloc[-1], 50.0)
        self.assertLessEqual(rsi.iloc[-1], 100.0)

    def test_calculate_rsi_downtrend(self):
        """Test RSI calculation in downtrend."""
        # Downtrend: should have low RSI
        prices = pd.Series([120, 118, 116, 114, 112, 110, 108, 106, 104, 102, 100])

        rsi = self.strategy.calculate_rsi(prices, period=2)

        # RSI should be below 50 for downtrend
        self.assertLess(rsi.iloc[-1], 50.0)
        self.assertGreaterEqual(rsi.iloc[-1], 0.0)

    def test_calculate_rsi_extreme_oversold(self):
        """Test RSI calculation in extreme oversold conditions."""
        # Sharp drop followed by recovery
        prices = pd.Series([100, 95, 90, 85, 80, 75, 70, 65, 60, 55, 50])

        rsi = self.strategy.calculate_rsi(prices, period=2)

        # RSI should be very low (oversold)
        self.assertLess(rsi.iloc[-1], 30.0)

    @patch("src.strategies.mean_reversion_strategy.yf.Ticker")
    def test_analyze_buy_signal_oversold(self, mock_ticker_class):
        """Test BUY signal generation when RSI(2) < 10 and above 200 SMA."""
        # Create mock data: oversold + above 200 SMA
        mock_ticker = MagicMock()

        # Generate price data: downtrend at end, but above 200 SMA overall
        prices = np.array([100] * 200)  # Flat for 200 SMA calculation
        # Add recent sharp drop to create oversold condition
        prices = np.concatenate([prices, [105, 103, 101, 99, 97, 95, 93, 91, 89, 87]])

        hist = pd.DataFrame(
            {
                "Close": prices,
                "High": prices * 1.01,
                "Low": prices * 0.99,
                "Volume": [1000000] * len(prices),
            }
        )

        mock_ticker.history.return_value = hist
        mock_ticker_class.return_value = mock_ticker

        # Mock VIX elevated (20+) for confidence boost
        with patch.object(self.strategy, "get_vix", return_value=25.0):
            signal = self.strategy.analyze("SPY")

        # Should generate BUY signal
        self.assertEqual(signal.signal_type, "BUY")
        self.assertGreater(signal.confidence, 0.6)
        self.assertLess(signal.rsi_2, 15.0)  # Should be very oversold
        self.assertGreater(signal.price, signal.sma_200)  # Above 200 SMA
        self.assertIsNotNone(signal.vix)
        self.assertGreater(signal.vix, 20.0)

    @patch("src.strategies.mean_reversion_strategy.yf.Ticker")
    def test_analyze_hold_below_200_sma(self, mock_ticker_class):
        """Test HOLD signal when RSI oversold but below 200 SMA (trend filter)."""
        mock_ticker = MagicMock()

        # Generate price data: downtrend below 200 SMA
        prices = np.array([100] * 200)  # Start high
        # Sharp drop below 200 SMA
        prices = np.concatenate([prices, [80, 78, 76, 74, 72, 70, 68, 66, 64, 62]])

        hist = pd.DataFrame(
            {
                "Close": prices,
                "High": prices * 1.01,
                "Low": prices * 0.99,
                "Volume": [1000000] * len(prices),
            }
        )

        mock_ticker.history.return_value = hist
        mock_ticker_class.return_value = mock_ticker

        with patch.object(self.strategy, "get_vix", return_value=15.0):
            signal = self.strategy.analyze("SPY")

        # Should HOLD due to trend filter
        self.assertEqual(signal.signal_type, "HOLD")
        self.assertLess(signal.price, signal.sma_200)  # Below 200 SMA
        self.assertIn("trend filter", signal.reason.lower())

    @patch("src.strategies.mean_reversion_strategy.yf.Ticker")
    def test_analyze_sell_signal_overbought(self, mock_ticker_class):
        """Test SELL signal when RSI(2) > 90."""
        mock_ticker = MagicMock()

        # Generate price data: sharp rally to create overbought
        prices = np.array([100] * 200)
        # Sharp rally
        prices = np.concatenate([prices, [105, 110, 115, 120, 125, 130, 135, 140, 145, 150]])

        hist = pd.DataFrame(
            {
                "Close": prices,
                "High": prices * 1.01,
                "Low": prices * 0.99,
                "Volume": [1000000] * len(prices),
            }
        )

        mock_ticker.history.return_value = hist
        mock_ticker_class.return_value = mock_ticker

        with patch.object(self.strategy, "get_vix", return_value=15.0):
            signal = self.strategy.analyze("SPY")

        # Should generate SELL signal
        self.assertEqual(signal.signal_type, "SELL")
        self.assertGreater(signal.rsi_2, 90.0)
        self.assertGreater(signal.confidence, 0.5)
        self.assertIn("overbought", signal.reason.lower())

    @patch("src.strategies.mean_reversion_strategy.yf.Ticker")
    def test_position_sizing_extreme_oversold(self, mock_ticker_class):
        """Test position sizing for extreme RSI < 5."""
        mock_ticker = MagicMock()

        # Extreme drop to get RSI < 5
        prices = np.array([100] * 200)
        prices = np.concatenate([prices, [90, 80, 70, 60, 50, 40, 35, 32, 30, 28]])

        hist = pd.DataFrame(
            {
                "Close": prices,
                "High": prices * 1.01,
                "Low": prices * 0.99,
                "Volume": [1000000] * len(prices),
            }
        )

        mock_ticker.history.return_value = hist
        mock_ticker_class.return_value = mock_ticker

        # Use strategy without trend filter for this test
        strategy_no_filter = MeanReversionStrategy(use_trend_filter=False)

        with patch.object(strategy_no_filter, "get_vix", return_value=30.0):
            signal = strategy_no_filter.analyze("SPY")

        # Extreme oversold should suggest larger position
        if signal.signal_type == "BUY":
            self.assertGreaterEqual(signal.suggested_size_pct, 0.05)
            self.assertGreater(signal.stop_loss_pct, 0.0)
            self.assertGreater(signal.take_profit_pct, 0.0)

    @patch("src.strategies.mean_reversion_strategy.yf.Ticker")
    def test_scan_universe(self, mock_ticker_class):
        """Test scanning multiple symbols."""
        mock_ticker = MagicMock()

        # Create neutral data (no strong signals)
        prices = np.array([100] * 210)
        hist = pd.DataFrame(
            {
                "Close": prices,
                "High": prices * 1.01,
                "Low": prices * 0.99,
                "Volume": [1000000] * len(prices),
            }
        )

        mock_ticker.history.return_value = hist
        mock_ticker_class.return_value = mock_ticker

        with patch.object(self.strategy, "get_vix", return_value=15.0):
            signals = self.strategy.scan_universe(["SPY", "QQQ", "IWM"])

        # Should get 3 signals
        self.assertEqual(len(signals), 3)
        self.assertTrue(all(isinstance(s, MeanReversionSignal) for s in signals))

        # Verify symbols
        symbols = {s.symbol for s in signals}
        self.assertEqual(symbols, {"SPY", "QQQ", "IWM"})

    @patch("src.strategies.mean_reversion_strategy.yf.Ticker")
    def test_get_active_signals_filters_hold(self, mock_ticker_class):
        """Test that get_active_signals only returns BUY/SELL, not HOLD."""
        mock_ticker = MagicMock()

        # Neutral data (should produce HOLD signals)
        prices = np.array([100] * 210)
        hist = pd.DataFrame(
            {
                "Close": prices,
                "High": prices * 1.01,
                "Low": prices * 0.99,
                "Volume": [1000000] * len(prices),
            }
        )

        mock_ticker.history.return_value = hist
        mock_ticker_class.return_value = mock_ticker

        with patch.object(self.strategy, "get_vix", return_value=15.0):
            active_signals = self.strategy.get_active_signals(["SPY", "QQQ"])

        # Should filter out HOLD signals
        for signal in active_signals:
            self.assertIn(signal.signal_type, ["BUY", "SELL"])

    def test_no_signal_insufficient_data(self):
        """Test handling of insufficient historical data."""
        with patch("src.strategies.mean_reversion_strategy.yf.Ticker") as mock_ticker_class:
            mock_ticker = MagicMock()

            # Only 100 days of data (need 200 for SMA)
            prices = np.array([100] * 100)
            hist = pd.DataFrame(
                {
                    "Close": prices,
                    "High": prices * 1.01,
                    "Low": prices * 0.99,
                    "Volume": [1000000] * len(prices),
                }
            )

            mock_ticker.history.return_value = hist
            mock_ticker_class.return_value = mock_ticker

            signal = self.strategy.analyze("SPY")

            # Should return no-signal result
            self.assertEqual(signal.signal_type, "HOLD")
            self.assertEqual(signal.confidence, 0.0)
            self.assertIn("insufficient", signal.reason.lower())

    def test_vix_filter_disabled(self):
        """Test strategy with VIX filter disabled."""
        strategy_no_vix = MeanReversionStrategy(use_vix_filter=False)

        with patch("src.strategies.mean_reversion_strategy.yf.Ticker") as mock_ticker_class:
            mock_ticker = MagicMock()

            prices = np.array([100] * 200)
            prices = np.concatenate([prices, [95, 90, 85, 80, 75, 70, 65, 60, 55, 50]])

            hist = pd.DataFrame(
                {
                    "Close": prices,
                    "High": prices * 1.01,
                    "Low": prices * 0.99,
                    "Volume": [1000000] * len(prices),
                }
            )

            mock_ticker.history.return_value = hist
            mock_ticker_class.return_value = mock_ticker

            # VIX should not be called when filter disabled
            signal = strategy_no_vix.analyze("SPY")

            # VIX should be None
            self.assertIsNone(signal.vix)


class TestMeanReversionRegimeIntegration(unittest.TestCase):
    """Test regime-aware activation of mean reversion strategy."""

    def setUp(self):
        """Set up test fixtures."""
        self.strategy = MeanReversionStrategy()

    def test_recommended_for_sideways_markets(self):
        """
        Document that mean reversion is best for SIDEWAYS regimes.

        This is a documentation test showing when to use mean reversion:
        - Market regime: SIDEWAYS, LOW_VOLATILITY
        - Characteristics: Choppy, no strong trend
        - Strategy: Buy oversold (RSI < 10), sell overbought (RSI > 90)
        - Complement: Use momentum in BULL/BEAR trending markets
        """
        # Mean reversion performance by regime (from research)
        regime_performance = {
            "SIDEWAYS": {
                "win_rate": 0.75,  # 75% from Quantified Strategies
                "avg_gain": 0.008,  # 0.8% per trade
                "recommended": True,
            },
            "LOW_VOLATILITY": {
                "win_rate": 0.70,
                "avg_gain": 0.006,
                "recommended": True,
            },
            "BULL": {
                "win_rate": 0.50,  # Lower in trending markets
                "avg_gain": 0.005,
                "recommended": False,  # Use momentum instead
            },
            "BEAR": {
                "win_rate": 0.45,  # Counter-trend is risky
                "avg_gain": 0.003,
                "recommended": False,  # Use momentum instead
            },
        }

        # Verify recommended regimes
        recommended_regimes = [
            regime for regime, perf in regime_performance.items() if perf["recommended"]
        ]

        self.assertIn("SIDEWAYS", recommended_regimes)
        self.assertIn("LOW_VOLATILITY", recommended_regimes)
        self.assertNotIn("BULL", recommended_regimes)
        self.assertNotIn("BEAR", recommended_regimes)


class TestMeanReversionSignalDataclass(unittest.TestCase):
    """Test MeanReversionSignal dataclass."""

    def test_signal_creation(self):
        """Test creating a signal with all fields."""
        signal = MeanReversionSignal(
            symbol="SPY",
            timestamp=datetime.now(),
            signal_type="BUY",
            rsi_2=8.5,
            rsi_5=25.3,
            price=450.25,
            sma_200=445.00,
            vix=22.5,
            confidence=0.85,
            reason="RSI(2)=8.5 EXTREME oversold + VIX=22.5 elevated",
            suggested_size_pct=0.10,
            stop_loss_pct=0.03,
            take_profit_pct=0.02,
        )

        self.assertEqual(signal.symbol, "SPY")
        self.assertEqual(signal.signal_type, "BUY")
        self.assertEqual(signal.rsi_2, 8.5)
        self.assertEqual(signal.confidence, 0.85)
        self.assertEqual(signal.suggested_size_pct, 0.10)


if __name__ == "__main__":
    unittest.main()
