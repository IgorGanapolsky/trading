"""Trading Constants - Single Source of Truth."""

from __future__ import annotations

import re

ALLOWED_TICKERS: set[str] = {"SPY"}  # SPY ONLY per CLAUDE.md — best liquidity, no early assignment
MAX_POSITION_PCT: float = 0.05
MAX_DAILY_LOSS_PCT: float = 0.02
MAX_POSITIONS: int = 8  # 2 ICs x 4 legs — CLAUDE.md mandate
MAX_CONTRACTS_PER_TRADE: int = 2
MAX_CONCURRENT_IRON_CONDORS: int = 2  # CLAUDE.md: 2 concurrent ICs max (8 legs)
MAX_CUMULATIVE_RISK_PCT: float = 0.10
CRISIS_LOSS_PCT: float = 0.25
CRISIS_POSITION_COUNT: int = 4
IRON_CONDOR_STOP_LOSS_MULTIPLIER: float = 1.0

# Canonical Profit Target
IC_PROFIT_TARGET_PCT: float = 0.50

MAX_EXPIRY_CONCENTRATION_PCT: float = 0.40
FOMO_INTRADAY_MOVE_PCT: float = 0.02
STOP_LOSS_COOLING_HOURS: int = 24
MAX_DAILY_STRUCTURES: int = 1  # Reverted: 2 caused churn loop
MAX_DAILY_FILLS: int = 20
MIN_DTE: int = 30
MAX_DTE: int = 45

NORTH_STAR_TARGET_CAPITAL: float = 300_000.0
NORTH_STAR_MONTHLY_AFTER_TAX: float = 6_000.0
NORTH_STAR_DAILY_AFTER_TAX: float = 200.0
NORTH_STAR_TARGET_WIN_RATE_PCT: float = 80.0
NORTH_STAR_PAPER_VALIDATION_DAYS: int = 90

FORBIDDEN_STRATEGIES: set[str] = {"naked_put", "naked_call", "short_straddle", "short_strangle"}

_OCC_PATTERN = re.compile(r"^([A-Z]{1,6})(\d{6})[PC](\d{8})$")

def extract_underlying(symbol: str) -> str:
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
