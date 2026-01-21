#!/usr/bin/env python3
"""
Tests for the advanced risk metrics module.

These tests validate that our risk calculations are correct and handle
edge cases properly (zero variance, empty data, etc.).
"""

import pytest

# Skip entire module if numpy not available (sandbox environment)
np = pytest.importorskip("numpy")

from src.backtest.risk_metrics import (
    calculate_max_drawdown,
    calculate_risk_metrics,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_var_cvar,
    generate_risk_report,
)


class TestSharpeRatio:
    """Tests for Sharpe ratio calculation."""

    def test_positive_sharpe(self):
        """Test Sharpe with positive returns."""
        returns = np.array([10, 20, 15, 25, 10, 20, 15, 10, 20, 15])
        sharpe = calculate_sharpe_ratio(returns)
        assert sharpe > 0, "Positive returns should give positive Sharpe"

    def test_negative_sharpe(self):
        """Test Sharpe with negative returns."""
        returns = np.array([-10, -20, -15, -25, -10, -20, -15, -10, -20, -15])
        sharpe = calculate_sharpe_ratio(returns)
        assert sharpe < 0, "Negative returns should give negative Sharpe"

    def test_zero_variance_positive(self):
        """Test Sharpe with zero variance (all same positive return)."""
        returns = np.array([40.0] * 20)
        sharpe = calculate_sharpe_ratio(returns)
        # Should return capped value, not infinity
        assert sharpe == 3.0, "Zero variance positive should cap at 3.0"

    def test_zero_variance_negative(self):
        """Test Sharpe with zero variance (all same negative return)."""
        returns = np.array([-40.0] * 20)
        sharpe = calculate_sharpe_ratio(returns)
        assert sharpe == -3.0, "Zero variance negative should cap at -3.0"

    def test_insufficient_data(self):
        """Test Sharpe with too few observations."""
        returns = np.array([10, 20, 30])  # Only 3 observations
        sharpe = calculate_sharpe_ratio(returns, min_observations=10)
        assert sharpe == 0.0, "Insufficient data should return 0"

    def test_empty_array(self):
        """Test Sharpe with empty array."""
        returns = np.array([])
        sharpe = calculate_sharpe_ratio(returns)
        assert sharpe == 0.0, "Empty array should return 0"


class TestSortinoRatio:
    """Tests for Sortino ratio calculation."""

    def test_no_downside(self):
        """Test Sortino with no negative returns."""
        returns = np.array([10, 20, 15, 25, 10, 20, 15, 10, 20, 15])
        sortino = calculate_sortino_ratio(returns)
        assert sortino == 3.0, "No downside should return capped value"

    def test_with_downside(self):
        """Test Sortino with mixed returns."""
        returns = np.array([10, -5, 15, -10, 10, -3, 15, 10, -8, 15])
        sortino = calculate_sortino_ratio(returns)
        assert sortino > 0, "Mixed positive returns should give positive Sortino"

    def test_sortino_vs_sharpe(self):
        """Sortino should be higher than Sharpe when upside > downside."""
        returns = np.array([50, -10, 40, -5, 60, -10, 50, -5, 40, 30])
        sharpe = calculate_sharpe_ratio(returns)
        sortino = calculate_sortino_ratio(returns)
        assert sortino >= sharpe, "Sortino should be >= Sharpe when upside dominates"


class TestMaxDrawdown:
    """Tests for maximum drawdown calculation."""

    def test_no_drawdown(self):
        """Test with monotonically increasing equity."""
        equity = np.array([100, 110, 120, 130, 140, 150])
        max_dd, duration = calculate_max_drawdown(equity)
        assert max_dd == 0.0, "No drawdown for increasing equity"
        assert duration == 0, "No duration for no drawdown"

    def test_simple_drawdown(self):
        """Test with simple drawdown scenario."""
        equity = np.array([100, 110, 105, 95, 100, 110])
        max_dd, duration = calculate_max_drawdown(equity)
        # Max drawdown is from 110 to 95 = 15/110 = 13.6%
        assert abs(max_dd - 0.136) < 0.01, f"Expected ~13.6% drawdown, got {max_dd:.1%}"

    def test_drawdown_duration(self):
        """Test drawdown duration calculation."""
        equity = np.array([100, 110, 100, 90, 95, 100, 105, 110, 115])
        max_dd, duration = calculate_max_drawdown(equity)
        # Drawdown from 110 (index 1) to recovery at 110 (index 7) = 6 periods
        assert duration > 0, "Should have non-zero duration"


class TestVarCvar:
    """Tests for Value at Risk and Conditional VaR."""

    def test_var_cvar_basic(self):
        """Test basic VaR/CVaR calculation."""
        returns = np.array([10, -5, 15, -10, 10, -20, 15, 10, -8, 15])
        var, cvar = calculate_var_cvar(returns, confidence=0.95)
        assert var >= 0, "VaR should be non-negative"
        assert cvar >= var, "CVaR should be >= VaR"

    def test_var_with_no_losses(self):
        """Test VaR with all positive returns."""
        returns = np.array([10, 20, 15, 25, 10, 20, 15, 10, 20, 15])
        var, cvar = calculate_var_cvar(returns)
        # With all positive returns, the "worst" returns are still positive
        # So VaR might be negative (meaning no loss at that percentile)
        assert var >= 0 or cvar >= 0, "Should handle all-positive case"


