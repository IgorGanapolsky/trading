"""
Monte Carlo Simulation Module for Strategy Robustness Testing.

This module provides Monte Carlo simulation capabilities to test whether trading
strategy results are due to skill or luck. It generates thousands of simulated
equity curves by resampling historical trade returns to estimate the probability
distribution of future outcomes.

Features:
    - Bootstrap resampling of historical trade returns
    - Confidence interval estimation (e.g., 95% CI)
    - Profit probability calculation
    - Risk of ruin estimation
    - Distribution analysis of potential outcomes

Author: Trading System
Created: 2025-12-04
"""

import logging
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MonteCarloResults:
    """Results from Monte Carlo simulation."""

    # Simulation parameters
    num_simulations: int
    num_trades_per_sim: int
    initial_capital: float

    # Final equity statistics
    mean_final_equity: float
    median_final_equity: float
    std_final_equity: float
    min_final_equity: float
    max_final_equity: float

    # Percentiles
    percentile_5: float
    percentile_25: float
    percentile_75: float
    percentile_95: float

    # Probability metrics
    profit_probability: float  # P(final equity > initial capital)
    double_probability: float  # P(final equity > 2 * initial capital)
    ruin_probability: float  # P(final equity < ruin_threshold)

    # Drawdown statistics
    mean_max_drawdown: float
    median_max_drawdown: float
    worst_max_drawdown: float

    # Return statistics
    mean_return: float
    median_return: float
    sharpe_distribution: list[float]

    # Raw data for plotting
    equity_curves: np.ndarray  # Shape: (num_simulations, num_trades + 1)
    final_equities: np.ndarray


@dataclass
class TradeStatistics:
    """Statistics extracted from historical trades."""

    returns: np.ndarray
    mean_return: float
    std_return: float
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    num_trades: int


