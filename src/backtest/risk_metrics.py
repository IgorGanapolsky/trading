#!/usr/bin/env python3
"""
Advanced Risk Metrics for Backtesting

Provides industry-standard risk metrics for evaluating trading strategies:
- Sharpe Ratio (annualized, with proper edge case handling)
- Sortino Ratio (downside deviation only)
- Calmar Ratio (return / max drawdown)
- Maximum Drawdown
- Value at Risk (VaR)
- Expected Shortfall (CVaR)

Reference: Phil Town Rule #1 - Don't Lose Money
These metrics help validate that capital preservation is maintained.
"""

from dataclasses import dataclass

import numpy as np


@dataclass
class RiskMetrics:
    """Container for all risk metrics from a backtest."""

    # Return metrics
    total_return: float
    annualized_return: float
    avg_trade_return: float

    # Risk-adjusted returns
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float

    # Drawdown metrics
    max_drawdown: float
    max_drawdown_duration: int  # in trading days
    avg_drawdown: float

    # Tail risk
    var_95: float  # 95% Value at Risk
    cvar_95: float  # 95% Conditional VaR (Expected Shortfall)

    # Trade statistics
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    win_loss_ratio: float

    # Consistency metrics
    std_dev: float
    downside_dev: float
    skewness: float
    kurtosis: float

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_return": round(self.total_return, 2),
            "annualized_return": round(self.annualized_return, 4),
            "avg_trade_return": round(self.avg_trade_return, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 3),
            "sortino_ratio": round(self.sortino_ratio, 3),
            "calmar_ratio": round(self.calmar_ratio, 3),
            "max_drawdown": round(self.max_drawdown, 4),
            "max_drawdown_duration": self.max_drawdown_duration,
            "avg_drawdown": round(self.avg_drawdown, 4),
            "var_95": round(self.var_95, 2),
            "cvar_95": round(self.cvar_95, 2),
            "win_rate": round(self.win_rate, 4),
            "profit_factor": round(self.profit_factor, 3),
            "avg_win": round(self.avg_win, 2),
            "avg_loss": round(self.avg_loss, 2),
            "win_loss_ratio": round(self.win_loss_ratio, 3),
            "std_dev": round(self.std_dev, 2),
            "downside_dev": round(self.downside_dev, 2),
            "skewness": round(self.skewness, 3),
            "kurtosis": round(self.kurtosis, 3),
        }

    def is_phil_town_compliant(self) -> tuple[bool, list[str]]:
        """
        Check if strategy meets Phil Town Rule #1 requirements.

        Returns:
            (compliant, violations) tuple
        """
        violations = []

        # Rule #1: Don't lose money
        if self.total_return < 0:
            violations.append(f"Total return is negative: ${self.total_return:.2f}")

        # Max drawdown should be limited (5% per CEO mandate)
        if self.max_drawdown > 0.05:
            violations.append(f"Max drawdown {self.max_drawdown:.1%} exceeds 5% limit")

        # Profit factor should be > 1 (make more than you lose)
        if self.profit_factor < 1.0:
            violations.append(f"Profit factor {self.profit_factor:.2f} < 1.0")

        # Win rate should support profitability
        if self.win_rate < 0.50 and self.win_loss_ratio < 2.0:
            violations.append(
                f"Low win rate {self.win_rate:.1%} without compensating win/loss ratio"
            )

        return len(violations) == 0, violations


def calculate_sharpe_ratio(
    returns: np.ndarray,
    risk_free_rate: float = 0.05,
    periods_per_year: int = 252,
    min_observations: int = 10,
) -> float:
    """
    Calculate annualized Sharpe Ratio with proper edge case handling.

    Args:
        returns: Array of trade returns (in dollars or percentages)
        risk_free_rate: Annual risk-free rate (default 5%)
        periods_per_year: Trading periods per year (252 for daily)
        min_observations: Minimum observations required

    Returns:
        Annualized Sharpe Ratio (0.0 if insufficient data or zero variance)
    """
    if len(returns) < min_observations:
        return 0.0

    excess_returns = returns - (risk_free_rate / periods_per_year)
    std = np.std(excess_returns, ddof=1)

    # Handle zero or near-zero variance (degenerate case)
    if std < 1e-10:
        # If all returns are positive, return a high but capped Sharpe
        mean_return = np.mean(excess_returns)
        if mean_return > 0:
            return 3.0  # Cap at 3.0 for "perfect" strategies
        elif mean_return < 0:
            return -3.0  # Cap at -3.0 for consistently losing strategies
        return 0.0

    # Annualized Sharpe = (mean excess return / std) * sqrt(periods_per_year)
    sharpe = (np.mean(excess_returns) / std) * np.sqrt(periods_per_year)

    return float(sharpe)


