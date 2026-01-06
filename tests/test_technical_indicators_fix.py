#!/usr/bin/env python3
"""
Tests for technical_indicators.py - Series formatting fixes.

Created: Jan 6, 2026
Coverage: Tests to verify technical indicators return floats, not Series
"""

import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestTechnicalScoreCalculation:
    """Test technical score doesn't produce Series formatting errors."""

    def test_calculate_technical_score_returns_float(self):
        """Technical score calculation should return float, not Series."""
        pytest.importorskip("pandas")
        import pandas as pd
        from src.utils.technical_indicators import calculate_technical_score

        # Create sample OHLCV data with uppercase column names (yfinance style)
        data = pd.DataFrame(
            {
                "Open": [100 + i for i in range(50)],
                "High": [101 + i for i in range(50)],
                "Low": [99 + i for i in range(50)],
                "Close": [100.5 + i for i in range(50)],
                "Volume": [1000000 + i * 10000 for i in range(50)],
            }
        )

        try:
            # Function returns (score, indicators_dict) tuple
            score, indicators = calculate_technical_score(data, symbol="SPY")
            # Should be able to format without error
            _formatted = f"{score:.2f}"  # noqa: F841
            assert isinstance(score, (int, float)), f"Score should be numeric, got {type(score)}"
            assert isinstance(indicators, dict), (
                f"Indicators should be dict, got {type(indicators)}"
            )
        except TypeError as e:
            if "Series" in str(e):
                pytest.fail(f"Technical score returned Series instead of float: {e}")
            raise

    def test_technical_score_is_formattable(self):
        """Technical score should be directly usable in f-string formatting."""
        pytest.importorskip("pandas")
        import pandas as pd
        from src.utils.technical_indicators import calculate_technical_score

        data = pd.DataFrame(
            {
                "Open": [100 + i for i in range(50)],
                "High": [101 + i for i in range(50)],
                "Low": [99 + i for i in range(50)],
                "Close": [100.5 + i for i in range(50)],
                "Volume": [1000000 + i * 10000 for i in range(50)],
            }
        )

        try:
            # Function returns (score, indicators_dict) tuple
            score, _ = calculate_technical_score(data, symbol="SPY")
            # This should NOT raise "unsupported format string passed to Series.__format__"
            message = f"Technical score: {score:.2f}"
            assert "Technical score:" in message
        except TypeError as e:
            pytest.fail(f"Failed to format technical score: {e}")


class TestMACDCalculation:
    """Test MACD calculation in technical_indicators module."""

    def test_calculate_macd_returns_tuple(self):
        """calculate_macd should return (macd, signal, histogram) tuple."""
        pytest.importorskip("pandas")
        import pandas as pd
        from src.utils.technical_indicators import calculate_macd

        prices = pd.Series([100 + i * 0.5 for i in range(50)])
        result = calculate_macd(prices)

        assert isinstance(result, tuple), f"Should return tuple, got {type(result)}"
        assert len(result) == 3, f"Should return 3 values, got {len(result)}"

    def test_macd_values_are_floats(self):
        """MACD values should be floats, not Series."""
        pytest.importorskip("pandas")
        import pandas as pd
        from src.utils.technical_indicators import calculate_macd

        prices = pd.Series([100 + i * 0.5 for i in range(50)])
        macd, signal, histogram = calculate_macd(prices)

        assert isinstance(macd, (int, float)), f"MACD should be float, got {type(macd)}"
        assert isinstance(signal, (int, float)), f"Signal should be float, got {type(signal)}"
        assert isinstance(histogram, (int, float)), (
            f"Histogram should be float, got {type(histogram)}"
        )

    def test_macd_histogram_equals_difference(self):
        """Histogram should equal MACD minus signal."""
        pytest.importorskip("pandas")
        import pandas as pd
        from src.utils.technical_indicators import calculate_macd

        prices = pd.Series([100 + i * 0.5 for i in range(50)])
        macd, signal, histogram = calculate_macd(prices)

        expected = macd - signal
        assert abs(histogram - expected) < 0.0001, (
            f"Histogram {histogram} != MACD {macd} - Signal {signal}"
        )

    def test_macd_formattable(self):
        """MACD values should be formattable in f-strings."""
        pytest.importorskip("pandas")
        import pandas as pd
        from src.utils.technical_indicators import calculate_macd

        prices = pd.Series([100 + i * 0.5 for i in range(50)])
        macd, signal, histogram = calculate_macd(prices)

        try:
            msg = f"MACD: {macd:.4f}, Signal: {signal:.4f}, Histogram: {histogram:.4f}"
            assert "MACD:" in msg
        except TypeError as e:
            pytest.fail(f"MACD values not formattable: {e}")


