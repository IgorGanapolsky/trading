"""
Daily Target Model - $100/Day Profit Constraint

This module turns "$100/day" from a vibe into a measurable design constraint.
It computes the required returns, acceptable volatility, and risk envelope
needed to realistically achieve the target.

Author: Trading System
Created: 2025-12-03
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TargetMetrics:
    """Metrics showing progress toward daily target."""

    # Core performance
    average_daily_pnl: float
    target_daily_pnl: float = 100.0
    pct_days_hit_target: float = 0.0
    total_trading_days: int = 0
    days_above_target: int = 0

    # Risk metrics
    worst_5day_drawdown: float = 0.0
    worst_20day_drawdown: float = 0.0
    max_single_day_loss: float = 0.0
    daily_volatility: float = 0.0
    sharpe_ratio: float = 0.0

    # Progress indicators
    progress_to_target_pct: float = 0.0
    estimated_days_to_target: int | None = None
    trend_direction: str = "neutral"  # improving, declining, neutral

    # Capital efficiency
    capital_utilized: float = 0.0
    return_on_capital_daily: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "average_daily_pnl": round(self.average_daily_pnl, 2),
            "target_daily_pnl": self.target_daily_pnl,
            "pct_days_hit_target": round(self.pct_days_hit_target, 2),
            "total_trading_days": self.total_trading_days,
            "days_above_target": self.days_above_target,
            "worst_5day_drawdown": round(self.worst_5day_drawdown, 2),
            "worst_20day_drawdown": round(self.worst_20day_drawdown, 2),
            "max_single_day_loss": round(self.max_single_day_loss, 2),
            "daily_volatility": round(self.daily_volatility, 4),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "progress_to_target_pct": round(self.progress_to_target_pct, 2),
            "estimated_days_to_target": self.estimated_days_to_target,
            "trend_direction": self.trend_direction,
            "capital_utilized": round(self.capital_utilized, 2),
            "return_on_capital_daily": round(self.return_on_capital_daily, 4),
        }


@dataclass
class DailyTargetModel:
    """
    Model for computing and tracking the $100/day profit target.

    This class:
    - Computes required daily return given capital and constraints
    - Tracks progress toward target
    - Calculates what's needed to realistically hit $100/day
    - Outputs metrics for every backtest/paper run
    """

    # Configuration
    target_daily_profit: float = 100.0  # North Star: $100/day
    capital: float = 10000.0  # Starting capital
    max_leverage: float = 1.0  # 1.0 = no leverage
    trading_days_per_year: int = 252
    risk_free_rate: float = 0.04  # 4% annual

    # Cost assumptions
    commission_per_trade: float = 0.0  # Alpaca is commission-free
    estimated_slippage_bps: float = 5.0  # 5 basis points
    avg_trades_per_day: int = 1

    # Risk limits
    max_daily_drawdown_pct: float = 3.0  # Max 3% daily loss
    max_20day_drawdown_pct: float = 10.0  # Max 10% over 20 days
    psychological_loss_limit: float = 500.0  # Dollar limit per day

    # Computed fields
    _daily_pnl_history: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._validate_inputs()

    def _validate_inputs(self) -> None:
        """Validate configuration parameters."""
        if self.capital <= 0:
            raise ValueError("Capital must be positive")
        if self.target_daily_profit <= 0:
            raise ValueError("Target daily profit must be positive")
        if self.max_leverage < 1.0:
            raise ValueError("Leverage must be >= 1.0")

    @property
    def required_daily_return_pct(self) -> float:
        """Calculate the required daily return to hit target."""
        effective_capital = self.capital * self.max_leverage
        return (self.target_daily_profit / effective_capital) * 100

    @property
    def required_annual_return_pct(self) -> float:
        """Calculate implied annual return requirement."""
        # Compounding daily returns
        daily_return = self.required_daily_return_pct / 100
        annual = ((1 + daily_return) ** self.trading_days_per_year - 1) * 100
        return annual

    @property
    def daily_cost_estimate(self) -> float:
        """Estimate daily trading costs (slippage + commissions)."""
        avg_trade_size = self.capital * self.max_leverage / max(1, self.avg_trades_per_day)
        slippage_cost = (
            avg_trade_size * (self.estimated_slippage_bps / 10000) * self.avg_trades_per_day
        )
        commission_cost = self.commission_per_trade * self.avg_trades_per_day
        return slippage_cost + commission_cost

    @property
    def required_gross_daily_return(self) -> float:
        """Return needed before costs to achieve target."""
        return self.target_daily_profit + self.daily_cost_estimate

    def compute_minimum_capital_for_target(
        self,
        realistic_daily_return_pct: float = 0.5,  # 0.5% daily is aggressive
    ) -> float:
        """
        Calculate minimum capital needed to hit $100/day target.

        Args:
            realistic_daily_return_pct: Expected daily return percentage

        Returns:
            Minimum capital required
        """
        if realistic_daily_return_pct <= 0:
            return float("inf")

        # Account for costs
        gross_target = self.required_gross_daily_return
        required_capital = gross_target / (realistic_daily_return_pct / 100)
        return required_capital / self.max_leverage

    def compute_required_sharpe(self, target_win_rate: float = 0.55) -> float:
        """
        Calculate required Sharpe ratio for consistent target achievement.

        A higher Sharpe means more consistent returns relative to risk.
        """
        if target_win_rate <= 0.5:
            logger.warning("Win rate below 50% makes target difficult")

        # Required daily return
        daily_return = self.required_daily_return_pct / 100

        # Assume reasonable daily volatility (1-2% for active trading)
        estimated_daily_vol = 0.015  # 1.5% daily volatility

        # Risk-free daily rate
        rf_daily = self.risk_free_rate / self.trading_days_per_year

        # Sharpe = (return - rf) / volatility * sqrt(252)
        required_sharpe = (
            (daily_return - rf_daily) / estimated_daily_vol * math.sqrt(self.trading_days_per_year)
        )

        return required_sharpe

    def add_daily_pnl(self, pnl: float, date: str | None = None) -> None:
        """Record a day's P&L for tracking."""
        self._daily_pnl_history.append(pnl)
        logger.debug(f"Recorded daily P&L: ${pnl:.2f} for {date or 'today'}")

    def calculate_metrics(self) -> TargetMetrics:
        """
        Calculate comprehensive metrics from P&L history.

        Returns:
            TargetMetrics object with all progress indicators
        """
        if not self._daily_pnl_history:
            return TargetMetrics(
                average_daily_pnl=0.0,
                target_daily_pnl=self.target_daily_profit,
            )

        import numpy as np

        pnl_array = np.array(self._daily_pnl_history)

        # Basic stats
        avg_daily = float(np.mean(pnl_array))
        total_days = len(pnl_array)
        days_above = int(np.sum(pnl_array >= self.target_daily_profit))
        pct_hit = (days_above / total_days) * 100 if total_days > 0 else 0.0

        # Volatility and Sharpe
        daily_vol = float(np.std(pnl_array)) if len(pnl_array) > 1 else 0.0
        rf_daily = self.risk_free_rate / self.trading_days_per_year
        excess_return = avg_daily / self.capital - rf_daily
        sharpe = (
            (excess_return / (daily_vol / self.capital)) * math.sqrt(252) if daily_vol > 0 else 0.0
        )

        # Drawdown calculations
        cumulative = np.cumsum(pnl_array)
        running_max = np.maximum.accumulate(cumulative)
        cumulative - running_max

        # Rolling drawdowns
        worst_5d = (
            float(np.min(np.convolve(pnl_array, np.ones(5), mode="valid")))
            if len(pnl_array) >= 5
            else float(np.min(pnl_array))
        )
        worst_20d = (
            float(np.min(np.convolve(pnl_array, np.ones(20), mode="valid")))
            if len(pnl_array) >= 20
            else float(np.min(pnl_array))
        )
        max_loss = float(np.min(pnl_array))

        # Progress to target
        progress = (
            (avg_daily / self.target_daily_profit) * 100 if self.target_daily_profit > 0 else 0.0
        )

        # Trend direction (compare last 5 days to previous 5)
        if len(pnl_array) >= 10:
            recent_avg = float(np.mean(pnl_array[-5:]))
            prior_avg = float(np.mean(pnl_array[-10:-5]))
            if recent_avg > prior_avg * 1.05:
                trend = "improving"
            elif recent_avg < prior_avg * 0.95:
                trend = "declining"
            else:
                trend = "neutral"
        else:
            trend = "neutral"

        # Estimated days to target (if improving)
        est_days = None
        if avg_daily > 0 and avg_daily < self.target_daily_profit:
            # Very rough estimate - assumes linear improvement
            improvement_rate = (
                (self.target_daily_profit - avg_daily) / avg_daily
                if avg_daily > 0
                else float("inf")
            )
            est_days = int(improvement_rate * total_days) if improvement_rate < 1000 else None

        return TargetMetrics(
            average_daily_pnl=avg_daily,
            target_daily_pnl=self.target_daily_profit,
            pct_days_hit_target=pct_hit,
            total_trading_days=total_days,
            days_above_target=days_above,
            worst_5day_drawdown=worst_5d,
            worst_20day_drawdown=worst_20d,
            max_single_day_loss=max_loss,
            daily_volatility=daily_vol,
            sharpe_ratio=sharpe,
            progress_to_target_pct=progress,
            estimated_days_to_target=est_days,
            trend_direction=trend,
            capital_utilized=self.capital,
            return_on_capital_daily=avg_daily / self.capital if self.capital > 0 else 0.0,
        )

    def generate_target_report(self) -> str:
        """Generate a human-readable report on target progress."""
        metrics = self.calculate_metrics()

        report = []
        report.append("=" * 60)
        report.append("$100/DAY TARGET PROGRESS REPORT")
        report.append("=" * 60)
        report.append("")

        # Progress bar
        progress = min(100, max(0, metrics.progress_to_target_pct))
        bar_filled = int(progress / 5)
        bar = "█" * bar_filled + "░" * (20 - bar_filled)
        report.append(f"Progress: [{bar}] {progress:.1f}%")
        report.append("")

        # Core metrics
        report.append("CORE METRICS")
        report.append("-" * 40)
        report.append(f"  Average Daily P&L:     ${metrics.average_daily_pnl:>10.2f}")
        report.append(f"  Target Daily P&L:      ${metrics.target_daily_pnl:>10.2f}")
        report.append(
            f"  Gap to Target:         ${(metrics.target_daily_pnl - metrics.average_daily_pnl):>10.2f}"
        )
        report.append(
            f"  Days Above Target:     {metrics.days_above_target:>10} / {metrics.total_trading_days}"
        )
        report.append(f"  Hit Rate:              {metrics.pct_days_hit_target:>10.1f}%")
        report.append("")

        # Risk metrics
        report.append("RISK METRICS")
        report.append("-" * 40)
        report.append(f"  Daily Volatility:      ${metrics.daily_volatility:>10.2f}")
        report.append(f"  Sharpe Ratio:          {metrics.sharpe_ratio:>10.2f}")
        report.append(f"  Max Single Day Loss:   ${metrics.max_single_day_loss:>10.2f}")
        report.append(f"  Worst 5-Day Drawdown:  ${metrics.worst_5day_drawdown:>10.2f}")
        report.append(f"  Worst 20-Day Drawdown: ${metrics.worst_20day_drawdown:>10.2f}")
        report.append("")

        # Capital analysis
        report.append("CAPITAL ANALYSIS")
        report.append("-" * 40)
        report.append(f"  Capital Deployed:      ${metrics.capital_utilized:>10.2f}")
        report.append(f"  Daily Return on Cap:   {metrics.return_on_capital_daily * 100:>10.4f}%")
        report.append(f"  Required Daily Return: {self.required_daily_return_pct:>10.4f}%")

        # Feasibility check
        min_capital = self.compute_minimum_capital_for_target()
        report.append(f"  Min Capital for Target: ${min_capital:>9.2f}")
        report.append("")

        # Trend and outlook
        report.append("OUTLOOK")
        report.append("-" * 40)
        trend_emoji = {"improving": "📈", "declining": "📉", "neutral": "➡️"}
        report.append(
            f"  Trend Direction:       {trend_emoji.get(metrics.trend_direction, '')} {metrics.trend_direction}"
        )
        if metrics.estimated_days_to_target:
            report.append(f"  Est. Days to Target:   {metrics.estimated_days_to_target}")
        report.append("")

        report.append("=" * 60)

        return "\n".join(report)

    def save_metrics(self, filepath: str | Path | None = None) -> Path:
        """Save metrics to JSON file."""
        if filepath is None:
            filepath = Path("data/target_metrics.json")
        else:
            filepath = Path(filepath)

        filepath.parent.mkdir(parents=True, exist_ok=True)

        metrics = self.calculate_metrics()
        data = {
            "timestamp": datetime.now().isoformat(),
            "config": {
                "target_daily_profit": self.target_daily_profit,
                "capital": self.capital,
                "max_leverage": self.max_leverage,
            },
            "metrics": metrics.to_dict(),
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved target metrics to {filepath}")
        return filepath

    @classmethod
    def from_backtest_results(
        cls,
        equity_curve: list[float],
        initial_capital: float = 10000.0,
        target_daily_profit: float = 100.0,
    ) -> DailyTargetModel:
        """
        Create a DailyTargetModel from backtest equity curve.

        Args:
            equity_curve: List of daily portfolio values
            initial_capital: Starting capital
            target_daily_profit: Daily profit target

        Returns:
            DailyTargetModel with P&L history populated
        """
        model = cls(
            target_daily_profit=target_daily_profit,
            capital=initial_capital,
        )

        # Convert equity curve to daily P&L
        for i in range(1, len(equity_curve)):
            daily_pnl = equity_curve[i] - equity_curve[i - 1]
            model.add_daily_pnl(daily_pnl)

        return model


# Convenience function for integration
def evaluate_backtest_vs_target(
    equity_curve: list[float],
    initial_capital: float = 10000.0,
    target: float = 100.0,
) -> tuple[TargetMetrics, str]:
    """
    Evaluate a backtest against the $100/day target.

    Returns:
        Tuple of (metrics, report_string)
    """
    model = DailyTargetModel.from_backtest_results(
        equity_curve=equity_curve,
        initial_capital=initial_capital,
        target_daily_profit=target,
    )
    metrics = model.calculate_metrics()
    report = model.generate_target_report()
    return metrics, report