def calculate_sortino_ratio(
    returns: np.ndarray,
    risk_free_rate: float = 0.05,
    periods_per_year: int = 252,
    target_return: float = 0.0,
) -> float:
    """
    Calculate annualized Sortino Ratio (uses downside deviation only).

    The Sortino ratio is more appropriate for trading strategies because
    it only penalizes downside volatility, not upside.

    Args:
        returns: Array of trade returns
        risk_free_rate: Annual risk-free rate
        periods_per_year: Trading periods per year
        target_return: Minimum acceptable return (usually 0)

    Returns:
        Annualized Sortino Ratio
    """
    if len(returns) < 10:
        return 0.0

    # Calculate downside deviation (only negative returns below target)
    downside_returns = returns[returns < target_return] - target_return
    if len(downside_returns) == 0:
        # No downside = perfect strategy, return high value
        return 3.0 if np.mean(returns) > 0 else 0.0

    downside_dev = np.sqrt(np.mean(downside_returns**2))

    if downside_dev < 1e-10:
        return 3.0 if np.mean(returns) > 0 else 0.0

    excess_return = np.mean(returns) - (risk_free_rate / periods_per_year)
    sortino = (excess_return / downside_dev) * np.sqrt(periods_per_year)

    return float(sortino)


def calculate_max_drawdown(equity_curve: np.ndarray) -> tuple[float, int]:
    """
    Calculate maximum drawdown and its duration.

    Args:
        equity_curve: Cumulative equity values over time

    Returns:
        (max_drawdown_percentage, duration_in_periods)
    """
    if len(equity_curve) < 2:
        return 0.0, 0

    # Calculate running maximum
    running_max = np.maximum.accumulate(equity_curve)

    # Calculate drawdown at each point
    drawdowns = (running_max - equity_curve) / running_max

    # Find maximum drawdown
    max_dd = float(np.max(drawdowns))

    # Calculate duration of max drawdown
    max_dd_idx = np.argmax(drawdowns)
    # Find when we recovered (or end of series)
    recovery_idx = max_dd_idx
    while recovery_idx < len(equity_curve) - 1:
        if equity_curve[recovery_idx] >= running_max[max_dd_idx]:
            break
        recovery_idx += 1

    duration = recovery_idx - max_dd_idx

    return max_dd, duration


def calculate_var_cvar(returns: np.ndarray, confidence: float = 0.95) -> tuple[float, float]:
    """
    Calculate Value at Risk (VaR) and Conditional VaR (Expected Shortfall).

    VaR: The maximum expected loss at a given confidence level
    CVaR: The expected loss given that loss exceeds VaR

    Args:
        returns: Array of trade returns
        confidence: Confidence level (0.95 = 95%)

    Returns:
        (VaR, CVaR) tuple - both as positive values representing losses
    """
    if len(returns) < 10:
        return 0.0, 0.0

    # Sort returns (worst to best)
    sorted_returns = np.sort(returns)

    # VaR is the return at the (1-confidence) percentile
    var_idx = int((1 - confidence) * len(sorted_returns))
    var = -sorted_returns[var_idx]  # Convert to positive loss value

    # CVaR is the average of returns worse than VaR
    cvar = -np.mean(sorted_returns[: var_idx + 1]) if var_idx > 0 else var

    return max(0, float(var)), max(0, float(cvar))


