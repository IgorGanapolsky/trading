"""Trading Constants - Single Source of Truth.

This module contains trading constants that should NOT change between environments
and do NOT depend on pydantic or other optional dependencies.

CRITICAL: All trading-related modules should import constants from HERE
to avoid maintenance issues with duplicated definitions.

Created: Jan 19, 2026 (Adversarial audit finding - 4 duplicate definitions)
"""

from datetime import date

# =============================================================================
# TICKER WHITELIST - SINGLE SOURCE OF TRUTH
# =============================================================================
# Liquid ETFs and index options for defined-risk strategies.
# SPY = S&P 500 ETF (default, best liquidity)
# QQQ = Nasdaq-100 ETF (tech-heavy, liquid options)
# IWM = Russell 2000 ETF (small-cap, wider ranges)
# SPX/XSP = Index options with Section 1256 tax treatment (60/40 split)
# This is the ONLY place ticker whitelist should be defined.
# All modules MUST import from here to avoid maintenance issues.
# =============================================================================
ALLOWED_TICKERS: set[str] = {"SPY", "SPX", "XSP", "QQQ", "IWM"}

# =============================================================================
# POSITION LIMITS - Phil Town Rule #1 (SINGLE SOURCE OF TRUTH)
# =============================================================================
# CRITICAL: All modules MUST import from HERE to avoid duplicates
# LL-281 (Jan 22, 2026): 8 contracts accumulated when max was 4 due to
# scattered definitions and race conditions.
# =============================================================================
MAX_POSITION_PCT: float = 0.05  # 5% max per position per CLAUDE.md ($5K on $100K account)
# Hard daily loss limit (intraday) to prevent churn spirals off North Star.
# Align with src/constants/trading_thresholds.py and risk manager defaults.
MAX_DAILY_LOSS_PCT: float = 0.02  # 2% max daily loss
MAX_POSITIONS: int = 8  # 2 iron condors = 8 legs max (UPDATED Jan 30, 2026 for $100K account)
MAX_CONTRACTS_PER_TRADE: int = 2  # Max contracts per single trade (scaled for $100K)
CRISIS_LOSS_PCT: float = 0.25  # 25% unrealized loss triggers crisis mode
CRISIS_POSITION_COUNT: int = 4  # More than 4 positions triggers crisis mode
# Iron condor stop-loss: close if one side reaches 100% of credit received (positive EV)
IRON_CONDOR_STOP_LOSS_MULTIPLIER: float = 1.0

# =============================================================================
# ANTI-CHURN GUARDRAILS (intraday) - SINGLE SOURCE OF TRUTH
# =============================================================================
# "Structures" = strategy-level structures (e.g., 1 iron condor entry record).
# "Fills"      = per-execution fills (can be many due to partial fills/churn).
MAX_DAILY_STRUCTURES: int = 1  # 1 structure/day during validation
MAX_DAILY_FILLS: int = 20  # stop death-by-churn (partial fills included)

# =============================================================================
# OPTIONS PARAMETERS
# =============================================================================
MIN_DTE: int = 30  # Minimum days to expiration per CLAUDE.md
MAX_DTE: int = 45  # Maximum days to expiration per CLAUDE.md

# =============================================================================
# NORTH STAR TARGETS - SINGLE SOURCE OF TRUTH
# =============================================================================
# Validated autonomous iron condor system → consistent $500/month on $25K+ capital.
NORTH_STAR_TARGET_DATE: date = date(2029, 11, 14)
NORTH_STAR_TARGET_CAPITAL: float = 25_000.0
NORTH_STAR_MONTHLY_AFTER_TAX: float = 500.0
NORTH_STAR_DAILY_AFTER_TAX: float = 16.67
NORTH_STAR_TARGET_WIN_RATE_PCT: float = 80.0
NORTH_STAR_PAPER_VALIDATION_DAYS: int = 90

# =============================================================================
# FORBIDDEN STRATEGIES
# =============================================================================
FORBIDDEN_STRATEGIES: set[str] = {
    "naked_put",  # NO NAKED PUTS - must use spreads
    "naked_call",  # NO NAKED CALLS
    "short_straddle",  # Undefined risk
    "short_strangle",  # Undefined risk without wings
}
