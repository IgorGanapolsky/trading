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

    # Optimal IV Rank for aggressive premium selling (Invest with Henry)
    # "IVR > 80% = Premiums unusually high = OPTIMAL time to sell"
    OPTIMAL_IV_RANK_FOR_SELLING = 80

    # Good IV Rank range for selling (50-80%)
    GOOD_IV_RANK_MIN = 50
    GOOD_IV_RANK_MAX = 80

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
    # Jan 16 fix: $3 spread = $300 collateral, not $5000!
    STRATEGY_MINIMUMS = {
        "equity_accumulation": 0,
        "covered_call": 1000,
        "cash_secured_put": 500,  # Lowered from 2000 for $5 strike stocks
        "vertical_spread": 300,  # $3 spread = $300 collateral (fixed Jan 16)
        "iron_condor": 600,  # 2 spreads = $600 collateral (fixed Jan 16)
        "delta_neutral": 50000,
    }

    # PDT rule threshold
    PDT_THRESHOLD = 25000


class PositionSizing:
    """Position sizing constraints."""

    # Minimum capital for trading (per CLAUDE.md: $500 for first CSP trade)
    MIN_CAPITAL = 500.0

    # Max allocation per position
    # CRITICAL FIX Jan 16: Per CLAUDE.md 5% rule ($248 max risk on $5K account)
    # Previous 15% allowed 96% SOFI position which almost wiped account
    MAX_POSITION_PCT = 0.05  # 5% max per position (CLAUDE.md rule)

    # Cash reserve requirement
    MIN_CASH_RESERVE_PCT = 0.20  # Keep 20% in cash

    # Daily loss limit
    MAX_DAILY_LOSS_PCT = 0.02  # 2% max daily drawdown

    # Delta thresholds for CSPs (Phil Town approach = conservative)
    TARGET_CSP_DELTA = 0.20  # 20% chance of assignment
    MAX_CSP_DELTA = 0.30  # Never sell puts above 30 delta

    # Iron condor delta thresholds (per CLAUDE.md Jan 19)
    # "Sell 15-20 delta put spread + Sell 15-20 delta call spread"
    IRON_CONDOR_MIN_DELTA = 0.15  # Minimum delta for short strikes
    IRON_CONDOR_MAX_DELTA = 0.20  # Maximum delta for short strikes (86% win rate)
    IRON_CONDOR_TARGET_DELTA = 0.15  # Target 15-delta = 85% probability of profit


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

    # DTE thresholds (per CLAUDE.md Jan 19 - Iron Condor strategy)
    # Entry: 30-45 DTE optimal for theta decay
    IRON_CONDOR_MIN_DTE = 30
    IRON_CONDOR_MAX_DTE = 45

    # Exit at 21 DTE to avoid gamma risk (CLAUDE.md rule)
    # "Close positions at 21 DTE to avoid gamma risk"
    EXIT_AT_DTE = 21  # Close iron condors at 21 DTE

    # Rolling threshold (Invest with Henry: "Roll before expiration")
    # Roll options when DTE falls below this to avoid assignment risk
    ROLL_AT_DTE = 5  # Roll positions when 5 DTE or less (backup if 21 DTE exit missed)

    # Trade frequency limit (Invest with Henry: "10-15 trades/week max")
    # Prevents overtrading which "primarily benefits the brokerage"
    MAX_TRADES_PER_WEEK = 15

    # Ex-dividend buffer (days) - check before selling covered calls
    # "Options may be exercised EARLY to capture dividend"
    EX_DIV_BUFFER_DAYS = 7  # Avoid selling CCs within 7 days of ex-div


class TargetSymbols:
    """Target symbols for trading strategies (per CLAUDE.md - Jan 19 revision).

    CRITICAL UPDATE Jan 19, 2026 (Iron Condor Strategy):
    - 100K account succeeded with SPY focus (+$16,661)
    - 5K account failed with SOFI (individual stock risk)
    - IRON CONDORS on SPY ONLY - defined risk on BOTH sides
    - NO individual stocks, NO IWM until proven in paper trading
    """

    # Primary targets - SPY ONLY per CLAUDE.md strategy
    # Iron condor collateral = spread width x 2 (~$1000 for $5-wide wings)
    CSP_WATCHLIST = ["SPY"]  # SPY ONLY - best liquidity, tightest spreads

    # Max strike for credit spreads (SPY ~$590, IWM ~$220)
    # This is informational - actual strike from 30-delta put
    MAX_CSP_STRIKE = 600.0

    # BLACKLIST - DO NOT TRADE until proven
    BLACKLIST = ["SOFI", "F", "PLTR", "T", "INTC"]  # Individual stocks blocked


# Singleton access for easy importing
IV = IVThresholds
CAPITAL = CapitalThresholds
SIZING = PositionSizing
RISK = RiskThresholds
SYMBOLS = TargetSymbols