def calculate_risk_metrics(
    trade_pnls: list[float],
    initial_capital: float = 5000.0,
    risk_free_rate: float = 0.05,
    periods_per_year: int = 252,
) -> RiskMetrics:
    """
    Calculate comprehensive risk metrics from trade P/Ls.

    Args:
        trade_pnls: List of trade P/L values in dollars
        initial_capital: Starting capital
        risk_free_rate: Annual risk-free rate
        periods_per_year: Trading periods per year

    Returns:
        RiskMetrics dataclass with all calculated metrics
    """
    pnls = np.array(trade_pnls, dtype=float)
    n_trades = len(pnls)

    if n_trades == 0:
        # Return zero metrics for empty trades
        return RiskMetrics(
            total_return=0.0,
            annualized_return=0.0,
            avg_trade_return=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            max_drawdown=0.0,
            max_drawdown_duration=0,
            avg_drawdown=0.0,
            var_95=0.0,
            cvar_95=0.0,
            win_rate=0.0,
            profit_factor=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            win_loss_ratio=0.0,
            std_dev=0.0,
            downside_dev=0.0,
            skewness=0.0,
            kurtosis=0.0,
        )

    # Basic return metrics
    total_return = float(np.sum(pnls))
    avg_trade_return = float(np.mean(pnls))

    # Annualized return (assuming trades are spread over the year)
    # For n trades over 252 days, annualized = total_return * (252 / n_trades)
    annualized_return = (total_return / initial_capital) * (periods_per_year / max(n_trades, 1))

    # Build equity curve
    equity_curve = initial_capital + np.cumsum(pnls)

    # Risk-adjusted returns
    sharpe = calculate_sharpe_ratio(pnls, risk_free_rate, periods_per_year)
    sortino = calculate_sortino_ratio(pnls, risk_free_rate, periods_per_year)

    # Drawdown metrics
    max_dd, max_dd_duration = calculate_max_drawdown(equity_curve)
    running_max = np.maximum.accumulate(equity_curve)
    drawdowns = (running_max - equity_curve) / running_max
    avg_dd = float(np.mean(drawdowns))

    # Calmar ratio = annualized return / max drawdown
    calmar = annualized_return / max_dd if max_dd > 0.01 else 0.0

    # VaR and CVaR
    var_95, cvar_95 = calculate_var_cvar(pnls)

    # Trade statistics
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]

    win_rate = len(wins) / n_trades if n_trades > 0 else 0.0
    avg_win = float(np.mean(wins)) if len(wins) > 0 else 0.0
    avg_loss = float(np.mean(losses)) if len(losses) > 0 else 0.0

    gross_profit = float(np.sum(wins)) if len(wins) > 0 else 0.0
    gross_loss = abs(float(np.sum(losses))) if len(losses) > 0 else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    win_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float("inf")

    # Consistency metrics
    std_dev = float(np.std(pnls, ddof=1)) if n_trades > 1 else 0.0

    downside_pnls = pnls[pnls < 0]
    downside_dev = float(np.std(downside_pnls, ddof=1)) if len(downside_pnls) > 1 else 0.0

    # Higher moments
    if n_trades > 3 and std_dev > 0:
        skewness = float(((pnls - avg_trade_return) ** 3).mean() / std_dev**3)
        kurtosis = float(((pnls - avg_trade_return) ** 4).mean() / std_dev**4 - 3)
    else:
        skewness = 0.0
        kurtosis = 0.0

    return RiskMetrics(
        total_return=total_return,
        annualized_return=annualized_return,
        avg_trade_return=avg_trade_return,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        calmar_ratio=calmar,
        max_drawdown=max_dd,
        max_drawdown_duration=max_dd_duration,
        avg_drawdown=avg_dd,
        var_95=var_95,
        cvar_95=cvar_95,
        win_rate=win_rate,
        profit_factor=profit_factor,
        avg_win=avg_win,
        avg_loss=avg_loss,
        win_loss_ratio=win_loss_ratio,
        std_dev=std_dev,
        downside_dev=downside_dev,
        skewness=skewness,
        kurtosis=kurtosis,
    )


