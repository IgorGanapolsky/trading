"""Regime snapshot and entry gate for spy_put_credit paper validation.

Research-backed minimal filter (Parallel deep research 2026-07-24)
plus Fahmy-style market-health OS (FORMAT steal 2026-09-10, AGENT-602):
- Prefer short premium when IV rank proxy is elevated (IVR >= 30)
- Hard veto when VIX is extreme (VIX > 30)
- Trend soft-flags: SPY vs 50-day SMA (intermediate) and 200-day SMA (longer-term)
- Pre-entry OS: market healthy / structure strong / clean setup / predefined risk
  (growth-stock earnings screens intentionally NOT transferred — SPY put-credit only)
- Unusual Whales FORMAT (AGENT-657): predefined-risk P/L receipt + local
  size>OI honesty overlay. Not their feed, API, Discord, or multi-name screener.

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
# Paper hard floor is VIX (crash veto). Default 0 matches CI PUT_CREDIT_MIN_IVR
# (AGENT-361/566/608). Research preferred 30 stays a soft flag for stratification.
MIN_IV_RANK = float(os.environ.get("PUT_CREDIT_MIN_IVR", "0"))
MAX_VIX = float(os.environ.get("PUT_CREDIT_MAX_VIX", "30"))
# Buffett rebuild (AGENT-616): default ON — only sell bull puts when SPY is
# above the 200-DMA (equity drift / capital-preservation regime).
REQUIRE_ABOVE_200DMA = os.environ.get("PUT_CREDIT_REQUIRE_200DMA", "1").lower() in {
    "1",
    "true",
    "yes",
}
# Hard cap: max loss per structure as fraction of equity (Rule #1).
MAX_RISK_PCT_OF_EQUITY = float(os.environ.get("PUT_CREDIT_MAX_RISK_PCT", "0.01"))
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
    dealer_net_gamma: float | None = None
    dealer_put_wall: float | None = None
    dealer_gamma_flip: float | None = None
    dealer_regime_safety: str | None = None
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
        msg = "SPY 200-DMA unavailable"
        if require_above_200dma and fail_closed_on_missing:
            blockers.append(msg)
    dealer_safety = snap.get("dealer_regime_safety")
    if dealer_safety == "unhedged_breakdown":
        soft.append("Dealer gamma regime: Put Wall breached (unhedged dealer breakdown)")
    elif dealer_safety == "hazardous_negative_gamma":
        soft.append("Dealer gamma regime: spot below Gamma Flip (dealers short gamma)")

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
            "max_risk_pct_of_equity": MAX_RISK_PCT_OF_EQUITY,
        },
        "snapshot": snap,
    }


def evaluate_buffett_risk_budget(
    *,
    equity: float | None,
    wing_width: float,
    credit: float | None,
    quantity: int = 1,
    max_risk_pct: float = MAX_RISK_PCT_OF_EQUITY,
) -> dict[str, Any]:
    """Rule #1: refuse structures whose max loss exceeds ~1% of equity."""

    blockers: list[str] = []
    try:
        eq = float(equity) if equity is not None else None
    except (TypeError, ValueError):
        eq = None
    try:
        cr = float(credit) if credit is not None else 0.0
    except (TypeError, ValueError):
        cr = 0.0
    qty = max(int(quantity or 0), 0)
    width = float(wing_width)
    max_loss = max(width - cr, 0.0) * 100.0 * qty
    if eq is None or eq <= 0:
        blockers.append("equity unavailable for Buffett risk budget")
        budget = None
    else:
        budget = eq * float(max_risk_pct)
        if max_loss > budget + 1e-9:
            blockers.append(
                f"max loss ${max_loss:.2f} exceeds {float(max_risk_pct) * 100:.2f}% "
                f"of equity (${budget:.2f})"
            )
    receipt = defined_risk_receipt(
        credit=cr,
        wing_width=width,
        quantity=qty,
        equity=eq,
    )
    return {
        "allowed": not blockers,
        "blockers": blockers,
        "max_loss": round(max_loss, 2),
        "budget": None if budget is None else round(budget, 2),
        "max_risk_pct": float(max_risk_pct),
        "equity": eq,
        "receipt": receipt,
    }


