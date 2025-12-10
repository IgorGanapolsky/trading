"""
Capital Model - Requirements Calculator for $100/Day Target

This module calculates the capital requirements, position sizing,
and risk constraints needed to realistically achieve the daily target.

Author: Trading System
Created: 2025-12-03
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CapitalRequirements:
    """Results of capital analysis for target achievement."""

    # Required capital at different return assumptions
    capital_at_0_25_pct_daily: float  # Conservative: 0.25%/day
    capital_at_0_50_pct_daily: float  # Moderate: 0.50%/day
    capital_at_1_00_pct_daily: float  # Aggressive: 1.00%/day

    # Current situation
    current_capital: float
    daily_target: float

    # What's achievable
    achievable_daily_pnl_conservative: float
    achievable_daily_pnl_moderate: float
    achievable_daily_pnl_aggressive: float

    # Risk metrics
    required_win_rate_at_current_capital: float
    position_size_recommendation: float
    max_position_count: int

    # Timeline to target
    months_to_target_with_reinvestment: int | None
    starting_daily_for_compound: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "capital_requirements": {
                "conservative_0.25pct": round(self.capital_at_0_25_pct_daily, 2),
                "moderate_0.50pct": round(self.capital_at_0_50_pct_daily, 2),
                "aggressive_1.00pct": round(self.capital_at_1_00_pct_daily, 2),
            },
            "current_situation": {
                "capital": round(self.current_capital, 2),
                "daily_target": self.daily_target,
            },
            "achievable_daily_pnl": {
                "conservative": round(self.achievable_daily_pnl_conservative, 2),
                "moderate": round(self.achievable_daily_pnl_moderate, 2),
                "aggressive": round(self.achievable_daily_pnl_aggressive, 2),
            },
            "risk_metrics": {
                "required_win_rate": round(self.required_win_rate_at_current_capital * 100, 1),
                "position_size": round(self.position_size_recommendation, 2),
                "max_positions": self.max_position_count,
            },
            "timeline": {
                "months_to_target": self.months_to_target_with_reinvestment,
                "starting_daily": round(self.starting_daily_for_compound, 2),
            },
        }


@dataclass
class CapitalModel:
    """
    Capital model for computing requirements to hit $100/day target.

    This class analyzes:
    - How much capital is needed at various return assumptions
    - What's achievable with current capital
    - How long it takes to compound to target
    - Position sizing constraints
    """

    # Target configuration
    daily_target: float = 100.0
    current_capital: float = 10000.0

    # Return assumptions (daily %)
    conservative_daily_return: float = 0.25  # Very achievable
    moderate_daily_return: float = 0.50  # Requires skill
    aggressive_daily_return: float = 1.00  # Very difficult

    # Trading assumptions
    trading_days_per_year: int = 252
    avg_trades_per_day: int = 1
    win_rate_assumption: float = 0.55
    avg_win_to_loss_ratio: float = 1.5

    # Risk constraints
    max_position_pct: float = 0.10  # 10% per position
    max_portfolio_risk_pct: float = 0.02  # 2% daily loss limit
    cost_per_trade_bps: float = 5.0  # 5 basis points

    def calculate_requirements(self) -> CapitalRequirements:
        """Calculate all capital requirements and achievability metrics."""

        # Capital needed at different return levels
        cap_conservative = self.daily_target / (self.conservative_daily_return / 100)
        cap_moderate = self.daily_target / (self.moderate_daily_return / 100)
        cap_aggressive = self.daily_target / (self.aggressive_daily_return / 100)

        # What's achievable with current capital
        achievable_conservative = self.current_capital * (self.conservative_daily_return / 100)
        achievable_moderate = self.current_capital * (self.moderate_daily_return / 100)
        achievable_aggressive = self.current_capital * (self.aggressive_daily_return / 100)

        # Required win rate at current capital (Kelly-inspired)
        required_daily_return = self.daily_target / self.current_capital
        required_win_rate = self._calculate_required_win_rate(required_daily_return)

        # Position sizing
        position_size = self.current_capital * self.max_position_pct
        max_positions = int(1 / self.max_position_pct)

        # Compound timeline
        months_to_target, starting_daily = self._calculate_compound_timeline()

        return CapitalRequirements(
            capital_at_0_25_pct_daily=cap_conservative,
            capital_at_0_50_pct_daily=cap_moderate,
            capital_at_1_00_pct_daily=cap_aggressive,
            current_capital=self.current_capital,
            daily_target=self.daily_target,
            achievable_daily_pnl_conservative=achievable_conservative,
            achievable_daily_pnl_moderate=achievable_moderate,
            achievable_daily_pnl_aggressive=achievable_aggressive,
            required_win_rate_at_current_capital=required_win_rate,
            position_size_recommendation=position_size,
            max_position_count=max_positions,
            months_to_target_with_reinvestment=months_to_target,
            starting_daily_for_compound=starting_daily,
        )

    def _calculate_required_win_rate(self, required_daily_return: float) -> float:
        """
        Calculate required win rate given return requirement.

        Uses simplified Kelly criterion inversion.
        """
        # Expected value = win_rate * avg_win - (1 - win_rate) * avg_loss
        # We need: expected_value = required_return
        # Assuming avg_win = 1.5 * avg_loss (risk/reward = 1.5)
        # expected = W * 1.5 * L - (1-W) * L
        # For simplicity, normalize loss to 1
        # expected = W * 1.5 - (1-W) = 1.5W - 1 + W = 2.5W - 1
        # required = 2.5W - 1 => W = (required + 1) / 2.5

        # This is simplified; real calculation depends on position sizing
        simplified_win_rate = (required_daily_return + self.max_portfolio_risk_pct) / (
            self.avg_win_to_loss_ratio * self.max_portfolio_risk_pct + self.max_portfolio_risk_pct
        )

        # Clamp to reasonable range
        return max(0.30, min(0.95, simplified_win_rate))

    def _calculate_compound_timeline(self) -> tuple[int | None, float]:
        """
        Calculate months to reach target via compounding.

        Returns:
            Tuple of (months_to_target, starting_daily_pnl)
        """
        # Start with achievable daily at moderate assumption
        starting_daily = self.current_capital * (self.moderate_daily_return / 100)

        if starting_daily >= self.daily_target:
            return 0, starting_daily

        # Compound monthly (21 trading days per month)
        days_per_month = 21
        monthly_return = self.moderate_daily_return / 100 * days_per_month

        capital = self.current_capital
        months = 0
        max_months = 120  # 10 year limit

        while months < max_months:
            months += 1
            capital *= 1 + monthly_return
            achievable = capital * (self.moderate_daily_return / 100)

            if achievable >= self.daily_target:
                return months, starting_daily

        return None, starting_daily

    def generate_capital_report(self) -> str:
        """Generate human-readable capital requirements report."""
        reqs = self.calculate_requirements()

        report = []
        report.append("=" * 60)
        report.append("CAPITAL REQUIREMENTS FOR $100/DAY TARGET")
        report.append("=" * 60)
        report.append("")

        report.append("CAPITAL NEEDED BY RETURN SCENARIO")
        report.append("-" * 40)
        report.append(f"  Conservative (0.25%/day): ${reqs.capital_at_0_25_pct_daily:>12,.2f}")
        report.append(f"  Moderate (0.50%/day):     ${reqs.capital_at_0_50_pct_daily:>12,.2f}")
        report.append(f"  Aggressive (1.00%/day):   ${reqs.capital_at_1_00_pct_daily:>12,.2f}")
        report.append("")

        report.append("YOUR CURRENT SITUATION")
        report.append("-" * 40)
        report.append(f"  Current Capital:          ${reqs.current_capital:>12,.2f}")
        report.append(f"  Daily Target:             ${reqs.daily_target:>12,.2f}")
        report.append("")

        report.append("ACHIEVABLE DAILY P&L AT CURRENT CAPITAL")
        report.append("-" * 40)
        report.append(
            f"  Conservative:             ${reqs.achievable_daily_pnl_conservative:>12.2f}"
        )
        report.append(f"  Moderate:                 ${reqs.achievable_daily_pnl_moderate:>12.2f}")
        report.append(f"  Aggressive:               ${reqs.achievable_daily_pnl_aggressive:>12.2f}")
        report.append("")

        # Progress bar for capital vs. requirement
        pct_of_required = (reqs.current_capital / reqs.capital_at_0_50_pct_daily) * 100
        bar_filled = int(min(100, pct_of_required) / 5)
        bar = "█" * bar_filled + "░" * (20 - bar_filled)
        report.append(f"Capital Progress: [{bar}] {pct_of_required:.1f}%")
        report.append("                  (vs moderate scenario requirement)")
        report.append("")

        report.append("RISK METRICS")
        report.append("-" * 40)
        report.append(
            f"  Required Win Rate:        {reqs.required_win_rate_at_current_capital * 100:>12.1f}%"
        )
        report.append(f"  Max Position Size:        ${reqs.position_size_recommendation:>12.2f}")
        report.append(f"  Max Concurrent Positions: {reqs.max_position_count:>12}")
        report.append("")

        report.append("COMPOUND TIMELINE TO $100/DAY")
        report.append("-" * 40)
        report.append(f"  Starting Daily P&L:       ${reqs.starting_daily_for_compound:>12.2f}")
        if reqs.months_to_target_with_reinvestment is not None:
            report.append(
                f"  Months to Target:         {reqs.months_to_target_with_reinvestment:>12}"
            )
        else:
            report.append(f"  Months to Target:         {'> 10 years':>12}")
        report.append("")

        # Recommendation
        report.append("RECOMMENDATION")
        report.append("-" * 40)
        if reqs.current_capital >= reqs.capital_at_0_50_pct_daily:
            report.append("  ✅ Capital sufficient for moderate scenario.")
            report.append("  Focus on strategy refinement and execution.")
        elif (
            reqs.months_to_target_with_reinvestment
            and reqs.months_to_target_with_reinvestment <= 24
        ):
            report.append(
                f"  📈 Compound path viable: ~{reqs.months_to_target_with_reinvestment} months"
            )
            report.append("  Reinvest profits and maintain discipline.")
        else:
            gap = reqs.capital_at_0_50_pct_daily - reqs.current_capital
            report.append(f"  ⚠️  Capital gap: ${gap:,.2f}")
            report.append("  Consider adding capital or adjusting target timeline.")
        report.append("")

        report.append("=" * 60)

        return "\n".join(report)

    def calculate_position_sizing(
        self,
        entry_price: float,
        stop_loss_pct: float = 0.02,
    ) -> dict[str, float]:
        """
        Calculate optimal position sizing based on capital and risk.

        Args:
            entry_price: Entry price for the position
            stop_loss_pct: Stop loss percentage (default 2%)

        Returns:
            Dict with position sizing recommendations
        """
        # Max risk per trade (using 2% rule)
        max_risk_dollars = self.current_capital * self.max_portfolio_risk_pct

        # Position size based on stop loss
        risk_per_share = entry_price * stop_loss_pct
        shares_by_risk = max_risk_dollars / risk_per_share if risk_per_share > 0 else 0

        # Position size based on max position %
        max_position_value = self.current_capital * self.max_position_pct
        shares_by_position = max_position_value / entry_price if entry_price > 0 else 0

        # Use smaller of the two
        recommended_shares = min(shares_by_risk, shares_by_position)
        position_value = recommended_shares * entry_price

        return {
            "recommended_shares": round(recommended_shares, 2),
            "position_value": round(position_value, 2),
            "position_pct_of_capital": round((position_value / self.current_capital) * 100, 2),
            "risk_per_trade": round(recommended_shares * risk_per_share, 2),
            "max_loss_pct": round(
                (recommended_shares * risk_per_share / self.current_capital) * 100, 2
            ),
        }


# Convenience functions
def analyze_capital_for_target(
    capital: float,
    target: float = 100.0,
) -> tuple[CapitalRequirements, str]:
    """
    Analyze if capital is sufficient for daily target.

    Returns:
        Tuple of (requirements, report_string)
    """
    model = CapitalModel(
        daily_target=target,
        current_capital=capital,
    )
    reqs = model.calculate_requirements()
    report = model.generate_capital_report()
    return reqs, report
