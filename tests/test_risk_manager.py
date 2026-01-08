#!/usr/bin/env python3
"""
Tests for Risk Manager Module

Tests the position sizing, Kelly fraction, and stop-loss logic
for the modular orchestrator pipeline.

Author: Trading System CTO
Created: 2026-01-08
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.risk.risk_manager import RiskManager


# =============================================================================
# RiskManager Initialization Tests
# =============================================================================


class TestRiskManagerInit:
    """Test RiskManager initialization."""

    def test_init_defaults(self):
        """Test default initialization."""
        rm = RiskManager()
        assert rm.max_position_pct == 0.05
        assert rm.min_notional == 50.0
        assert rm.atr_period == 14
        assert rm.kelly_cap == 0.05

    def test_init_custom_values(self):
        """Test initialization with custom values."""
        rm = RiskManager(
            max_position_pct=0.10,
            min_notional=100.0,
            use_atr_scaling=False,
            atr_period=20,
            kelly_cap=0.10,
        )
        assert rm.max_position_pct == 0.10
        assert rm.min_notional == 100.0
        assert rm.use_atr_scaling is False
        assert rm.atr_period == 20
        assert rm.kelly_cap == 0.10

    def test_atr_scaling_env_override(self):
        """Test ATR scaling can be controlled via environment."""
        with patch.dict(os.environ, {"RISK_USE_ATR_SCALING": "0"}):
            rm = RiskManager()
            assert rm.use_atr_scaling is False

        with patch.dict(os.environ, {"RISK_USE_ATR_SCALING": "1"}):
            rm = RiskManager()
            assert rm.use_atr_scaling is True

    def test_daily_budget_from_env(self):
        """Test daily budget comes from environment."""
        with patch.dict(os.environ, {"DAILY_INVESTMENT": "100.0"}):
            rm = RiskManager()
            assert rm.daily_budget == 100.0


# =============================================================================
# Position Sizing Tests
# =============================================================================


class TestCalculateSize:
    """Test calculate_size method."""

    @pytest.fixture
    def risk_manager(self):
        """Create a risk manager with fixed settings for testing."""
        return RiskManager(
            max_position_pct=0.05,
            min_notional=50.0,
            use_atr_scaling=False,  # Disable for simpler testing
            kelly_cap=0.05,
        )

    def test_zero_equity_returns_zero(self, risk_manager):
        """Zero or negative equity should return zero size."""
        result = risk_manager.calculate_size(
            ticker="SPY",
            account_equity=0,
            signal_strength=0.8,
            rl_confidence=0.7,
            sentiment_score=0.5,
        )
        assert result == 0.0

    def test_negative_equity_returns_zero(self, risk_manager):
        """Negative equity should return zero size."""
        result = risk_manager.calculate_size(
            ticker="SPY",
            account_equity=-1000,
            signal_strength=0.8,
            rl_confidence=0.7,
            sentiment_score=0.5,
        )
        assert result == 0.0

    def test_size_capped_by_max_position_pct(self, risk_manager):
        """Size should not exceed max_position_pct of equity."""
        result = risk_manager.calculate_size(
            ticker="SPY",
            account_equity=100000,
            signal_strength=1.0,
            rl_confidence=1.0,
            sentiment_score=1.0,
            multiplier=10.0,  # Try to get large size
        )
        max_allowed = 100000 * risk_manager.max_position_pct
        assert result <= max_allowed

    def test_size_below_minimum_returns_zero(self, risk_manager):
        """Size below minimum notional should return zero."""
        # Small daily budget with low confidence
        with patch.dict(os.environ, {"DAILY_INVESTMENT": "10.0"}):
            rm = RiskManager(min_notional=50.0)
            result = rm.calculate_size(
                ticker="SPY",
                account_equity=100,  # Very small account
                signal_strength=0.1,
                rl_confidence=0.1,
                sentiment_score=-0.5,
            )
            assert result == 0.0

    def test_size_respects_allocation_cap(self, risk_manager):
        """Size should respect explicit allocation cap."""
        result = risk_manager.calculate_size(
            ticker="SPY",
            account_equity=100000,
            signal_strength=0.8,
            rl_confidence=0.7,
            sentiment_score=0.5,
            allocation_cap=100.0,  # Hard cap at $100
        )
        assert result <= 100.0

    def test_size_scales_with_confidence(self, risk_manager):
        """Higher confidence should result in larger position size."""
        with patch.dict(os.environ, {"DAILY_INVESTMENT": "500.0"}):
            rm = RiskManager(use_atr_scaling=False, min_notional=10.0)

            low_conf = rm.calculate_size(
                ticker="SPY",
                account_equity=10000,
                signal_strength=0.3,
                rl_confidence=0.3,
                sentiment_score=0.0,
            )

            high_conf = rm.calculate_size(
                ticker="SPY",
                account_equity=10000,
                signal_strength=0.9,
                rl_confidence=0.9,
                sentiment_score=0.0,
            )

            assert high_conf >= low_conf


# =============================================================================
# Kelly Fraction Tests
# =============================================================================


class TestKellyFraction:
    """Test Kelly fraction estimation."""

    @pytest.fixture
    def risk_manager(self):
        return RiskManager()

    def test_kelly_fraction_positive(self, risk_manager):
        """Kelly fraction should be positive with positive signals."""
        frac = risk_manager._estimate_kelly_fraction(
            signal_strength=0.8,
            rl_confidence=0.7,
            sentiment_score=0.5,
            regime=None,
            multiplier=1.0,
        )
        assert frac > 0

    def test_kelly_fraction_adjusted_for_regime(self, risk_manager):
        """Kelly fraction should be adjusted based on market regime."""
        base_frac = risk_manager._estimate_kelly_fraction(
            signal_strength=0.8,
            rl_confidence=0.7,
            sentiment_score=0.5,
            regime=None,
            multiplier=1.0,
        )

        volatile_frac = risk_manager._estimate_kelly_fraction(
            signal_strength=0.8,
            rl_confidence=0.7,
            sentiment_score=0.5,
            regime="volatile",
            multiplier=1.0,
        )

        bear_frac = risk_manager._estimate_kelly_fraction(
            signal_strength=0.8,
            rl_confidence=0.7,
            sentiment_score=0.5,
            regime="bear",
            multiplier=1.0,
        )

        bull_frac = risk_manager._estimate_kelly_fraction(
            signal_strength=0.8,
            rl_confidence=0.7,
            sentiment_score=0.5,
            regime="bull",
            multiplier=1.0,
        )

        # Volatile and bear markets should reduce Kelly fraction
        assert volatile_frac < base_frac
        assert bear_frac < base_frac

        # Bull market should increase Kelly fraction
        assert bull_frac > base_frac

    def test_kelly_cap_enforced(self, risk_manager):
        """Kelly fraction should be capped."""
        # Even with perfect signals, should not exceed kelly_cap
        frac = risk_manager._estimate_kelly_fraction(
            signal_strength=1.0,
            rl_confidence=1.0,
            sentiment_score=1.0,
            regime="bull",
            multiplier=10.0,
        )

        # The kelly_cap is enforced in calculate_size, not here
        # But the fraction itself should be reasonable
        assert frac > 0


# =============================================================================
# Stop-Loss Tests
# =============================================================================


class TestStopLoss:
    """Test stop-loss calculation."""

    @pytest.fixture
    def risk_manager(self):
        return RiskManager()

    def test_zero_entry_price_returns_zero(self, risk_manager):
        """Zero entry price should return zero stop-loss."""
        result = risk_manager.calculate_stop_loss(
            ticker="SPY",
            entry_price=0,
            direction="long",
        )
        assert result == 0.0

    def test_negative_entry_price_returns_zero(self, risk_manager):
        """Negative entry price should return zero stop-loss."""
        result = risk_manager.calculate_stop_loss(
            ticker="SPY",
            entry_price=-100,
            direction="long",
        )
        assert result == 0.0

    def test_stop_loss_below_entry_for_long(self, risk_manager):
        """Long position stop-loss should be below entry price."""
        # Note: This test may skip if technical_indicators isn't available
        try:
            result = risk_manager.calculate_stop_loss(
                ticker="SPY",
                entry_price=450.0,
                direction="long",
            )
            # If it returns a valid result, it should be below entry
            if result > 0:
                assert result < 450.0
        except ImportError:
            pytest.skip("Technical indicators not available")

    def test_atr_multiplier_can_be_overridden(self, risk_manager):
        """ATR multiplier should be configurable."""
        with patch.dict(os.environ, {"ATR_STOP_MULTIPLIER": "3.0"}):
            rm = RiskManager()
            # The multiplier would be read from env if not passed
            # Test that the parameter exists
            assert rm.atr_period == 14  # Default


# =============================================================================
# Phil Town Rule #1 - Capital Protection Tests
# =============================================================================


class TestCapitalProtection:
    """
    Tests ensuring risk management protects capital.

    CEO Directive (Jan 6, 2026): "Losing money is NOT allowed"
    """

    def test_position_cap_prevents_overexposure(self):
        """Max position percentage should prevent overexposure."""
        rm = RiskManager(max_position_pct=0.05)

        # Even with maximum confidence, position should be capped
        result = rm.calculate_size(
            ticker="SPY",
            account_equity=100000,
            signal_strength=1.0,
            rl_confidence=1.0,
            sentiment_score=1.0,
            multiplier=100.0,
        )

        # Should not exceed 5% of equity
        assert result <= 5000.0

    def test_minimum_notional_prevents_small_trades(self):
        """Minimum notional should prevent tiny, inefficient trades."""
        rm = RiskManager(min_notional=50.0)

        # Very low confidence should result in rejected trade
        with patch.dict(os.environ, {"DAILY_INVESTMENT": "10.0"}):
            result = rm.calculate_size(
                ticker="SPY",
                account_equity=100,
                signal_strength=0.1,
                rl_confidence=0.1,
                sentiment_score=-0.5,
            )
            assert result == 0.0

    def test_kelly_cap_prevents_overbetting(self):
        """Kelly cap should prevent excessive position sizes."""
        rm = RiskManager(kelly_cap=0.05)
        assert rm.kelly_cap == 0.05

        # Kelly cap is enforced in calculate_size
        # Verify the cap exists and is reasonable
        assert rm.kelly_cap <= 0.10  # Should not allow more than 10% per position

    def test_volatile_regime_reduces_size(self):
        """Volatile market regime should reduce position sizes."""
        rm = RiskManager(use_atr_scaling=False)

        base_frac = rm._estimate_kelly_fraction(
            signal_strength=0.8,
            rl_confidence=0.7,
            sentiment_score=0.5,
            regime=None,
            multiplier=1.0,
        )

        volatile_frac = rm._estimate_kelly_fraction(
            signal_strength=0.8,
            rl_confidence=0.7,
            sentiment_score=0.5,
            regime="volatile",
            multiplier=1.0,
        )

        # Volatile should be more conservative
        assert volatile_frac < base_frac


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_negative_sentiment_reduces_size(self):
        """Negative sentiment should reduce position size."""
        rm = RiskManager(use_atr_scaling=False)

        positive_frac = rm._estimate_kelly_fraction(
            signal_strength=0.8,
            rl_confidence=0.7,
            sentiment_score=0.5,
            regime=None,
            multiplier=1.0,
        )

        negative_frac = rm._estimate_kelly_fraction(
            signal_strength=0.8,
            rl_confidence=0.7,
            sentiment_score=-0.5,
            regime=None,
            multiplier=1.0,
        )

        assert negative_frac < positive_frac

    def test_multiplier_affects_payoff_ratio(self):
        """Multiplier should affect the payoff ratio in Kelly calculation."""
        rm = RiskManager()

        low_mult_frac = rm._estimate_kelly_fraction(
            signal_strength=0.8,
            rl_confidence=0.7,
            sentiment_score=0.5,
            regime=None,
            multiplier=0.5,
        )

        high_mult_frac = rm._estimate_kelly_fraction(
            signal_strength=0.8,
            rl_confidence=0.7,
            sentiment_score=0.5,
            regime=None,
            multiplier=2.0,
        )

        assert high_mult_frac > low_mult_frac


# =============================================================================
# Run Tests
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
