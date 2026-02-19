"""Trading Constants - Single Source of Truth.

This module contains trading constants that should NOT change between environments
and do NOT depend on pydantic or other optional dependencies.

CRITICAL: All trading-related modules should import constants from HERE
to avoid maintenance issues with duplicated definitions.

Created: Jan 19, 2026 (Adversarial audit finding - 4 duplicate definitions)
Updated: Feb 17, 2026 (P0 tech debt - consolidated 5 duplicate extract_underlying impls)
"""

import re
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
# BEHAVIORAL + EXPIRY CONCENTRATION GUARDS
# =============================================================================
MAX_EXPIRY_CONCENTRATION_PCT: float = 0.40  # 40% max ICs in one expiry week
FOMO_INTRADAY_MOVE_PCT: float = 0.02        # 2% SPY move blocks new IC entry
STOP_LOSS_COOLING_HOURS: int = 24            # Hours to wait after stop-loss exit

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
# North Star = reach $6K/month after-tax as soon as possible (no fixed deadline date).
# Keep target capital as an implied benchmark (2% monthly yield -> ~$300K capital base).
NORTH_STAR_TARGET_DATE: date | None = None
NORTH_STAR_TARGET_CAPITAL: float = 300_000.0
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

# =============================================================================
# OCC SYMBOL PARSING - SINGLE SOURCE OF TRUTH
# =============================================================================
# Consolidates 5 duplicate implementations (P0 tech debt audit Feb 17, 2026):
#   - src/safety/mandatory_trade_gate.py::_extract_underlying
#   - src/trading/options_executor.py::_extract_underlying_from_option
#   - src/risk/pre_trade_checklist.py::PreTradeChecklist._extract_underlying
#   - src/validators/rule_one_validator.py::RuleOneValidator._extract_underlying
#   - src/risk/trade_gateway.py::TradeGateway._get_underlying_symbol
# =============================================================================
_OCC_PATTERN = re.compile(r"^([A-Z]{1,6})(\d{6})[PC](\d{8})$")


def extract_underlying(symbol: str) -> str:
    """Extract underlying ticker from an option symbol (OCC format).

    OCC format: [UNDERLYING][YYMMDD][P/C][STRIKE*1000]
    Examples:
        SPY260115C00600000 -> SPY
        SOFI260206P00024000 -> SOFI
        SPY -> SPY

    Args:
        symbol: Stock ticker or OCC option symbol.

    Returns:
        Underlying ticker symbol in uppercase.
    """
    symbol = symbol.strip().upper()
    if len(symbol) <= 6:
        return symbol
    match = _OCC_PATTERN.match(symbol)
    if match:
        return match.group(1)
    if len(symbol) >= 15:
        potential_underlying = symbol[:-15]
        if potential_underlying and potential_underlying.isalpha():
            return potential_underlying
    return symbol
