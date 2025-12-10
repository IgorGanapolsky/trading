"""
Tests for VIX Monitoring and Volatility Regime Detection

Tests cover:
1. VIX data fetching (Alpaca and yfinance)
2. VIX percentile calculation
3. Term structure analysis
4. Contango/backwardation detection
5. VVIX monitoring
6. Volatility regime classification
7. VIX spike detection
8. Mean reversion probability
9. Trading signals (sell/buy premium)
10. Position sizing recommendations
11. Strategy recommendations
12. State export for system integration

Author: Claude (CTO)
Created: 2025-12-10
"""

import json
import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import Mock, patch

import numpy as np
from src.options.vix_monitor import (
    TermStructureState,
    VIXMonitor,
    VIXSignals,
    VolatilityRegime,
)


class TestVolatilityRegime(unittest.TestCase):
    """Test VolatilityRegime enum"""

    def test_regime_values(self):
        """Test all regime values are defined"""
        self.assertEqual(VolatilityRegime.EXTREME_LOW.value, "extreme_low")
        self.assertEqual(VolatilityRegime.LOW.value, "low")
        self.assertEqual(VolatilityRegime.NORMAL.value, "normal")
        self.assertEqual(VolatilityRegime.ELEVATED.value, "elevated")
        self.assertEqual(VolatilityRegime.HIGH.value, "high")
        self.assertEqual(VolatilityRegime.EXTREME.value, "extreme")


class TestTermStructureState(unittest.TestCase):
    """Test TermStructureState enum"""

    def test_term_structure_values(self):
        """Test term structure states"""
        self.assertEqual(TermStructureState.CONTANGO.value, "contango")
        self.assertEqual(TermStructureState.BACKWARDATION.value, "backwardation")
        self.assertEqual(TermStructureState.FLAT.value, "flat")


