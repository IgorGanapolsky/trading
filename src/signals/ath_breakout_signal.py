"""Prior-high breakout signal for SPY-style continuation setups."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

import pandas as pd
from src.utils.technical_indicators import calculate_atr

BreakoutStatus = Literal[
    "breakout",
    "holding_prior_high",
    "failed_breakout",
    "below_prior_high",
    "insufficient_data",
]


@dataclass(frozen=True)
class ATHBreakoutSignal:
    """Structured read of a prior all-time-high breakout setup."""

    symbol: str
    status: BreakoutStatus
    current_price: float
    prior_high: float
    support_floor: float
    atr: float
    breakout_pct: float
    stop_price: float
    risk_per_share: float
    target_1r: float
    target_2r: float
    confidence: float
    bias: str
    reason: str

    def to_dict(self) -> dict[str, float | str]:
        """Return a JSON-serializable representation for gates/reports."""
        return asdict(self)


def _scalar(value: object, default: float = 0.0) -> float:
    try:
        if hasattr(value, "item"):
            value = value.item()
        return float(value)
    except (TypeError, ValueError):
        return default


def _empty_signal(symbol: str, reason: str) -> ATHBreakoutSignal:
    return ATHBreakoutSignal(
        symbol=symbol,
        status="insufficient_data",
        current_price=0.0,
        prior_high=0.0,
        support_floor=0.0,
        atr=0.0,
        breakout_pct=0.0,
        stop_price=0.0,
        risk_per_share=0.0,
        target_1r=0.0,
        target_2r=0.0,
        confidence=0.0,
        bias="neutral",
        reason=reason,
    )


def generate_ath_breakout_signal(
    hist: pd.DataFrame,
    *,
    symbol: str = "SPY",
    lookback_bars: int = 252,
    min_bars: int = 30,
    atr_period: int = 14,
    support_buffer_atr: float = 0.50,
    stop_buffer_atr: float = 1.00,
    confirmation_bars: int = 5,
) -> ATHBreakoutSignal:
    """Translate a prior-high breakout chart read into a deterministic signal.

    The signal treats the highest high before the recent confirmation window as
    the old high. A bullish setup is valid while the latest close remains above
    that old high after an ATR-scaled noise buffer. A close beneath that support
    floor after a recent breakout is marked as a failed breakout.
    """
    required = {"High", "Low", "Close"}
    if hist.empty or not required.issubset(hist.columns):
        return _empty_signal(symbol, "Missing OHLC data for prior-high breakout signal")

    if len(hist) < min_bars or len(hist) < atr_period + 1:
        return _empty_signal(
            symbol,
            f"Need at least {max(min_bars, atr_period + 1)} bars for breakout signal",
        )

    ordered = hist.sort_index()
    recent_bars = max(1, confirmation_bars)
    prior_end = -(recent_bars + 1) if len(ordered) > recent_bars + 1 else -1
    prior_window = ordered.iloc[max(0, len(ordered) - lookback_bars - recent_bars) : prior_end]
    if prior_window.empty:
        return _empty_signal(symbol, "No prior bars available to define old high")

    current_price = _scalar(ordered["Close"].iloc[-1])
    current_low = _scalar(ordered["Low"].iloc[-1])
    prior_high = _scalar(prior_window["High"].max())
    atr = calculate_atr(ordered, period=atr_period)

    if current_price <= 0 or prior_high <= 0:
        return _empty_signal(symbol, "Invalid price data for breakout signal")

    support_buffer = max(0.0, atr * support_buffer_atr)
    stop_buffer = max(0.0, atr * stop_buffer_atr)
    support_floor = max(0.0, prior_high - support_buffer)
    stop_price = max(0.0, prior_high - stop_buffer)
    risk_per_share = max(0.0, current_price - stop_price)
    target_1r = current_price + risk_per_share
    target_2r = current_price + (2 * risk_per_share)
    breakout_pct = (current_price - prior_high) / prior_high

    recent_window = ordered.iloc[max(0, len(ordered) - confirmation_bars - 1) : -1]
    recent_breakout = bool((recent_window["Close"] > prior_high).any())

    if current_price > prior_high and current_low >= support_floor and not recent_breakout:
        status: BreakoutStatus = "breakout"
        confidence = min(0.95, 0.60 + min(0.25, breakout_pct * 10))
        bias = "bullish_continuation"
        reason = (
            f"{symbol} closed above prior high {prior_high:.2f}; "
            f"support floor is {support_floor:.2f}."
        )
    elif current_price >= support_floor and recent_breakout:
        status = "holding_prior_high"
        confidence = 0.65
        bias = "bullish_continuation"
        reason = (
            f"{symbol} is retesting and holding prior high support "
            f"within {support_buffer_atr:.2f} ATR buffer."
        )
    elif current_price < support_floor and recent_breakout:
        status = "failed_breakout"
        confidence = 0.80
        bias = "exit_or_hedge"
        reason = (
            f"{symbol} closed below ATR-buffered prior high support "
            f"({current_price:.2f} < {support_floor:.2f})."
        )
    else:
        status = "below_prior_high"
        confidence = 0.50
        bias = "neutral"
        reason = f"{symbol} has not confirmed a prior-high breakout."

    return ATHBreakoutSignal(
        symbol=symbol,
        status=status,
        current_price=round(current_price, 4),
        prior_high=round(prior_high, 4),
        support_floor=round(support_floor, 4),
        atr=round(atr, 4),
        breakout_pct=round(breakout_pct, 6),
        stop_price=round(stop_price, 4),
        risk_per_share=round(risk_per_share, 4),
        target_1r=round(target_1r, 4),
        target_2r=round(target_2r, 4),
        confidence=round(confidence, 3),
        bias=bias,
        reason=reason,
    )