def defined_risk_receipt(
    *,
    credit: float | None,
    wing_width: float,
    quantity: int = 1,
    take_profit_pct: float = 0.50,
    stop_loss_pct: float = 2.0,
    equity: float | None = None,
) -> dict[str, Any]:
    """UW options-profit-calculator FORMAT: print the P/L shape before entry.

    Not their calculator SKU. Paper SPY 1-lot bull put only.
    """

    try:
        cr = float(credit) if credit is not None else 0.0
    except (TypeError, ValueError):
        cr = 0.0
    qty = max(int(quantity or 0), 0)
    width = float(wing_width)
    max_profit = cr * 100.0 * qty
    max_loss = max(width - cr, 0.0) * 100.0 * qty
    return {
        "format": "prebuilt_strategy_shape_receipt",
        "source": "unusual_whales_profit_calculator_format_AGENT-657",
        "vendor_unusual_whales": False,
        "structure": "spy_bull_put_credit",
        "quantity": qty,
        "wing_width": width,
        "credit": round(cr, 4),
        "max_profit": round(max_profit, 2),
        "max_loss": round(max_loss, 2),
        "take_profit_pct": float(take_profit_pct),
        "stop_loss_pct": float(stop_loss_pct),
        "take_profit_dollars": round(max_profit * float(take_profit_pct), 2),
        "stop_loss_dollars": round(-max_profit * float(stop_loss_pct), 2),
        "equity": equity,
    }


def evaluate_spy_tape_unusual(
    *,
    ticker: str | None,
    short_put_volume: float | None = None,
    short_put_open_interest: float | None = None,
) -> dict[str, Any]:
    """UW size>OI unusual tag as a local honesty overlay.

    Soft flags only. Never an entry chase. Never calls api.unusualwhales.com.
    Non-SPY tickers are refused so this cannot become a multi-name screener.
    """

    symbol = (ticker or "SPY").strip().upper() or "SPY"
    if symbol != "SPY":
        return {
            "allowed": False,
            "blockers": [f"tape overlay is SPY-only (got {symbol})"],
            "soft_flags": [],
            "unusual_whales_api": False,
            "source": "local_option_chain_not_unusual_whales",
            "ticker": symbol,
        }
    flags: list[str] = []
    if (
        short_put_volume is not None
        and short_put_open_interest is not None
        and float(short_put_open_interest) > 0
        and float(short_put_volume) > float(short_put_open_interest)
    ):
        flags.append(
            "short put volume>OI (crowded contract; UW-style unusual tag — not an entry signal)"
        )
    return {
        "allowed": True,
        "blockers": [],
        "soft_flags": flags,
        "unusual_whales_api": False,
        "source": "local_option_chain_not_unusual_whales",
        "ticker": symbol,
        "short_put_volume": short_put_volume,
        "short_put_open_interest": short_put_open_interest,
    }


