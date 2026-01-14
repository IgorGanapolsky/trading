"""
Trading Thresholds - Centralized Constants for Strategy Alignment

This module consolidates all IV rank, capital, and position sizing thresholds
to ensure consistency across the entire trading system.

Author: AI Trading System CTO
Created: January 13, 2026
Ref: Investment strategy review - alignment audit
"""


class EntryTiming:
    """Optimal trade entry timing constants.

    Research shows 10:15 AM is optimal because:
    - Opening volatility has settled (first 30-45 min choppy)
    - Better bid-ask spreads (liquidity improved)
    - More reliable price action (trend direction clearer)

    Updated Jan 14, 2026: Changed from 9:35 AM to 10:15 AM.
    """

    # Optimal entry time (research-backed)
    OPTIMAL_ENTRY_TIME = "10:15"  # Research-backed optimal entry

    # Entry window boundaries
    ENTRY_WINDOW_START = "10:00"
    ENTRY_WINDOW_END = "10:30"

    # Legacy entry time (kept for reference)
    LEGACY_ENTRY_TIME = "09:35"

    @classmethod
    def is_optimal_entry_window(cls) -> bool:
        """Check if current time is in the optimal 10:00-10:30 AM entry window.

        Returns:
            True if current ET time is between 10:00 AM and 10:30 AM.
        """
        from datetime import datetime

        try:
            from pytz import timezone

            eastern = timezone("US/Eastern")
            now = datetime.now(eastern)
        except ImportError:
            # Fallback for environments without pytz
            from zoneinfo import ZoneInfo

            now = datetime.now(ZoneInfo("America/New_York"))

        start = now.replace(hour=10, minute=0, second=0, microsecond=0)
        end = now.replace(hour=10, minute=30, second=0, microsecond=0)
        return start <= now <= end


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
    # Tightened from 25% to 15% per Invest with Henry recommendation
    # "Never allocate more than 15% to any single position"
    MAX_POSITION_PCT = 0.15  # 15% max per position (was 25%)

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

    # Rolling threshold (Invest with Henry: "Roll before expiration")
    # Roll options when DTE falls below this to avoid assignment risk
    ROLL_AT_DTE = 5  # Roll positions when 5 DTE or less

    # Trade frequency limit (Invest with Henry: "10-15 trades/week max")
    # Prevents overtrading which "primarily benefits the brokerage"
    MAX_TRADES_PER_WEEK = 15

    # Ex-dividend buffer (days) - check before selling covered calls
    # "Options may be exercised EARLY to capture dividend"
    EX_DIV_BUFFER_DAYS = 7  # Avoid selling CCs within 7 days of ex-div


class TargetSymbols:
    """Target symbols for trading strategies (per CLAUDE.md)."""

    # Primary CSP targets - cheap stocks for $500 capital
    CSP_WATCHLIST = ["SOFI", "F"]

    # Max strike price for CSPs with small capital
    MAX_CSP_STRIKE = 5.0

    # Fallback symbols if primary not available
    FALLBACK_SYMBOLS = ["PLTR", "T", "INTC"]


# Singleton access for easy importing
ENTRY = EntryTiming
IV = IVThresholds
CAPITAL = CapitalThresholds
SIZING = PositionSizing
RISK = RiskThresholds
SYMBOLS = TargetSymbols