def generate_risk_report(metrics: RiskMetrics, strategy_name: str = "Iron Condor") -> str:
    """Generate a human-readable risk report."""
    compliant, violations = metrics.is_phil_town_compliant()

    report = f"""
{"=" * 60}
RISK METRICS REPORT: {strategy_name}
{"=" * 60}

RETURN METRICS
  Total Return:        ${metrics.total_return:,.2f}
  Annualized Return:   {metrics.annualized_return:.2%}
  Avg Trade Return:    ${metrics.avg_trade_return:.2f}

RISK-ADJUSTED RETURNS
  Sharpe Ratio:        {metrics.sharpe_ratio:.3f}
  Sortino Ratio:       {metrics.sortino_ratio:.3f}
  Calmar Ratio:        {metrics.calmar_ratio:.3f}

DRAWDOWN ANALYSIS
  Max Drawdown:        {metrics.max_drawdown:.2%}
  Max DD Duration:     {metrics.max_drawdown_duration} periods
  Avg Drawdown:        {metrics.avg_drawdown:.2%}

TAIL RISK (95% Confidence)
  Value at Risk:       ${metrics.var_95:.2f}
  Expected Shortfall:  ${metrics.cvar_95:.2f}

TRADE STATISTICS
  Win Rate:            {metrics.win_rate:.1%}
  Profit Factor:       {metrics.profit_factor:.2f}
  Avg Win:             ${metrics.avg_win:.2f}
  Avg Loss:            ${metrics.avg_loss:.2f}
  Win/Loss Ratio:      {metrics.win_loss_ratio:.2f}

CONSISTENCY
  Std Deviation:       ${metrics.std_dev:.2f}
  Downside Dev:        ${metrics.downside_dev:.2f}
  Skewness:            {metrics.skewness:.3f}
  Kurtosis:            {metrics.kurtosis:.3f}

PHIL TOWN RULE #1 COMPLIANCE
  Status:              {"COMPLIANT" if compliant else "VIOLATIONS FOUND"}
"""
    if violations:
        report += "  Violations:\n"
        for v in violations:
            report += f"    - {v}\n"

    report += "=" * 60

    return report


def calculate_rolling_sharpe(
    returns: np.ndarray,
    window_size: int = 20,
    risk_free_rate: float = 0.05,
    periods_per_year: int = 252,
) -> tuple[np.ndarray, float]:
    """
    Calculate rolling Sharpe ratio to detect regime changes.

    Industry best practice: Sharpe should exceed 1.0 in at least 80% of windows
    to indicate strategy robustness.

    Args:
        returns: Array of trade returns
        window_size: Rolling window size (default 20 trades)
        risk_free_rate: Annual risk-free rate
        periods_per_year: Trading periods per year

    Returns:
        (rolling_sharpes, consistency_ratio) where consistency_ratio is
        the fraction of windows with Sharpe > 1.0
    """
    if len(returns) < window_size:
        return np.array([]), 0.0

    n_windows = len(returns) - window_size + 1
    rolling_sharpes = np.zeros(n_windows)

    for i in range(n_windows):
        window_returns = returns[i : i + window_size]
        rolling_sharpes[i] = calculate_sharpe_ratio(
            window_returns, risk_free_rate, periods_per_year, min_observations=5
        )

    # Calculate consistency (fraction of windows with Sharpe > 1.0)
    consistency = np.mean(rolling_sharpes > 1.0)

    return rolling_sharpes, float(consistency)


def monte_carlo_sharpe_confidence(
    returns: np.ndarray,
    n_simulations: int = 1000,
    confidence_level: float = 0.95,
    risk_free_rate: float = 0.05,
    periods_per_year: int = 252,
) -> tuple[float, float, float]:
    """
    Calculate bootstrap confidence interval for Sharpe ratio.

    Industry insight: Backtested Sharpe ratios typically overstate live
    performance by 30-50%. This provides statistical bounds.

    Args:
        returns: Array of trade returns
        n_simulations: Number of bootstrap samples
        confidence_level: Confidence level (0.95 = 95%)
        risk_free_rate: Annual risk-free rate
        periods_per_year: Trading periods per year

    Returns:
        (sharpe_estimate, lower_bound, upper_bound) tuple
    """
    if len(returns) < 10:
        return 0.0, 0.0, 0.0

    # Bootstrap sampling
    bootstrap_sharpes = np.zeros(n_simulations)
    n_samples = len(returns)

    for i in range(n_simulations):
        # Sample with replacement
        sample_idx = np.random.randint(0, n_samples, size=n_samples)
        sample_returns = returns[sample_idx]
        bootstrap_sharpes[i] = calculate_sharpe_ratio(
            sample_returns, risk_free_rate, periods_per_year, min_observations=5
        )

    # Calculate confidence interval
    alpha = 1 - confidence_level
    lower_bound = float(np.percentile(bootstrap_sharpes, alpha / 2 * 100))
    upper_bound = float(np.percentile(bootstrap_sharpes, (1 - alpha / 2) * 100))
    estimate = float(np.mean(bootstrap_sharpes))

    return estimate, lower_bound, upper_bound