class TestVIXMonitor(unittest.TestCase):
    """Test VIXMonitor class"""

    def setUp(self):
        """Set up test fixtures"""
        # Use temporary file for VIX history
        self.temp_dir = tempfile.mkdtemp()
        self.vix_history_file = os.path.join(self.temp_dir, "vix_history.json")

        # Patch the VIX_HISTORY_FILE constant
        self.patcher = patch.object(VIXMonitor, "VIX_HISTORY_FILE", self.vix_history_file)
        self.patcher.start()

        # Initialize monitor without Alpaca (use yfinance only for tests)
        self.monitor = VIXMonitor(use_alpaca=False)

    def tearDown(self):
        """Clean up after tests"""
        self.patcher.stop()
        # Clean up temp files
        if os.path.exists(self.vix_history_file):
            os.remove(self.vix_history_file)
        os.rmdir(self.temp_dir)

    @patch("src.options.vix_monitor.yf.Ticker")
    def test_get_current_vix(self, mock_ticker):
        """Test fetching current VIX value"""
        # Mock yfinance response
        mock_vix = Mock()
        mock_vix.history.return_value = Mock(
            empty=False,
            Close=Mock(iloc=[-1]),
            __getitem__=lambda self, key: Mock(iloc=[Mock(__getitem__=lambda s, i: 18.5)]),
        )
        mock_ticker.return_value = mock_vix

        # Proper mock setup for pandas Series
        import pandas as pd

        mock_history = pd.DataFrame({"Close": [18.5]})
        mock_vix.history.return_value = mock_history

        vix = self.monitor.get_current_vix()

        self.assertEqual(vix, 18.5)
        mock_ticker.assert_called_with("^VIX")

    @patch("src.options.vix_monitor.yf.Ticker")
    def test_get_current_vix_failure(self, mock_ticker):
        """Test VIX fetch failure handling"""
        mock_vix = Mock()
        import pandas as pd

        mock_vix.history.return_value = pd.DataFrame()  # Empty dataframe
        mock_ticker.return_value = mock_vix

        with self.assertRaises(RuntimeError):
            self.monitor.get_current_vix()

    def test_get_volatility_regime(self):
        """Test volatility regime classification"""
        # Test all regimes
        test_cases = [
            (10.0, VolatilityRegime.EXTREME_LOW),
            (13.0, VolatilityRegime.LOW),
            (17.0, VolatilityRegime.NORMAL),
            (22.0, VolatilityRegime.ELEVATED),
            (30.0, VolatilityRegime.HIGH),
            (40.0, VolatilityRegime.EXTREME),
        ]

        for vix_value, expected_regime in test_cases:
            with self.subTest(vix=vix_value):
                regime = self.monitor.get_volatility_regime(vix_value)
                self.assertEqual(regime, expected_regime)

    @patch("src.options.vix_monitor.yf.Ticker")
    def test_get_vix_percentile(self, mock_ticker):
        """Test VIX percentile calculation"""
        # Create mock historical data
        import pandas as pd

        dates = pd.date_range(end=datetime.now(), periods=252, freq="D")
        historical_vix = np.random.normal(16, 5, 252)  # Mean 16, std 5
        mock_history = pd.DataFrame({"Close": historical_vix}, index=dates)

        mock_vix = Mock()
        mock_vix.history.side_effect = [
            pd.DataFrame({"Close": [18.0]}),  # Current VIX
            mock_history,  # Historical data
        ]
        mock_ticker.return_value = mock_vix

        percentile = self.monitor.get_vix_percentile(lookback_days=252)

        self.assertGreaterEqual(percentile, 0)
        self.assertLessEqual(percentile, 100)

    @patch("src.options.vix_monitor.yf.Ticker")
    def test_get_vix_term_structure(self, mock_ticker):
        """Test VIX term structure fetching"""
        import pandas as pd

        # Mock VIX and VXV
        def mock_ticker_side_effect(symbol):
            mock = Mock()
            if symbol == "^VIX":
                mock.history.return_value = pd.DataFrame({"Close": [18.0]})
            elif symbol == "^VXV":
                mock.history.return_value = pd.DataFrame({"Close": [20.0]})
            return mock

        mock_ticker.side_effect = mock_ticker_side_effect

        term_structure = self.monitor.get_vix_term_structure()

        self.assertIn("vx1", term_structure)
        self.assertIn("vx2", term_structure)
        self.assertIn("vx3", term_structure)
        self.assertIn("overall_slope", term_structure)

        self.assertEqual(term_structure["vx1"], 18.0)
        self.assertEqual(term_structure["vx3"], 20.0)
        self.assertGreater(term_structure["vx2"], term_structure["vx1"])
        self.assertLess(term_structure["vx2"], term_structure["vx3"])

    @patch("src.options.vix_monitor.yf.Ticker")
    def test_is_contango(self, mock_ticker):
        """Test contango detection"""
        import pandas as pd

        def mock_ticker_side_effect(symbol):
            mock = Mock()
            if symbol == "^VIX":
                mock.history.return_value = pd.DataFrame({"Close": [15.0]})
            elif symbol == "^VXV":
                mock.history.return_value = pd.DataFrame({"Close": [18.0]})  # Higher = contango
            return mock

        mock_ticker.side_effect = mock_ticker_side_effect

        is_contango = self.monitor.is_contango(threshold=0.5)
        self.assertTrue(is_contango)

    @patch("src.options.vix_monitor.yf.Ticker")
    def test_is_backwardation(self, mock_ticker):
        """Test backwardation detection"""
        import pandas as pd

        def mock_ticker_side_effect(symbol):
            mock = Mock()
            if symbol == "^VIX":
                mock.history.return_value = pd.DataFrame({"Close": [25.0]})
            elif symbol == "^VXV":
                mock.history.return_value = pd.DataFrame({"Close": [22.0]})  # Lower = backwardation
            return mock

        mock_ticker.side_effect = mock_ticker_side_effect

        is_backwardation = self.monitor.is_backwardation(threshold=-0.5)
        self.assertTrue(is_backwardation)

    @patch("src.options.vix_monitor.yf.Ticker")
    def test_get_term_structure_state(self, mock_ticker):
        """Test term structure state classification"""
        import pandas as pd

        # Test contango
        def mock_contango(symbol):
            mock = Mock()
            if symbol == "^VIX":
                mock.history.return_value = pd.DataFrame({"Close": [15.0]})
            elif symbol == "^VXV":
                mock.history.return_value = pd.DataFrame({"Close": [18.0]})
            return mock

        mock_ticker.side_effect = mock_contango
        state = self.monitor.get_term_structure_state()
        self.assertEqual(state, TermStructureState.CONTANGO)

        # Test backwardation
        def mock_backwardation(symbol):
            mock = Mock()
            if symbol == "^VIX":
                mock.history.return_value = pd.DataFrame({"Close": [25.0]})
            elif symbol == "^VXV":
                mock.history.return_value = pd.DataFrame({"Close": [22.0]})
            return mock

        mock_ticker.side_effect = mock_backwardation
        state = self.monitor.get_term_structure_state()
        self.assertEqual(state, TermStructureState.BACKWARDATION)

    @patch("src.options.vix_monitor.yf.Ticker")
    def test_get_vvix(self, mock_ticker):
        """Test VVIX fetching"""
        import pandas as pd

        mock_vvix = Mock()
        mock_vvix.history.return_value = pd.DataFrame({"Close": [95.0]})
        mock_ticker.return_value = mock_vvix

        vvix = self.monitor.get_vvix()

        self.assertEqual(vvix, 95.0)
        mock_ticker.assert_called_with("^VVIX")

    @patch("src.options.vix_monitor.yf.Ticker")
    def test_calculate_vix_statistics(self, mock_ticker):
        """Test VIX statistics calculation"""
        import pandas as pd

        dates = pd.date_range(end=datetime.now(), periods=252, freq="D")
        historical_vix = np.array([15.0] * 252)  # Constant for easy testing

        def mock_ticker_side_effect(symbol):
            mock = Mock()
            if symbol == "^VIX":
                # First call for current VIX
                if not hasattr(mock_ticker_side_effect, "call_count"):
                    mock_ticker_side_effect.call_count = 0
                    mock.history.return_value = pd.DataFrame({"Close": [18.0]})
                else:
                    # Second call for historical data
                    mock.history.return_value = pd.DataFrame({"Close": historical_vix}, index=dates)
                mock_ticker_side_effect.call_count += 1
            return mock

        mock_ticker.side_effect = mock_ticker_side_effect

        stats = self.monitor.calculate_vix_statistics(lookback_days=252)

        self.assertIn("current", stats)
        self.assertIn("mean", stats)
        self.assertIn("std", stats)
        self.assertIn("min", stats)
        self.assertIn("max", stats)
        self.assertIn("percentile", stats)
        self.assertIn("z_score", stats)

    @patch("src.options.vix_monitor.yf.Ticker")
    def test_detect_vix_spike(self, mock_ticker):
        """Test VIX spike detection"""
        import pandas as pd

        dates = pd.date_range(end=datetime.now(), periods=252, freq="D")
        historical_vix = np.array([15.0] * 252)  # Mean = 15, Std = 0

        call_counter = {"count": 0}

        def mock_ticker_side_effect(symbol):
            mock = Mock()
            if symbol == "^VIX":
                if call_counter["count"] == 0:
                    # Current VIX = 30 (spike!)
                    mock.history.return_value = pd.DataFrame({"Close": [30.0]})
                else:
                    # Historical data
                    mock.history.return_value = pd.DataFrame({"Close": historical_vix}, index=dates)
                call_counter["count"] += 1
            return mock

        mock_ticker.side_effect = mock_ticker_side_effect

        spike_info = self.monitor.detect_vix_spike(threshold_z_score=2.0)

        self.assertIn("is_spike", spike_info)
        self.assertIn("z_score", spike_info)
        self.assertIn("severity", spike_info)

    @patch("src.options.vix_monitor.yf.Ticker")
    def test_calculate_mean_reversion_probability(self, mock_ticker):
        """Test mean reversion probability calculation"""
        import pandas as pd

        dates = pd.date_range(end=datetime.now(), periods=252, freq="D")
        historical_vix = np.full(252, 16.0)  # Mean = 16

        call_counter = {"count": 0}

        def mock_ticker_side_effect(symbol):
            mock = Mock()
            if symbol == "^VIX":
                if call_counter["count"] == 0:
                    # Current VIX high = likely to revert
                    mock.history.return_value = pd.DataFrame({"Close": [30.0]})
                else:
                    mock.history.return_value = pd.DataFrame({"Close": historical_vix}, index=dates)
                call_counter["count"] += 1
            return mock

        mock_ticker.side_effect = mock_ticker_side_effect

        reversion_prob = self.monitor.calculate_mean_reversion_probability()

        self.assertGreaterEqual(reversion_prob, 0.0)
        self.assertLessEqual(reversion_prob, 1.0)
        self.assertGreater(reversion_prob, 0.6)  # High VIX should have high reversion prob

    def test_vix_history_persistence(self):
        """Test VIX history save/load"""
        # Simulate updating VIX history
        self.monitor._update_vix_history(18.5)

        # Load from file
        with open(self.vix_history_file) as f:
            history = json.load(f)

        self.assertIn("daily_values", history)
        self.assertIn("last_updated", history)
        self.assertGreater(len(history["daily_values"]), 0)

        # Verify value
        today = datetime.now().date().isoformat()
        today_value = next(v for v in history["daily_values"] if v["date"] == today)
        self.assertEqual(today_value["vix"], 18.5)

    @patch("src.options.vix_monitor.yf.Ticker")
    def test_export_state(self, mock_ticker):
        """Test state export for system_state.json integration"""
        import pandas as pd

        # Mock all required data
        call_counter = {"count": 0}

        def mock_ticker_side_effect(symbol):
            mock = Mock()
            if symbol == "^VIX":
                if call_counter["count"] % 3 == 0:
                    mock.history.return_value = pd.DataFrame({"Close": [18.0]})
                else:
                    dates = pd.date_range(end=datetime.now(), periods=252, freq="D")
                    mock.history.return_value = pd.DataFrame(
                        {"Close": np.full(252, 16.0)}, index=dates
                    )
                call_counter["count"] += 1
            elif symbol == "^VXV":
                mock.history.return_value = pd.DataFrame({"Close": [20.0]})
            elif symbol == "^VVIX":
                mock.history.return_value = pd.DataFrame({"Close": [95.0]})
            return mock

        mock_ticker.side_effect = mock_ticker_side_effect

        state = self.monitor.export_state()

        # Verify all required fields
        self.assertIn("current_vix", state)
        self.assertIn("volatility_regime", state)
        self.assertIn("vix_percentile", state)
        self.assertIn("term_structure", state)
        self.assertIn("statistics", state)
        self.assertIn("vvix", state)
        self.assertIn("spike_detected", state)
        self.assertIn("mean_reversion_probability", state)
        self.assertIn("last_updated", state)


