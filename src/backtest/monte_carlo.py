#!/usr/bin/env python3
"""
Monte Carlo Simulation for Options Strategy Backtesting

Provides statistical validation of trading strategies by:
1. Shuffling historical trade sequences to remove time dependency
2. Running thousands of simulations to build probability distributions
3. Calculating confidence intervals for expected returns
4. Stress testing under various market conditions

Reference: Phil Town Rule #1 - Don't Lose Money
Monte Carlo helps validate that a strategy is robust, not just lucky.
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class MonteCarloResults:
    """Results from Monte Carlo simulation."""

    # Simulation parameters
    n_simulations: int
    n_trades_per_sim: int
    original_pnls: list[float]

    # Distribution statistics
    mean_total_return: float
    median_total_return: float
    std_total_return: float

    # Confidence intervals (percentiles)
    ci_5: float  # 5th percentile (worst case)
    ci_25: float  # 25th percentile
    ci_75: float  # 75th percentile
    ci_95: float  # 95th percentile (best case)

    # Risk metrics
    probability_of_profit: float
    probability_of_ruin: float  # P(loss > 50% of capital)
    expected_max_drawdown: float

    # Sharpe distribution
    mean_sharpe: float
    sharpe_ci_5: float
    sharpe_ci_95: float

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization.

        Note: Explicitly convert numpy types to Python types for JSON compatibility.
        """
        return {
            "n_simulations": int(self.n_simulations),
            "n_trades_per_sim": int(self.n_trades_per_sim),
            "mean_total_return": float(round(self.mean_total_return, 2)),
            "median_total_return": float(round(self.median_total_return, 2)),
            "std_total_return": float(round(self.std_total_return, 2)),
            "ci_5_pct": float(round(self.ci_5, 2)),
            "ci_25_pct": float(round(self.ci_25, 2)),
            "ci_75_pct": float(round(self.ci_75, 2)),
            "ci_95_pct": float(round(self.ci_95, 2)),
            "probability_of_profit": float(round(self.probability_of_profit, 4)),
            "probability_of_ruin": float(round(self.probability_of_ruin, 4)),
            "expected_max_drawdown": float(round(self.expected_max_drawdown, 4)),
            "mean_sharpe": float(round(self.mean_sharpe, 3)),
            "sharpe_ci_5": float(round(self.sharpe_ci_5, 3)),
            "sharpe_ci_95": float(round(self.sharpe_ci_95, 3)),
        }

    def is_statistically_profitable(self) -> tuple[bool, str]:
        """
        Determine if strategy is statistically profitable.

        Returns:
            (is_profitable, reason) tuple
        """
        # Must have >50% probability of profit
        if self.probability_of_profit < 0.50:
            return False, f"Probability of profit {self.probability_of_profit:.1%} < 50%"

        # 5th percentile should not be catastrophic (< -25% of trades)
        if self.ci_5 < -self.n_trades_per_sim * 50:  # Assuming $50 max loss per trade
            return False, f"5th percentile return ${self.ci_5:.0f} is too risky"

        # Probability of ruin should be < 5%
        if self.probability_of_ruin > 0.05:
            return False, f"Probability of ruin {self.probability_of_ruin:.1%} > 5%"

        # Median should be positive
        if self.median_total_return <= 0:
            return False, f"Median return ${self.median_total_return:.0f} <= 0"

        return True, "Strategy passes statistical validation"


def run_monte_carlo(
    trade_pnls: list[float],
    n_simulations: int = 10000,
    n_trades_per_sim: Optional[int] = None,
    initial_capital: float = 5000.0,
    ruin_threshold: float = 0.50,
    random_seed: Optional[int] = None,
) -> MonteCarloResults:
    """
    Run Monte Carlo simulation on historical trade P/Ls.

    Args:
        trade_pnls: List of historical trade P/L values
        n_simulations: Number of simulations to run
        n_trades_per_sim: Trades per simulation (default: same as historical)
        initial_capital: Starting capital for ruin calculation
        ruin_threshold: Loss percentage considered "ruin" (default 50%)
        random_seed: Random seed for reproducibility

    Returns:
        MonteCarloResults with statistical analysis
    """
    if random_seed is not None:
        np.random.seed(random_seed)

    pnls = np.array(trade_pnls, dtype=float)
    n_historical = len(pnls)

    if n_historical == 0:
        raise ValueError("Cannot run Monte Carlo with empty trade history")

    if n_trades_per_sim is None:
        n_trades_per_sim = n_historical

    # Run simulations
    total_returns = []
    max_drawdowns = []
    sharpe_ratios = []

    for _ in range(n_simulations):
        # Bootstrap sample with replacement
        sim_pnls = np.random.choice(pnls, size=n_trades_per_sim, replace=True)

        # Calculate metrics for this simulation
        total_return = np.sum(sim_pnls)
        total_returns.append(total_return)

        # Calculate max drawdown
        equity_curve = initial_capital + np.cumsum(sim_pnls)
        running_max = np.maximum.accumulate(equity_curve)
        drawdowns = (running_max - equity_curve) / running_max
        max_drawdowns.append(np.max(drawdowns))

        # Calculate Sharpe (simplified for speed)
        if np.std(sim_pnls) > 0:
            sharpe = np.mean(sim_pnls) / np.std(sim_pnls) * np.sqrt(252)
        else:
            sharpe = 3.0 if np.mean(sim_pnls) > 0 else -3.0
        sharpe_ratios.append(sharpe)

    total_returns = np.array(total_returns)
    max_drawdowns = np.array(max_drawdowns)
    sharpe_ratios = np.array(sharpe_ratios)

    # Calculate statistics
    mean_return = float(np.mean(total_returns))
    median_return = float(np.median(total_returns))
    std_return = float(np.std(total_returns))

    # Percentiles
    ci_5 = float(np.percentile(total_returns, 5))
    ci_25 = float(np.percentile(total_returns, 25))
    ci_75 = float(np.percentile(total_returns, 75))
    ci_95 = float(np.percentile(total_returns, 95))

    # Probabilities
    prob_profit = float(np.mean(total_returns > 0))
    ruin_amount = initial_capital * ruin_threshold
    prob_ruin = float(np.mean(total_returns < -ruin_amount))

    # Drawdown
    expected_max_dd = float(np.mean(max_drawdowns))

    # Sharpe statistics
    mean_sharpe = float(np.mean(sharpe_ratios))
    sharpe_ci_5 = float(np.percentile(sharpe_ratios, 5))
    sharpe_ci_95 = float(np.percentile(sharpe_ratios, 95))

    return MonteCarloResults(
        n_simulations=n_simulations,
        n_trades_per_sim=n_trades_per_sim,
        original_pnls=list(trade_pnls),
        mean_total_return=mean_return,
        median_total_return=median_return,
        std_total_return=std_return,
        ci_5=ci_5,
        ci_25=ci_25,
        ci_75=ci_75,
        ci_95=ci_95,
        probability_of_profit=prob_profit,
        probability_of_ruin=prob_ruin,
        expected_max_drawdown=expected_max_dd,
        mean_sharpe=mean_sharpe,
        sharpe_ci_5=sharpe_ci_5,
        sharpe_ci_95=sharpe_ci_95,
    )