def benchmark_comparison(
    strategy_returns: np.ndarray,
    benchmark_returns: np.ndarray,
    risk_free_rate: float = 0.05,
    periods_per_year: int = 252,
) -> dict:
    """
    Compare strategy performance to a benchmark (e.g., SPY buy-and-hold).

    Args:
        strategy_returns: Strategy trade returns
        benchmark_returns: Benchmark returns (same period)
        risk_free_rate: Annual risk-free rate
        periods_per_year: Trading periods per year

    Returns:
        Dictionary with comparison metrics
    """
    strategy_sharpe = calculate_sharpe_ratio(
        strategy_returns, risk_free_rate, periods_per_year
    )
    benchmark_sharpe = calculate_sharpe_ratio(
        benchmark_returns, risk_free_rate, periods_per_year
    )

    # Information ratio = (strategy return - benchmark return) / tracking error
    excess_returns = strategy_returns - benchmark_returns
    tracking_error = np.std(excess_returns, ddof=1) if len(excess_returns) > 1 else 0.0
    info_ratio = (
        np.mean(excess_returns) / tracking_error if tracking_error > 0 else 0.0
    )

    return {
        "strategy_sharpe": round(strategy_sharpe, 3),
        "benchmark_sharpe": round(benchmark_sharpe, 3),
        "sharpe_difference": round(strategy_sharpe - benchmark_sharpe, 3),
        "outperforms_benchmark": strategy_sharpe > benchmark_sharpe,
        "information_ratio": round(info_ratio, 3),
        "tracking_error": round(tracking_error, 2),
        "alpha": round(
            float(np.sum(strategy_returns) - np.sum(benchmark_returns)), 2
        ),
    }


def validate_backtest_realism(metrics: RiskMetrics) -> tuple[bool, list[str]]:
    """
    Validate backtest results for realism (detect potential overfitting).

    Industry insight: Backtested Sharpe > 2.5 or Win Rate > 90% often
    indicates overfitting or unrealistic assumptions.

    Returns:
        (is_realistic, warnings) tuple
    """
    warnings = []

    # Sharpe > 2.5 is suspicious for options strategies
    if metrics.sharpe_ratio > 2.5:
        warnings.append(
            f"Sharpe ratio {metrics.sharpe_ratio:.2f} > 2.5 may indicate overfitting"
        )

    # Win rate > 90% is suspicious
    if metrics.win_rate > 0.90:
        warnings.append(
            f"Win rate {metrics.win_rate:.1%} > 90% may be unrealistic"
        )

    # Sortino >> Sharpe suggests tail risk underestimation
    if metrics.sortino_ratio > metrics.sharpe_ratio * 2:
        warnings.append(
            "Sortino/Sharpe ratio suggests possible tail risk underestimation"
        )

    # Zero or near-zero std_dev indicates degenerate results
    if metrics.std_dev < 1.0 and metrics.total_return != 0:
        warnings.append(
            f"Std dev ${metrics.std_dev:.2f} is suspiciously low - check for data issues"
        )

    # Negative kurtosis indicates thinner tails than normal
    if metrics.kurtosis < -1.0:
        warnings.append(
            f"Negative kurtosis {metrics.kurtosis:.2f} suggests unrealistic return distribution"
        )

    return len(warnings) == 0, warnings


# CLI for testing
if __name__ == "__main__":
    # Example usage with sample data
    sample_pnls = [40, 40, 40, -80, 60, 40, 40, -120, 40, 40, 80, 40, -40, 60, 40, 40, 40, 40]

    metrics = calculate_risk_metrics(sample_pnls, initial_capital=5000.0)
    print(generate_risk_report(metrics))

    # New: Rolling Sharpe analysis
    pnls_array = np.array(sample_pnls, dtype=float)
    rolling_sharpes, consistency = calculate_rolling_sharpe(pnls_array, window_size=10)
    print(f"\nRolling Sharpe Consistency (>1.0): {consistency:.1%}")

    # New: Bootstrap confidence interval
    estimate, lower, upper = monte_carlo_sharpe_confidence(pnls_array)
    print(f"Sharpe 95% CI: [{lower:.3f}, {upper:.3f}] (est: {estimate:.3f})")

    # New: Realism validation
    is_realistic, warnings = validate_backtest_realism(metrics)
    if not is_realistic:
        print("\nREALISM WARNINGS:")
        for w in warnings:
            print(f"  - {w}")

    print("\nJSON Output:")
    import json

    print(json.dumps(metrics.to_dict(), indent=2))
