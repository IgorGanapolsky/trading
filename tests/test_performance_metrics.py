"""Tests for performance_metrics module."""

import pytest

np = pytest.importorskip("numpy")

from src.utils.performance_metrics import (
    calculate_all_metrics,
    calculate_annualized_sharpe,
    calculate_calmar_ratio,
    calculate_max_drawdown,
    calculate_profit_factor,
    calculate_rolling_sharpe,
    calculate_sortino_ratio,
    format_metrics_report,
)


class TestAnnualizedSharpe:
    """Tests for Sharpe ratio calculation."""

    def test_positive_returns(self):
        """Positive consistent returns should have positive Sharpe."""
        returns = np.array([0.01, 0.02, 0.01, 0.015, 0.01] * 10)  # 50 trades
        sharpe = calculate_annualized_sharpe(returns, risk_free_rate=0.0)
        assert sharpe > 0

    def test_negative_returns(self):
        """Negative returns should have negative Sharpe."""
        returns = np.array([-0.01, -0.02, -0.01, -0.015, -0.01] * 10)
        sharpe = calculate_annualized_sharpe(returns, risk_free_rate=0.0)
        assert sharpe < 0

    def test_zero_volatility(self):
        """Zero volatility should return 0."""
        returns = np.array([0.01, 0.01, 0.01, 0.01])
        sharpe = calculate_annualized_sharpe(returns)
        assert sharpe == 0.0

    def test_empty_returns(self):
        """Empty returns should return 0."""
        sharpe = calculate_annualized_sharpe(np.array([]))
        assert sharpe == 0.0

    def test_single_return(self):
        """Single return should return 0."""
        sharpe = calculate_annualized_sharpe(np.array([0.05]))
        assert sharpe == 0.0

    def test_risk_free_rate_impact(self):
        """Higher risk-free rate should lower Sharpe."""
        returns = np.array([0.01, 0.02, 0.01, 0.015] * 10)
        sharpe_low_rf = calculate_annualized_sharpe(returns, risk_free_rate=0.0)
        sharpe_high_rf = calculate_annualized_sharpe(returns, risk_free_rate=0.10)
        assert sharpe_low_rf > sharpe_high_rf


class TestSortinoRatio:
    """Tests for Sortino ratio calculation."""

    def test_no_downside(self):
        """No downside should return high Sortino."""
        returns = np.array([0.01, 0.02, 0.03, 0.01])
        sortino = calculate_sortino_ratio(returns)
        assert sortino == 10.0  # Capped value

    def test_with_downside(self):
        """Returns with downside should have finite Sortino."""
        returns = np.array([0.01, -0.01, 0.02, -0.005, 0.01] * 10)
        sortino = calculate_sortino_ratio(returns)
        assert sortino != 10.0
        assert np.isfinite(sortino)

    def test_sortino_vs_sharpe(self):
        """Sortino should be higher than Sharpe for asymmetric returns."""
        # Asymmetric: small losses, big wins
        returns = np.array([0.05, -0.01, 0.04, -0.01, 0.03] * 10)
        sharpe = calculate_annualized_sharpe(returns, risk_free_rate=0.0)
        sortino = calculate_sortino_ratio(returns, risk_free_rate=0.0)
        # Sortino typically higher when downside is limited
        assert sortino > sharpe


class TestMaxDrawdown:
    """Tests for max drawdown calculation."""

    def test_no_drawdown(self):
        """Monotonically increasing equity has no drawdown."""
        equity = np.array([100, 110, 120, 130, 140])
        max_dd, duration = calculate_max_drawdown(equity)
        assert max_dd == 0.0
        assert duration == 0

    def test_simple_drawdown(self):
        """Simple drawdown calculation."""
        equity = np.array([100, 110, 100, 95, 105])
        max_dd, duration = calculate_max_drawdown(equity)
        # Max drawdown from 110 to 95 = 15/110 = 13.6%
        assert max_dd == pytest.approx(15 / 110, rel=0.01)

    def test_recovery(self):
        """Test drawdown duration with recovery."""
        equity = np.array([100, 110, 100, 110, 120])
        max_dd, duration = calculate_max_drawdown(equity)
        assert max_dd == pytest.approx(10 / 110, rel=0.01)


