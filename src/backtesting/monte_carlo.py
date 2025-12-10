"""
Monte Carlo Simulation for Backtest Validation

This module provides Monte Carlo simulations for stress-testing trading strategies
by testing robustness to different return sequences. Key capabilities:

1. Return shuffling: Test if profits are path-dependent
2. Confidence intervals: 95% bounds on key metrics (Sharpe, return, drawdown)
3. Probability analysis: Estimate ruin probability and tail risk
4. Bootstrap resampling: Statistical significance testing

Critical for production-grade backtesting - addresses a key gap identified in
the system audit (Dec 4, 2025).

Author: Trading System
Created: 2025-12-04
"""

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MonteCarloResult:
    """Results from Monte Carlo simulation."""

    # Core metrics with confidence intervals
    sharpe_mean: float
    sharpe_std: float
    sharpe_95_lower: float
    sharpe_95_upper: float

    total_return_mean: float
    total_return_std: float
    return_95_lower: float
    return_95_upper: float

    max_drawdown_mean: float
    max_drawdown_std: float
    drawdown_95_lower: float
    drawdown_95_upper: float  # 95th percentile of worst drawdowns

    # Risk metrics
    probability_of_loss: float  # % of simulations with negative return
    probability_of_ruin: float  # % hitting >20% drawdown
    value_at_risk_95: float  # 5th percentile of final returns
    expected_shortfall_95: float  # Average of worst 5% outcomes

    # Simulation stats
    num_simulations: int
    original_sharpe: float
    original_return: float
    original_drawdown: float

    # Path dependency score (0 = no dependency, 1 = fully dependent)
    path_dependency: float

    # Distribution of outcomes
    sharpe_distribution: list[float] = field(default_factory=list)
    return_distribution: list[float] = field(default_factory=list)
    drawdown_distribution: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "sharpe": {
                "mean": round(self.sharpe_mean, 3),
                "std": round(self.sharpe_std, 3),
                "95_ci": [round(self.sharpe_95_lower, 3), round(self.sharpe_95_upper, 3)],
                "original": round(self.original_sharpe, 3),
            },
            "total_return_pct": {
                "mean": round(self.total_return_mean * 100, 2),
                "std": round(self.total_return_std * 100, 2),
                "95_ci": [
                    round(self.return_95_lower * 100, 2),
                    round(self.return_95_upper * 100, 2),
                ],
                "original": round(self.original_return * 100, 2),
            },
            "max_drawdown_pct": {
                "mean": round(self.max_drawdown_mean * 100, 2),
                "std": round(self.max_drawdown_std * 100, 2),
                "95_worst": round(self.drawdown_95_upper * 100, 2),
                "original": round(self.original_drawdown * 100, 2),
            },
            "risk_metrics": {
                "probability_of_loss_pct": round(self.probability_of_loss * 100, 1),
                "probability_of_ruin_pct": round(self.probability_of_ruin * 100, 1),
                "var_95_pct": round(self.value_at_risk_95 * 100, 2),
                "es_95_pct": round(self.expected_shortfall_95 * 100, 2),
            },
            "path_dependency": round(self.path_dependency, 3),
            "num_simulations": self.num_simulations,
            "verdict": self._get_verdict(),
        }

    def _get_verdict(self) -> str:
        """Provide human-readable assessment."""
        issues = []

        # Check if original is outside confidence interval (overfit)
        if self.original_sharpe > self.sharpe_95_upper:
            issues.append("Sharpe may be overfit (above 95% CI)")

        # Check ruin probability
        if self.probability_of_ruin > 0.10:
            issues.append(f"High ruin risk ({self.probability_of_ruin * 100:.0f}%)")

        # Check path dependency
        if self.path_dependency > 0.5:
            issues.append("High path dependency - profits may be luck")

        # Check loss probability
        if self.probability_of_loss > 0.40:
            issues.append(f"High loss probability ({self.probability_of_loss * 100:.0f}%)")

        if not issues:
            return "ROBUST: Strategy passes Monte Carlo validation"
        return f"CAUTION: {'; '.join(issues)}"


