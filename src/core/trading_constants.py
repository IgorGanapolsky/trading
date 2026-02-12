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
# Per CLAUDE.md: SPY/SPX/XSP for index options
# SPY = Standard equity ETF option (100% short-term capital gains)
# SPX/XSP = Index options with Section 1256 tax treatment (60/40 split)
# This is the ONLY place ticker whitelist should be defined.
# All modules MUST import from here to avoid maintenance issues.
# UPDATED Jan 19, 2026 (LL-244): IWM removed per adversarial audit
# UPDATED Feb 8, 2026: Added SPX and XSP for Section 1256 tax treatment
# =============================================================================
ALLOWED_TICKERS: set[str] = {"SPY", "SPX", "XSP"}  # SPY/SPX/XSP per CLAUDE.md Feb 8, 2026

# =============================================================================
# POSITION LIMITS - Phil Town Rule #1 (SINGLE SOURCE OF TRUTH)
# =============================================================================
# CRITICAL: All modules MUST import from HERE to avoid duplicates
# LL-281 (Jan 22, 2026): 8 contracts accumulated when max was 4 due to
# scattered definitions and race conditions.
# =============================================================================
MAX_POSITION_PCT: float = 0.05  # 5% max per position per CLAUDE.md ($5K on $100K account)
MAX_DAILY_LOSS_PCT: float = 0.05  # 5% max daily loss
MAX_POSITIONS: int = 8  # 2 iron condors = 8 legs max (UPDATED Jan 30, 2026 for $100K account)
MAX_CONTRACTS_PER_TRADE: int = 2  # Max contracts per single trade (scaled for $100K)
CRISIS_LOSS_PCT: float = 0.25  # 25% unrealized loss triggers crisis mode
CRISIS_POSITION_COUNT: int = 4  # More than 4 positions triggers crisis mode
# Iron condor stop-loss: close if one side reaches 200% of credit received (per CLAUDE.md)
IRON_CONDOR_STOP_LOSS_MULTIPLIER: float = 2.0

# =============================================================================
# OPTIONS PARAMETERS
# =============================================================================
MIN_DTE: int = 30  # Minimum days to expiration per CLAUDE.md
MAX_DTE: int = 45  # Maximum days to expiration per CLAUDE.md

# =============================================================================
# NORTH STAR TARGETS - SINGLE SOURCE OF TRUTH
# =============================================================================
# Financial independence target by CEO's 50th birthday.
NORTH_STAR_TARGET_DATE: date = date(2029, 11, 14)
NORTH_STAR_TARGET_CAPITAL: float = 600_000.0
NORTH_STAR_MONTHLY_AFTER_TAX: float = 6_000.0
NORTH_STAR_DAILY_AFTER_TAX: float = 200.0
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