def evaluate_dealer_gamma_regime(
    *,
    spot_price: float | None,
    net_gamma: float | None = None,
    put_wall: float | None = None,
    call_wall: float | None = None,
    gamma_flip: float | None = None,
    block_on_negative_gamma: bool = False,
) -> dict[str, Any]:
    """Dealer Gamma & Market Maker Positioning assessment (Unusual Whales Periscope format).

    Evaluates:
    1. Net Gamma Regime: Positive Gamma (stabilizing dampener) vs Negative Gamma (cascading accelerator).
    2. Support/Resistance Defense: Put Wall (dealer floor) defended vs abandoned.
    3. Delta Hedging Pressure: Expected dealer buying/selling on market drops.

    Soft flags by default; blocks entry if block_on_negative_gamma is explicitly True.
    """
    if spot_price is None or spot_price <= 0.0:
        return {
            "allowed": True,
            "blockers": [],
            "soft_flags": ["Dealer gamma positioning unavailable (missing spot price)"],
            "regime_safety": "unknown",
            "net_gamma": net_gamma,
            "put_wall": put_wall,
            "gamma_flip": gamma_flip,
        }

    from src.analytics.options_vol_gex import (
        calculate_expected_hedging_flow,
        evaluate_dealer_defense_levels,
    )

    blockers: list[str] = []
    soft_flags: list[str] = []

    defense = evaluate_dealer_defense_levels(
        spot_price=spot_price,
        put_wall=put_wall,
        call_wall=call_wall,
        gamma_flip=gamma_flip,
    )

    flow = (
        calculate_expected_hedging_flow(
            spot_price=spot_price,
            net_gamma=net_gamma,
            spot_move_pct=-0.01,
        )
        if net_gamma is not None
        else None
    )

    if defense.put_wall_status == "abandoned":
        msg = f"Put Wall at {put_wall} breached! Dealers abandoned support; short puts trigger forced selling."
        if block_on_negative_gamma:
            blockers.append(msg)
        else:
            soft_flags.append(msg)
    elif defense.above_gamma_flip is False:
        msg = f"Spot {spot_price:.2f} below Gamma Flip {gamma_flip:.2f}; dealers in negative gamma (volatility expansion)."
        if block_on_negative_gamma:
            blockers.append(msg)
        else:
            soft_flags.append(msg)

    if flow and flow.hedging_pressure == "accelerating_selling":
        soft_flags.append(
            f"Dealer hedging pressure is negative (${abs(flow.hedging_flow_dollars):,.0f} selling per 1% drop)."
        )

    return {
        "allowed": not blockers,
        "blockers": blockers,
        "soft_flags": soft_flags,
        "regime_safety": defense.regime_safety,
        "defense_summary": defense.summary,
        "put_wall_status": defense.put_wall_status,
        "call_wall_status": defense.call_wall_status,
        "hedging_pressure": flow.hedging_pressure if flow else "unknown",
        "hedging_flow_dollars_per_1pct_drop": flow.hedging_flow_dollars if flow else 0.0,
        "spot_price": spot_price,
        "net_gamma": net_gamma,
        "put_wall": put_wall,
        "call_wall": call_wall,
        "gamma_flip": gamma_flip,
    }