class TestVIXSignals(unittest.TestCase):
    """Test VIXSignals class"""

    def setUp(self):
        """Set up test fixtures"""
        self.monitor = Mock(spec=VIXMonitor)
        self.signals = VIXSignals(vix_monitor=self.monitor)

    def test_should_sell_premium_high_vix(self):
        """Test premium selling signal in high VIX regime"""
        # High VIX scenario
        self.monitor.get_current_vix.return_value = 30.0
        self.monitor.get_volatility_regime.return_value = VolatilityRegime.HIGH
        self.monitor.get_vix_percentile.return_value = 85.0
        self.monitor.calculate_mean_reversion_probability.return_value = 0.85

        result = self.signals.should_sell_premium()

        self.assertTrue(result["should_sell_premium"])
        self.assertEqual(result["confidence"], "HIGH")
        self.assertIn("recommended_strategies", result)
        self.assertGreater(len(result["recommended_strategies"]), 0)

    def test_should_sell_premium_low_vix(self):
        """Test premium selling signal in low VIX regime"""
        # Low VIX scenario
        self.monitor.get_current_vix.return_value = 12.0
        self.monitor.get_volatility_regime.return_value = VolatilityRegime.LOW
        self.monitor.get_vix_percentile.return_value = 20.0
        self.monitor.calculate_mean_reversion_probability.return_value = 0.35

        result = self.signals.should_sell_premium()

        self.assertFalse(result["should_sell_premium"])

    def test_should_buy_premium_low_vix(self):
        """Test premium buying signal in low VIX regime"""
        # Low VIX + backwardation
        self.monitor.get_current_vix.return_value = 11.0
        self.monitor.get_volatility_regime.return_value = VolatilityRegime.EXTREME_LOW
        self.monitor.get_vix_percentile.return_value = 15.0
        self.monitor.get_term_structure_state.return_value = TermStructureState.BACKWARDATION

        result = self.signals.should_buy_premium()

        self.assertTrue(result["should_buy_premium"])
        self.assertEqual(result["confidence"], "HIGH")
        self.assertIn("recommended_strategies", result)

    def test_should_buy_premium_high_vix(self):
        """Test premium buying signal in high VIX regime"""
        # High VIX scenario (should NOT buy)
        self.monitor.get_current_vix.return_value = 28.0
        self.monitor.get_volatility_regime.return_value = VolatilityRegime.HIGH
        self.monitor.get_vix_percentile.return_value = 80.0
        self.monitor.get_term_structure_state.return_value = TermStructureState.CONTANGO

        result = self.signals.should_buy_premium()

        self.assertFalse(result["should_buy_premium"])

    def test_get_position_size_multiplier_extreme_low(self):
        """Test position sizing in extreme low VIX"""
        self.monitor.get_volatility_regime.return_value = VolatilityRegime.EXTREME_LOW
        self.monitor.get_vix_percentile.return_value = 5.0

        result = self.signals.get_position_size_multiplier()

        self.assertGreater(result["multiplier"], 1.0)  # Larger positions in low VIX
        self.assertEqual(result["regime"], "extreme_low")

    def test_get_position_size_multiplier_extreme_high(self):
        """Test position sizing in extreme high VIX"""
        self.monitor.get_volatility_regime.return_value = VolatilityRegime.EXTREME
        self.monitor.get_vix_percentile.return_value = 95.0

        result = self.signals.get_position_size_multiplier()

        self.assertLess(result["multiplier"], 0.5)  # Smaller positions in high VIX
        self.assertEqual(result["regime"], "extreme")

    def test_get_position_size_multiplier_normal(self):
        """Test position sizing in normal VIX"""
        self.monitor.get_volatility_regime.return_value = VolatilityRegime.NORMAL
        self.monitor.get_vix_percentile.return_value = 50.0

        result = self.signals.get_position_size_multiplier()

        self.assertAlmostEqual(result["multiplier"], 1.0, places=1)  # Standard size
        self.assertEqual(result["regime"], "normal")

    def test_get_strategy_recommendation_sell_premium(self):
        """Test comprehensive strategy recommendation for selling premium"""
        # High VIX scenario
        self.monitor.get_current_vix.return_value = 28.0
        self.monitor.get_volatility_regime.return_value = VolatilityRegime.HIGH
        self.monitor.get_vix_percentile.return_value = 80.0
        self.monitor.get_term_structure_state.return_value = TermStructureState.CONTANGO
        self.monitor.calculate_mean_reversion_probability.return_value = 0.80

        # Mock the should_sell_premium and should_buy_premium calls
        with (
            patch.object(self.signals, "should_sell_premium") as mock_sell,
            patch.object(self.signals, "should_buy_premium") as mock_buy,
            patch.object(self.signals, "get_position_size_multiplier") as mock_size,
        ):
            mock_sell.return_value = {
                "should_sell_premium": True,
                "recommended_strategies": ["Iron Condor", "Credit Spreads"],
            }
            mock_buy.return_value = {"should_buy_premium": False, "recommended_strategies": []}
            mock_size.return_value = {"multiplier": 0.5}

            recommendation = self.signals.get_strategy_recommendation()

            self.assertEqual(recommendation["primary_action"], "SELL_PREMIUM")
            self.assertIn("recommended_strategies", recommendation)
            self.assertIn("entry_rules", recommendation)
            self.assertIn("exit_rules", recommendation)
            self.assertEqual(recommendation["risk_level"], "HIGH")

    def test_get_strategy_recommendation_buy_premium(self):
        """Test comprehensive strategy recommendation for buying premium"""
        # Low VIX scenario
        self.monitor.get_current_vix.return_value = 11.0
        self.monitor.get_volatility_regime.return_value = VolatilityRegime.EXTREME_LOW
        self.monitor.get_vix_percentile.return_value = 10.0
        self.monitor.get_term_structure_state.return_value = TermStructureState.BACKWARDATION
        self.monitor.calculate_mean_reversion_probability.return_value = 0.35

        with (
            patch.object(self.signals, "should_sell_premium") as mock_sell,
            patch.object(self.signals, "should_buy_premium") as mock_buy,
            patch.object(self.signals, "get_position_size_multiplier") as mock_size,
        ):
            mock_sell.return_value = {"should_sell_premium": False, "recommended_strategies": []}
            mock_buy.return_value = {
                "should_buy_premium": True,
                "recommended_strategies": ["Long Straddles", "Debit Spreads"],
            }
            mock_size.return_value = {"multiplier": 1.5}

            recommendation = self.signals.get_strategy_recommendation()

            self.assertEqual(recommendation["primary_action"], "BUY_PREMIUM")
            self.assertGreater(len(recommendation["recommended_strategies"]), 0)
            self.assertEqual(recommendation["risk_level"], "LOW")

    def test_get_strategy_recommendation_wait(self):
        """Test strategy recommendation when no clear signal"""
        # Neutral scenario
        self.monitor.get_current_vix.return_value = 17.0
        self.monitor.get_volatility_regime.return_value = VolatilityRegime.NORMAL
        self.monitor.get_vix_percentile.return_value = 50.0
        self.monitor.get_term_structure_state.return_value = TermStructureState.FLAT
        self.monitor.calculate_mean_reversion_probability.return_value = 0.5

        with (
            patch.object(self.signals, "should_sell_premium") as mock_sell,
            patch.object(self.signals, "should_buy_premium") as mock_buy,
            patch.object(self.signals, "get_position_size_multiplier") as mock_size,
        ):
            mock_sell.return_value = {"should_sell_premium": False, "recommended_strategies": []}
            mock_buy.return_value = {"should_buy_premium": False, "recommended_strategies": []}
            mock_size.return_value = {"multiplier": 1.0}

            recommendation = self.signals.get_strategy_recommendation()

            self.assertEqual(recommendation["primary_action"], "WAIT")


