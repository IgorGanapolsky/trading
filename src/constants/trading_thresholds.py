"""
Trading Thresholds - Centralized Constants for Strategy Alignment

This module consolidates all IV rank, capital, and position sizing thresholds
to ensure consistency across the entire trading system.

Author: AI Trading System CTO
Created: January 13, 2026
Ref: Investment strategy review - alignment audit
"""


class IVThresholds:
    """Implied Volatility thresholds for premium selling strategies."""

    # Minimum IV Rank to sell premium (too low = cheap premium, not worth it)
    MIN_IV_RANK_FOR_CREDIT = 20

    # Maximum IV Rank for CSPs (too high = assignment risk elevated)
    # Phil Town approach: sell CSPs on wonderful companies, not volatility plays
    MAX_IV_RANK_FOR_CSP = 50

    # Optimal IV ranges by strategy
    OPTIMAL_IV_RANK = {
        "cash_secured_put": {"min": 20, "max": 50, "optimal": 30},
        "covered_call": {"min": 20, "max": 50, "optimal": 30},
        "iron_condor": {"min": 30, "max": 70, "optimal": 50},
        "vertical_spread": {"min": 20, "max": 60, "optimal": 40},
        "straddle_short": {"min": 50, "max": 90, "optimal": 70},
    }

    @classmethod
    def is_iv_suitable(cls, strategy: str, iv_rank: float) -> bool:
        """Check if IV rank is suitable for given strategy."""
        if strategy not in cls.OPTIMAL_IV_RANK:
            return True  # Unknown strategy, allow
        thresholds = cls.OPTIMAL_IV_RANK[strategy]
        return thresholds["min"] <= iv_rank <= thresholds["max"]


class CapitalThresholds:
    """Capital requirements for trading strategies.

    Updated Jan 13, 2026: Aligned with $5 strike CSP strategy on F/SOFI.
    $5 strike = $500 collateral, so CSP viable at $500+ for Tier 1 stocks.
    """

    # Minimum batch size (avoid fee erosion)
    MIN_BATCH = 200

    # CSP by strike tier - CRITICAL: matches CLAUDE.md strategy
    CSP_MIN_CAPITAL = {
        "tier_1_low_strike": 500,  # F, SOFI at $5 strike = $500 collateral
        "tier_2_mid_strike": 2000,  # Stocks $15-20 strike
        "tier_3_high_strike": 5000,  # Stocks $50+ strike
    }

    # General strategy minimums (for capital efficiency calculator)
    STRATEGY_MINIMUMS = {
        "equity_accumulation": 0,
        "covered_call": 1000,
        "cash_secured_put": 500,  # Lowered from 2000 for $5 strike stocks
        "vertical_spread": 5000,
        "iron_condor": 10000,
        "delta_neutral": 50000,
    }

    # PDT rule threshold
    PDT_THRESHOLD = 25000


class PositionSizing:
    """Position sizing constraints."""

    # Minimum capital for trading (per CLAUDE.md: $500 for first CSP trade)
    MIN_CAPITAL = 500.0

    # Max allocation per position
    MAX_POSITION_PCT = 0.25  # 25% max per position

    # Cash reserve requirement
    MIN_CASH_RESERVE_PCT = 0.20  # Keep 20% in cash

    # Daily loss limit
    MAX_DAILY_LOSS_PCT = 0.02  # 2% max daily drawdown

    # Delta thresholds for CSPs (Phil Town approach = conservative)
    TARGET_CSP_DELTA = 0.20  # 20% chance of assignment
    MAX_CSP_DELTA = 0.30  # Never sell puts above 30 delta


class RiskThresholds:
    """Risk management thresholds."""

    # VIX circuit breaker levels (Note: VIX module deleted in Jan 13 cleanup)
    VIX_HALT_THRESHOLD = 30  # Halt all new trades above VIX 30
    VIX_REDUCE_THRESHOLD = 25  # Reduce position sizing above VIX 25

    # Stop loss levels
    CSP_STOP_LOSS_MULTIPLIER = 2.0  # Exit at 2x premium received
    COVERED_CALL_STOP_LOSS_MULTIPLIER = 2.0
    IRON_CONDOR_STOP_LOSS_MULTIPLIER = 2.2  # McMillan rule

    # Take profit levels
    CSP_TAKE_PROFIT_PCT = 0.50  # Close at 50% profit
    IRON_CONDOR_TAKE_PROFIT_PCT = 0.50


class TargetSymbols:
    """Target symbols for trading strategies (per CLAUDE.md)."""

    # Primary CSP targets - cheap stocks for $500 capital
    CSP_WATCHLIST = ["SOFI", "F"]

    # Max strike price for CSPs with small capital
    MAX_CSP_STRIKE = 5.0

    # Fallback symbols if primary not available
    FALLBACK_SYMBOLS = ["PLTR", "T", "INTC"]


# Singleton access for easy importing
IV = IVThresholds
CAPITAL = CapitalThresholds
SIZING = PositionSizing
RISK = RiskThresholds
SYMBOLS = TargetSymbols
