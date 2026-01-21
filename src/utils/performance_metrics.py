"""
Performance Metrics Module - Risk-adjusted return calculations.

Provides proper calculation of:
- Annualized Sharpe Ratio (with risk-free rate)
- Sortino Ratio (downside deviation only)
- Calmar Ratio (return / max drawdown)
- Max Drawdown
- Rolling Sharpe analysis

Based on industry best practices:
- https://www.quantstart.com/articles/Sharpe-Ratio-for-Algorithmic-Trading-Performance-Measurement/
- https://blog.quantinsti.com/sharpe-ratio-applications-algorithmic-trading/

Author: AI Trading System
Created: January 21, 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Default risk-free rate (current 3-month T-bill ~4.5% as of Jan 2026)
DEFAULT_RISK_FREE_RATE = 0.045

# Trading days per year for annualization
TRADING_DAYS_PER_YEAR = 252


@dataclass
class PerformanceMetrics:
    """Container for all performance metrics."""

    # Core metrics
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float

    # Risk metrics
    volatility: float
    downside_deviation: float
    max_drawdown: float
    max_drawdown_duration: int  # in trading days

    # Trade statistics
    total_trades: int
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float

    # Rolling metrics
    rolling_sharpe_mean: Optional[float] = None
    rolling_sharpe_std: Optional[float] = None
    sharpe_consistency: Optional[float] = None  # % of windows with Sharpe > 1

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_return": round(self.total_return, 4),
            "annualized_return": round(self.annualized_return, 4),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "sortino_ratio": round(self.sortino_ratio, 4),
            "calmar_ratio": round(self.calmar_ratio, 4),
            "volatility": round(self.volatility, 4),
            "downside_deviation": round(self.downside_deviation, 4),
            "max_drawdown": round(self.max_drawdown, 4),
            "max_drawdown_duration": self.max_drawdown_duration,
            "total_trades": self.total_trades,
            "win_rate": round(self.win_rate, 4),
            "profit_factor": round(self.profit_factor, 4),
            "avg_win": round(self.avg_win, 2),
            "avg_loss": round(self.avg_loss, 2),
            "largest_win": round(self.largest_win, 2),
            "largest_loss": round(self.largest_loss, 2),
            "rolling_sharpe_mean": round(self.rolling_sharpe_mean, 4)
            if self.rolling_sharpe_mean
            else None,
            "rolling_sharpe_std": round(self.rolling_sharpe_std, 4)
            if self.rolling_sharpe_std
            else None,
            "sharpe_consistency": round(self.sharpe_consistency, 4)
            if self.sharpe_consistency
            else None,
        }


def calculate_annualized_sharpe(
    returns: np.ndarray,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    """
    Calculate annualized Sharpe Ratio.

    Formula: (mean(R) - Rf) / std(R) * sqrt(N)

    Where:
    - R = returns
    - Rf = risk-free rate (per period)
    - N = periods per year

    Args:
        returns: Array of returns (can be daily P/L or % returns)
        risk_free_rate: Annual risk-free rate (default 4.5%)
        periods_per_year: Trading periods per year (252 for daily)

    Returns:
        Annualized Sharpe ratio

    Note: For options strategies with tail risk, Sharpe may overstate
    risk-adjusted performance. Use Sortino as a complement.
    """
    if len(returns) < 2:
        return 0.0

    returns = np.array(returns)
    mean_return = np.mean(returns)
    std_return = np.std(returns, ddof=1)  # Use sample std

    if std_return == 0 or np.isnan(std_return):
        return 0.0

    # Convert annual risk-free rate to per-period
    rf_per_period = risk_free_rate / periods_per_year

    excess_return = mean_return - rf_per_period
    sharpe = (excess_return / std_return) * np.sqrt(periods_per_year)

    return float(sharpe)


def calculate_sortino_ratio(
    returns: np.ndarray,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
    target_return: float = 0.0,
) -> float:
    """
    Calculate Sortino Ratio - uses downside deviation instead of total std.

    Better for options strategies where upside and downside are asymmetric.

    Formula: (mean(R) - target) / downside_deviation * sqrt(N)

    Args:
        returns: Array of returns
        risk_free_rate: Annual risk-free rate
        periods_per_year: Trading periods per year
        target_return: Target return per period (default 0)

    Returns:
        Annualized Sortino ratio
    """
    if len(returns) < 2:
        return 0.0

    returns = np.array(returns)
    mean_return = np.mean(returns)

    # Calculate downside deviation (only negative returns)
    downside_returns = returns[returns < target_return]

    if len(downside_returns) < 1:
        # No downside - infinite Sortino (cap at reasonable value)
        return 10.0

    downside_deviation = np.std(downside_returns, ddof=1)

    if downside_deviation == 0 or np.isnan(downside_deviation):
        return 10.0 if mean_return > 0 else 0.0

    rf_per_period = risk_free_rate / periods_per_year
    excess_return = mean_return - rf_per_period

    sortino = (excess_return / downside_deviation) * np.sqrt(periods_per_year)

    return float(sortino)


def calculate_max_drawdown(equity_curve: np.ndarray) -> tuple[float, int]:
    """
    Calculate maximum drawdown and its duration.

    Args:
        equity_curve: Array of cumulative equity values

    Returns:
        Tuple of (max_drawdown_pct, duration_in_periods)
    """
    if len(equity_curve) < 2:
        return 0.0, 0

    equity_curve = np.array(equity_curve)

    # Running maximum
    running_max = np.maximum.accumulate(equity_curve)

    # Drawdown at each point
    drawdowns = (running_max - equity_curve) / running_max

    max_dd = float(np.max(drawdowns))

    # Find duration of worst drawdown
    peak_idx = np.argmax(running_max[: np.argmax(drawdowns) + 1])
    recovery_indices = np.where(equity_curve[peak_idx:] >= running_max[peak_idx])[0]

    if len(recovery_indices) > 1:
        duration = int(recovery_indices[1])
    else:
        duration = len(equity_curve) - peak_idx  # Still in drawdown

    return max_dd, duration


def calculate_calmar_ratio(
    annualized_return: float,
    max_drawdown: float,
) -> float:
    """
    Calculate Calmar Ratio - return / max drawdown.

    Useful for evaluating risk relative to worst-case scenario.

    Args:
        annualized_return: Annualized return (decimal, e.g., 0.15 for 15%)
        max_drawdown: Maximum drawdown (decimal, e.g., 0.10 for 10%)

    Returns:
        Calmar ratio
    """
    if max_drawdown == 0:
        return 10.0 if annualized_return > 0 else 0.0

    return annualized_return / max_drawdown


def calculate_rolling_sharpe(
    returns: np.ndarray,
    window: int = 20,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
) -> tuple[np.ndarray, float, float, float]:
    """
    Calculate rolling Sharpe ratio for consistency analysis.

    A good strategy should have consistent Sharpe across time windows.
    Target: Sharpe > 1.0 in at least 80% of windows.

    Args:
        returns: Array of returns
        window: Rolling window size (default 20 periods)
        risk_free_rate: Annual risk-free rate

    Returns:
        Tuple of (rolling_sharpes, mean, std, consistency)
        where consistency = % of windows with Sharpe > 1.0
    """
    if len(returns) < window + 1:
        return np.array([]), 0.0, 0.0, 0.0

    returns = np.array(returns)
    rolling_sharpes = []

    for i in range(len(returns) - window + 1):
        window_returns = returns[i : i + window]
        sharpe = calculate_annualized_sharpe(window_returns, risk_free_rate)
        rolling_sharpes.append(sharpe)

    rolling_sharpes = np.array(rolling_sharpes)

    mean_sharpe = float(np.mean(rolling_sharpes))
    std_sharpe = float(np.std(rolling_sharpes))
    consistency = float(np.mean(rolling_sharpes > 1.0))

    return rolling_sharpes, mean_sharpe, std_sharpe, consistency


def calculate_profit_factor(wins: list[float], losses: list[float]) -> float:
    """
    Calculate profit factor = gross profit / gross loss.

    Args:
        wins: List of winning trade amounts (positive)
        losses: List of losing trade amounts (negative)

    Returns:
        Profit factor (> 1.0 is profitable)
    """
    gross_profit = sum(abs(w) for w in wins if w > 0)
    gross_loss = sum(abs(loss) for loss in losses if loss < 0)

    if gross_loss == 0:
        return 10.0 if gross_profit > 0 else 0.0

    return gross_profit / gross_loss


def calculate_all_metrics(
    pnls: list[float],
    initial_capital: float = 5000.0,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> PerformanceMetrics:
    """
    Calculate all performance metrics from a list of P/L values.

    This is the main entry point for comprehensive performance analysis.

    Args:
        pnls: List of trade P/L values (in dollars)
        initial_capital: Starting capital for return calculations
        risk_free_rate: Annual risk-free rate
        periods_per_year: Trading periods per year

    Returns:
        PerformanceMetrics dataclass with all calculated values
    """
    if not pnls:
        return PerformanceMetrics(
            total_return=0.0,
            annualized_return=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            volatility=0.0,
            downside_deviation=0.0,
            max_drawdown=0.0,
            max_drawdown_duration=0,
            total_trades=0,
            win_rate=0.0,
            profit_factor=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            largest_win=0.0,
            largest_loss=0.0,
        )

    pnls = np.array(pnls)

    # Convert P/L to returns (percentage of capital)
    returns = pnls / initial_capital

    # Build equity curve
    equity_curve = initial_capital + np.cumsum(pnls)
    equity_curve = np.insert(equity_curve, 0, initial_capital)

    # Trade statistics
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]

    total_trades = len(pnls)
    win_rate = len(wins) / total_trades if total_trades > 0 else 0.0

    avg_win = float(np.mean(wins)) if len(wins) > 0 else 0.0
    avg_loss = float(np.mean(losses)) if len(losses) > 0 else 0.0
    largest_win = float(np.max(wins)) if len(wins) > 0 else 0.0
    largest_loss = float(np.min(losses)) if len(losses) > 0 else 0.0

    # Return metrics
    total_return = float(np.sum(pnls)) / initial_capital

    # Annualize based on number of trades (assume 1 trade per day max)
    trading_days = len(pnls)
    if trading_days > 0:
        annualized_return = total_return * (periods_per_year / trading_days)
    else:
        annualized_return = 0.0

    # Risk metrics
    volatility = float(np.std(returns, ddof=1)) * np.sqrt(periods_per_year)

    downside_returns = returns[returns < 0]
    downside_deviation = (
        float(np.std(downside_returns, ddof=1)) * np.sqrt(periods_per_year)
        if len(downside_returns) > 0
        else 0.0
    )

    max_drawdown, max_dd_duration = calculate_max_drawdown(equity_curve)

    # Risk-adjusted metrics
    sharpe = calculate_annualized_sharpe(returns, risk_free_rate, periods_per_year)
    sortino = calculate_sortino_ratio(returns, risk_free_rate, periods_per_year)
    calmar = calculate_calmar_ratio(annualized_return, max_drawdown)

    profit_factor = calculate_profit_factor(list(wins), list(losses))

    # Rolling analysis (if enough data)
    rolling_sharpe_mean = None
    rolling_sharpe_std = None
    sharpe_consistency = None

    if len(returns) >= 10:
        _, rolling_sharpe_mean, rolling_sharpe_std, sharpe_consistency = (
            calculate_rolling_sharpe(returns, window=min(20, len(returns) // 2))
        )

    return PerformanceMetrics(
        total_return=total_return,
        annualized_return=annualized_return,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        calmar_ratio=calmar,
        volatility=volatility,
        downside_deviation=downside_deviation,
        max_drawdown=max_drawdown,
        max_drawdown_duration=max_dd_duration,
        total_trades=total_trades,
        win_rate=win_rate,
        profit_factor=profit_factor,
        avg_win=avg_win,
        avg_loss=avg_loss,
        largest_win=largest_win,
        largest_loss=largest_loss,
        rolling_sharpe_mean=rolling_sharpe_mean,
        rolling_sharpe_std=rolling_sharpe_std,
        sharpe_consistency=sharpe_consistency,
    )


def format_metrics_report(metrics: PerformanceMetrics) -> str:
    """
    Format metrics as a readable report.

    Args:
        metrics: PerformanceMetrics object

    Returns:
        Formatted string report
    """
    lines = [
        "=" * 60,
        "PERFORMANCE METRICS REPORT",
        "=" * 60,
        "",
        "RETURNS",
        f"  Total Return:      {metrics.total_return * 100:>8.2f}%",
        f"  Annualized Return: {metrics.annualized_return * 100:>8.2f}%",
        "",
        "RISK-ADJUSTED METRICS",
        f"  Sharpe Ratio:      {metrics.sharpe_ratio:>8.2f}",
        f"  Sortino Ratio:     {metrics.sortino_ratio:>8.2f}",
        f"  Calmar Ratio:      {metrics.calmar_ratio:>8.2f}",
        "",
        "RISK METRICS",
        f"  Volatility (Ann.): {metrics.volatility * 100:>8.2f}%",
        f"  Downside Dev:      {metrics.downside_deviation * 100:>8.2f}%",
        f"  Max Drawdown:      {metrics.max_drawdown * 100:>8.2f}%",
        f"  Max DD Duration:   {metrics.max_drawdown_duration:>8d} days",
        "",
        "TRADE STATISTICS",
        f"  Total Trades:      {metrics.total_trades:>8d}",
        f"  Win Rate:          {metrics.win_rate * 100:>8.2f}%",
        f"  Profit Factor:     {metrics.profit_factor:>8.2f}",
        f"  Avg Win:           ${metrics.avg_win:>7.2f}",
        f"  Avg Loss:          ${metrics.avg_loss:>7.2f}",
        f"  Largest Win:       ${metrics.largest_win:>7.2f}",
        f"  Largest Loss:      ${metrics.largest_loss:>7.2f}",
    ]

    if metrics.rolling_sharpe_mean is not None:
        lines.extend(
            [
                "",
                "ROLLING ANALYSIS",
                f"  Rolling Sharpe (Mean): {metrics.rolling_sharpe_mean:>6.2f}",
                f"  Rolling Sharpe (Std):  {metrics.rolling_sharpe_std:>6.2f}",
                f"  Sharpe Consistency:    {metrics.sharpe_consistency * 100:>6.1f}% windows > 1.0",
            ]
        )

    lines.extend(["", "=" * 60])

    return "\n".join(lines)