class TestIntegration(unittest.TestCase):
    """Integration tests for VIX monitoring system"""

    @patch("src.options.vix_monitor.yf.Ticker")
    def test_full_workflow(self, mock_ticker):
        """Test complete workflow from VIX fetch to signal generation"""
        import pandas as pd

        # Mock all Yahoo Finance calls
        call_counter = {"count": 0}

        def mock_ticker_side_effect(symbol):
            mock = Mock()
            if symbol == "^VIX":
                if call_counter["count"] % 3 == 0:
                    mock.history.return_value = pd.DataFrame({"Close": [25.0]})  # High VIX
                else:
                    dates = pd.date_range(end=datetime.now(), periods=252, freq="D")
                    mock.history.return_value = pd.DataFrame(
                        {"Close": np.full(252, 16.0)}, index=dates
                    )
                call_counter["count"] += 1
            elif symbol == "^VXV":
                mock.history.return_value = pd.DataFrame({"Close": [27.0]})  # Contango
            elif symbol == "^VVIX":
                mock.history.return_value = pd.DataFrame({"Close": [100.0]})
            return mock

        mock_ticker.side_effect = mock_ticker_side_effect

        # Create monitor with temp file
        with tempfile.TemporaryDirectory() as temp_dir:
            vix_file = os.path.join(temp_dir, "vix_history.json")

            with patch.object(VIXMonitor, "VIX_HISTORY_FILE", vix_file):
                monitor = VIXMonitor(use_alpaca=False)
                signals = VIXSignals(monitor)

                # 1. Get current VIX
                vix = monitor.get_current_vix()
                self.assertEqual(vix, 25.0)

                # 2. Get regime
                regime = monitor.get_volatility_regime()
                self.assertEqual(regime, VolatilityRegime.HIGH)

                # 3. Get signals
                sell_signal = signals.should_sell_premium()
                self.assertIn("should_sell_premium", sell_signal)

                # 4. Get recommendation
                recommendation = signals.get_strategy_recommendation()
                self.assertIn("primary_action", recommendation)
                self.assertIn("recommended_strategies", recommendation)

                # 5. Export state
                state = monitor.export_state()
                self.assertIn("current_vix", state)
                self.assertIn("volatility_regime", state)


if __name__ == "__main__":
    unittest.main()