class TestRSICalculation:
    """Test RSI calculation."""

    def test_calculate_rsi_returns_float(self):
        """RSI should return float value."""
        pytest.importorskip("pandas")
        import pandas as pd
        from src.utils.technical_indicators import calculate_rsi

        prices = pd.Series([100 + i * 0.5 for i in range(50)])
        rsi = calculate_rsi(prices)

        assert isinstance(rsi, (int, float)), f"RSI should be float, got {type(rsi)}"

    def test_rsi_in_valid_range(self):
        """RSI should be between 0 and 100."""
        pytest.importorskip("pandas")
        import pandas as pd
        from src.utils.technical_indicators import calculate_rsi

        prices = pd.Series([100 + i * 0.5 for i in range(50)])
        rsi = calculate_rsi(prices)

        assert 0 <= rsi <= 100, f"RSI should be 0-100, got {rsi}"

    def test_rsi_high_in_uptrend(self):
        """RSI should be high (>=50) in strong uptrend."""
        pytest.importorskip("pandas")
        import pandas as pd
        from src.utils.technical_indicators import calculate_rsi

        # Strong uptrend
        prices = pd.Series([100 + i * 5 for i in range(30)])
        rsi = calculate_rsi(prices)

        assert rsi >= 50, f"RSI should be >=50 in uptrend, got {rsi}"

    def test_rsi_low_in_downtrend(self):
        """RSI should be low (<50) in strong downtrend."""
        pytest.importorskip("pandas")
        import pandas as pd
        from src.utils.technical_indicators import calculate_rsi

        # Strong downtrend
        prices = pd.Series([200 - i * 5 for i in range(30)])
        rsi = calculate_rsi(prices)

        assert rsi < 50, f"RSI should be <50 in downtrend, got {rsi}"

    def test_rsi_formattable(self):
        """RSI should be formattable in f-strings."""
        pytest.importorskip("pandas")
        import pandas as pd
        from src.utils.technical_indicators import calculate_rsi

        prices = pd.Series([100 + i * 0.5 for i in range(50)])
        rsi = calculate_rsi(prices)

        try:
            msg = f"RSI: {rsi:.2f}"
            assert "RSI:" in msg
        except TypeError as e:
            pytest.fail(f"RSI not formattable: {e}")


class TestATRCalculation:
    """Test ATR calculation."""

    def test_calculate_atr_returns_float(self):
        """ATR should return float value."""
        pytest.importorskip("pandas")
        import pandas as pd
        from src.utils.technical_indicators import calculate_atr

        data = pd.DataFrame(
            {
                "high": [101 + i for i in range(30)],
                "low": [99 + i for i in range(30)],
                "close": [100 + i for i in range(30)],
            }
        )
        atr = calculate_atr(data)

        assert isinstance(atr, (int, float)), f"ATR should be float, got {type(atr)}"

    def test_atr_positive(self):
        """ATR should always be positive."""
        pytest.importorskip("pandas")
        import pandas as pd
        from src.utils.technical_indicators import calculate_atr

        data = pd.DataFrame(
            {
                "high": [101 + i for i in range(30)],
                "low": [99 + i for i in range(30)],
                "close": [100 + i for i in range(30)],
            }
        )
        atr = calculate_atr(data)

        assert atr >= 0, f"ATR should be positive, got {atr}"


class TestVolumeRatio:
    """Test volume ratio calculation."""

    def test_volume_ratio_returns_float(self):
        """Volume ratio should return float."""
        pytest.importorskip("pandas")
        import pandas as pd
        from src.utils.technical_indicators import calculate_volume_ratio

        # Function expects DataFrame with 'Volume' column
        hist = pd.DataFrame({"Volume": [1000000 + i * 10000 for i in range(30)]})
        ratio = calculate_volume_ratio(hist)

        assert isinstance(ratio, (int, float)), f"Volume ratio should be float, got {type(ratio)}"

    def test_volume_ratio_positive(self):
        """Volume ratio should be positive."""
        pytest.importorskip("pandas")
        import pandas as pd
        from src.utils.technical_indicators import calculate_volume_ratio

        # Function expects DataFrame with 'Volume' column
        hist = pd.DataFrame({"Volume": [1000000 + i * 10000 for i in range(30)]})
        ratio = calculate_volume_ratio(hist)

        assert ratio > 0, f"Volume ratio should be positive, got {ratio}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
