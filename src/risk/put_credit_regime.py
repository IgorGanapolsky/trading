"""Regime snapshot and entry gate for spy_put_credit paper validation.

Research-backed minimal filter (Parallel deep research 2026-07-24):
- Prefer short premium when IV rank proxy is elevated (IVR >= 30)
- Hard veto when VIX is extreme (VIX > 30)
- Optional trend soft-flag: SPY vs 200-day SMA (logged; hard only if enabled)

Does NOT claim edge. Live remains blocked by kill switch until cohort gates pass.
Missing market data fails closed for *new entries* (fail open for pure logging).
"""

from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# Research defaults — keep knobs explicit for audit.
# Preferred short-premium IVR for *edge claims* is still 30 (research 2026-07-24).
# Paper validation may lower the hard floor via PUT_CREDIT_MIN_IVR so the n→30
# cohort is not frozen in multi-week low-vol regimes; stratify scorecards by
# iv_rank_proxy >= RESEARCH_PREFERRED_IVR when claiming edge.
RESEARCH_PREFERRED_IVR = float(os.environ.get("PUT_CREDIT_RESEARCH_IVR", "30"))
MIN_IV_RANK = float(os.environ.get("PUT_CREDIT_MIN_IVR", "30"))
MAX_VIX = float(os.environ.get("PUT_CREDIT_MAX_VIX", "30"))
REQUIRE_ABOVE_200DMA = os.environ.get("PUT_CREDIT_REQUIRE_200DMA", "0").lower() in {
    "1",
    "true",
    "yes",
}
# When true, missing IVR/VIX blocks entries. Default true for reliability.
FAIL_CLOSED_ON_MISSING = os.environ.get("PUT_CREDIT_REGIME_FAIL_CLOSED", "1").lower() in {
    "1",
    "true",
    "yes",
}


@dataclass(frozen=True)
class RegimeSnapshot:
    """Point-in-time regime fields recorded on each put-credit entry."""

    captured_at: str
    spy_price: float | None
    vix: float | None
    iv_rank_proxy: float | None
    iv_rank_method: str
    spy_sma_200: float | None
    spy_above_200dma: bool | None
    source_errors: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source_errors"] = list(self.source_errors)
        return payload


def _spy_sma_200(spy_price: float | None) -> tuple[float | None, bool | None, str | None]:
    """Return (sma200, above, error)."""
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        from src.utils.alpaca_client import get_alpaca_credentials

        key, secret = get_alpaca_credentials()
        if not key:
            return None, None, "no_alpaca_credentials"
        client = StockHistoricalDataClient(key, secret)
        end = datetime.now(UTC)
        start = end - timedelta(days=400)
        req = StockBarsRequest(
            symbol_or_symbols=["SPY"],
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
            # Without an explicit feed the SDK falls back to a data tier this account
            # is not entitled to. Every request failed, the 200-day average came back
            # None, and fail_closed_on_missing correctly refused every entry -- for 12
            # days, while the scheduled check reported success. Mirrors
            # src/utils/market_data.py, which already defaults to iex.
            feed=os.getenv("ALPACA_DATA_FEED", "iex"),
        )
        bars = client.get_stock_bars(req)
        rows = bars.data.get("SPY") if hasattr(bars, "data") else None
        if not rows or len(rows) < 200:
            return None, None, f"insufficient_spy_bars:{0 if not rows else len(rows)}"
        closes = [float(b.close) for b in rows if getattr(b, "close", None) is not None]
        if len(closes) < 200:
            return None, None, f"insufficient_spy_closes:{len(closes)}"
        sma = sum(closes[-200:]) / 200.0
        price = float(spy_price) if spy_price is not None else closes[-1]
        return round(sma, 4), bool(price >= sma), None
    except Exception as exc:  # noqa: BLE001
        logger.debug("SPY 200-DMA fetch failed: %s", exc)
        return None, None, f"spy_sma_error:{exc}"


def capture_regime_snapshot(spy_price: float | None = None) -> RegimeSnapshot:
    """Best-effort regime snapshot. Never raises — returns partial fields + errors."""

    errors: list[str] = []
    vix: float | None = None
    ivr: float | None = None
    ivr_method = "none"

    try:
        from src.options.vix_monitor import VIXMonitor

        monitor = VIXMonitor()
        vix = float(monitor.get_current_vix())
    except Exception as exc:  # noqa: BLE001
        errors.append(f"vix:{exc}")
        logger.warning("Regime snapshot: VIX unavailable: %s", exc)

    try:
        from src.markets.iv_rank import current_iv_rank_proxy

        ivr = current_iv_rank_proxy("SPY")
        if ivr is not None:
            ivr_method = "vixy_percentile_proxy"
        else:
            errors.append("iv_rank_proxy_none")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"iv_rank:{exc}")
        logger.warning("Regime snapshot: IV rank proxy unavailable: %s", exc)

    # Prefer VIX percentile as IVR when proxy missing but VIX monitor works
    if ivr is None:
        try:
            from src.options.vix_monitor import VIXMonitor

            pct = float(VIXMonitor().get_vix_percentile(252))
            ivr = pct
            ivr_method = "vix_percentile_252"
        except Exception as exc:  # noqa: BLE001
            errors.append(f"vix_percentile:{exc}")

    sma, above, sma_err = _spy_sma_200(spy_price)
    if sma_err:
        errors.append(sma_err)

    return RegimeSnapshot(
        captured_at=datetime.now(UTC).isoformat(),
        spy_price=float(spy_price) if spy_price is not None else None,
        vix=round(vix, 4) if vix is not None else None,
        iv_rank_proxy=round(ivr, 2) if ivr is not None else None,
        iv_rank_method=ivr_method,
        spy_sma_200=sma,
        spy_above_200dma=above,
        source_errors=tuple(errors),
    )


