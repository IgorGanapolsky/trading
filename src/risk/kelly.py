"""
Kelly sizing helpers for deterministic position sizing.

Supports multiple Kelly modes:
- Full Kelly: Maximum growth (aggressive, high volatility)
- Half Kelly: Balanced growth/volatility (recommended for most traders)
- Quarter Kelly: Conservative (current default)
- Income Mode: Fixed risk for consistent daily income
"""

from __future__ import annotations

from enum import Enum
from typing import NamedTuple


class KellyMode(Enum):
    """Position sizing modes based on Kelly Criterion."""

    FULL = 1.0  # Maximum growth, high volatility
    HALF = 0.5  # Balanced approach (recommended)
    QUARTER = 0.25  # Conservative (current default)
    EIGHTH = 0.125  # Very conservative
    INCOME = 0.0  # Fixed risk mode, ignores Kelly


class IncomeSizingResult(NamedTuple):
    """Result of income-based position sizing calculation."""

    target_daily_income: float
    required_notional_per_trade: float
    actual_notional: float
    achievable_daily_income: float
    minimum_account_for_target: float
    position_pct: float
    trades_per_week: int
    avg_premium_yield: float


def kelly_fraction(win_probability: float, payoff_ratio: float) -> float:
    """
    Compute the Kelly fraction for a single trade opportunity.
    """
    win_probability = max(0.0, min(1.0, win_probability))
    payoff_ratio = max(0.0, payoff_ratio)
    if payoff_ratio <= 0 or win_probability <= 0:
        return 0.0
    loss_probability = 1.0 - win_probability
    numerator = (win_probability * payoff_ratio) - loss_probability
    denominator = payoff_ratio
    if denominator == 0:
        return 0.0
    return max(0.0, numerator / denominator)


def fractional_kelly(
    win_probability: float,
    payoff_ratio: float,
    mode: KellyMode = KellyMode.QUARTER,
) -> float:
    """
    Compute fractional Kelly for different risk profiles.

    Args:
        win_probability: Probability of winning (0-1)
        payoff_ratio: Average win / average loss
        mode: Kelly mode (FULL, HALF, QUARTER, EIGHTH)

    Returns:
        Position size as fraction of portfolio (0-1)

    Example:
        >>> fractional_kelly(0.60, 1.5, KellyMode.HALF)
        0.1333  # 13.33% of portfolio
    """
    if mode == KellyMode.INCOME:
        return 0.0  # Income mode uses fixed sizing, not Kelly

    raw_kelly = kelly_fraction(win_probability, payoff_ratio)
    return raw_kelly * mode.value


def calculate_income_position_size(
    account_value: float,
    target_daily_income: float = 100.0,
    avg_premium_yield: float = 0.015,  # 1.5% per trade
    trades_per_week: int = 5,
    max_position_pct: float = 0.10,  # 10% max per position
) -> IncomeSizingResult:
    """
    Calculate position size for consistent income generation.

    This is the "Income Mode" sizing - optimizes for consistent daily
    income rather than maximum growth.

    Target: $100/day = $500/week = $2,000/month

    Math:
    - If avg premium yield is 1.5% per trade
    - Need $500/week from 5 trades
    - Each trade needs to yield $100
    - $100 / 1.5% = $6,667 notional per trade

    Args:
        account_value: Current account value
        target_daily_income: Target daily income in dollars
        avg_premium_yield: Expected premium yield per trade (0.01 = 1%)
        trades_per_week: Number of trades per week (default: 5)
        max_position_pct: Maximum position size as % of account

    Returns:
        IncomeSizingResult with sizing details

    Example:
        >>> result = calculate_income_position_size(100000, target_daily_income=100)
        >>> print(f"Need ${result.required_notional_per_trade:.0f} per trade")
        Need $6667 per trade
    """
    if account_value <= 0:
        return IncomeSizingResult(
            target_daily_income=target_daily_income,
            required_notional_per_trade=0.0,
            actual_notional=0.0,
            achievable_daily_income=0.0,
            minimum_account_for_target=0.0,
            position_pct=0.0,
            trades_per_week=trades_per_week,
            avg_premium_yield=avg_premium_yield,
        )

    # Calculate required notional
    weekly_income = target_daily_income * 5  # 5 trading days
    income_per_trade = weekly_income / trades_per_week
    required_notional = income_per_trade / avg_premium_yield if avg_premium_yield > 0 else 0

    # Cap at max position size
    max_notional = account_value * max_position_pct
    actual_notional = min(required_notional, max_notional)

    # Calculate achievable income with capped position
    achievable_weekly = actual_notional * avg_premium_yield * trades_per_week
    achievable_daily = achievable_weekly / 5

    # Minimum account needed for full target
    min_account = required_notional / max_position_pct if max_position_pct > 0 else 0

    return IncomeSizingResult(
        target_daily_income=target_daily_income,
        required_notional_per_trade=round(required_notional, 2),
        actual_notional=round(actual_notional, 2),
        achievable_daily_income=round(achievable_daily, 2),
        minimum_account_for_target=round(min_account, 2),
        position_pct=round((actual_notional / account_value) * 100, 2) if account_value > 0 else 0,
        trades_per_week=trades_per_week,
        avg_premium_yield=avg_premium_yield,
    )
