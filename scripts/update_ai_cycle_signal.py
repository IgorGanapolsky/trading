#!/usr/bin/env python3
"""Update AI cycle signal from public market proxies.

This signal converts AI-cycle market structure into autonomous gating inputs:
- Infrastructure buildout proxies (AI infra basket momentum)
- Edge monetization proxies (consumer/platform basket momentum)
- Hyperscaler capex sentiment proxy (hyperscaler basket momentum)
- NVDA gross margin proxy trend (from public quote metadata when available)

The resulting payload feeds weekly North Star risk gating and autonomous sizing.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils import yfinance_wrapper as yf

DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "market_signals" / "ai_cycle_signal.json"
DEFAULT_STATE_PATH = PROJECT_ROOT / "data" / "system_state.json"

HYPERSCALER_CAPEX_PROXY = ("AMZN", "MSFT", "GOOGL", "META", "ORCL")
AI_INFRA_PROXY = ("NVDA", "AVGO", "ANET", "AMD", "SMCI")
EDGE_MONETIZATION_PROXY = ("META", "AAPL", "GOOGL", "AMZN", "ORCL")
ALL_TICKERS = sorted(
    {
        *HYPERSCALER_CAPEX_PROXY,
        *AI_INFRA_PROXY,
        *EDGE_MONETIZATION_PROXY,
        "NVDA",
    }
)

WATCH_SCORE = 30.0
BLOCK_SCORE = 60.0
HARD_SHOCK_SCORE = 75.0
WATCH_MULTIPLIER = 0.95
BLOCK_MULTIPLIER = 0.85


@dataclass
class TickerReturnSummary:
    symbol: str
    latest_close: float | None
    latest_date: str | None
    ret_5d: float | None
    ret_20d: float | None
    point_count: int


def _safe_read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _safe_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _to_float(value: Any, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _percent_change(values: list[float], lookback: int) -> float | None:
    if len(values) <= lookback:
        return None
    latest = values[-1]
    baseline = values[-1 - lookback]
    if baseline == 0:
        return None
    return round((latest - baseline) / baseline, 6)


def _extract_latest_date(index_obj: Any) -> str | None:
    try:
        latest = index_obj[-1]
        if hasattr(latest, "to_pydatetime"):
            latest_dt = latest.to_pydatetime()
            return latest_dt.date().isoformat()
        latest_str = str(latest)
        return latest_str[:10]
    except Exception:
        return None


def _fetch_ticker_summary(symbol: str, *, period: str = "9mo") -> TickerReturnSummary:
    try:
        ticker = yf.get_ticker(symbol)
        history = ticker.history(period=period, interval="1d")
    except Exception:
        history = None

    if history is None or isinstance(history, dict):
        return TickerReturnSummary(
            symbol=symbol,
            latest_close=None,
            latest_date=None,
            ret_5d=None,
            ret_20d=None,
            point_count=0,
        )

    try:
        closes_series = history.get("Close")
        if closes_series is None:
            raise ValueError("missing close series")
        closes = [float(v) for v in closes_series.dropna().tolist()]
        if not closes:
            raise ValueError("empty close series")
        latest_close = round(closes[-1], 6)
        latest_date = _extract_latest_date(history.index)
        return TickerReturnSummary(
            symbol=symbol,
            latest_close=latest_close,
            latest_date=latest_date,
            ret_5d=_percent_change(closes, 5),
            ret_20d=_percent_change(closes, 20),
            point_count=len(closes),
        )
    except Exception:
        return TickerReturnSummary(
            symbol=symbol,
            latest_close=None,
            latest_date=None,
            ret_5d=None,
            ret_20d=None,
            point_count=0,
        )


def _average_returns(
    summaries: dict[str, TickerReturnSummary],
    symbols: tuple[str, ...],
) -> tuple[float | None, float | None, int]:
    ret_20_values: list[float] = []
    ret_5_values: list[float] = []
    for symbol in symbols:
        summary = summaries.get(symbol)
        if not summary:
            continue
        if summary.ret_20d is not None:
            ret_20_values.append(float(summary.ret_20d))
        if summary.ret_5d is not None:
            ret_5_values.append(float(summary.ret_5d))

    avg_20 = round(sum(ret_20_values) / len(ret_20_values), 6) if ret_20_values else None
    avg_5 = round(sum(ret_5_values) / len(ret_5_values), 6) if ret_5_values else None
    coverage = len(ret_20_values)
    return avg_20, avg_5, coverage


def _resolve_nvda_gross_margin_pct() -> float | None:
    try:
        info = yf.get_ticker("NVDA").info
    except Exception:
        return None

    if not isinstance(info, dict):
        return None

    gross = _to_float(info.get("grossMargins"), None)
    if gross is None:
        return None
    if gross < 0:
        return None
    if gross <= 1.0:
        return round(gross * 100.0, 2)
    return round(gross, 2)


def _multiplier_for_status(status: str) -> float:
    if status == "blocked":
        return BLOCK_MULTIPLIER
    if status == "watch":
        return WATCH_MULTIPLIER
    return 1.0


def evaluate_ai_cycle_signal(
    *,
    capex_ret_20d: float | None,
    capex_ret_5d: float | None,
    infra_ret_20d: float | None,
    edge_ret_20d: float | None,
    nvda_gross_margin_pct: float | None,
    prior_nvda_gross_margin_pct: float | None,
) -> tuple[str, float, float, str, bool, float | None, float, list[str]]:
    """Return AI-cycle signal classification.

    Returns:
        status, severity_score, size_multiplier, regime, capex_deceleration_shock,
        gross_margin_trend_bps, confidence, reasons
    """
    reasons: list[str] = []

    available_points = [
        capex_ret_20d,
        capex_ret_5d,
        infra_ret_20d,
        edge_ret_20d,
    ]
    if all(value is None for value in available_points):
        return "unknown", 0.0, 1.0, "unknown", False, None, 0.0, ["No AI-cycle market data available."]

    capex20 = float(capex_ret_20d or 0.0)
    capex5 = float(capex_ret_5d or 0.0)
    infra20 = float(infra_ret_20d or 0.0)
    edge20 = float(edge_ret_20d or 0.0)

    capex_momentum_delta = capex5 - capex20
    edge_vs_infra_spread = edge20 - infra20
    monetization_proxy_score = edge20 - capex20

    gross_margin_trend_bps: float | None = None
    if (
        nvda_gross_margin_pct is not None
        and prior_nvda_gross_margin_pct is not None
        and prior_nvda_gross_margin_pct > 0
    ):
        gross_margin_trend_bps = round((nvda_gross_margin_pct - prior_nvda_gross_margin_pct) * 100.0, 2)

    severity_score = 0.0

    if capex20 <= -0.08:
        severity_score += 35.0
        reasons.append(f"Hyperscaler capex proxy 20D drawdown {capex20 * 100:.2f}%")
    elif capex20 <= -0.04:
        severity_score += 20.0
        reasons.append(f"Hyperscaler capex proxy weakening {capex20 * 100:.2f}%")

    if capex_momentum_delta <= -0.06:
        severity_score += 30.0
        reasons.append(
            f"Capex momentum decelerating sharply ({capex_momentum_delta * 100:.2f}% 5D-20D delta)"
        )
    elif capex_momentum_delta <= -0.03:
        severity_score += 15.0
        reasons.append(
            f"Capex momentum decelerating ({capex_momentum_delta * 100:.2f}% 5D-20D delta)"
        )

    if infra20 <= -0.10:
        severity_score += 20.0
        reasons.append(f"AI infra basket under pressure ({infra20 * 100:.2f}% 20D)")
    elif infra20 <= -0.05:
        severity_score += 10.0
        reasons.append(f"AI infra basket soft ({infra20 * 100:.2f}% 20D)")

    if gross_margin_trend_bps is not None:
        if gross_margin_trend_bps <= -150:
            severity_score += 15.0
            reasons.append(f"NVDA gross margin trend down {gross_margin_trend_bps:.0f} bps")
        elif gross_margin_trend_bps <= -50:
            severity_score += 8.0
            reasons.append(f"NVDA gross margin trend slightly down {gross_margin_trend_bps:.0f} bps")

    if edge_vs_infra_spread >= 0.05 and edge20 > 0:
        severity_score -= 8.0
        reasons.append(
            "Edge monetization proxy outperforming infrastructure, partially offsetting capex risk"
        )

    if monetization_proxy_score >= 0.04 and edge20 > 0:
        severity_score -= 5.0
        reasons.append("Monetization proxy positive versus capex proxy")

    severity_score = round(max(0.0, min(100.0, severity_score)), 2)

    capex_deceleration_shock = bool(
        severity_score >= HARD_SHOCK_SCORE
        or (capex5 <= -0.05 and capex_momentum_delta <= -0.04)
        or (capex20 <= -0.10 and infra20 <= -0.08)
    )
    if capex_deceleration_shock:
        reasons.append("Capex deceleration shock condition triggered")

    if capex_deceleration_shock:
        regime = "capex_deceleration"
    elif infra20 - edge20 >= 0.03 and capex20 > 0:
        regime = "infrastructure_buildout"
    elif edge_vs_infra_spread >= 0.03 and edge20 > 0:
        regime = "edge_monetization"
    else:
        regime = "transition"

    if severity_score >= BLOCK_SCORE:
        status = "blocked"
    elif severity_score >= WATCH_SCORE:
        status = "watch"
    else:
        status = "pass"

    confidence = min(
        0.99,
        max(
            0.2,
            abs(capex_momentum_delta) * 4.0
            + abs(edge_vs_infra_spread) * 3.5
            + (0.25 if capex_deceleration_shock else 0.0),
        ),
    )
    confidence = round(confidence, 3)

    if not reasons:
        reasons.append("AI-cycle proxies stable")

    return (
        status,
        severity_score,
        _multiplier_for_status(status),
        regime,
        capex_deceleration_shock,
        gross_margin_trend_bps,
        confidence,
        reasons,
    )


def _build_payload(
    *,
    summaries: dict[str, TickerReturnSummary],
    status: str,
    severity_score: float,
    position_size_multiplier: float,
    regime: str,
    capex_deceleration_shock: bool,
    gross_margin_trend_bps: float | None,
    confidence: float,
    reasons: list[str],
    source: str,
    max_stale_days: int,
) -> dict:
    latest_dates = [
        datetime.strptime(summary.latest_date, "%Y-%m-%d").date()
        for summary in summaries.values()
        if summary.latest_date
    ]
    freshest = max(latest_dates) if latest_dates else None
    stale_days = (date.today() - freshest).days if freshest else None
    stale = stale_days is not None and stale_days > max_stale_days

    capex_ret_20d, capex_ret_5d, capex_cov = _average_returns(summaries, HYPERSCALER_CAPEX_PROXY)
    infra_ret_20d, _infra_ret_5d, infra_cov = _average_returns(summaries, AI_INFRA_PROXY)
    edge_ret_20d, _edge_ret_5d, edge_cov = _average_returns(summaries, EDGE_MONETIZATION_PROXY)

    capex_momentum_delta = (
        round(float(capex_ret_5d) - float(capex_ret_20d), 6)
        if capex_ret_5d is not None and capex_ret_20d is not None
        else None
    )
    edge_vs_infra_spread = (
        round(float(edge_ret_20d) - float(infra_ret_20d), 6)
        if edge_ret_20d is not None and infra_ret_20d is not None
        else None
    )
    monetization_proxy = (
        round(float(edge_ret_20d) - float(capex_ret_20d), 6)
        if edge_ret_20d is not None and capex_ret_20d is not None
        else None
    )

    nvda_margin = _resolve_nvda_gross_margin_pct()

    effective_status = status
    effective_multiplier = position_size_multiplier
    effective_shock = capex_deceleration_shock
    effective_reasons = list(reasons)
    if stale:
        effective_status = "unknown"
        effective_multiplier = 1.0
        effective_shock = False
        effective_reasons.append(f"AI-cycle data stale: {stale_days} days old (max {max_stale_days})")

    return {
        "signal": "ai_cycle",
        "status": effective_status,
        "severity_score": severity_score,
        "position_size_multiplier": round(min(1.0, max(0.1, effective_multiplier)), 4),
        "blocked": effective_status == "blocked",
        "watch": effective_status == "watch",
        "regime": regime,
        "confidence": confidence,
        "capex_deceleration_shock": effective_shock,
        "reasons": effective_reasons,
        "latest_data_date": freshest.isoformat() if freshest else None,
        "stale_days": stale_days,
        "features": {
            "hyperscaler_capex_proxy_ret_20d": capex_ret_20d,
            "hyperscaler_capex_proxy_ret_5d": capex_ret_5d,
            "capex_proxy_momentum_delta": capex_momentum_delta,
            "ai_infra_proxy_ret_20d": infra_ret_20d,
            "edge_monetization_proxy_ret_20d": edge_ret_20d,
            "edge_vs_infra_spread_20d": edge_vs_infra_spread,
            "ai_monetization_proxy_score": monetization_proxy,
            "nvda_gross_margin_pct": nvda_margin,
            "nvda_gross_margin_trend_bps": gross_margin_trend_bps,
        },
        "coverage": {
            "hyperscaler_capex_proxy_tickers": list(HYPERSCALER_CAPEX_PROXY),
            "hyperscaler_capex_proxy_observed": capex_cov,
            "ai_infra_proxy_tickers": list(AI_INFRA_PROXY),
            "ai_infra_proxy_observed": infra_cov,
            "edge_monetization_proxy_tickers": list(EDGE_MONETIZATION_PROXY),
            "edge_monetization_proxy_observed": edge_cov,
            "total_symbols_requested": len(ALL_TICKERS),
            "total_symbols_observed": sum(1 for s in summaries.values() if s.ret_20d is not None),
        },
        "metrics": {
            symbol: {
                "latest_close": summary.latest_close,
                "latest_date": summary.latest_date,
                "ret_5d": summary.ret_5d,
                "ret_20d": summary.ret_20d,
                "point_count": summary.point_count,
            }
            for symbol, summary in summaries.items()
        },
        "source": source,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _apply_override(payload: dict, override_status: str, override_reason: str) -> dict:
    status = override_status.strip().lower()
    if status not in {"pass", "watch", "blocked", "unknown"}:
        return payload

    out = dict(payload)
    reasons = list(out.get("reasons", []))
    reasons.append(override_reason.strip() if override_reason.strip() else f"Manual override applied: {status}")
    out["status"] = status
    out["position_size_multiplier"] = _multiplier_for_status(status)
    if status == "unknown":
        out["position_size_multiplier"] = 1.0
        out["capex_deceleration_shock"] = False
    out["blocked"] = status == "blocked"
    out["watch"] = status == "watch"
    out["reasons"] = reasons
    out["source"] = f"{out.get('source', 'unknown')}+override"
    out["updated_at"] = datetime.now(timezone.utc).isoformat()
    return out


def _sync_to_system_state(state_path: Path, payload: dict) -> None:
    state = _safe_read_json(state_path)
    if not isinstance(state, dict):
        state = {}
    market_signals = state.get("market_signals")
    if not isinstance(market_signals, dict):
        market_signals = {}
    market_signals["ai_cycle"] = payload
    state["market_signals"] = market_signals
    _safe_write_json(state_path, state)


def main() -> int:
    parser = argparse.ArgumentParser(description="Update AI cycle signal from public market data.")
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT_PATH), help="Signal output JSON path.")
    parser.add_argument(
        "--state",
        default=str(DEFAULT_STATE_PATH),
        help="system_state.json path for --sync-state updates.",
    )
    parser.add_argument(
        "--sync-state",
        action="store_true",
        help="Write signal payload into system_state.market_signals.ai_cycle.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip market fetch and reuse existing output payload if available.",
    )
    parser.add_argument(
        "--max-stale-days",
        type=int,
        default=7,
        help="Mark signal unknown when freshest data exceeds this age.",
    )
    parser.add_argument(
        "--override-status",
        default="",
        help="Optional manual override status: pass/watch/blocked/unknown.",
    )
    parser.add_argument(
        "--override-reason",
        default="",
        help="Optional text appended to reasons when override is used.",
    )
    parser.add_argument("--print-json", action="store_true", help="Print payload JSON to stdout.")
    args = parser.parse_args()

    out_path = Path(args.out).resolve()
    state_path = Path(args.state).resolve()
    existing_payload = _safe_read_json(out_path)

    if args.offline and existing_payload:
        payload = dict(existing_payload)
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        payload["source"] = f"{payload.get('source', 'unknown')}+offline"
    else:
        summaries = {symbol: _fetch_ticker_summary(symbol) for symbol in ALL_TICKERS}
        capex_ret_20d, capex_ret_5d, _ = _average_returns(summaries, HYPERSCALER_CAPEX_PROXY)
        infra_ret_20d, _infra_ret_5d, _ = _average_returns(summaries, AI_INFRA_PROXY)
        edge_ret_20d, _edge_ret_5d, _ = _average_returns(summaries, EDGE_MONETIZATION_PROXY)

        prior_margin = _to_float(
            _safe_read_json(out_path).get("features", {}).get("nvda_gross_margin_pct"), None
        )
        current_margin = _resolve_nvda_gross_margin_pct()

        (
            status,
            score,
            multiplier,
            regime,
            shock,
            gm_trend_bps,
            confidence,
            reasons,
        ) = evaluate_ai_cycle_signal(
            capex_ret_20d=capex_ret_20d,
            capex_ret_5d=capex_ret_5d,
            infra_ret_20d=infra_ret_20d,
            edge_ret_20d=edge_ret_20d,
            nvda_gross_margin_pct=current_margin,
            prior_nvda_gross_margin_pct=prior_margin,
        )

        payload = _build_payload(
            summaries=summaries,
            status=status,
            severity_score=score,
            position_size_multiplier=multiplier,
            regime=regime,
            capex_deceleration_shock=shock,
            gross_margin_trend_bps=gm_trend_bps,
            confidence=confidence,
            reasons=reasons,
            source="yfinance_public",
            max_stale_days=max(0, args.max_stale_days),
        )

    if args.override_status:
        payload = _apply_override(payload, args.override_status, args.override_reason)

    _safe_write_json(out_path, payload)

    if args.sync_state:
        _sync_to_system_state(state_path, payload)

    if args.print_json:
        print(json.dumps(payload, indent=2))
    else:
        print(
            "AI cycle signal updated:",
            f"status={payload.get('status')}",
            f"regime={payload.get('regime')}",
            f"score={payload.get('severity_score')}",
            f"multiplier={payload.get('position_size_multiplier')}",
            f"shock={payload.get('capex_deceleration_shock')}",
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
