#!/usr/bin/env python3
"""
Tests for the Monte Carlo simulation module.

Validates that Monte Carlo simulations provide statistically sound
analysis of trading strategies.
"""

import pytest

# Skip entire module if numpy not available (sandbox environment)
np = pytest.importorskip("numpy")

from src.backtest.monte_carlo import (
    generate_monte_carlo_report,
    run_monte_carlo,
    stress_test_strategy,
)


class TestMonteCarloSimulation:
    """Tests for Monte Carlo simulation."""

    def test_basic_simulation(self):
        """Test basic Monte Carlo simulation runs."""
        pnls = [40, 40, 40, -80, 60, 40, 40, -120, 40, 40, 80, 40, -40, 60, 40, 40, 40, 40]
        results = run_monte_carlo(pnls, n_simulations=1000, random_seed=42)

        assert results.n_simulations == 1000
        assert results.n_trades_per_sim == len(pnls)
        assert isinstance(results.mean_total_return, float)
        assert isinstance(results.probability_of_profit, float)

    def test_reproducibility(self):
        """Test that random seed produces reproducible results."""
        pnls = [40, -20, 60, -40, 50, 30, -10, 40]

        results1 = run_monte_carlo(pnls, n_simulations=100, random_seed=42)
        results2 = run_monte_carlo(pnls, n_simulations=100, random_seed=42)

        assert results1.mean_total_return == results2.mean_total_return
        assert results1.probability_of_profit == results2.probability_of_profit

    def test_all_winners(self):
        """Test Monte Carlo with all winning trades."""
        pnls = [40, 50, 30, 60, 40, 50, 30, 40, 50, 30]
        results = run_monte_carlo(pnls, n_simulations=1000, random_seed=42)

        assert results.probability_of_profit == 1.0
        assert results.probability_of_ruin == 0.0
        assert results.mean_total_return > 0

    def test_all_losers(self):
        """Test Monte Carlo with all losing trades."""
        pnls = [-40, -50, -30, -60, -40, -50, -30, -40, -50, -30]
        results = run_monte_carlo(pnls, n_simulations=1000, random_seed=42)

        assert results.probability_of_profit == 0.0
        assert results.mean_total_return < 0

    def test_confidence_intervals(self):
        """Test that confidence intervals are ordered correctly."""
        pnls = [40, -20, 60, -40, 50, 30, -10, 40, -30, 20]
        results = run_monte_carlo(pnls, n_simulations=10000, random_seed=42)

        # Percentiles should be ordered
        assert results.ci_5 <= results.ci_25
        assert results.ci_25 <= results.median_total_return
        assert results.median_total_return <= results.ci_75
        assert results.ci_75 <= results.ci_95

    def test_empty_pnls_raises_error(self):
        """Test that empty P/L list raises error."""
        with pytest.raises(ValueError, match="Cannot run Monte Carlo with empty"):
            run_monte_carlo([], n_simulations=100)

    def test_custom_trades_per_sim(self):
        """Test Monte Carlo with custom trades per simulation."""
        pnls = [40, -20, 60, -40, 50]
        results = run_monte_carlo(pnls, n_simulations=100, n_trades_per_sim=20, random_seed=42)

        assert results.n_trades_per_sim == 20


class TestStatisticalValidation:
    """Tests for statistical validation logic."""

    def test_profitable_strategy_passes(self):
        """Test that clearly profitable strategy passes validation."""
        pnls = [40, 50, 30, -20, 60, 40, 50, -10, 40, 50, 30, 40, 50, 30]
        results = run_monte_carlo(pnls, n_simulations=1000, random_seed=42)

        is_profitable, reason = results.is_statistically_profitable()
        assert is_profitable, f"Should be profitable but: {reason}"

    def test_losing_strategy_fails(self):
        """Test that clearly losing strategy fails validation."""
        pnls = [-40, -50, -30, 10, -60, -40, -50, 5, -40, -50]
        results = run_monte_carlo(pnls, n_simulations=1000, random_seed=42)

        is_profitable, reason = results.is_statistically_profitable()
        assert not is_profitable, "Losing strategy should fail validation"


class TestStressTest:
    """Tests for stress testing functionality."""

    def test_stress_test_runs(self):
        """Test that stress test produces results."""
        pnls = [40, -20, 60, -40, 50, 30, -10, 40]
        results = stress_test_strategy(pnls, n_simulations=100)

        assert "normal" in results
        assert "moderate_stress" in results
        assert "severe_stress" in results
        assert "black_swan" in results

    def test_stress_degrades_performance(self):
        """Test that stress scenarios show degraded performance."""
        pnls = [40, -20, 60, -40, 50, 30, -10, 40]
        results = stress_test_strategy(pnls, n_simulations=1000)

        # More stress should reduce mean returns
        assert results["normal"]["mean_return"] >= results["moderate_stress"]["mean_return"]
        assert results["moderate_stress"]["mean_return"] >= results["severe_stress"]["mean_return"]


class TestMonteCarloReport:
    """Tests for report generation."""

    def test_report_generation(self):
        """Test that report generates without errors."""
        pnls = [40, -20, 60, -40, 50, 30, -10, 40]
        results = run_monte_carlo(pnls, n_simulations=100, random_seed=42)
        report = generate_monte_carlo_report(results, "Test Strategy")

        assert "Test Strategy" in report
        assert "probability of profit" in report.lower()  # Case-insensitive check
        assert "CONFIDENCE INTERVALS" in report  # Report uses uppercase headers
        assert "PASS" in report or "FAIL" in report

    def test_to_dict_serializable(self):
        """Test that to_dict produces JSON-serializable output."""
        import json

        pnls = [40, -20, 60, -40, 50]
        results = run_monte_carlo(pnls, n_simulations=100, random_seed=42)
        d = results.to_dict()

        # Should not raise
        json_str = json.dumps(d)
        assert len(json_str) > 0