class TestRiskMetrics:
    """Tests for comprehensive risk metrics calculation."""

    def test_empty_trades(self):
        """Test with empty trade list."""
        metrics = calculate_risk_metrics([])
        assert metrics.total_return == 0.0
        assert metrics.sharpe_ratio == 0.0
        assert metrics.win_rate == 0.0

    def test_all_winners(self):
        """Test with all winning trades."""
        pnls = [40, 50, 30, 60, 40, 50, 30, 40, 50, 30]
        metrics = calculate_risk_metrics(pnls)
        assert metrics.win_rate == 1.0, "All wins should give 100% win rate"
        assert metrics.profit_factor == float("inf"), "No losses = infinite profit factor"

    def test_all_losers(self):
        """Test with all losing trades."""
        pnls = [-40, -50, -30, -60, -40, -50, -30, -40, -50, -30]
        metrics = calculate_risk_metrics(pnls)
        assert metrics.win_rate == 0.0, "All losses should give 0% win rate"
        assert metrics.profit_factor == 0.0, "No wins = zero profit factor"

    def test_mixed_trades(self):
        """Test with realistic mixed P/L."""
        pnls = [40, 40, 40, -80, 60, 40, 40, -120, 40, 40, 80, 40, -40, 60, 40, 40, 40, 40]
        metrics = calculate_risk_metrics(pnls)

        assert metrics.total_return > 0, "Sample should be profitable"
        assert 0 < metrics.win_rate < 1, "Should have mixed win rate"
        assert metrics.sharpe_ratio != 0, "Should have non-zero Sharpe"
        assert metrics.max_drawdown >= 0, "Max drawdown should be non-negative"

    def test_phil_town_compliance_pass(self):
        """Test Phil Town compliance with good metrics."""
        pnls = [40, 50, 30, -20, 60, 40, 50, -30, 40, 50, 30, 40, 50, 30]
        metrics = calculate_risk_metrics(pnls, initial_capital=10000)
        compliant, violations = metrics.is_phil_town_compliant()
        assert compliant, f"Should be compliant but got violations: {violations}"

    def test_phil_town_compliance_fail_negative_return(self):
        """Test Phil Town compliance fails with negative total return."""
        pnls = [-40, -50, -30, -60, 40, 50]  # Net negative
        metrics = calculate_risk_metrics(pnls)
        compliant, violations = metrics.is_phil_town_compliant()
        assert not compliant, "Should fail with negative return"
        assert any("negative" in v.lower() for v in violations)


class TestRiskReport:
    """Tests for risk report generation."""

    def test_report_generation(self):
        """Test that report generates without errors."""
        pnls = [40, 40, -20, 60, 40, -30, 40, 50, 40, 40]
        metrics = calculate_risk_metrics(pnls)
        report = generate_risk_report(metrics, "Test Strategy")

        assert "Test Strategy" in report
        assert "Sharpe Ratio" in report
        assert "Win Rate" in report
        assert "Phil Town" in report

    def test_report_with_violations(self):
        """Test report shows violations when present."""
        pnls = [-100, -200, -150, 50, -100]  # Heavy losses
        metrics = calculate_risk_metrics(pnls)
        report = generate_risk_report(metrics)

        assert "VIOLATIONS FOUND" in report


class TestEdgeCases:
    """Tests for edge cases and numerical stability."""

    def test_single_trade(self):
        """Test with single trade."""
        metrics = calculate_risk_metrics([40])
        assert metrics.total_return == 40
        assert metrics.win_rate == 1.0

    def test_large_numbers(self):
        """Test with large P/L values."""
        pnls = [10000, -5000, 15000, -8000, 20000]
        metrics = calculate_risk_metrics(pnls, initial_capital=100000)
        assert np.isfinite(metrics.sharpe_ratio), "Should handle large numbers"
        assert np.isfinite(metrics.sortino_ratio), "Should handle large numbers"

    def test_small_numbers(self):
        """Test with small P/L values."""
        pnls = [0.01, -0.005, 0.02, -0.008, 0.015]
        metrics = calculate_risk_metrics(pnls, initial_capital=100)
        assert np.isfinite(metrics.sharpe_ratio), "Should handle small numbers"

    def test_to_dict_serializable(self):
        """Test that to_dict produces JSON-serializable output."""
        import json

        pnls = [40, -20, 60, -30, 50]
        metrics = calculate_risk_metrics(pnls)
        d = metrics.to_dict()

        # Should not raise
        json_str = json.dumps(d)
        assert len(json_str) > 0
