"""Trading Constants - Single Source of Truth."""

from __future__ import annotations

import re

from src.core.trading_profiles import get_iron_condor_profile

ALLOWED_TICKERS: set[str] = {"SPY", "SPX", "XSP", "QQQ", "IWM"}
ACTIVE_IRON_CONDOR_PROFILE = get_iron_condor_profile()

MAX_POSITION_PCT: float = ACTIVE_IRON_CONDOR_PROFILE.position_size_pct
MAX_DAILY_LOSS_PCT: float = 0.02
MAX_CONCURRENT_IRON_CONDORS: int = ACTIVE_IRON_CONDOR_PROFILE.max_concurrent_positions
MAX_POSITIONS: int = MAX_CONCURRENT_IRON_CONDORS * 4
MAX_CONTRACTS_PER_TRADE: int = ACTIVE_IRON_CONDOR_PROFILE.max_contracts_per_trade
MAX_CUMULATIVE_RISK_PCT: float = MAX_POSITION_PCT * MAX_CONCURRENT_IRON_CONDORS
CRISIS_LOSS_PCT: float = 0.25
CRISIS_POSITION_COUNT: int = 4
IRON_CONDOR_UNDERLYING: str = ACTIVE_IRON_CONDOR_PROFILE.underlying
IRON_CONDOR_TARGET_DTE: int = ACTIVE_IRON_CONDOR_PROFILE.target_dte
IRON_CONDOR_TARGET_DELTA: float = ACTIVE_IRON_CONDOR_PROFILE.short_delta
IRON_CONDOR_DELTA_MIN: float = ACTIVE_IRON_CONDOR_PROFILE.delta_band_min
IRON_CONDOR_DELTA_MAX: float = ACTIVE_IRON_CONDOR_PROFILE.delta_band_max
IRON_CONDOR_WING_WIDTH: float = ACTIVE_IRON_CONDOR_PROFILE.wing_width
IRON_CONDOR_STOP_LOSS_MULTIPLIER: float = ACTIVE_IRON_CONDOR_PROFILE.stop_loss_pct
IRON_CONDOR_EXIT_DTE: int = ACTIVE_IRON_CONDOR_PROFILE.exit_dte
IRON_CONDOR_MIN_HOLD_HOURS: int = ACTIVE_IRON_CONDOR_PROFILE.min_hold_hours

# Canonical Profit Target
IC_PROFIT_TARGET_PCT: float = ACTIVE_IRON_CONDOR_PROFILE.take_profit_pct

MAX_EXPIRY_CONCENTRATION_PCT: float = 0.40
FOMO_INTRADAY_MOVE_PCT: float = 0.02
STOP_LOSS_COOLING_HOURS: int = 24
MAX_DAILY_STRUCTURES: int = ACTIVE_IRON_CONDOR_PROFILE.max_daily_structures
MAX_DAILY_FILLS: int = 20
MIN_DTE: int = ACTIVE_IRON_CONDOR_PROFILE.min_dte
MAX_DTE: int = ACTIVE_IRON_CONDOR_PROFILE.max_dte

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
