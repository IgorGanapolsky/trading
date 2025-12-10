"""
Target Model Module - $100/Day Constraint Encoding

This module makes the $100/day North Star an explicit, measurable design constraint
rather than a narrative goal. It calculates capital requirements, risk parameters,
and trading frequency needed to achieve the target, then provides metrics to track
progress toward that goal.

Author: Trading System
Created: 2025-12-03
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TargetModelParameters:
    """Parameters for calculating target model requirements."""

    target_daily_net_income: float  # Target daily P&L (e.g., $100)
    available_capital: float  # Capital allocated to trading
    max_leverage: float = 1.0  # Maximum leverage allowed (1.0 = no leverage)
    trading_days_per_year: int = 252  # Standard trading days
    commission_per_trade: float = 0.0  # Commission cost per trade
    slippage_bps: float = 5.0  # Slippage in basis points
    max_position_risk_pct: float = 2.0  # Max risk per position (% of capital)
    target_win_rate: float = 0.60  # Target win rate (60%)
    avg_hold_period_days: float = 1.0  # Average holding period


@dataclass
class TargetModelOutput:
    """Output metrics from target model calculation."""

    # Requirements
    required_daily_return_pct: float  # Required daily return %
    required_annual_return_pct: float  # Required annual return %
    required_sharpe_ratio: float  # Minimum Sharpe to sustainably achieve target
    max_acceptable_drawdown_pct: float  # Maximum acceptable drawdown

    # Trading frequency
    required_trades_per_day: float  # Average trades needed per day
    required_win_rate: float  # Minimum win rate needed
    avg_profit_per_winning_trade: float  # Average profit on winners
    avg_loss_per_losing_trade: float  # Average loss on losers

    # Risk parameters
    position_size_per_trade: float  # Suggested position size ($)
    max_daily_loss_limit: float  # Maximum acceptable daily loss ($)
    max_positions: int  # Maximum concurrent positions

    # Reality check metrics
    is_feasible: bool  # Is target feasible with given parameters?
    feasibility_score: float  # 0-100 score of feasibility
    required_skill_level: str  # Required trader skill level
    risk_level: str  # Risk level assessment
    warnings: list[str]  # List of warnings about feasibility


class TargetModel:
    """
    Calculates capital, risk, and performance requirements to achieve $100/day target.

    This makes the North Star quantifiable:
    - Input: Target daily income, available capital, constraints
    - Output: Required returns, win rate, Sharpe, position sizing, feasibility

    Usage:
        model = TargetModel()
        params = TargetModelParameters(
            target_daily_net_income=100.0,
            available_capital=10000.0,
        )
        output = model.calculate(params)
        print(f"Required daily return: {output.required_daily_return_pct:.2f}%")
        print(f"Feasible: {output.is_feasible}")
    """

    def __init__(self):
        """Initialize the target model."""
        self.logger = logging.getLogger(self.__class__.__name__)

    def calculate(self, params: TargetModelParameters) -> TargetModelOutput:
        """
        Calculate requirements to achieve target daily net income.

        Args:
            params: Input parameters including target, capital, and constraints

        Returns:
            TargetModelOutput with all calculated requirements and feasibility assessment
        """
        self.logger.info("=" * 80)
        self.logger.info("TARGET MODEL CALCULATION")
        self.logger.info("=" * 80)
        self.logger.info(f"Target Daily Net Income: ${params.target_daily_net_income:.2f}")
        self.logger.info(f"Available Capital: ${params.available_capital:,.2f}")
        self.logger.info(f"Max Leverage: {params.max_leverage}x")

        warnings = []

        # Calculate effective capital with leverage
        effective_capital = params.available_capital * params.max_leverage

        # Calculate required daily return (before costs)
        # Net income = Gross return - Costs
        # Need to work backwards from net income
        estimated_daily_costs = self._estimate_daily_costs(params)
        required_gross_daily_profit = params.target_daily_net_income + estimated_daily_costs

        required_daily_return_pct = (required_gross_daily_profit / effective_capital) * 100

        # Calculate required annual return
        required_annual_return_pct = (
            (1 + required_daily_return_pct / 100) ** params.trading_days_per_year - 1
        ) * 100

        # Calculate required Sharpe ratio for sustainability
        # Higher returns require higher Sharpe to be sustainable
        # Rule of thumb: Sharpe should be at least sqrt(required_annual_return / 15%)
        base_sharpe = max(1.5, (required_annual_return_pct / 15.0) ** 0.5)
        required_sharpe_ratio = base_sharpe

        # Calculate maximum acceptable drawdown
        # Kelly criterion suggests max drawdown ~= 1 / (2 * Sharpe^2)
        # We use a more conservative estimate
        max_acceptable_drawdown_pct = min(
            params.max_position_risk_pct * 5,  # 5x single position risk
            15.0,  # Never accept >15% drawdown for daily income strategy
        )

        # Calculate trading frequency requirements
        # Assume we need to make target daily, so calculate based on win rate
        win_rate = params.target_win_rate
        loss_rate = 1 - win_rate

        # Using simplified risk/reward ratio
        # If win rate = 60%, we need R:R >= (1-WR)/WR = 0.4/0.6 = 0.67
        # To be conservative, we target 1.5:1 R:R
        risk_reward_ratio = 1.5

        # Calculate average profit and loss per trade
        # Let avg_loss = -X, then avg_win = X * risk_reward_ratio
        # Net daily = (win_rate * avg_win + loss_rate * avg_loss) * trades_per_day
        # Solve for X and trades_per_day

        # Start with reasonable position size (2% of capital)
        position_size_per_trade = effective_capital * (params.max_position_risk_pct / 100)

        # Assume we risk 1% of position on each trade (stop loss)
        risk_per_trade = position_size_per_trade * 0.01
        avg_loss_per_losing_trade = -risk_per_trade
        avg_profit_per_winning_trade = risk_per_trade * risk_reward_ratio

        # Calculate expected value per trade
        expected_value_per_trade = (
            win_rate * avg_profit_per_winning_trade + loss_rate * avg_loss_per_losing_trade
        )

        # Calculate required trades per day
        if expected_value_per_trade > 0:
            required_trades_per_day = required_gross_daily_profit / expected_value_per_trade
        else:
            required_trades_per_day = float("inf")
            warnings.append("Negative expected value per trade - strategy not viable")

        # Calculate max concurrent positions
        max_positions = max(1, int(effective_capital / position_size_per_trade))

        # Calculate max daily loss limit (3x target profit, or 3% of capital)
        max_daily_loss_limit = min(params.target_daily_net_income * 3, effective_capital * 0.03)

        # Feasibility assessment
        feasibility_score, is_feasible, skill_level, risk_level = self._assess_feasibility(
            required_annual_return_pct=required_annual_return_pct,
            required_sharpe_ratio=required_sharpe_ratio,
            required_trades_per_day=required_trades_per_day,
            win_rate=win_rate,
            warnings=warnings,
            params=params,
        )

        output = TargetModelOutput(
            required_daily_return_pct=required_daily_return_pct,
            required_annual_return_pct=required_annual_return_pct,
            required_sharpe_ratio=required_sharpe_ratio,
            max_acceptable_drawdown_pct=max_acceptable_drawdown_pct,
            required_trades_per_day=required_trades_per_day,
            required_win_rate=win_rate,
            avg_profit_per_winning_trade=avg_profit_per_winning_trade,
            avg_loss_per_losing_trade=avg_loss_per_losing_trade,
            position_size_per_trade=position_size_per_trade,
            max_daily_loss_limit=max_daily_loss_limit,
            max_positions=max_positions,
            is_feasible=is_feasible,
            feasibility_score=feasibility_score,
            required_skill_level=skill_level,
            risk_level=risk_level,
            warnings=warnings,
        )

        self._log_output(output, params)

        return output

    def _estimate_daily_costs(self, params: TargetModelParameters) -> float:
        """Estimate daily trading costs (commissions + slippage)."""
        # Rough estimate: 3 trades per day average
        estimated_trades = 3
        commission_cost = params.commission_per_trade * estimated_trades

        # Slippage cost: slippage_bps on position size
        position_size = params.available_capital * 0.02  # 2% position
        slippage_cost = (params.slippage_bps / 10000) * position_size * estimated_trades

        return commission_cost + slippage_cost

    def _assess_feasibility(
        self,
        required_annual_return_pct: float,
        required_sharpe_ratio: float,
        required_trades_per_day: float,
        win_rate: float,
        warnings: list[str],
        params: TargetModelParameters,
    ) -> tuple[float, bool, str, str]:
        """
        Assess feasibility of achieving target with given parameters.

        Returns:
            (feasibility_score, is_feasible, skill_level, risk_level)
        """
        score = 100.0
        is_feasible = True

        # Check annual return requirement
        if required_annual_return_pct > 100:
            score -= 30
            warnings.append(
                f"Required annual return {required_annual_return_pct:.1f}% is very high (>100%)"
            )
            is_feasible = False
        elif required_annual_return_pct > 50:
            score -= 20
            warnings.append(
                f"Required annual return {required_annual_return_pct:.1f}% is high (>50%)"
            )
        elif required_annual_return_pct > 30:
            score -= 10
            warnings.append(
                f"Required annual return {required_annual_return_pct:.1f}% is ambitious"
            )

        # Check Sharpe ratio requirement
        if required_sharpe_ratio > 3.0:
            score -= 25
            warnings.append(
                f"Required Sharpe {required_sharpe_ratio:.2f} is exceptionally high (>3.0)"
            )
            is_feasible = False
        elif required_sharpe_ratio > 2.0:
            score -= 15
            warnings.append(
                f"Required Sharpe {required_sharpe_ratio:.2f} is high (>2.0) - difficult to sustain"
            )

        # Check trading frequency
        if required_trades_per_day > 10:
            score -= 20
            warnings.append(
                f"Required {required_trades_per_day:.1f} trades/day is high (>10) - may trigger PDT"
            )
            is_feasible = False
        elif required_trades_per_day > 5:
            score -= 10
            warnings.append(f"Required {required_trades_per_day:.1f} trades/day is moderate (>5)")
        elif required_trades_per_day < 0.5:
            score -= 5
            warnings.append(
                f"Required {required_trades_per_day:.1f} trades/day is very low - may miss opportunities"
            )

        # Check capital adequacy
        capital_per_dollar_target = params.available_capital / params.target_daily_net_income
        if capital_per_dollar_target < 50:
            score -= 30
            warnings.append(
                f"Capital ratio {capital_per_dollar_target:.0f}:1 is very low (<50:1) - high risk"
            )
            is_feasible = False
        elif capital_per_dollar_target < 100:
            score -= 15
            warnings.append(f"Capital ratio {capital_per_dollar_target:.0f}:1 is low (<100:1)")

        # Determine skill level required
        if required_annual_return_pct > 50 or required_sharpe_ratio > 2.5:
            skill_level = "Expert (Top 1% of traders)"
        elif required_annual_return_pct > 30 or required_sharpe_ratio > 2.0:
            skill_level = "Advanced (Top 5% of traders)"
        elif required_annual_return_pct > 20 or required_sharpe_ratio > 1.5:
            skill_level = "Intermediate (Top 20% of traders)"
        else:
            skill_level = "Beginner-Friendly"

        # Determine risk level
        if not is_feasible or score < 50:
            risk_level = "HIGH - Not recommended without significant improvements"
        elif score < 70:
            risk_level = "MODERATE - Achievable with disciplined execution"
        else:
            risk_level = "LOW - Conservative and achievable"

        return score, is_feasible, skill_level, risk_level

    def _log_output(self, output: TargetModelOutput, params: TargetModelParameters) -> None:
        """Log the target model output in a readable format."""
        self.logger.info("")
        self.logger.info("=" * 80)
        self.logger.info("TARGET MODEL RESULTS")
        self.logger.info("=" * 80)
        self.logger.info("")
        self.logger.info("REQUIRED PERFORMANCE:")
        self.logger.info(f"  Daily Return:   {output.required_daily_return_pct:.3f}%")
        self.logger.info(f"  Annual Return:  {output.required_annual_return_pct:.1f}%")
        self.logger.info(f"  Sharpe Ratio:   {output.required_sharpe_ratio:.2f}")
        self.logger.info(f"  Win Rate:       {output.required_win_rate * 100:.1f}%")
        self.logger.info(f"  Max Drawdown:   {output.max_acceptable_drawdown_pct:.1f}%")
        self.logger.info("")
        self.logger.info("TRADING REQUIREMENTS:")
        self.logger.info(f"  Trades/Day:     {output.required_trades_per_day:.2f}")
        self.logger.info(f"  Avg Win:        ${output.avg_profit_per_winning_trade:.2f}")
        self.logger.info(f"  Avg Loss:       ${output.avg_loss_per_losing_trade:.2f}")
        self.logger.info(f"  Position Size:  ${output.position_size_per_trade:,.2f}")
        self.logger.info(f"  Max Positions:  {output.max_positions}")
        self.logger.info(f"  Max Daily Loss: ${output.max_daily_loss_limit:,.2f}")
        self.logger.info("")
        self.logger.info("FEASIBILITY ASSESSMENT:")
        self.logger.info(f"  Feasible:       {output.is_feasible}")
        self.logger.info(f"  Score:          {output.feasibility_score:.0f}/100")
        self.logger.info(f"  Skill Level:    {output.required_skill_level}")
        self.logger.info(f"  Risk Level:     {output.risk_level}")
        self.logger.info("")

        if output.warnings:
            self.logger.warning("WARNINGS:")
            for warning in output.warnings:
                self.logger.warning(f"  ⚠️  {warning}")
            self.logger.info("")

        self.logger.info("=" * 80)

    def calculate_progress_to_target(
        self,
        params: TargetModelParameters,
        actual_daily_pnl: float,
        actual_win_rate: float,
        actual_sharpe: float,
        actual_avg_trades_per_day: float,
        days_measured: int,
    ) -> dict:
        """
        Calculate progress toward $100/day target.

        Args:
            params: Target model parameters
            actual_daily_pnl: Actual average daily P&L
            actual_win_rate: Actual win rate (0-1)
            actual_sharpe: Actual Sharpe ratio
            actual_avg_trades_per_day: Actual average trades per day
            days_measured: Number of days measured

        Returns:
            Dictionary with progress metrics
        """
        # Calculate target requirements
        target_output = self.calculate(params)

        # Calculate progress percentages
        pnl_progress_pct = (actual_daily_pnl / params.target_daily_net_income) * 100
        win_rate_progress_pct = (actual_win_rate / target_output.required_win_rate) * 100
        sharpe_progress_pct = (actual_sharpe / target_output.required_sharpe_ratio) * 100

        # Days until target at current rate
        if actual_daily_pnl > 0:
            daily_improvement_needed = params.target_daily_net_income - actual_daily_pnl
            # Assume linear improvement (optimistic)
            days_to_target = (
                "N/A - already at target" if daily_improvement_needed <= 0 else "Unknown"
            )
        else:
            days_to_target = "Negative P&L - not trending toward target"

        # Percentage of days hitting target
        # (This would need actual day-by-day data, using estimate)
        estimated_pct_days_above_target = max(0, min(100, pnl_progress_pct))

        progress_report = {
            "target_daily_income": params.target_daily_net_income,
            "actual_daily_pnl": actual_daily_pnl,
            "pnl_progress_pct": pnl_progress_pct,
            "win_rate_progress_pct": win_rate_progress_pct,
            "sharpe_progress_pct": sharpe_progress_pct,
            "days_measured": days_measured,
            "estimated_pct_days_above_target": estimated_pct_days_above_target,
            "days_to_target": days_to_target,
            "status": self._get_progress_status(pnl_progress_pct),
            "target_requirements": {
                "required_daily_return_pct": target_output.required_daily_return_pct,
                "required_annual_return_pct": target_output.required_annual_return_pct,
                "required_sharpe": target_output.required_sharpe_ratio,
                "required_win_rate": target_output.required_win_rate,
            },
        }

        return progress_report

    def _get_progress_status(self, progress_pct: float) -> str:
        """Get status string based on progress percentage."""
        if progress_pct >= 100:
            return "🎯 TARGET ACHIEVED"
        elif progress_pct >= 80:
            return "🟢 Excellent Progress (80%+)"
        elif progress_pct >= 60:
            return "🟡 Good Progress (60-79%)"
        elif progress_pct >= 40:
            return "🟠 Moderate Progress (40-59%)"
        elif progress_pct >= 20:
            return "🔴 Limited Progress (20-39%)"
        else:
            return "❌ Poor Progress (<20%)"


def generate_target_model_report(
    target_daily_income: float = 100.0,
    available_capital: float = 10000.0,
    actual_daily_pnl: float | None = None,
    actual_win_rate: float | None = None,
    actual_sharpe: float | None = None,
    actual_trades_per_day: float | None = None,
    days_measured: int | None = None,
) -> str:
    """
    Generate a comprehensive target model report.

    Args:
        target_daily_income: Target daily net income ($)
        available_capital: Available capital ($)
        actual_daily_pnl: Actual average daily P&L (optional, for progress tracking)
        actual_win_rate: Actual win rate 0-1 (optional)
        actual_sharpe: Actual Sharpe ratio (optional)
        actual_trades_per_day: Actual trades per day (optional)
        days_measured: Number of days measured (optional)

    Returns:
        Formatted report string
    """
    model = TargetModel()
    params = TargetModelParameters(
        target_daily_net_income=target_daily_income,
        available_capital=available_capital,
    )

    output = model.calculate(params)

    report = []
    report.append("=" * 80)
    report.append(f"TARGET MODEL REPORT - ${target_daily_income:.0f}/DAY GOAL")
    report.append("=" * 80)
    report.append("")
    report.append(f"Capital Available: ${available_capital:,.2f}")
    report.append(f"Target Daily Income: ${target_daily_income:.2f}")
    report.append("")
    report.append("REQUIREMENTS TO HIT TARGET:")
    report.append(f"  • Daily Return: {output.required_daily_return_pct:.3f}%")
    report.append(f"  • Annual Return: {output.required_annual_return_pct:.1f}%")
    report.append(f"  • Sharpe Ratio: {output.required_sharpe_ratio:.2f}+")
    report.append(f"  • Win Rate: {output.required_win_rate * 100:.0f}%+")
    report.append(f"  • Trades/Day: {output.required_trades_per_day:.1f}")
    report.append(f"  • Max Drawdown: <{output.max_acceptable_drawdown_pct:.1f}%")
    report.append("")
    report.append("RISK PARAMETERS:")
    report.append(f"  • Position Size: ${output.position_size_per_trade:,.2f}")
    report.append(f"  • Max Daily Loss: ${output.max_daily_loss_limit:,.2f}")
    report.append(f"  • Max Positions: {output.max_positions}")
    report.append("")
    report.append(f"FEASIBILITY: {output.feasibility_score:.0f}/100")
    report.append(f"  • Status: {'✅ FEASIBLE' if output.is_feasible else '❌ NOT FEASIBLE'}")
    report.append(f"  • Skill Required: {output.required_skill_level}")
    report.append(f"  • Risk Level: {output.risk_level}")

    if output.warnings:
        report.append("")
        report.append("⚠️  WARNINGS:")
        for warning in output.warnings:
            report.append(f"  • {warning}")

    # Add progress tracking if actual data provided
    if actual_daily_pnl is not None and days_measured is not None:
        progress = model.calculate_progress_to_target(
            params=params,
            actual_daily_pnl=actual_daily_pnl or 0.0,
            actual_win_rate=actual_win_rate or 0.5,
            actual_sharpe=actual_sharpe or 0.0,
            actual_avg_trades_per_day=actual_trades_per_day or 0.0,
            days_measured=days_measured,
        )

        report.append("")
        report.append("=" * 80)
        report.append("PROGRESS TOWARD TARGET")
        report.append("=" * 80)
        report.append(f"Status: {progress['status']}")
        report.append(f"Days Measured: {days_measured}")
        report.append(
            f"Actual Daily P&L: ${actual_daily_pnl:.2f} ({progress['pnl_progress_pct']:.1f}% of target)"
        )
        report.append(
            f"Win Rate: {actual_win_rate * 100:.1f}% ({progress['win_rate_progress_pct']:.1f}% of required)"
        )
        report.append(
            f"Sharpe Ratio: {actual_sharpe:.2f} ({progress['sharpe_progress_pct']:.1f}% of required)"
        )
        report.append(
            f"% Days ≥ ${target_daily_income}: ~{progress['estimated_pct_days_above_target']:.0f}%"
        )

    report.append("")
    report.append("=" * 80)

    return "\n".join(report)


# CLI interface
if __name__ == "__main__":
    # Example usage
    print("\n" + "=" * 80)
    print("TARGET MODEL - $100/DAY ANALYSIS")
    print("=" * 80 + "\n")

    # Scenario 1: $10k capital
    print("SCENARIO 1: $10,000 Capital")
    print("-" * 80)
    report1 = generate_target_model_report(
        target_daily_income=100.0,
        available_capital=10000.0,
    )
    print(report1)
    print("\n")

    # Scenario 2: $25k capital (PDT minimum)
    print("SCENARIO 2: $25,000 Capital (PDT Minimum)")
    print("-" * 80)
    report2 = generate_target_model_report(
        target_daily_income=100.0,
        available_capital=25000.0,
    )
    print(report2)
    print("\n")

    # Scenario 3: Current progress example
    print("SCENARIO 3: Progress Tracking Example")
    print("-" * 80)
    report3 = generate_target_model_report(
        target_daily_income=100.0,
        available_capital=100000.0,  # Paper trading capital
        actual_daily_pnl=15.0,  # Making $15/day currently
        actual_win_rate=0.62,
        actual_sharpe=2.18,
        actual_trades_per_day=1.2,
        days_measured=60,
    )
    print(report3)
