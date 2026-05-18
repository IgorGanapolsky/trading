"""Option Chain Service - Delta-based strike selection from live Alpaca data.

Replaces the 5% OTM heuristic with real greeks from the options chain.
When strikes at target delta aren't available, falls back to the heuristic
with a logged warning so the trade is traceable.

Created: 2026-03-25 (closes explainer gap #1: fake 15-delta)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from math import log, sqrt
from typing import TYPE_CHECKING, Literal, Sequence

from src.core.trading_constants import (
    IRON_CONDOR_DELTA_MAX,
    IRON_CONDOR_DELTA_MIN,
    IRON_CONDOR_TARGET_DELTA,
    IRON_CONDOR_TARGET_DTE,
    IRON_CONDOR_UNDERLYING,
    IRON_CONDOR_WING_WIDTH,
    MAX_DTE,
    MIN_DTE,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Delta tolerance band for strike selection
DELTA_TARGET = IRON_CONDOR_TARGET_DELTA
DELTA_MIN = IRON_CONDOR_DELTA_MIN
DELTA_MAX = IRON_CONDOR_DELTA_MAX
MIN_OPEN_INTEREST = 0  # OI=0 normal for newer expiries
MIN_BID = 0.05


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass
class StrikeSelection:
    """Result of delta-based strike selection (consumed by iron_condor_trader)."""

    short_put: float
    long_put: float
    short_call: float
    long_call: float
    put_delta: float  # Actual delta of selected short put
    call_delta: float  # Actual delta of selected short call
    method: str  # "live_delta" or "heuristic_fallback"
    expiry: str  # YYYY-MM-DD
    put_bid: float = 0.0  # Short put bid (we collect this)
    call_bid: float = 0.0  # Short call bid (we collect this)
    long_put_ask: float = 0.0  # Long put ask (we pay this)
    long_call_ask: float = 0.0  # Long call ask (we pay this)

    @property
    def net_credit(self) -> float:
        """Net credit = short premiums collected - long premiums paid."""
        return (self.put_bid + self.call_bid) - (self.long_put_ask + self.long_call_ask)


@dataclass
class OptionContract:
    """Normalized option contract from the chain."""

    symbol: str
    strike: float
    expiry: date
    option_type: Literal["call", "put"]
    bid: float | None
    ask: float | None
    mid: float | None
    delta: float | None
    iv: float | None
    gamma: float | None
    theta: float | None
    vega: float | None
    open_interest: int
    volume: int

    @property
    def delta_abs(self) -> float | None:
        if self.delta is None:
            return None
        return abs(self.delta)


# ---------------------------------------------------------------------------
# High-level API (used by iron_condor_trader.py)
# ---------------------------------------------------------------------------


def select_strikes_by_delta(
    underlying_price: float,
    underlying: str = IRON_CONDOR_UNDERLYING,
    wing_width: float = IRON_CONDOR_WING_WIDTH,
    target_delta: float = DELTA_TARGET,
    target_dte: int = IRON_CONDOR_TARGET_DTE,
    min_dte: int = MIN_DTE,
    max_dte: int = MAX_DTE,
) -> StrikeSelection:
    """Select iron condor strikes using real delta from Alpaca option chain.

    Falls back to heuristic if chain data is unavailable.
    """
    expiry_date = _find_expiry_friday(target_dte, min_dte)

    try:
        return _select_from_live_chain(
            underlying,
            underlying_price,
            wing_width,
            target_delta,
            expiry_date,
            min_dte,
            max_dte,
        )
    except Exception as e:
        logger.warning(f"Live chain unavailable ({e}), using heuristic fallback")
        return _heuristic_fallback(underlying_price, wing_width, expiry_date)


# ---------------------------------------------------------------------------
# OptionChainService (lower-level, reusable)
# ---------------------------------------------------------------------------


class OptionChainService:
    """Fetches and normalizes option contracts from Alpaca."""

    def __init__(self, data_client: object | None = None):
        from src.utils.alpaca_client import get_options_data_client

        self._client = data_client or get_options_data_client()
        if not self._client:
            raise RuntimeError("Alpaca credentials required for option chain data")

    def query(self, underlying: str, expiry: date) -> list[OptionContract]:
        from alpaca.data.requests import OptionChainRequest

        payload = OptionChainRequest(
            underlying_symbol=underlying,
            expiration_date_gte=expiry.strftime("%Y-%m-%d"),
            expiration_date_lte=expiry.strftime("%Y-%m-%d"),
        )
        try:
            chain = self._client.get_option_chain(payload)
        except Exception as exc:
            logger.error("Failed to fetch option chain for %s: %s", underlying, exc)
            raise

        return [self._normalize(sym, snap) for sym, snap in chain.items()]

    def select_by_delta(
        self,
        contracts: Sequence[OptionContract],
        option_type: Literal["call", "put"],
        target_delta: float,
        delta_band: tuple[float, float] = (DELTA_MIN, DELTA_MAX),
        min_open_interest: int = MIN_OPEN_INTEREST,
    ) -> OptionContract | None:
        lower, upper = delta_band
        candidates = []
        for c in contracts:
            if c.option_type != option_type:
                continue
            if c.mid is None or c.mid <= 0:
                continue
            d = c.delta_abs
            if d is None or not (lower <= d <= upper):
                continue
            if c.open_interest < min_open_interest:
                continue
            candidates.append((abs(d - target_delta), c))
        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]

    def _normalize(self, symbol: str, snapshot: object) -> OptionContract:
        parsed = _parse_occ(symbol)
        bid, ask = _get_quote_prices(snapshot)
        mid = _calculate_mid(bid, ask, snapshot)
        iv = getattr(snapshot, "implied_volatility", None)
        oi = int(getattr(snapshot, "open_interest", 0) or 0)
        vol = int(getattr(snapshot, "volume", 0) or 0)
        delta = _extract_delta(snapshot, parsed, mid, iv)
        greeks = getattr(snapshot, "greeks", None)
        return OptionContract(
            symbol=symbol,
            strike=parsed.strike,
            expiry=parsed.expiry,
            option_type=parsed.option_type,
            bid=bid,
            ask=ask,
            mid=mid,
            delta=delta,
            iv=iv,
            gamma=getattr(greeks, "gamma", None) if greeks else None,
            theta=getattr(greeks, "theta", None) if greeks else None,
            vega=getattr(greeks, "vega", None) if greeks else None,
            open_interest=oi,
            volume=vol,
        )


# ---------------------------------------------------------------------------
# Internal: live chain selection
# ---------------------------------------------------------------------------


def _select_from_live_chain(
    underlying: str,
    price: float,
    wing_width: float,
    target_delta: float,
    expiry_date: datetime,
    min_dte: int,
    max_dte: int,
) -> StrikeSelection:
    """Select strikes from live Alpaca option chain by delta."""
    from src.data.iv_data_provider import IVDataProvider

    provider = IVDataProvider()
    expiry_str = expiry_date.strftime("%Y-%m-%d")

    options = provider.get_options_chain_with_greeks(
        symbol=underlying,
        expiration=expiry_str,
        min_delta=DELTA_MIN,
        max_delta=DELTA_MAX,
        min_open_interest=MIN_OPEN_INTEREST,
    )

    # Try adjacent Fridays if no results
    if not options:
        for offset_weeks in [-1, 1, -2, 2]:
            alt_expiry = expiry_date + timedelta(weeks=offset_weeks)
            alt_dte = (alt_expiry - datetime.now()).days
            if alt_dte < min_dte or alt_dte > max_dte:
                continue
            alt_str = alt_expiry.strftime("%Y-%m-%d")
            options = provider.get_options_chain_with_greeks(
                symbol=underlying,
                expiration=alt_str,
                min_delta=DELTA_MIN,
                max_delta=DELTA_MAX,
                min_open_interest=MIN_OPEN_INTEREST,
            )
            if options:
                expiry_str = alt_str
                break

    if not options:
        raise ValueError(
            f"No {underlying} options with delta {DELTA_MIN}-{DELTA_MAX} near {expiry_str}"
        )

    puts = [o for o in options if o["type"] == "put" and o.get("bid", 0) >= MIN_BID]
    calls = [o for o in options if o["type"] == "call" and o.get("bid", 0) >= MIN_BID]

    if not puts or not calls:
        raise ValueError(f"Insufficient liquid puts ({len(puts)}) or calls ({len(calls)})")

    best_put = min(puts, key=lambda o: abs(abs(o["delta"]) - target_delta))
    best_call = min(calls, key=lambda o: abs(abs(o["delta"]) - target_delta))

    short_put = best_put["strike"]
    short_call = best_call["strike"]
    # Compute target wing strikes, then snap to nearest valid strike in the chain.
    # SPY has $1 strikes near the money but $5 increments further OTM.
    # Without snapping, 712 + 10 = 722 which doesn't exist (should be 720 or 725).
    #
    # CRITICAL: snap against the UNFILTERED chain. The `options` list above was
    # delta-band-filtered to [DELTA_MIN, DELTA_MAX] for short-strike selection,
    # which means the deep-OTM long-wing strikes (intentionally outside that
    # band) are absent. Snapping against the filtered list silently collapses
    # wings — at best to the band edge, at worst inverted. The wing-width
    # validator (PR #3996) catches gross violations but a $5 wing where $10
    # was requested passes the 50% MIN_WING_PCT and contaminates risk math.
    unfiltered = provider.get_options_chain_with_greeks(
        symbol=underlying,
        expiration=expiry_str,
        min_open_interest=MIN_OPEN_INTEREST,
    )
    snap_universe = unfiltered if unfiltered else options
    all_puts = [o for o in snap_universe if o["type"] == "put"]
    all_calls = [o for o in snap_universe if o["type"] == "call"]

    def _snap_to_chain(target: float, chain: list[dict], direction: str) -> float:
        """Find the nearest valid strike to target from the option chain."""
        strikes = sorted(set(o["strike"] for o in chain))
        if not strikes:
            return target
        if direction == "below":  # long put: want strike <= target
            valid = [s for s in strikes if s <= target]
            return max(valid) if valid else min(strikes)
        else:  # long call: want strike >= target
            valid = [s for s in strikes if s >= target]
            return min(valid) if valid else max(strikes)

    long_put_strike = _snap_to_chain(short_put - wing_width, all_puts, "below")
    long_call_strike = _snap_to_chain(short_call + wing_width, all_calls, "above")

    # Validate wing widths — reject if snap produced a wing too narrow.
    # SPY far OTM has $5 strike increments, so $5 wing on $10 target is valid (50%).
    MIN_WING_PCT = 0.5  # Allow $5 wings on $10 target (SPY far OTM reality)
    put_wing = short_put - long_put_strike
    call_wing = long_call_strike - short_call
    if put_wing < wing_width * MIN_WING_PCT or call_wing < wing_width * MIN_WING_PCT:
        logger.warning(
            f"Wing too narrow after chain snap: put_wing=${put_wing:.0f} call_wing=${call_wing:.0f} "
            f"(target=${wing_width:.0f}, min=${wing_width * MIN_WING_PCT:.0f}). "
            f"Chain may not have strikes far enough OTM."
        )
        return _heuristic_fallback(price, wing_width, expiry_date)

    long_put_opt = next((o for o in all_puts if o["strike"] == long_put_strike), None)
    long_call_opt = next((o for o in all_calls if o["strike"] == long_call_strike), None)

    # Use ask price for long legs (we're buying), with conservative estimate if not found
    long_put_ask = long_put_opt.get("ask", 0.0) if long_put_opt else best_put.get("bid", 0.0) * 0.4
    long_call_ask = (
        long_call_opt.get("ask", 0.0) if long_call_opt else best_call.get("bid", 0.0) * 0.4
    )

    result = StrikeSelection(
        short_put=short_put,
        long_put=long_put_strike,
        short_call=short_call,
        long_call=long_call_strike,
        put_delta=abs(best_put["delta"]),
        call_delta=abs(best_call["delta"]),
        method="live_delta",
        expiry=expiry_str,
        put_bid=best_put.get("bid", 0.0),
        call_bid=best_call.get("bid", 0.0),
        long_put_ask=long_put_ask,
        long_call_ask=long_call_ask,
    )

    logger.info(
        f"Delta-selected strikes: SP={short_put} (delta={result.put_delta:.3f}) "
        f"SC={short_call} (delta={result.call_delta:.3f}) | "
        f"Short bids: put=${result.put_bid:.2f} call=${result.call_bid:.2f} | "
        f"Long asks: put=${result.long_put_ask:.2f} call=${result.long_call_ask:.2f} | "
        f"Net credit=${result.net_credit:.2f} | "
        f"Expiry={expiry_str}"
    )
    return result


# ---------------------------------------------------------------------------
# Internal: heuristic fallback
# ---------------------------------------------------------------------------


def _heuristic_fallback(price: float, wing_width: float, expiry_date: datetime) -> StrikeSelection:
    """Fallback: 5% OTM rounded to $5 increments (SPY OTM strike spacing)."""

    def round_to_5(x: float) -> float:
        return round(x / 5) * 5

    short_put = round_to_5(price * 0.95)
    short_call = round_to_5(price * 1.05)

    logger.warning(
        f"HEURISTIC FALLBACK: strikes at +/-5%% OTM "
        f"(SP={short_put}, SC={short_call}) — NOT true 15-delta"
    )

    return StrikeSelection(
        short_put=short_put,
        long_put=short_put - wing_width,
        short_call=short_call,
        long_call=short_call + wing_width,
        put_delta=0.0,
        call_delta=0.0,
        method="heuristic_fallback",
        expiry=expiry_date.strftime("%Y-%m-%d"),
    )


# ---------------------------------------------------------------------------
# Internal: OCC parsing and greeks helpers
# ---------------------------------------------------------------------------


@dataclass
class _ParsedOcc:
    expiry: date
    strike: float
    option_type: Literal["call", "put"]


def _parse_occ(symbol: str) -> _ParsedOcc:
    idx = 0
    while idx < len(symbol) and symbol[idx].isalpha():
        idx += 1
    body = symbol[idx:]
    year = int("20" + body[0:2])
    month = int(body[2:4])
    day = int(body[4:6])
    option_char = body[6]
    strike = int(body[7:]) / 1000.0
    return _ParsedOcc(
        expiry=date(year, month, day),
        strike=strike,
        option_type="call" if option_char == "C" else "put",
    )


def _get_quote_prices(snapshot: object) -> tuple[float | None, float | None]:
    quote = getattr(snapshot, "latest_quote", None)
    if quote:
        return getattr(quote, "bid_price", None), getattr(quote, "ask_price", None)
    return None, None


def _calculate_mid(bid: float | None, ask: float | None, snapshot: object) -> float | None:
    if bid and ask:
        return (bid + ask) / 2
    trade = getattr(snapshot, "latest_trade", None)
    if trade:
        return getattr(trade, "price", None)
    return None


def _extract_delta(
    snapshot: object,
    parsed: _ParsedOcc,
    mid: float | None,
    iv: float | None,
    underlying_price: float | None = None,
) -> float | None:
    greeks = getattr(snapshot, "greeks", None)
    delta = getattr(greeks, "delta", None) if greeks else None
    if delta is not None:
        return float(delta)
    # Black-Scholes fallback — needs underlying price, NOT option mid
    # If underlying_price not available, skip BS (wrong spot = wrong delta)
    if underlying_price is None or iv is None or iv <= 0:
        return None
    t_years = max((parsed.expiry - datetime.now().date()).days, 0) / 365
    if t_years <= 0:
        return None
    return _black_scholes_delta(
        spot=underlying_price,
        strike=parsed.strike,
        t_years=t_years,
        iv=iv,
        option_type=parsed.option_type,
    )


def _black_scholes_delta(
    spot: float,
    strike: float,
    t_years: float,
    iv: float,
    option_type: str,
    r: float = 0.05,
) -> float:
    if iv <= 0 or t_years <= 0 or spot <= 0:
        return 0.0
    try:
        from scipy.stats import norm
    except ImportError:
        logger.warning("scipy not available for BS delta calculation")
        return 0.0
    d1 = (log(spot / strike) + (r + 0.5 * iv**2) * t_years) / (iv * sqrt(t_years))
    if option_type == "call":
        return float(norm.cdf(d1))
    return float(norm.cdf(d1) - 1)


def _find_expiry_friday(target_dte: int, min_dte: int) -> datetime:
    """Find the nearest Friday at or after target DTE. Supports 4 DTE."""
    target_date = datetime.now() + timedelta(days=target_dte)
    days_until_friday = (4 - target_date.weekday()) % 7
    expiry = target_date + timedelta(days=days_until_friday)

    # Only enforce min_dte if it's not a short-dated request
    if target_dte >= 21 and (expiry - datetime.now()).days < min_dte:
        expiry += timedelta(days=7)
    return expiry
