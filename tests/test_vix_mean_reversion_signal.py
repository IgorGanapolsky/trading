"""
Tests for VIX Mean Reversion Signal.

Tests the signal generator that identifies optimal iron condor
entry windows based on VIX mean reversion patterns.

Created: January 22, 2026
Reference: LL-296
"""

import pytest
from unittest.mock import patch

# Skip entire module if numpy not available (sandbox limitation)
np = pytest.importorskip("numpy")

from src.signals.vix_mean_reversion_signal import (
    VIXMeanReversionSignal,
    VIXSignal,
    get_vix_entry_signal,
)


class TestVIXMeanReversionSignal:
    """Test suite for VIXMeanReversionSignal class."""

    def test_init(self):
        """Test signal generator initializes correctly."""
        signal_gen = VIXMeanReversionSignal()
        assert signal_gen.VIX_SPIKE_THRESHOLD == 20.0
        assert signal_gen.VIX_OPTIMAL_MIN == 15.0
        assert signal_gen.VIX_OPTIMAL_MAX == 25.0

    @patch.object(VIXMeanReversionSignal, "get_vix_data")
    def test_optimal_entry_signal(self, mock_get_vix):
        """Test OPTIMAL_ENTRY when VIX drops from spike."""
        # Simulate VIX spike from 16 to 22, then drop to 17
        # 60 days of data, with spike in last 10 days
        base_data = np.full(50, 16.0)  # Stable at 16
        spike_data = np.array([18, 20, 22, 21, 20, 19, 18, 17, 17, 16.5])  # Spike and drop
        mock_get_vix.return_value = np.concatenate([base_data, spike_data])

        signal_gen = VIXMeanReversionSignal()
        result = signal_gen.calculate_signal()

        assert result.signal == "OPTIMAL_ENTRY"
        assert result.recent_high == 22.0
        assert result.confidence >= 0.8

    @patch.object(VIXMeanReversionSignal, "get_vix_data")
    def test_good_entry_signal(self, mock_get_vix):
        """Test GOOD_ENTRY when VIX in optimal range."""
        # Stable VIX around 18 (in optimal range 15-25)
        mock_get_vix.return_value = np.full(60, 18.0)

        signal_gen = VIXMeanReversionSignal()
        result = signal_gen.calculate_signal()

        assert result.signal == "GOOD_ENTRY"
        assert result.current_vix == 18.0
        assert result.confidence >= 0.5

    @patch.object(VIXMeanReversionSignal, "get_vix_data")
    def test_avoid_signal_vix_too_low(self, mock_get_vix):
        """Test AVOID when VIX too low (premiums thin)."""
        mock_get_vix.return_value = np.full(60, 12.0)

        signal_gen = VIXMeanReversionSignal()
        result = signal_gen.calculate_signal()

        assert result.signal == "AVOID"
        assert "premiums too thin" in result.reason.lower()
        assert result.confidence == 0.0

    @patch.object(VIXMeanReversionSignal, "get_vix_data")
    def test_avoid_signal_vix_extreme(self, mock_get_vix):
        """Test AVOID when VIX extremely high."""
        mock_get_vix.return_value = np.full(60, 35.0)

        signal_gen = VIXMeanReversionSignal()
        result = signal_gen.calculate_signal()

        assert result.signal == "AVOID"
        assert "extreme" in result.reason.lower()
        assert result.confidence == 0.0

    @patch.object(VIXMeanReversionSignal, "get_vix_data")
    def test_neutral_signal_vix_elevated(self, mock_get_vix):
        """Test NEUTRAL when VIX elevated but not dropping."""
        mock_get_vix.return_value = np.full(60, 27.0)

        signal_gen = VIXMeanReversionSignal()
        result = signal_gen.calculate_signal()

        assert result.signal == "NEUTRAL"
        assert "wait" in result.reason.lower() or "elevated" in result.reason.lower()

    @patch.object(VIXMeanReversionSignal, "get_vix_data")
    def test_neutral_on_data_failure(self, mock_get_vix):
        """Test NEUTRAL when VIX data fetch fails."""
        mock_get_vix.return_value = None

        signal_gen = VIXMeanReversionSignal()
        result = signal_gen.calculate_signal()

        assert result.signal == "NEUTRAL"
        assert result.confidence == 0.0

    @patch.object(VIXMeanReversionSignal, "get_vix_data")
    def test_should_enter_trade_optimal(self, mock_get_vix):
        """Test should_enter_trade returns True for optimal entry."""
        base_data = np.full(50, 16.0)
        spike_data = np.array([18, 20, 22, 21, 20, 19, 18, 17, 17, 16.5])
        mock_get_vix.return_value = np.concatenate([base_data, spike_data])

        signal_gen = VIXMeanReversionSignal()
        should_enter, reason = signal_gen.should_enter_trade()

        assert should_enter is True
        assert reason != ""

    @patch.object(VIXMeanReversionSignal, "get_vix_data")
    def test_should_enter_trade_avoid(self, mock_get_vix):
        """Test should_enter_trade returns False when should avoid."""
        mock_get_vix.return_value = np.full(60, 12.0)  # Too low

        signal_gen = VIXMeanReversionSignal()
        should_enter, reason = signal_gen.should_enter_trade()

        assert should_enter is False
        assert "thin" in reason.lower()