def generate_monte_carlo_report(
    results: MonteCarloResults, strategy_name: str = "Iron Condor"
) -> str:
    """Generate a human-readable Monte Carlo report."""
    profitable, reason = results.is_statistically_profitable()

    report = f"""
{"=" * 70}
MONTE CARLO SIMULATION REPORT: {strategy_name}
{"=" * 70}

SIMULATION PARAMETERS
  Simulations Run:      {results.n_simulations:,}
  Trades per Sim:       {results.n_trades_per_sim}
  Historical Trades:    {len(results.original_pnls)}

RETURN DISTRIBUTION
  Mean Total Return:    ${results.mean_total_return:,.2f}
  Median Total Return:  ${results.median_total_return:,.2f}
  Std Deviation:        ${results.std_total_return:,.2f}

CONFIDENCE INTERVALS
  5th Percentile:       ${results.ci_5:,.2f}  (worst case)
  25th Percentile:      ${results.ci_25:,.2f}
  75th Percentile:      ${results.ci_75:,.2f}
  95th Percentile:      ${results.ci_95:,.2f}  (best case)

RISK ANALYSIS
  Probability of Profit:  {results.probability_of_profit:.1%}
  Probability of Ruin:    {results.probability_of_ruin:.1%}
  Expected Max Drawdown:  {results.expected_max_drawdown:.1%}

SHARPE RATIO DISTRIBUTION
  Mean Sharpe:            {results.mean_sharpe:.3f}
  5th Percentile:         {results.sharpe_ci_5:.3f}
  95th Percentile:        {results.sharpe_ci_95:.3f}

STATISTICAL VALIDATION
  Status:  {"PASS" if profitable else "FAIL"}
  Reason:  {reason}

{"=" * 70}
"""
    return report


def stress_test_strategy(
    trade_pnls: list[float],
    stress_scenarios: Optional[dict] = None,
    n_simulations: int = 1000,
) -> dict:
    """
    Run stress tests on the strategy under various market conditions.

    Args:
        trade_pnls: Historical trade P/Ls
        stress_scenarios: Dict of scenario_name -> loss_multiplier
        n_simulations: Simulations per scenario

    Returns:
        Dict of scenario results
    """
    if stress_scenarios is None:
        stress_scenarios = {
            "normal": 1.0,
            "moderate_stress": 1.5,  # Losses are 50% larger
            "severe_stress": 2.0,  # Losses are 100% larger
            "black_swan": 3.0,  # Losses are 200% larger
        }

    pnls = np.array(trade_pnls, dtype=float)
    results = {}

    for scenario_name, loss_multiplier in stress_scenarios.items():
        # Apply stress to losses only
        stressed_pnls = pnls.copy()
        stressed_pnls[stressed_pnls < 0] *= loss_multiplier

        # Run Monte Carlo on stressed data
        mc_results = run_monte_carlo(
            list(stressed_pnls),
            n_simulations=n_simulations,
            random_seed=42,  # Reproducible
        )

        results[scenario_name] = {
            "loss_multiplier": loss_multiplier,
            "mean_return": mc_results.mean_total_return,
            "prob_profit": mc_results.probability_of_profit,
            "prob_ruin": mc_results.probability_of_ruin,
            "passes_validation": mc_results.is_statistically_profitable()[0],
        }

    return results


# CLI for testing
if __name__ == "__main__":
    # Example usage with sample data
    sample_pnls = [40, 40, 40, -80, 60, 40, 40, -120, 40, 40, 80, 40, -40, 60, 40, 40, 40, 40]

    print("Running Monte Carlo simulation...")
    results = run_monte_carlo(sample_pnls, n_simulations=10000, random_seed=42)
    print(generate_monte_carlo_report(results))

    print("\nRunning stress tests...")
    import json

    stress_results = stress_test_strategy(sample_pnls)
    print(json.dumps(stress_results, indent=2))