def evaluate_regime_gate(
    snapshot: RegimeSnapshot | dict[str, Any],
    *,
    min_iv_rank: float = MIN_IV_RANK,
    max_vix: float = MAX_VIX,
    require_above_200dma: bool = REQUIRE_ABOVE_200DMA,
    fail_closed_on_missing: bool = FAIL_CLOSED_ON_MISSING,
) -> dict[str, Any]:
    """Return {allowed, blockers, soft_flags, snapshot}.

    Hard blockers (default):
    - VIX > max_vix
    - IV rank proxy < min_iv_rank
    - missing VIX or IVR when fail_closed_on_missing
    Soft flags (never block unless require_above_200dma):
    - SPY below 200-DMA
    """

    if isinstance(snapshot, RegimeSnapshot):
        snap = snapshot.as_dict()
    else:
        snap = dict(snapshot)

    blockers: list[str] = []
    soft: list[str] = []

    vix = snap.get("vix")
    ivr = snap.get("iv_rank_proxy")
    above = snap.get("spy_above_200dma")

    if vix is None:
        msg = "VIX unavailable for regime gate"
        if fail_closed_on_missing:
            blockers.append(msg)
        else:
            soft.append(msg)
    elif float(vix) > float(max_vix):
        blockers.append(f"VIX {float(vix):.2f} > max {float(max_vix):.2f} (hard veto)")

    if ivr is None:
        msg = "IV rank proxy unavailable for regime gate"
        if fail_closed_on_missing:
            blockers.append(msg)
        else:
            soft.append(msg)
    elif float(ivr) < float(min_iv_rank):
        blockers.append(
            f"IV rank proxy {float(ivr):.1f} < min {float(min_iv_rank):.1f} (short-premium filter)"
        )
    elif float(ivr) < float(RESEARCH_PREFERRED_IVR):
        # Allowed under a lowered paper floor, but not "rich premium" for edge claims.
        soft.append(
            f"IV rank proxy {float(ivr):.1f} < research preferred "
            f"{float(RESEARCH_PREFERRED_IVR):.1f} (lean premium; stratify later)"
        )

    if above is False:
        msg = "SPY below 200-day SMA (trend soft-flag)"
        if require_above_200dma:
            blockers.append(msg)
        else:
            soft.append(msg)
    elif above is None:
        soft.append("SPY 200-DMA unavailable")

    return {
        "allowed": not blockers,
        "blockers": blockers,
        "soft_flags": soft,
        "thresholds": {
            "min_iv_rank": min_iv_rank,
            "research_preferred_ivr": RESEARCH_PREFERRED_IVR,
            "max_vix": max_vix,
            "require_above_200dma": require_above_200dma,
            "fail_closed_on_missing": fail_closed_on_missing,
        },
        "snapshot": snap,
    }


def attach_counterfactuals(
    exit_eval: dict[str, Any],
    *,
    credit: float,
    quantity: int = 1,
    dte: int | None = None,
) -> dict[str, Any]:
    """Add public-rule counterfactuals (50% TP, 21 DTE) without changing live exits."""

    qty = abs(int(quantity or 1))
    max_profit = float(credit) * 100.0 * qty
    pnl = float(exit_eval.get("estimated_pnl") or 0.0)
    out = dict(exit_eval)
    out["counterfactuals"] = {
        "tp_25_target": round(max_profit * 0.25, 2),
        "tp_50_target": round(max_profit * 0.50, 2),
        "would_hit_tp_25_now": pnl >= max_profit * 0.25,
        "would_hit_tp_50_now": pnl >= max_profit * 0.50,
        "public_exit_dte": 21,
        "dte_now": dte,
        "would_trigger_public_21dte_exit": (dte is not None and dte <= 21),
        "note": (
            "Counterfactuals only — system still exits at profile TP 25% / exit_dte=7. "
            "Used to compare our rules to public 50%/21-DTE research without re-running history."
        ),
    }
    return out
