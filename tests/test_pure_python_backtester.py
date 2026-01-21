"""Tests for pure Python backtester."""

import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "backtest"))

from pure_python_backtester import (
    BacktestConfig,
    calculate_max_drawdown,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    monte_carlo_simulation,
    run_backtest,
    simulate_iron_condor_trade,
)


class TestBacktestConfig:
    """Test BacktestConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = BacktestConfig()
        assert config.underlying_symbol == "SPY"
        assert config.short_delta_min == 0.15
        assert config.short_delta_max == 0.20
        assert config.spread_width == 5.0
        assert config.iron_condor_mode is True
        assert config.account_size == 5000.0

    def test_custom_values(self):
        """Test custom configuration."""
        config = BacktestConfig(spread_width=10.0, account_size=10000.0)
        assert config.spread_width == 10.0
        assert config.account_size == 10000.0


class TestSimulateIronCondorTrade:
    """Test single trade simulation."""

    def test_trade_returns_dict(self):
        """Test trade returns expected structure."""
        config = BacktestConfig()
        trade = simulate_iron_condor_trade(config, seed=42)

        assert "credit_received" in trade
        assert "max_risk" in trade
        assert "pnl" in trade
        assert "win" in trade
        assert "exit_reason" in trade
        assert "return_pct" in trade

    def test_trade_with_seed_reproducible(self):
        """Test reproducibility with seed."""
        config = BacktestConfig()
        trade1 = simulate_iron_condor_trade(config, seed=123)
        trade2 = simulate_iron_condor_trade(config, seed=123)

        assert trade1["pnl"] == trade2["pnl"]
        assert trade1["win"] == trade2["win"]

    def test_credit_in_expected_range(self):
        """Test credit received is reasonable."""
        config = BacktestConfig()
        trade = simulate_iron_condor_trade(config, seed=42)

        # Iron condor: $0.80-$1.50 per side x2 x100
        assert 160 <= trade["credit_received"] <= 300


class TestSharpeRatio:
    """Test Sharpe ratio calculation."""

    def test_positive_sharpe(self):
        """Test positive returns give positive Sharpe."""
        returns = [0.01, 0.02, 0.015, 0.01, 0.02]  # All positive
        sharpe = calculate_sharpe_ratio(returns)
        assert sharpe > 0

    def test_negative_sharpe(self):
        """Test negative returns give negative Sharpe."""
        returns = [-0.01, -0.02, -0.015, -0.01, -0.02]  # All negative
        sharpe = calculate_sharpe_ratio(returns)
        assert sharpe < 0

    def test_empty_returns(self):
        """Test empty returns give zero."""
        assert calculate_sharpe_ratio([]) == 0.0

    def test_single_return(self):
        """Test single return gives zero."""
        assert calculate_sharpe_ratio([0.01]) == 0.0


class TestSortinoRatio:
    """Test Sortino ratio calculation."""

    def test_positive_sortino(self):
        """Test mostly positive returns give high Sortino."""
        returns = [0.02, 0.03, 0.01, 0.02, -0.005]  # Mostly positive
        sortino = calculate_sortino_ratio(returns)
        assert sortino > 0

    def test_no_downside(self):
        """Test no negative returns gives high Sortino."""
        returns = [0.01, 0.02, 0.015]  # All above risk-free
        sortino = calculate_sortino_ratio(returns, risk_free_rate=0.0)
        assert sortino == 99.0  # Capped at 99


class TestMaxDrawdown:
    """Test max drawdown calculation."""

    def test_no_drawdown(self):
        """Test consistently increasing values."""
        cumulative = [100, 200, 300, 400, 500]
        assert calculate_max_drawdown(cumulative) == 0.0

    def test_drawdown_exists(self):
        """Test drawdown calculation."""
        cumulative = [100, 150, 120, 180, 160]  # Peak 150, trough 120
        dd = calculate_max_drawdown(cumulative)
        assert dd > 0

    def test_empty_list(self):
        """Test empty list."""
        assert calculate_max_drawdown([]) == 0.0


class TestMonteCarlo:
    """Test Monte Carlo simulation."""

    def test_returns_expected_keys(self):
        """Test Monte Carlo returns expected structure."""
        returns = [10, 20, -5, 15, -10, 25, 30]
        mc = monte_carlo_simulation(returns, n_simulations=100, n_periods=10)

        assert "p5_pnl" in mc
        assert "p50_pnl" in mc
        assert "p95_pnl" in mc
        assert "worst_case" in mc
        assert "best_case" in mc

    def test_percentile_ordering(self):
        """Test percentiles are in order."""
        returns = [10, 20, 15, 25, 30, 5, 10]
        mc = monte_carlo_simulation(returns, n_simulations=500, n_periods=20)

        assert mc["worst_case"] <= mc["p5_pnl"]
        assert mc["p5_pnl"] <= mc["p50_pnl"]
        assert mc["p50_pnl"] <= mc["p95_pnl"]
        assert mc["p95_pnl"] <= mc["best_case"]


class TestRunBacktest:
    """Test full backtest run."""

    def test_backtest_returns_structure(self):
        """Test backtest returns expected structure."""
        results = run_backtest(n_trades=10, seed=42)

        assert "summary" in results
        assert "trades" in results
        assert len(results["trades"]) == 10

    def test_summary_has_metrics(self):
        """Test summary contains all metrics."""
        results = run_backtest(n_trades=20, seed=42)
        summary = results["summary"]

        required_keys = [
            "total_trades",
            "total_pnl",
            "win_rate",
            "sharpe_ratio",
            "sortino_ratio",
            "max_drawdown_pct",
            "monte_carlo",
        ]
        for key in required_keys:
            assert key in summary, f"Missing key: {key}"

    def test_win_rate_in_range(self):
        """Test win rate is valid percentage."""
        results = run_backtest(n_trades=50, seed=42)
        assert 0 <= results["summary"]["win_rate"] <= 100

    def test_reproducibility_with_seed(self):
        """Test backtest is reproducible with seed."""
        results1 = run_backtest(n_trades=20, seed=999)
        results2 = run_backtest(n_trades=20, seed=999)

        assert results1["summary"]["total_pnl"] == results2["summary"]["total_pnl"]
        assert results1["summary"]["win_rate"] == results2["summary"]["win_rate"]
