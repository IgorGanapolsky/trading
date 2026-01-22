"""Trading Constants - Single Source of Truth.

This module contains trading constants that should NOT change between environments
and do NOT depend on pydantic or other optional dependencies.

CRITICAL: All trading-related modules should import constants from HERE
to avoid maintenance issues with duplicated definitions.

Created: Jan 19, 2026 (Adversarial audit finding - 4 duplicate definitions)
"""

# =============================================================================
# TICKER WHITELIST - SINGLE SOURCE OF TRUTH
# =============================================================================
# Per CLAUDE.md Jan 19, 2026: "SPY ONLY - best liquidity, tightest spreads"
# This is the ONLY place ticker whitelist should be defined.
# All modules MUST import from here to avoid maintenance issues.
# UPDATED Jan 19, 2026 (LL-244): IWM removed per adversarial audit
# =============================================================================
ALLOWED_TICKERS: set[str] = {"SPY"}  # SPY ONLY per CLAUDE.md Jan 19, 2026

# =============================================================================
# POSITION LIMITS - Phil Town Rule #1 (SINGLE SOURCE OF TRUTH)
# =============================================================================
# CRITICAL: All modules MUST import from HERE to avoid duplicates
# LL-281 (Jan 22, 2026): 8 contracts accumulated when max was 4 due to
# scattered definitions and race conditions.
# =============================================================================
MAX_POSITION_PCT: float = 0.05  # 5% max per position per CLAUDE.md
MAX_DAILY_LOSS_PCT: float = 0.05  # 5% max daily loss
MAX_POSITIONS: int = 4  # 1 iron condor = 4 legs max (HARDCODED per CLAUDE.md)
MAX_CONTRACTS_PER_TRADE: int = 1  # Max contracts per single trade
CRISIS_LOSS_PCT: float = 0.25  # 25% unrealized loss triggers crisis mode
CRISIS_POSITION_COUNT: int = 4  # More than 4 positions triggers crisis mode

# =============================================================================
# OPTIONS PARAMETERS
# =============================================================================
MIN_DTE: int = 30  # Minimum days to expiration per CLAUDE.md
MAX_DTE: int = 45  # Maximum days to expiration per CLAUDE.md

# =============================================================================
# FORBIDDEN STRATEGIES
# =============================================================================
FORBIDDEN_STRATEGIES: set[str] = {
    "naked_put",  # NO NAKED PUTS - must use spreads
    "naked_call",  # NO NAKED CALLS
    "short_straddle",  # Undefined risk
    "short_strangle",  # Undefined risk without wings
}