class TestCalmarRatio:
    """Tests for Calmar ratio calculation."""

    def test_positive_calmar(self):
        """Positive return with drawdown should give positive Calmar."""
        calmar = calculate_calmar_ratio(0.20, 0.10)  # 20% return, 10% DD
        assert calmar == 2.0

    def test_zero_drawdown(self):
        """Zero drawdown should return capped value."""
        calmar = calculate_calmar_ratio(0.15, 0.0)
        assert calmar == 10.0

    def test_negative_return(self):
        """Negative return should give negative Calmar."""
        calmar = calculate_calmar_ratio(-0.10, 0.15)
        assert calmar < 0


class TestProfitFactor:
    """Tests for profit factor calculation."""

    def test_profitable(self):
        """Profitable trades should have PF > 1."""
        wins = [100, 150, 80]
        losses = [-50, -30]
        pf = calculate_profit_factor(wins, losses)
        assert pf > 1.0
        assert pf == pytest.approx(330 / 80, rel=0.01)

    def test_unprofitable(self):
        """Unprofitable trades should have PF < 1."""
        wins = [50]
        losses = [-100, -50]
        pf = calculate_profit_factor(wins, losses)
        assert pf < 1.0

    def test_no_losses(self):
        """No losses should return capped value."""
        wins = [100, 50]
        losses = []
        pf = calculate_profit_factor(wins, losses)
        assert pf == 10.0


class TestRollingSharpe:
    """Tests for rolling Sharpe analysis."""

    def test_consistency_calculation(self):
        """Test rolling Sharpe consistency metric."""
        # High consistent returns
        returns = np.array([0.02, 0.015, 0.02, 0.018, 0.022] * 10)
        _, mean, std, consistency = calculate_rolling_sharpe(returns, window=10)
        assert mean > 0
        assert std >= 0
        assert 0 <= consistency <= 1

    def test_insufficient_data(self):
        """Insufficient data should return empty results."""
        returns = np.array([0.01, 0.02])
        result, mean, std, consistency = calculate_rolling_sharpe(returns, window=10)
        assert len(result) == 0
        assert mean == 0.0


class TestCalculateAllMetrics:
    """Integration tests for full metrics calculation."""

    def test_winning_strategy(self):
        """Test metrics for a winning strategy."""
        # Simulated profitable trades
        pnls = [50, -20, 80, -10, 60, -15, 70, -25, 55, -5] * 3  # 30 trades
        metrics = calculate_all_metrics(pnls, initial_capital=5000)

        assert metrics.total_trades == 30
        assert metrics.total_return > 0
        assert metrics.win_rate > 0.4
        assert metrics.profit_factor > 1.0
        assert metrics.sharpe_ratio != 0  # Should have calculated

    def test_losing_strategy(self):
        """Test metrics for a losing strategy."""
        pnls = [-50, 20, -80, 10, -60, 15, -70, 25] * 3
        metrics = calculate_all_metrics(pnls, initial_capital=5000)

        assert metrics.total_return < 0
        assert metrics.profit_factor < 1.0

    def test_empty_pnls(self):
        """Empty P/L list should return zero metrics."""
        metrics = calculate_all_metrics([])
        assert metrics.total_trades == 0
        assert metrics.sharpe_ratio == 0.0

    def test_metrics_to_dict(self):
        """Test serialization to dict."""
        pnls = [50, -20, 80, -10, 60]
        metrics = calculate_all_metrics(pnls)
        d = metrics.to_dict()

        assert "sharpe_ratio" in d
        assert "sortino_ratio" in d
        assert "win_rate" in d
        assert isinstance(d["total_trades"], int)


class TestFormatReport:
    """Tests for report formatting."""

    def test_format_produces_output(self):
        """Format should produce non-empty string."""
        pnls = [50, -20, 80, -10, 60] * 5
        metrics = calculate_all_metrics(pnls)
        report = format_metrics_report(metrics)

        assert len(report) > 100
        assert "Sharpe Ratio" in report
        assert "Win Rate" in report
        assert "Max Drawdown" in report