class MonteCarloSimulator:
    """
    Monte Carlo simulator for backtest stress testing.

    Uses bootstrap resampling and return shuffling to test
    strategy robustness to different return sequences.

    Args:
        num_simulations: Number of Monte Carlo paths (default: 1000)
        risk_free_rate: Annual risk-free rate for Sharpe (default: 0.04)
        ruin_threshold: Drawdown threshold for ruin (default: 0.20)
    """

    def __init__(
        self,
        num_simulations: int = 1000,
        risk_free_rate: float = 0.04,
        ruin_threshold: float = 0.20,
    ):
        self.num_simulations = num_simulations
        self.risk_free_rate = risk_free_rate
        self.ruin_threshold = ruin_threshold
        self._rng = np.random.default_rng(seed=42)  # Reproducibility

    def simulate_from_returns(
        self,
        daily_returns: np.ndarray,
        initial_capital: float = 100000.0,
        method: str = "shuffle",
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation from daily returns.

        Args:
            daily_returns: Array of daily percentage returns (e.g., 0.01 = 1%)
            initial_capital: Starting capital
            method: Simulation method ('shuffle', 'bootstrap', 'parametric')

        Returns:
            MonteCarloResult with confidence intervals and risk metrics
        """
        if len(daily_returns) < 20:
            raise ValueError("Need at least 20 daily returns for Monte Carlo")

        daily_returns = np.asarray(daily_returns, dtype=np.float64)

        # Remove any NaN/Inf
        daily_returns = daily_returns[np.isfinite(daily_returns)]

        # Calculate original metrics
        original_sharpe = self._calculate_sharpe(daily_returns)
        original_return = self._calculate_total_return(daily_returns)
        original_drawdown = self._calculate_max_drawdown(daily_returns)

        # Run simulations
        sharpe_results = []
        return_results = []
        drawdown_results = []

        for _ in range(self.num_simulations):
            # Generate shuffled/resampled returns
            if method == "shuffle":
                sim_returns = self._shuffle_returns(daily_returns)
            elif method == "bootstrap":
                sim_returns = self._bootstrap_returns(daily_returns)
            elif method == "parametric":
                sim_returns = self._parametric_returns(daily_returns)
            else:
                sim_returns = self._shuffle_returns(daily_returns)

            # Calculate metrics for this simulation
            sharpe_results.append(self._calculate_sharpe(sim_returns))
            return_results.append(self._calculate_total_return(sim_returns))
            drawdown_results.append(self._calculate_max_drawdown(sim_returns))

        # Convert to arrays
        sharpe_arr = np.array(sharpe_results)
        return_arr = np.array(return_results)
        drawdown_arr = np.array(drawdown_results)

        # Calculate statistics
        sharpe_mean = float(np.mean(sharpe_arr))
        sharpe_std = float(np.std(sharpe_arr))
        sharpe_95_lower = float(np.percentile(sharpe_arr, 2.5))
        sharpe_95_upper = float(np.percentile(sharpe_arr, 97.5))

        return_mean = float(np.mean(return_arr))
        return_std = float(np.std(return_arr))
        return_95_lower = float(np.percentile(return_arr, 2.5))
        return_95_upper = float(np.percentile(return_arr, 97.5))

        drawdown_mean = float(np.mean(drawdown_arr))
        drawdown_std = float(np.std(drawdown_arr))
        drawdown_95_lower = float(np.percentile(drawdown_arr, 2.5))
        drawdown_95_upper = float(np.percentile(drawdown_arr, 95))  # 95th = worst

        # Risk metrics
        prob_loss = float(np.mean(return_arr < 0))
        prob_ruin = float(np.mean(drawdown_arr > self.ruin_threshold))
        var_95 = float(np.percentile(return_arr, 5))  # 5th percentile
        es_95 = float(np.mean(return_arr[return_arr <= var_95])) if prob_loss > 0 else 0

        # Path dependency: how much does shuffling change results?
        # If Sharpe is same after shuffling, strategy is not path-dependent
        sharpe_diff = abs(original_sharpe - sharpe_mean)
        sharpe_spread = sharpe_95_upper - sharpe_95_lower
        path_dependency = min(1.0, sharpe_diff / max(sharpe_spread, 0.1))

        return MonteCarloResult(
            sharpe_mean=sharpe_mean,
            sharpe_std=sharpe_std,
            sharpe_95_lower=sharpe_95_lower,
            sharpe_95_upper=sharpe_95_upper,
            total_return_mean=return_mean,
            total_return_std=return_std,
            return_95_lower=return_95_lower,
            return_95_upper=return_95_upper,
            max_drawdown_mean=drawdown_mean,
            max_drawdown_std=drawdown_std,
            drawdown_95_lower=drawdown_95_lower,
            drawdown_95_upper=drawdown_95_upper,
            probability_of_loss=prob_loss,
            probability_of_ruin=prob_ruin,
            value_at_risk_95=var_95,
            expected_shortfall_95=es_95,
            num_simulations=self.num_simulations,
            original_sharpe=original_sharpe,
            original_return=original_return,
            original_drawdown=original_drawdown,
            path_dependency=path_dependency,
            sharpe_distribution=sharpe_arr.tolist()[:100],  # Sample for storage
            return_distribution=return_arr.tolist()[:100],
            drawdown_distribution=drawdown_arr.tolist()[:100],
        )

    def simulate_from_equity_curve(
        self,
        equity_curve: np.ndarray,
        initial_capital: float | None = None,
    ) -> MonteCarloResult:
        """
        Run Monte Carlo from an equity curve (portfolio values over time).

        Args:
            equity_curve: Array of daily portfolio values
            initial_capital: Override starting capital (uses first value if None)

        Returns:
            MonteCarloResult
        """
        equity_curve = np.asarray(equity_curve, dtype=np.float64)

        # Calculate daily returns from equity curve
        daily_returns = np.diff(equity_curve) / equity_curve[:-1]

        capital = initial_capital if initial_capital else equity_curve[0]
        return self.simulate_from_returns(daily_returns, capital)

    def stress_test_scenarios(
        self,
        daily_returns: np.ndarray,
        scenarios: dict[str, dict[str, float]] | None = None,
    ) -> dict[str, MonteCarloResult]:
        """
        Run Monte Carlo under different stress scenarios.

        Args:
            daily_returns: Original daily returns
            scenarios: Dict of scenario configs, e.g.:
                {"2008_crisis": {"return_shock": -0.30, "vol_multiplier": 2.0}}

        Returns:
            Dict mapping scenario name to MonteCarloResult
        """
        if scenarios is None:
            # Default stress scenarios
            scenarios = {
                "base_case": {"return_shock": 0.0, "vol_multiplier": 1.0},
                "mild_stress": {"return_shock": -0.05, "vol_multiplier": 1.5},
                "moderate_stress": {"return_shock": -0.10, "vol_multiplier": 2.0},
                "severe_stress": {"return_shock": -0.20, "vol_multiplier": 3.0},
                "2008_scenario": {"return_shock": -0.35, "vol_multiplier": 4.0},
                "flash_crash": {"return_shock": -0.10, "vol_multiplier": 5.0},
            }

        results = {}
        daily_returns = np.asarray(daily_returns, dtype=np.float64)

        for scenario_name, config in scenarios.items():
            # Apply scenario adjustments
            shock = config.get("return_shock", 0.0)
            vol_mult = config.get("vol_multiplier", 1.0)

            # Adjust returns: scale volatility and add shock
            mean_return = np.mean(daily_returns)
            centered = daily_returns - mean_return
            stressed_returns = (centered * vol_mult) + mean_return + (shock / len(daily_returns))

            results[scenario_name] = self.simulate_from_returns(stressed_returns)
            logger.info(
                f"Scenario {scenario_name}: Sharpe={results[scenario_name].sharpe_mean:.2f}"
            )

        return results

    def _shuffle_returns(self, returns: np.ndarray) -> np.ndarray:
        """Shuffle return sequence (destroys autocorrelation)."""
        shuffled = returns.copy()
        self._rng.shuffle(shuffled)
        return shuffled

    def _bootstrap_returns(self, returns: np.ndarray) -> np.ndarray:
        """Bootstrap resample with replacement."""
        indices = self._rng.integers(0, len(returns), size=len(returns))
        return returns[indices]

    def _parametric_returns(self, returns: np.ndarray) -> np.ndarray:
        """Generate returns from fitted distribution."""
        # Fit normal distribution (could extend to t-distribution for fat tails)
        mean = np.mean(returns)
        std = np.std(returns)
        return self._rng.normal(mean, std, size=len(returns))

    def _calculate_sharpe(self, returns: np.ndarray) -> float:
        """Calculate annualized Sharpe ratio."""
        if len(returns) < 2 or np.std(returns) < 1e-10:
            return 0.0

        daily_excess = returns - (self.risk_free_rate / 252)
        mean_excess = np.mean(daily_excess)
        std_returns = np.std(returns)

        sharpe = (mean_excess / std_returns) * np.sqrt(252)
        return float(np.clip(sharpe, -10, 10))

    def _calculate_total_return(self, returns: np.ndarray) -> float:
        """Calculate total cumulative return."""
        cumulative = np.prod(1 + returns) - 1
        return float(cumulative)

    def _calculate_max_drawdown(self, returns: np.ndarray) -> float:
        """Calculate maximum drawdown from returns."""
        # Build equity curve
        equity = np.cumprod(1 + returns)

        # Calculate running max and drawdown
        running_max = np.maximum.accumulate(equity)
        drawdowns = (running_max - equity) / running_max

        return float(np.max(drawdowns))


def run_monte_carlo_validation(
    backtest_results: Any,
    num_simulations: int = 1000,
) -> MonteCarloResult:
    """
    Convenience function to run Monte Carlo on BacktestResults.

    Args:
        backtest_results: BacktestResults object with equity_curve
        num_simulations: Number of simulations

    Returns:
        MonteCarloResult
    """
    simulator = MonteCarloSimulator(num_simulations=num_simulations)

    # Extract equity curve or daily returns
    if hasattr(backtest_results, "equity_curve"):
        equity = np.array(backtest_results.equity_curve)
        return simulator.simulate_from_equity_curve(equity)
    elif hasattr(backtest_results, "daily_returns"):
        returns = np.array(backtest_results.daily_returns)
        return simulator.simulate_from_returns(returns)
    else:
        raise ValueError("backtest_results must have equity_curve or daily_returns")


if __name__ == "__main__":
    # Demo with synthetic data
    logging.basicConfig(level=logging.INFO)

    # Generate synthetic daily returns (60 days, ~15% annual return)
    np.random.seed(42)
    n_days = 60
    daily_return = 0.15 / 252  # ~15% annual
    daily_vol = 0.15 / np.sqrt(252)  # ~15% annual vol
    synthetic_returns = np.random.normal(daily_return, daily_vol, n_days)

    # Run Monte Carlo
    simulator = MonteCarloSimulator(num_simulations=1000)
    result = simulator.simulate_from_returns(synthetic_returns)

    print("\n=== Monte Carlo Simulation Results ===")
    print(f"Simulations: {result.num_simulations}")
    print("\nSharpe Ratio:")
    print(f"  Original: {result.original_sharpe:.3f}")
    print(f"  Mean (MC): {result.sharpe_mean:.3f} +/- {result.sharpe_std:.3f}")
    print(f"  95% CI: [{result.sharpe_95_lower:.3f}, {result.sharpe_95_upper:.3f}]")

    print("\nTotal Return:")
    print(f"  Original: {result.original_return * 100:.2f}%")
    print(
        f"  Mean (MC): {result.total_return_mean * 100:.2f}% +/- {result.total_return_std * 100:.2f}%"
    )
    print(f"  95% CI: [{result.return_95_lower * 100:.2f}%, {result.return_95_upper * 100:.2f}%]")

    print("\nMax Drawdown:")
    print(f"  Original: {result.original_drawdown * 100:.2f}%")
    print(f"  Mean (MC): {result.max_drawdown_mean * 100:.2f}%")
    print(f"  95th Percentile (Worst): {result.drawdown_95_upper * 100:.2f}%")

    print("\nRisk Metrics:")
    print(f"  Probability of Loss: {result.probability_of_loss * 100:.1f}%")
    print(f"  Probability of Ruin (>20% DD): {result.probability_of_ruin * 100:.1f}%")
    print(f"  VaR 95%: {result.value_at_risk_95 * 100:.2f}%")
    print(f"  Expected Shortfall 95%: {result.expected_shortfall_95 * 100:.2f}%")

    print(f"\nPath Dependency: {result.path_dependency:.3f}")
    print(f"\nVerdict: {result._get_verdict()}")

    # Run stress scenarios
    print("\n\n=== Stress Test Scenarios ===")
    stress_results = simulator.stress_test_scenarios(synthetic_returns)
    for scenario, res in stress_results.items():
        print(f"\n{scenario}:")
        print(
            f"  Sharpe: {res.sharpe_mean:.2f}, Return: {res.total_return_mean * 100:.1f}%, Max DD: {res.max_drawdown_mean * 100:.1f}%"
        )
        print(f"  Ruin Prob: {res.probability_of_ruin * 100:.0f}%")