def evaluate_entry_operating_system(
    *,
    regime_gate: dict[str, Any],
    opportunity: dict[str, Any] | None,
    risk_plan: dict[str, Any] | None,
    min_dte: int = 45,
    max_dte: int = 70,
    min_short_delta: float = 0.10,
    max_short_delta: float = 0.20,
    equity: float | None = None,
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
        # Buffett Rule #1 budget (AGENT-616)
        wing = None
        credit = None
        if isinstance(opportunity, dict):
            wing = opportunity.get("put_wing") or opportunity.get("wing_width")
            credit = opportunity.get("est_credit") or opportunity.get("natural_credit")
        if wing is None and isinstance(risk_plan, dict):
            wing = risk_plan.get("wing_width")
        tp_pct = 0.50
        sl_pct = 2.0
        try:
            if risk_plan.get("take_profit") is not None:
                tp_pct = float(risk_plan.get("take_profit"))
            if risk_plan.get("stop_loss") is not None:
                sl_pct = float(risk_plan.get("stop_loss"))
        except (TypeError, ValueError):
            pass
        budget = evaluate_buffett_risk_budget(
            equity=equity,
            wing_width=float(wing or 5.0),
            credit=credit,
            quantity=qty or 1,
        )
        risk_detail["buffett_risk_budget"] = budget
        risk_detail["defined_risk_receipt"] = defined_risk_receipt(
            credit=credit,
            wing_width=float(wing or 5.0),
            quantity=qty or 1,
            take_profit_pct=tp_pct,
            stop_loss_pct=sl_pct,
            equity=equity,
        )
        if not budget.get("allowed"):
            risk_ok = False
            risk_detail["buffett_blockers"] = list(budget.get("blockers") or [])
    answers["predefined_risk"] = {"yes": risk_ok, "detail": risk_detail}
    if not risk_ok:
        fails.append("predefined_risk=no")

    tape_ticker = "SPY"
    tape_vol = None
    tape_oi = None
    if isinstance(opportunity, dict):
        tape_ticker = str(opportunity.get("ticker") or opportunity.get("underlying") or "SPY")
        tape_vol = opportunity.get("short_put_volume")
        tape_oi = opportunity.get("short_put_open_interest")
    tape = evaluate_spy_tape_unusual(
        ticker=tape_ticker,
        short_put_volume=tape_vol,
        short_put_open_interest=tape_oi,
    )
    answers["tape_honesty"] = {"yes": bool(tape.get("allowed")), "detail": tape}
    if not tape.get("allowed"):
        fails.append("tape_honesty=no")

    return {
        "pass": not fails,
        "rule": "Market healthy? Structure strong? Clean technical setup? Predefined risk?",
        "source": "fahmy_os_format_steal_AGENT-602+buffett_AGENT-616",
        "answers": answers,
        "fails": fails,
        "note": (
            "FORMAT steal only — not a growth-stock earnings screen. "
            "Live capital stays blocked until put-credit EDGE_CANDIDATE."
        ),
    }


def _live_exit_profile_knobs(
    take_profit_pct: float | None,
    exit_dte: int | None,
) -> tuple[float, int]:
    """Resolve live manager knobs so the counterfactual note cannot lag the profile."""

    if take_profit_pct is not None and exit_dte is not None:
        return float(take_profit_pct), int(exit_dte)
    try:
        from src.core.trading_profiles import get_put_credit_profile

        profile = get_put_credit_profile()
        tp = float(profile.take_profit_pct if take_profit_pct is None else take_profit_pct)
        dte_exit = int(profile.exit_dte if exit_dte is None else exit_dte)
        return tp, dte_exit
    except (ImportError, AttributeError, TypeError, ValueError):
        # Buffett default (AGENT-616), not the legacy 25%/7-DTE baseline.
        return (
            0.50 if take_profit_pct is None else float(take_profit_pct),
            30 if exit_dte is None else int(exit_dte),
        )


def attach_counterfactuals(
    exit_eval: dict[str, Any],
    *,
    credit: float,
    quantity: int = 1,
    dte: int | None = None,
    take_profit_pct: float | None = None,
    exit_dte: int | None = None,
) -> dict[str, Any]:
    """Add public-rule counterfactuals (50% TP, 21 DTE) without changing live exits."""

    qty = abs(int(quantity or 1))
    max_profit = float(credit) * 100.0 * qty
    pnl = float(exit_eval.get("estimated_pnl") or 0.0)
    live_tp, live_exit_dte = _live_exit_profile_knobs(take_profit_pct, exit_dte)
    tp_pct_display = int(round(live_tp * 100.0))
    out = dict(exit_eval)
    out["counterfactuals"] = {
        "tp_25_target": round(max_profit * 0.25, 2),
        "tp_50_target": round(max_profit * 0.50, 2),
        "would_hit_tp_25_now": pnl >= max_profit * 0.25,
        "would_hit_tp_50_now": pnl >= max_profit * 0.50,
        "public_exit_dte": 21,
        "dte_now": dte,
        "would_trigger_public_21dte_exit": (dte is not None and dte <= 21),
        "live_take_profit_pct": live_tp,
        "live_exit_dte": live_exit_dte,
        "note": (
            "Counterfactuals only — live manager uses profile "
            f"TP {tp_pct_display}% / exit_dte={live_exit_dte}. "
            "Used to compare our rules to public 50%/21-DTE research without re-running history."
        ),
    }
    return out