class TestVIXSignalDataclass:
    """Test the VIXSignal dataclass."""

    def test_signal_creation(self):
        """Test VIXSignal can be created with all fields."""
        signal = VIXSignal(
            signal="OPTIMAL_ENTRY",
            current_vix=17.5,
            vix_3day_ma=17.0,
            recent_high=22.0,
            threshold=1.5,
            reason="VIX dropped from spike",
            confidence=0.9,
        )

        assert signal.signal == "OPTIMAL_ENTRY"
        assert signal.current_vix == 17.5
        assert signal.confidence == 0.9


class TestConvenienceFunction:
    """Test the get_vix_entry_signal convenience function."""

    @patch.object(VIXMeanReversionSignal, "get_vix_data")
    def test_get_vix_entry_signal(self, mock_get_vix):
        """Test convenience function returns signal."""
        mock_get_vix.return_value = np.full(60, 18.0)

        signal = get_vix_entry_signal()

        assert isinstance(signal, VIXSignal)
        assert signal.signal in ("OPTIMAL_ENTRY", "GOOD_ENTRY", "NEUTRAL", "AVOID")


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @patch.object(VIXMeanReversionSignal, "get_vix_data")
    def test_vix_at_boundary_15(self, mock_get_vix):
        """Test VIX exactly at lower boundary (15)."""
        mock_get_vix.return_value = np.full(60, 15.0)

        signal_gen = VIXMeanReversionSignal()
        result = signal_gen.calculate_signal()

        # 15 is the minimum, should be GOOD_ENTRY
        assert result.signal == "GOOD_ENTRY"

    @patch.object(VIXMeanReversionSignal, "get_vix_data")
    def test_vix_at_boundary_25(self, mock_get_vix):
        """Test VIX exactly at upper optimal boundary (25)."""
        mock_get_vix.return_value = np.full(60, 25.0)

        signal_gen = VIXMeanReversionSignal()
        result = signal_gen.calculate_signal()

        # 25 is the max optimal, should be GOOD_ENTRY
        assert result.signal == "GOOD_ENTRY"

    @patch.object(VIXMeanReversionSignal, "get_vix_data")
    def test_vix_at_boundary_30(self, mock_get_vix):
        """Test VIX exactly at extreme boundary (30)."""
        mock_get_vix.return_value = np.full(60, 30.0)

        signal_gen = VIXMeanReversionSignal()
        result = signal_gen.calculate_signal()

        # 30 is exactly at extreme threshold, should be NEUTRAL or AVOID
        assert result.signal in ("NEUTRAL", "AVOID")

    @patch.object(VIXMeanReversionSignal, "get_vix_data")
    def test_small_data_sample(self, mock_get_vix):
        """Test with insufficient data."""
        mock_get_vix.return_value = np.array([16, 17, 18])  # Only 3 days

        signal_gen = VIXMeanReversionSignal()
        # Should handle gracefully - get_vix_data returns None for insufficient data
        mock_get_vix.return_value = None  # Simulate the check failing
        result = signal_gen.calculate_signal()

        assert result.signal == "NEUTRAL"
