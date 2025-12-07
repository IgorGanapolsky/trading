"""
Target Model Module - $100/day Net Income Constraint

This module encodes the $100/day net income target as an explicit design constraint.
It computes required metrics, capital requirements, and feasibility analysis.

Author: Trading System
Created: 2025-12-02
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# North Star Target
TARGET_DAILY_NET_INCOME = 100.0  # $100/day


@dataclass
class TargetModelConfig:
    """Configuration for target model calculations."""

    target_daily_net_income: float = TARGET_DAILY_NET_INCOME
    capital: float = 100000.0  # Starting capital
    max_leverage: float = 1.0  # No leverage by default
    trading_frequency: float = 252.0  # Trading days per year
    commission_per_trade: float = 0.0  # Alpaca has no commissions
    slippage_bps: float = 5.0  # 5 basis points slippage
    max_daily_loss_pct: float = 2.0  # Max 2% daily loss
    max_drawdown_pct: float = 10.0  # Max 10% drawdown


@dataclass
class TargetModelMetrics:
    """Metrics computed from target model."""

    # Required metrics to hit target
    required_daily_return_pct: float
    required_annual_return_pct: float
    required_sharpe_ratio: float  # Estimated based on volatility assumptions

    # Feasibility analysis
    min_capital_required: float
    feasible_with_current_capital: bool

    # Risk constraints
    max_volatility_pct: float  # Max volatility to stay within risk limits
    max_position_size: float  # Max position size given risk limits

    # Cost analysis
    estimated_daily_costs: float  # Commissions, slippage, etc.
    net_after_costs: float  # Target net of costs

    # Psychological/financial limits
    worst_5day_drawdown_limit: float
    worst_20day_drawdown_limit: float


class TargetModel:
    """
    Target model that encodes $100/day net income as a design constraint.

    Computes:
    - Required daily return percentage
    - Minimum capital requirements
    - Risk limits aligned to target
    - Feasibility analysis
    """

    def __init__(self, config: TargetModelConfig | None = None):
        """
        Initialize target model.

        Args:
            config: Target model configuration. If None, uses defaults.
        """
        self.config = config or TargetModelConfig()

    def compute_metrics(self) -> TargetModelMetrics:
        """
        Compute all target model metrics.

        Returns:
            TargetModelMetrics with all computed values
        """
        # Required daily return (before costs)
        daily_costs = self._estimate_daily_costs()
        gross_target = self.config.target_daily_net_income + daily_costs
        required_daily_return_pct = (gross_target / self.config.capital) * 100

        # Required annual return
        required_annual_return_pct = required_daily_return_pct * (
            self.config.trading_frequency / 100
        )

        # Estimate required Sharpe ratio (assuming 15% volatility)
        # Sharpe = (Return - RiskFree) / Volatility
        # Assuming 4% risk-free rate
        assumed_volatility = 15.0  # 15% annual volatility
        risk_free_rate = 4.0  # 4% annual
        required_sharpe_ratio = (required_annual_return_pct - risk_free_rate) / assumed_volatility

        # Minimum capital required (assuming 1% daily return is achievable)
        # $100/day = $100 / 0.01 = $10,000 minimum capital
        achievable_daily_return_pct = 1.0  # Conservative assumption
        min_capital_required = self.config.target_daily_net_income / (
            achievable_daily_return_pct / 100
        )

        # Feasibility check
        feasible = self.config.capital >= min_capital_required

        # Max volatility to stay within risk limits
        # If we target $100/day profit, max daily loss should be < $200 (2% of $10k)
        max_volatility_pct = min(
            self.config.max_daily_loss_pct * 2,  # Conservative: 2x daily loss limit
            20.0,  # Cap at 20% annual volatility
        )

        # Max position size (based on risk limits)
        # Don't risk more than 2% of capital per trade
        max_position_size = self.config.capital * (self.config.max_daily_loss_pct / 100)

        # Worst-case drawdown limits
        worst_5day_drawdown_limit = self.config.capital * (self.config.max_daily_loss_pct * 5 / 100)
        worst_20day_drawdown_limit = self.config.capital * (self.config.max_drawdown_pct / 100)

        return TargetModelMetrics(
            required_daily_return_pct=required_daily_return_pct,
            required_annual_return_pct=required_annual_return_pct,
            required_sharpe_ratio=required_sharpe_ratio,
            min_capital_required=min_capital_required,
            feasible_with_current_capital=feasible,
            max_volatility_pct=max_volatility_pct,
            max_position_size=max_position_size,
            estimated_daily_costs=daily_costs,
            net_after_costs=self.config.target_daily_net_income,
            worst_5day_drawdown_limit=worst_5day_drawdown_limit,
            worst_20day_drawdown_limit=worst_20day_drawdown_limit,
        )

    def _estimate_daily_costs(self) -> float:
        """
        Estimate daily trading costs (commissions, slippage).

        Returns:
            Estimated daily cost in dollars
        """
        # Assume 2 trades per day on average
        trades_per_day = 2.0
        trade_size = self.config.capital * 0.01  # 1% of capital per trade

        # Commission costs (Alpaca = $0)
        commission_cost = trades_per_day * self.config.commission_per_trade

        # Slippage costs (in basis points)
        slippage_cost = trades_per_day * trade_size * (self.config.slippage_bps / 10000)

        return commission_cost + slippage_cost

    def analyze_backtest_vs_target(
        self,
        avg_daily_pnl: float,
        pct_days_above_target: float,
        worst_5day_drawdown: float,
        worst_20day_drawdown: float,
        sharpe_ratio: float,
    ) -> dict[str, any]:
        """
        Analyze backtest results against $100/day target.

        Args:
            avg_daily_pnl: Average daily P&L from backtest
            pct_days_above_target: Percentage of days where P&L >= $100
            worst_5day_drawdown: Worst 5-day drawdown in dollars
            worst_20day_drawdown: Worst 20-day drawdown in dollars
            sharpe_ratio: Sharpe ratio from backtest

        Returns:
            Dictionary with analysis results
        """
        metrics = self.compute_metrics()

        # Gap analysis
        daily_gap = self.config.target_daily_net_income - avg_daily_pnl
        pct_of_target = (avg_daily_pnl / self.config.target_daily_net_income) * 100

        # Risk check
        within_5day_limit = worst_5day_drawdown <= metrics.worst_5day_drawdown_limit
        within_20day_limit = worst_20day_drawdown <= metrics.worst_20day_drawdown_limit

        # Sharpe check
        sharpe_meets_target = sharpe_ratio >= metrics.required_sharpe_ratio

        # Overall feasibility
        feasible = (
            avg_daily_pnl >= self.config.target_daily_net_income * 0.8  # Within 20% of target
            and pct_days_above_target >= 50.0  # At least 50% of days hit target
            and within_5day_limit
            and within_20day_limit
            and sharpe_meets_target
        )

        return {
            "target_daily_net_income": self.config.target_daily_net_income,
            "avg_daily_pnl": avg_daily_pnl,
            "daily_gap": daily_gap,
            "pct_of_target": pct_of_target,
            "pct_days_above_target": pct_days_above_target,
            "worst_5day_drawdown": worst_5day_drawdown,
            "worst_5day_drawdown_limit": metrics.worst_5day_drawdown_limit,
            "within_5day_limit": within_5day_limit,
            "worst_20day_drawdown": worst_20day_drawdown,
            "worst_20day_drawdown_limit": metrics.worst_20day_drawdown_limit,
            "within_20day_limit": within_20day_limit,
            "sharpe_ratio": sharpe_ratio,
            "required_sharpe_ratio": metrics.required_sharpe_ratio,
            "sharpe_meets_target": sharpe_meets_target,
            "feasible": feasible,
            "required_daily_return_pct": metrics.required_daily_return_pct,
            "required_annual_return_pct": metrics.required_annual_return_pct,
        }

    def generate_target_report(self, backtest_analysis: dict[str, any] | None = None) -> str:
        """
        Generate human-readable report of target model analysis.

        Args:
            backtest_analysis: Optional backtest analysis from analyze_backtest_vs_target()

        Returns:
            Formatted report string
        """
        metrics = self.compute_metrics()

        lines = [
            "=" * 80,
            "$100/DAY TARGET MODEL ANALYSIS",
            "=" * 80,
            "",
            "TARGET CONSTRAINTS",
            "-" * 80,
            f"Target Daily Net Income:  ${self.config.target_daily_net_income:.2f}",
            f"Current Capital:          ${self.config.capital:,.2f}",
            f"Max Leverage:             {self.config.max_leverage:.1f}x",
            "",
            "REQUIRED METRICS",
            "-" * 80,
            f"Required Daily Return:    {metrics.required_daily_return_pct:.3f}%",
            f"Required Annual Return:   {metrics.required_annual_return_pct:.2f}%",
            f"Required Sharpe Ratio:    {metrics.required_sharpe_ratio:.2f}",
            "",
            "FEASIBILITY ANALYSIS",
            "-" * 80,
            f"Min Capital Required:     ${metrics.min_capital_required:,.2f}",
            f"Feasible with Capital:    {'✅ YES' if metrics.feasible_with_current_capital else '❌ NO'}",
            "",
            "RISK CONSTRAINTS",
            "-" * 80,
            f"Max Volatility:          {metrics.max_volatility_pct:.2f}%",
            f"Max Position Size:       ${metrics.max_position_size:,.2f}",
            f"Worst 5-Day Drawdown Limit:  ${metrics.worst_5day_drawdown_limit:,.2f}",
            f"Worst 20-Day Drawdown Limit: ${metrics.worst_20day_drawdown_limit:,.2f}",
            "",
            "COST ANALYSIS",
            "-" * 80,
            f"Estimated Daily Costs:    ${metrics.estimated_daily_costs:.2f}",
            f"Net After Costs:          ${metrics.net_after_costs:.2f}",
            "",
        ]

        if backtest_analysis:
            lines.extend(
                [
                    "BACKTEST vs TARGET",
                    "-" * 80,
                    f"Avg Daily P&L:            ${backtest_analysis['avg_daily_pnl']:.2f}",
                    f"Daily Gap:                ${backtest_analysis['daily_gap']:.2f}",
                    f"% of Target:              {backtest_analysis['pct_of_target']:.1f}%",
                    f"% Days ≥ $100:            {backtest_analysis['pct_days_above_target']:.1f}%",
                    "",
                    f"Worst 5-Day Drawdown:      ${backtest_analysis['worst_5day_drawdown']:.2f}",
                    f"  (Limit: ${backtest_analysis['worst_5day_drawdown_limit']:.2f})",
                    f"  Status: {'✅ WITHIN LIMIT' if backtest_analysis['within_5day_limit'] else '❌ EXCEEDS LIMIT'}",
                    "",
                    f"Worst 20-Day Drawdown:    ${backtest_analysis['worst_20day_drawdown']:.2f}",
                    f"  (Limit: ${backtest_analysis['worst_20day_drawdown_limit']:.2f})",
                    f"  Status: {'✅ WITHIN LIMIT' if backtest_analysis['within_20day_limit'] else '❌ EXCEEDS LIMIT'}",
                    "",
                    f"Sharpe Ratio:             {backtest_analysis['sharpe_ratio']:.2f}",
                    f"  (Required: {backtest_analysis['required_sharpe_ratio']:.2f})",
                    f"  Status: {'✅ MEETS TARGET' if backtest_analysis['sharpe_meets_target'] else '❌ BELOW TARGET'}",
                    "",
                    "OVERALL FEASIBILITY",
                    "-" * 80,
                    f"Status: {'✅ FEASIBLE' if backtest_analysis['feasible'] else '❌ NOT FEASIBLE'}",
                    "",
                ]
            )

        lines.append("=" * 80)

        return "\n".join(lines)
