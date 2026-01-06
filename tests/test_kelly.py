"""Tests for Kelly Criterion position sizing."""

import pytest
from src.risk.kelly import kelly_fraction


class TestKellyFraction:
    """Tests for kelly_fraction function."""

    def test_positive_edge_returns_fraction(self):
        """Test that positive edge returns appropriate Kelly fraction."""
        # 60% win rate, 1:1 payoff -> f* = (0.6 * 1 - 0.4) / 1 = 0.2
        result = kelly_fraction(0.6, 1.0)
        assert result == pytest.approx(0.2, abs=0.001)

    def test_negative_edge_returns_zero(self):
        """Test that negative edge returns zero (no bet)."""
        # 40% win rate, 1:1 payoff -> f* = (0.4 * 1 - 0.6) / 1 = -0.2 -> 0
        result = kelly_fraction(0.4, 1.0)
        assert result == 0.0

    def test_breakeven_returns_zero(self):
        """Test that breakeven returns zero."""
        # 50% win rate, 1:1 payoff -> f* = (0.5 * 1 - 0.5) / 1 = 0
        result = kelly_fraction(0.5, 1.0)
        assert result == 0.0

    def test_zero_win_probability_returns_zero(self):
        """Test that 0% win probability returns zero."""
        result = kelly_fraction(0.0, 2.0)
        assert result == 0.0

    def test_zero_payoff_returns_zero(self):
        """Test that zero payoff ratio returns zero."""
        result = kelly_fraction(0.6, 0.0)
        assert result == 0.0

    def test_negative_payoff_returns_zero(self):
        """Test that negative payoff is handled (clamped to 0)."""
        result = kelly_fraction(0.6, -1.0)
        assert result == 0.0

    def test_probability_clamped_to_valid_range(self):
        """Test that probability > 1 is clamped to 1."""
        # 100% win rate, 2:1 payoff -> f* = (1.0 * 2 - 0) / 2 = 1.0
        result = kelly_fraction(1.5, 2.0)  # Invalid >1 probability
        assert result == pytest.approx(1.0, abs=0.001)

    def test_negative_probability_clamped_to_zero(self):
        """Test that negative probability is clamped to 0."""
        result = kelly_fraction(-0.5, 2.0)
        assert result == 0.0

    def test_high_payoff_ratio(self):
        """Test with high payoff ratio (options-like)."""
        # 30% win rate, 5:1 payoff -> f* = (0.3 * 5 - 0.7) / 5 = 0.16
        result = kelly_fraction(0.3, 5.0)
        assert result == pytest.approx(0.16, abs=0.001)

    def test_typical_options_scenario(self):
        """Test typical cash-secured put scenario."""
        # CSP: 80% win rate, 0.25:1 payoff (win $25 or lose $100)
        # f* = (0.8 * 0.25 - 0.2) / 0.25 = 0
        result = kelly_fraction(0.8, 0.25)
        assert result == 0.0  # Negative edge despite high win rate!

    def test_favorable_options_scenario(self):
        """Test favorable options scenario."""
        # Better odds: 80% win rate, 0.5:1 payoff
        # f* = (0.8 * 0.5 - 0.2) / 0.5 = 0.4
        result = kelly_fraction(0.8, 0.5)
        assert result == pytest.approx(0.4, abs=0.001)
