"""Regime snapshot and entry gate for spy_put_credit paper validation.

Research-backed minimal filter (Parallel deep research 2026-07-24)
plus Fahmy-style market-health OS (FORMAT steal 2026-09-10, AGENT-602):
- Prefer short premium when IV rank proxy is elevated (IVR >= 30)
- Hard veto when VIX is extreme (VIX > 30)
- Trend soft-flags: SPY vs 50-day SMA (intermediate) and 200-day SMA (longer-term)
- Pre-entry OS: market healthy / structure strong / clean setup / predefined risk
  (growth-stock earnings screens intentionally NOT transferred — SPY put-credit only)

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
REQUIRE_ABOVE_50DMA = os.environ.get("PUT_CREDIT_REQUIRE_50DMA", "0").lower() in {
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
    spy_sma_50: float | None = None
    spy_above_50dma: bool | None = None
    source_errors: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source_errors"] = list(self.source_errors)
        return payload


def _spy_sma_levels(
    spy_price: float | None,
) -> tuple[float | None, bool | None, float | None, bool | None, str | None]:
    """Return (sma50, above50, sma200, above200, error)."""
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        from src.utils.alpaca_client import get_alpaca_credentials

        key, secret = get_alpaca_credentials()
        if not key:
            return None, None, None, None, "no_alpaca_credentials"
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
            return None, None, None, None, f"insufficient_spy_bars:{0 if not rows else len(rows)}"
        closes = [float(b.close) for b in rows if getattr(b, "close", None) is not None]
        if len(closes) < 200:
            return None, None, None, None, f"insufficient_spy_closes:{len(closes)}"
        sma200 = sum(closes[-200:]) / 200.0
        sma50 = sum(closes[-50:]) / 50.0 if len(closes) >= 50 else None
        price = float(spy_price) if spy_price is not None else closes[-1]
        above200 = bool(price >= sma200)
        above50 = bool(price >= sma50) if sma50 is not None else None
        return (
            round(sma50, 4) if sma50 is not None else None,
            above50,
            round(sma200, 4),
            above200,
            None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("SPY SMA fetch failed: %s", exc)
        return None, None, None, None, f"spy_sma_error:{exc}"


def _spy_sma_200(spy_price: float | None) -> tuple[float | None, bool | None, str | None]:
    """Backward-compatible wrapper: (sma200, above200, error)."""
    _s50, _a50, s200, a200, err = _spy_sma_levels(spy_price)
    return s200, a200, err


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

            pct = VIXMonitor().get_vix_percentile(252, default=None)
            if pct is not None:
                ivr = float(pct)
                ivr_method = "vix_percentile_252"
        except Exception as exc:  # noqa: BLE001
            errors.append(f"vix_percentile:{exc}")

    sma50, above50, sma200, above200, sma_err = _spy_sma_levels(spy_price)
    if sma_err:
        errors.append(sma_err)

    return RegimeSnapshot(
        captured_at=datetime.now(UTC).isoformat(),
        spy_price=float(spy_price) if spy_price is not None else None,
        vix=round(vix, 4) if vix is not None else None,
        iv_rank_proxy=round(ivr, 2) if ivr is not None else None,
        iv_rank_method=ivr_method,
        spy_sma_200=sma200,
        spy_above_200dma=above200,
        spy_sma_50=sma50,
        spy_above_50dma=above50,
        source_errors=tuple(errors),
    )


def evaluate_regime_gate(
    snapshot: RegimeSnapshot | dict[str, Any],
    *,
    min_iv_rank: float = MIN_IV_RANK,
    max_vix: float = MAX_VIX,
    require_above_200dma: bool = REQUIRE_ABOVE_200DMA,
    require_above_50dma: bool = REQUIRE_ABOVE_50DMA,
    fail_closed_on_missing: bool = FAIL_CLOSED_ON_MISSING,
) -> dict[str, Any]:
    """Return {allowed, blockers, soft_flags, snapshot}.

    Hard blockers (default):
    - VIX > max_vix
    - IV rank proxy < min_iv_rank
    - missing VIX or IVR when fail_closed_on_missing
    Soft flags (never block unless require_above_*dma):
    - SPY below 50-DMA (intermediate health)
    - SPY below 200-DMA (longer-term health)
    """

    if isinstance(snapshot, RegimeSnapshot):
        snap = snapshot.as_dict()
    else:
        snap = dict(snapshot)

    blockers: list[str] = []
    soft: list[str] = []

    vix = snap.get("vix")
    ivr = snap.get("iv_rank_proxy")
    above200 = snap.get("spy_above_200dma")
    above50 = snap.get("spy_above_50dma")

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
        # Paper floor 0: VIX is the hard crash veto; missing IVR is a soft flag
        # so n→30 is not frozen on a percentile gap (AGENT-566).
        if fail_closed_on_missing and float(min_iv_rank) > 0:
            blockers.append(msg)
        else:
            soft.append(msg)
    elif float(min_iv_rank) > 0 and float(ivr) < float(min_iv_rank):
        blockers.append(
            f"IV rank proxy {float(ivr):.1f} < min {float(min_iv_rank):.1f} (short-premium filter)"
        )
    elif float(ivr) < float(RESEARCH_PREFERRED_IVR):
        # Allowed under a lowered paper floor, but not "rich premium" for edge claims.
        soft.append(
            f"IV rank proxy {float(ivr):.1f} < research preferred "
            f"{float(RESEARCH_PREFERRED_IVR):.1f} (lean premium; stratify later)"
        )

    if above50 is False:
        msg = "SPY below 50-day SMA (intermediate trend soft-flag)"
        if require_above_50dma:
            blockers.append(msg)
        else:
            soft.append(msg)
    elif above50 is None:
        soft.append("SPY 50-DMA unavailable")

    if above200 is False:
        msg = "SPY below 200-day SMA (trend soft-flag)"
        if require_above_200dma:
            blockers.append(msg)
        else:
            soft.append(msg)
    elif above200 is None:
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
            "require_above_50dma": require_above_50dma,
            "fail_closed_on_missing": fail_closed_on_missing,
        },
        "snapshot": snap,
    }


def evaluate_entry_operating_system(
    *,
    regime_gate: dict[str, Any],
    opportunity: dict[str, Any] | None,
    risk_plan: dict[str, Any] | None,
    min_dte: int = 30,
    max_dte: int = 45,
    min_short_delta: float = 0.10,
    max_short_delta: float = 0.25,
) -> dict[str, Any]:
    """Fahmy-style four-question OS mapped onto SPY put-credit (AGENT-602).

    Questions (all must be yes to pass):
    1. Market healthy? — regime gate allowed
    2. Structure strong? — defined-risk 1-lot put vertical with positive credit
    3. Clean technical setup? — short delta + DTE in profile band
    4. Predefined risk? — stop, take-profit, time exit, and size written before entry

    Intentionally does NOT screen equity earnings growth or multi-name watchlists.
    """

    answers: dict[str, Any] = {}
    fails: list[str] = []

    market_ok = bool(regime_gate.get("allowed"))
    answers["market_healthy"] = {
        "yes": market_ok,
        "detail": {
            "blockers": list(regime_gate.get("blockers") or []),
            "soft_flags": list(regime_gate.get("soft_flags") or []),
        },
    }
    if not market_ok:
        fails.append("market_healthy=no")

    structure_ok = False
    structure_detail: dict[str, Any] = {"reason": "no_opportunity"}
    if isinstance(opportunity, dict):
        credit = opportunity.get("est_credit") or opportunity.get("natural_credit")
        qty = int(opportunity.get("quantity") or 0)
        short_put = opportunity.get("short_put")
        long_put = opportunity.get("long_put")
        wing = opportunity.get("put_wing")
        try:
            credit_f = float(credit) if credit is not None else 0.0
        except (TypeError, ValueError):
            credit_f = 0.0
        structure_ok = (
            credit_f > 0
            and qty == 1
            and short_put is not None
            and long_put is not None
            and float(short_put) > float(long_put)
        )
        structure_detail = {
            "credit": credit_f,
            "quantity": qty,
            "short_put": short_put,
            "long_put": long_put,
            "put_wing": wing,
            "defined_risk_put_vertical": structure_ok,
        }
    answers["structure_strong"] = {"yes": structure_ok, "detail": structure_detail}
    if not structure_ok:
        fails.append("structure_strong=no")

    technical_ok = False
    technical_detail: dict[str, Any] = {"reason": "no_opportunity"}
    if isinstance(opportunity, dict):
        delta = opportunity.get("put_delta")
        expiry = opportunity.get("expiry")
        dte = opportunity.get("dte")
        if dte is None and expiry:
            try:
                exp = datetime.strptime(str(expiry)[:10], "%Y-%m-%d").replace(tzinfo=UTC)
                dte = (exp.date() - datetime.now(UTC).date()).days
            except ValueError:
                dte = None
        try:
            delta_f = abs(float(delta)) if delta is not None else None
        except (TypeError, ValueError):
            delta_f = None
        delta_ok = delta_f is not None and min_short_delta <= delta_f <= max_short_delta
        dte_ok = dte is not None and min_dte <= int(dte) <= max_dte
        technical_ok = bool(delta_ok and dte_ok)
        technical_detail = {
            "put_delta": delta_f,
            "dte": dte,
            "delta_band": [min_short_delta, max_short_delta],
            "dte_band": [min_dte, max_dte],
            "delta_ok": delta_ok,
            "dte_ok": dte_ok,
        }
    answers["clean_technical_setup"] = {"yes": technical_ok, "detail": technical_detail}
    if not technical_ok:
        fails.append("clean_technical_setup=no")

    risk_ok = False
    risk_detail: dict[str, Any] = {"reason": "missing_risk_plan"}
    if isinstance(risk_plan, dict):
        required = ("entry", "quantity", "stop_loss", "take_profit", "time_exit")
        present = {k: risk_plan.get(k) for k in required}
        risk_ok = all(present[k] is not None and present[k] != "" for k in required)
        try:
            qty = int(present.get("quantity") or 0)
        except (TypeError, ValueError):
            qty = 0
        if qty != 1:
            risk_ok = False
        risk_detail = {"fields": present, "quantity_is_one_lot": qty == 1}
    answers["predefined_risk"] = {"yes": risk_ok, "detail": risk_detail}
    if not risk_ok:
        fails.append("predefined_risk=no")

    return {
        "pass": not fails,
        "rule": "Market healthy? Structure strong? Clean technical setup? Predefined risk?",
        "source": "fahmy_os_format_steal_AGENT-602",
        "answers": answers,
        "fails": fails,
        "note": (
            "FORMAT steal only — not a growth-stock earnings screen. "
            "Live capital stays blocked until put-credit EDGE_CANDIDATE."
        ),
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