class MonteCarloSimulator:
    """
    Monte Carlo simulator for strategy robustness testing.

    Uses bootstrap resampling of historical trade returns to generate
    thousands of possible equity curve outcomes. This helps answer:
    - What is the probability of profit?
    - What is the probability of ruin?
    - What is the expected range of outcomes?
    - Are the backtest results due to skill or luck?
    """

    def __init__(
        self,
        num_simulations: int = 10000,
        confidence_level: float = 0.95,
        ruin_threshold: float = 0.5,  # 50% loss = ruin
        random_seed: Optional[int] = None,
    ):
        """
        Initialize Monte Carlo simulator.

        Args:
            num_simulations: Number of simulation paths (default: 10,000)
            confidence_level: Confidence level for intervals (default: 0.95)
            ruin_threshold: Fraction of capital loss considered ruin (default: 0.5)
            random_seed: Random seed for reproducibility
        """
        self.num_simulations = num_simulations
        self.confidence_level = confidence_level
        self.ruin_threshold = ruin_threshold

        if random_seed is not None:
            np.random.seed(random_seed)

        logger.info(
            f"Initialized Monte Carlo simulator: {num_simulations} simulations, "
            f"{confidence_level:.0%} confidence, {ruin_threshold:.0%} ruin threshold"
        )

    def extract_trade_statistics(
        self,
        trades: list[dict[str, Any]],
    ) -> TradeStatistics:
        """
        Extract statistics from historical trade data.

        Args:
            trades: List of trade dictionaries with 'return_pct' or 'pnl' fields

        Returns:
            TradeStatistics object with computed metrics
        """
        if not trades:
            raise ValueError("No trades provided for analysis")

        # Extract returns
        returns = []
        for trade in trades:
            if "return_pct" in trade:
                returns.append(trade["return_pct"])
            elif "pnl" in trade and "entry_value" in trade:
                ret = trade["pnl"] / trade["entry_value"] * 100
                returns.append(ret)
            elif "exit_price" in trade and "entry_price" in trade:
                ret = (trade["exit_price"] - trade["entry_price"]) / trade["entry_price"] * 100
                returns.append(ret)

        if not returns:
            raise ValueError("Could not extract returns from trades")

        returns = np.array(returns)
        wins = returns[returns > 0]
        losses = returns[returns < 0]

        return TradeStatistics(
            returns=returns,
            mean_return=float(np.mean(returns)),
            std_return=float(np.std(returns)),
            win_rate=float(len(wins) / len(returns)) if len(returns) > 0 else 0.0,
            avg_win=float(np.mean(wins)) if len(wins) > 0 else 0.0,
            avg_loss=float(np.mean(losses)) if len(losses) > 0 else 0.0,
            profit_factor=float(np.sum(wins) / abs(np.sum(losses)))
            if len(losses) > 0 and np.sum(losses) != 0
            else float("inf"),
            num_trades=len(returns),
        )

    def run_simulation(
        self,
        trade_returns: np.ndarray,
        initial_capital: float = 100000.0,
        num_trades: Optional[int] = None,
        position_size_pct: float = 100.0,
    ) -> MonteCarloResults:
        """
        Run Monte Carlo simulation using bootstrap resampling.

        Args:
            trade_returns: Array of historical trade return percentages
            initial_capital: Starting capital
            num_trades: Number of trades per simulation (default: same as historical)
            position_size_pct: Position size as percentage of capital

        Returns:
            MonteCarloResults with comprehensive statistics
        """
        if len(trade_returns) == 0:
            raise ValueError("Empty trade returns array")

        if num_trades is None:
            num_trades = len(trade_returns)

        logger.info(f"Running {self.num_simulations} simulations with {num_trades} trades each")

        # Pre-allocate arrays for performance
        equity_curves = np.zeros((self.num_simulations, num_trades + 1))
        equity_curves[:, 0] = initial_capital
        max_drawdowns = np.zeros(self.num_simulations)
        sharpe_ratios = []

        # Convert returns to multipliers (e.g., 5% return = 1.05)
        position_fraction = position_size_pct / 100.0

        for sim in range(self.num_simulations):
            # Bootstrap resample trade returns
            sampled_returns = np.random.choice(trade_returns, size=num_trades, replace=True)

            # Simulate equity curve
            equity = initial_capital
            peak = initial_capital
            max_dd = 0.0

            for i, ret in enumerate(sampled_returns):
                # Apply return to position (partial capital at risk)
                trade_return = (ret / 100.0) * position_fraction
                equity = equity * (1 + trade_return)
                equity_curves[sim, i + 1] = equity

                # Track drawdown
                if equity > peak:
                    peak = equity
                current_dd = (peak - equity) / peak
                if current_dd > max_dd:
                    max_dd = current_dd

            max_drawdowns[sim] = max_dd

            # Calculate Sharpe ratio for this simulation
            sim_returns = np.diff(equity_curves[sim]) / equity_curves[sim, :-1]
            if np.std(sim_returns) > 0:
                sharpe = np.mean(sim_returns) / np.std(sim_returns) * np.sqrt(252)
                sharpe_ratios.append(float(sharpe))
            else:
                sharpe_ratios.append(0.0)

        # Calculate final equities
        final_equities = equity_curves[:, -1]

        # Calculate probabilities
        profit_probability = np.mean(final_equities > initial_capital)
        double_probability = np.mean(final_equities > 2 * initial_capital)
        ruin_threshold_value = initial_capital * (1 - self.ruin_threshold)
        ruin_probability = np.mean(final_equities < ruin_threshold_value)

        # Calculate returns
        total_returns = (final_equities - initial_capital) / initial_capital * 100

        results = MonteCarloResults(
            num_simulations=self.num_simulations,
            num_trades_per_sim=num_trades,
            initial_capital=initial_capital,
            mean_final_equity=float(np.mean(final_equities)),
            median_final_equity=float(np.median(final_equities)),
            std_final_equity=float(np.std(final_equities)),
            min_final_equity=float(np.min(final_equities)),
            max_final_equity=float(np.max(final_equities)),
            percentile_5=float(np.percentile(final_equities, 5)),
            percentile_25=float(np.percentile(final_equities, 25)),
            percentile_75=float(np.percentile(final_equities, 75)),
            percentile_95=float(np.percentile(final_equities, 95)),
            profit_probability=float(profit_probability),
            double_probability=float(double_probability),
            ruin_probability=float(ruin_probability),
            mean_max_drawdown=float(np.mean(max_drawdowns)),
            median_max_drawdown=float(np.median(max_drawdowns)),
            worst_max_drawdown=float(np.max(max_drawdowns)),
            mean_return=float(np.mean(total_returns)),
            median_return=float(np.median(total_returns)),
            sharpe_distribution=sharpe_ratios,
            equity_curves=equity_curves,
            final_equities=final_equities,
        )

        logger.info(
            f"Simulation complete: "
            f"Profit prob={profit_probability:.1%}, "
            f"Mean return={np.mean(total_returns):.1f}%, "
            f"Ruin prob={ruin_probability:.1%}"
        )

        return results

    def run_from_trades(
        self,
        trades: list[dict[str, Any]],
        initial_capital: float = 100000.0,
        future_trades: Optional[int] = None,
        position_size_pct: float = 100.0,
    ) -> MonteCarloResults:
        """
        Convenience method to run simulation from trade list.

        Args:
            trades: List of trade dictionaries
            initial_capital: Starting capital
            future_trades: Number of future trades to simulate
            position_size_pct: Position size percentage

        Returns:
            MonteCarloResults
        """
        stats = self.extract_trade_statistics(trades)
        return self.run_simulation(
            trade_returns=stats.returns,
            initial_capital=initial_capital,
            num_trades=future_trades or stats.num_trades,
            position_size_pct=position_size_pct,
        )

    def generate_report(self, results: MonteCarloResults) -> str:
        """
        Generate human-readable Monte Carlo report.

        Args:
            results: MonteCarloResults object

        Returns:
            Formatted report string
        """
        alpha = 1 - self.confidence_level
        lower_pct = alpha / 2 * 100
        upper_pct = (1 - alpha / 2) * 100

        report = []
        report.append("=" * 80)
        report.append("MONTE CARLO SIMULATION REPORT")
        report.append("=" * 80)

        report.append("\nSimulation Parameters:")
        report.append(f"  Simulations: {results.num_simulations:,}")
        report.append(f"  Trades per simulation: {results.num_trades_per_sim}")
        report.append(f"  Initial capital: ${results.initial_capital:,.2f}")
        report.append(f"  Confidence level: {self.confidence_level:.0%}")
        report.append(f"  Ruin threshold: {self.ruin_threshold:.0%} loss")

        report.append("\nFinal Equity Statistics:")
        report.append(f"  Mean: ${results.mean_final_equity:,.2f}")
        report.append(f"  Median: ${results.median_final_equity:,.2f}")
        report.append(f"  Std Dev: ${results.std_final_equity:,.2f}")
        report.append(f"  Min: ${results.min_final_equity:,.2f}")
        report.append(f"  Max: ${results.max_final_equity:,.2f}")

        report.append(f"\n{self.confidence_level:.0%} Confidence Interval:")
        report.append(f"  Lower ({lower_pct:.0f}%): ${results.percentile_5:,.2f}")
        report.append(f"  Upper ({upper_pct:.0f}%): ${results.percentile_95:,.2f}")

        report.append("\nProbability Analysis:")
        report.append(f"  Probability of Profit: {results.profit_probability:.1%}")
        report.append(f"  Probability of Doubling: {results.double_probability:.1%}")
        report.append(f"  Probability of Ruin: {results.ruin_probability:.1%}")

        report.append("\nReturn Statistics:")
        report.append(f"  Mean Return: {results.mean_return:.1f}%")
        report.append(f"  Median Return: {results.median_return:.1f}%")

        report.append("\nDrawdown Statistics:")
        report.append(f"  Mean Max Drawdown: {results.mean_max_drawdown:.1%}")
        report.append(f"  Median Max Drawdown: {results.median_max_drawdown:.1%}")
        report.append(f"  Worst Max Drawdown: {results.worst_max_drawdown:.1%}")

        # Risk assessment
        report.append("\nRisk Assessment:")
        if results.profit_probability >= 0.8:
            report.append("  [OK] High probability of profit (>80%)")
        elif results.profit_probability >= 0.6:
            report.append("  [WARN] Moderate probability of profit (60-80%)")
        else:
            report.append("  [FAIL] Low probability of profit (<60%)")

        if results.ruin_probability <= 0.01:
            report.append("  [OK] Very low risk of ruin (<1%)")
        elif results.ruin_probability <= 0.05:
            report.append("  [WARN] Moderate risk of ruin (1-5%)")
        else:
            report.append("  [FAIL] High risk of ruin (>5%)")

        if results.worst_max_drawdown <= 0.20:
            report.append("  [OK] Acceptable worst-case drawdown (<20%)")
        elif results.worst_max_drawdown <= 0.30:
            report.append("  [WARN] Moderate worst-case drawdown (20-30%)")
        else:
            report.append("  [FAIL] High worst-case drawdown (>30%)")

        report.append("\n" + "=" * 80)

        return "\n".join(report)

    def is_statistically_significant(
        self,
        results: MonteCarloResults,
        min_profit_probability: float = 0.6,
        max_ruin_probability: float = 0.05,
        min_sharpe: float = 0.5,
    ) -> tuple[bool, list[str]]:
        """
        Determine if strategy results are statistically significant.

        Args:
            results: Monte Carlo simulation results
            min_profit_probability: Minimum required profit probability
            max_ruin_probability: Maximum acceptable ruin probability
            min_sharpe: Minimum acceptable median Sharpe ratio

        Returns:
            Tuple of (is_valid, list of failure reasons)
        """
        failures = []

        if results.profit_probability < min_profit_probability:
            failures.append(
                f"Profit probability {results.profit_probability:.1%} < {min_profit_probability:.0%}"
            )

        if results.ruin_probability > max_ruin_probability:
            failures.append(
                f"Ruin probability {results.ruin_probability:.1%} > {max_ruin_probability:.0%}"
            )

        median_sharpe = np.median(results.sharpe_distribution)
        if median_sharpe < min_sharpe:
            failures.append(f"Median Sharpe {median_sharpe:.2f} < {min_sharpe:.1f}")

        return len(failures) == 0, failures


def run_monte_carlo_analysis(
    trades: list[dict[str, Any]],
    initial_capital: float = 100000.0,
    num_simulations: int = 10000,
    future_trades: Optional[int] = None,
) -> MonteCarloResults:
    """
    Convenience function to run Monte Carlo analysis.

    Args:
        trades: List of historical trade dictionaries
        initial_capital: Starting capital
        num_simulations: Number of simulation paths
        future_trades: Number of future trades to simulate

    Returns:
        MonteCarloResults object

    Example:
        >>> trades = [
        ...     {"return_pct": 2.5},
        ...     {"return_pct": -1.0},
        ...     {"return_pct": 3.0},
        ...     {"return_pct": -0.5},
        ... ]
        >>> results = run_monte_carlo_analysis(trades, num_simulations=1000)
        >>> print(f"Profit probability: {results.profit_probability:.1%}")
    """
    simulator = MonteCarloSimulator(num_simulations=num_simulations)
    return simulator.run_from_trades(
        trades=trades,
        initial_capital=initial_capital,
        future_trades=future_trades,
    )
