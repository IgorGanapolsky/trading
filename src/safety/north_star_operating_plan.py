"""North Star weekly operating plan and contribution tracking.

This module keeps the North Star execution loop practical:
- Weekly gate: cap/lock risk when edge deteriorates.
- Contribution plan: quantify required monthly capital support by return scenario.
"""

from __future__ import annotations

import calendar
import json
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.core.trading_constants import (
    NORTH_STAR_DAILY_AFTER_TAX,
    NORTH_STAR_MONTHLY_AFTER_TAX,
    NORTH_STAR_TARGET_CAPITAL,
)

DEFAULT_TRADES_PATH = Path("data/trades.json")
DEFAULT_WEEKLY_HISTORY_PATH = Path("data/north_star_weekly_history.json")
DEFAULT_LOOKBACK_DAYS = 7
DEFAULT_WEEKLY_MIN_SAMPLES = 5
DEFAULT_HISTORY_WEEKS = 104
DEFAULT_MIN_QUALIFIED_SETUPS_PER_WEEK = 3
DEFAULT_MIN_CLOSED_TRADES_PER_WEEK = 1
DEFAULT_MIN_CLOSED_TRADES_FOR_SCALING = 30
DEFAULT_MIN_LIQUIDITY_VOLUME_RATIO = 0.20
DEFAULT_GATE_OVERRIDES_PATH = Path("runtime/north_star_gate_overrides.json")
DEFAULT_MAX_TARGET_DTE = 45
DEFAULT_MIN_TARGET_DTE = 21
DEFAULT_AI_CREDIT_STRESS_PATH = Path("market_signals/ai_credit_stress_signal.json")
DEFAULT_AI_CREDIT_WATCH_SCORE = 30.0
DEFAULT_AI_CREDIT_BLOCK_SCORE = 60.0
DEFAULT_AI_CREDIT_HARD_BLOCK_SCORE = 80.0
DEFAULT_USD_MACRO_SENTIMENT_PATH = Path("market_signals/usd_macro_sentiment_signal.json")
DEFAULT_USD_MACRO_WATCH_SCORE = 30.0
DEFAULT_USD_MACRO_BLOCK_SCORE = 60.0
DEFAULT_USD_MACRO_WATCH_MULTIPLIER = 0.95
DEFAULT_USD_MACRO_BLOCK_MULTIPLIER = 0.90
DEFAULT_AI_CYCLE_SIGNAL_PATH = Path("market_signals/ai_cycle_signal.json")
DEFAULT_AI_CYCLE_WATCH_SCORE = 30.0
DEFAULT_AI_CYCLE_BLOCK_SCORE = 60.0
DEFAULT_AI_CYCLE_HARD_BLOCK_SCORE = 75.0
DEFAULT_AI_CYCLE_WATCH_MULTIPLIER = 0.95
DEFAULT_AI_CYCLE_BLOCK_MULTIPLIER = 0.85

_SPY_OPTION_RE = re.compile(r"^SPY(\d{6})[CP]\d{8}$")


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    raw = str(value).strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(raw).date()
    except ValueError:
        pass

    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _load_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return (
            [item for item in payload if isinstance(item, dict)]
            if isinstance(payload, list)
            else []
        )
    except Exception:
        return []


def _load_gate_overrides(data_dir: Path) -> dict[str, Any]:
    payload = _load_json_dict(data_dir / DEFAULT_GATE_OVERRIDES_PATH)
    return payload if isinstance(payload, dict) else {}


def _resolve_min_liquidity_volume_ratio(data_dir: Path) -> float:
    overrides = _load_gate_overrides(data_dir)
    ratio = _as_float(
        overrides.get("min_liquidity_volume_ratio"), DEFAULT_MIN_LIQUIDITY_VOLUME_RATIO
    )
    # Safety clamp: never allow pathological liquidity thresholds.
    return max(0.10, min(0.50, ratio))


def _parse_session_date_from_filename(path: Path) -> date | None:
    """Extract YYYY-MM-DD from session_decisions_*.json filename."""
    stem = path.stem
    if not stem.startswith("session_decisions_"):
        return None
    return _parse_date(stem.replace("session_decisions_", "", 1))


def _extract_recent_session_decisions(
    *,
    data_dir: Path,
    today: date,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> list[dict[str, Any]]:
    start_date = today - timedelta(days=max(1, lookback_days) - 1)
    rows: list[dict[str, Any]] = []
    for path in sorted(data_dir.glob("session_decisions_*.json")):
        payload = _load_json_dict(path)
        decisions = payload.get("decisions", [])
        if not isinstance(decisions, list):
            continue
        fallback_file_date = _parse_session_date_from_filename(path)
        for item in decisions:
            if not isinstance(item, dict):
                continue
            observed = _parse_date(item.get("timestamp")) or fallback_file_date
            if observed is None or observed < start_date or observed > today:
                continue
            decision = str(item.get("decision", "")).strip().upper()
            gate_reached = _as_int(item.get("gate_reached"), 0)
            rejection_reason = str(item.get("rejection_reason") or item.get("reason") or "").strip()
            indicators = item.get("indicators", {})
            volume_ratio: float | None = None
            if isinstance(indicators, dict):
                raw_volume = indicators.get("volume_ratio")
                try:
                    volume_ratio = float(raw_volume)
                except (TypeError, ValueError):
                    volume_ratio = None
            qualified = gate_reached >= 1 or decision in {
                "REJECTED",
                "APPROVED",
                "ACCEPTED",
                "EXECUTED",
                "BLOCKED",
                "SKIPPED",
            }
            rows.append(
                {
                    "date": observed.isoformat(),
                    "decision": decision,
                    "gate_reached": gate_reached,
                    "qualified": qualified,
                    "rejection_reason": rejection_reason,
                    "volume_ratio": volume_ratio,
                }
            )
    return rows


def _categorize_reason(reason: str) -> set[str]:
    text = reason.lower()
    categories: set[str] = set()
    if not text:
        return categories
    if any(token in text for token in ("vix", "volatility index")):
        categories.add("vix")
    if any(token in text for token in ("dte", "days to expiration", "expiration", "expiry")):
        categories.add("dte")
    if any(token in text for token in ("regime", "bearish", "trend", "momentum")):
        categories.add("regime")
    if any(
        token in text
        for token in (
            "buying power",
            "position limit",
            "max position",
            "max risk",
            "risk",
            "capital",
        )
    ):
        categories.add("risk_caps")
    if any(
        token in text for token in ("liquid", "volume", "vol=", "spread", "bid/ask", "illiquid")
    ):
        categories.add("liquidity")
    if any(
        token in text
        for token in (
            "credit spread",
            "credit-stress",
            "ai credit",
            "high yield oas",
            "baa10y",
        )
    ):
        categories.add("ai_credit_stress")
    if any(
        token in text
        for token in (
            "usd",
            "dollar",
            "dxy",
            "dtwex",
            "fx regime",
            "macro sentiment",
        )
    ):
        categories.add("usd_macro")
    if any(
        token in text
        for token in (
            "ai cycle",
            "hyperscaler capex",
            "capex proxy",
            "edge monetization",
            "gross margin",
            "capex deceleration",
            "infrastructure buildout",
        )
    ):
        categories.add("ai_cycle")
    return categories


def _safe_nested_dict(payload: dict[str, Any], *keys: str) -> dict[str, Any]:
    cur: Any = payload
    for key in keys:
        if not isinstance(cur, dict):
            return {}
        cur = cur.get(key)
    return cur if isinstance(cur, dict) else {}


def _normalize_ai_credit_stress_status(signal: dict[str, Any]) -> str:
    raw_status = str(signal.get("status") or "").strip().lower()
    score = _as_float(signal.get("severity_score"), 0.0)
    if (
        raw_status in {"blocked", "high", "stress", "critical"}
        or score >= DEFAULT_AI_CREDIT_BLOCK_SCORE
    ):
        return "blocked"
    if raw_status in {"watch", "warning", "elevated"} or score >= DEFAULT_AI_CREDIT_WATCH_SCORE:
        return "watch"
    if raw_status in {"pass", "ok", "normal", "low"}:
        return "pass"
    return "unknown"


def _normalize_usd_macro_status(signal: dict[str, Any]) -> str:
    raw_status = str(signal.get("status") or "").strip().lower()
    score = _as_float(signal.get("bearish_score"), 0.0)
    if (
        raw_status in {"blocked", "high", "stress", "critical"}
        or score >= DEFAULT_USD_MACRO_BLOCK_SCORE
    ):
        return "blocked"
    if raw_status in {"watch", "warning", "elevated"} or score >= DEFAULT_USD_MACRO_WATCH_SCORE:
        return "watch"
    if raw_status in {"pass", "ok", "normal", "low"}:
        return "pass"
    return "unknown"


def _normalize_ai_cycle_status(signal: dict[str, Any]) -> str:
    raw_status = str(signal.get("status") or "").strip().lower()
    score = _as_float(signal.get("severity_score"), 0.0)
    if (
        raw_status in {"blocked", "high", "stress", "critical"}
        or score >= DEFAULT_AI_CYCLE_BLOCK_SCORE
    ):
        return "blocked"
    if raw_status in {"watch", "warning", "elevated"} or score >= DEFAULT_AI_CYCLE_WATCH_SCORE:
        return "watch"
    if raw_status in {"pass", "ok", "normal", "low"}:
        return "pass"
    return "unknown"


def _load_ai_credit_stress_signal(data_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    file_payload = _load_json_dict(data_dir / DEFAULT_AI_CREDIT_STRESS_PATH)
    if file_payload:
        return file_payload
    state_payload = _safe_nested_dict(state, "market_signals").get("ai_credit_stress")
    if isinstance(state_payload, dict):
        return state_payload
    return {}


def _load_usd_macro_sentiment_signal(data_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    file_payload = _load_json_dict(data_dir / DEFAULT_USD_MACRO_SENTIMENT_PATH)
    if file_payload:
        return file_payload
    state_payload = _safe_nested_dict(state, "market_signals").get("usd_macro_sentiment")
    if isinstance(state_payload, dict):
        return state_payload
    return {}


def _load_ai_cycle_signal(data_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    file_payload = _load_json_dict(data_dir / DEFAULT_AI_CYCLE_SIGNAL_PATH)
    if file_payload:
        return file_payload
    state_payload = _safe_nested_dict(state, "market_signals").get("ai_cycle")
    if isinstance(state_payload, dict):
        return state_payload
    return {}


def _compute_no_trade_diagnostic(
    *,
    data_dir: Path,
    state: dict[str, Any],
    recent_decisions: list[dict[str, Any]],
    closed_trades_recent: int,
    qualified_setups_recent: int,
    min_liquidity_volume_ratio: float = DEFAULT_MIN_LIQUIDITY_VOLUME_RATIO,
) -> dict[str, Any]:
    workflow_state_dir = data_dir / "workflow_state"
    iron_condor_state = _load_json_dict(workflow_state_dir / "iron_condor_pipeline_state.json")
    swarm_state = _load_json_dict(workflow_state_dir / "swarm_integrated_pipeline_state.json")

    iron_regime = _safe_nested_dict(iron_condor_state, "results", "regime_gate", "output")
    options_chain = _safe_nested_dict(iron_condor_state, "results", "options_chain", "output")
    swarm_risk = _safe_nested_dict(swarm_state, "results", "risk_gate", "output")
    risk_checks = (
        swarm_risk.get("risk_checks", {}) if isinstance(swarm_risk.get("risk_checks"), dict) else {}
    )
    regime_check = (
        risk_checks.get("regime_check", {})
        if isinstance(risk_checks.get("regime_check"), dict)
        else {}
    )
    position_size_check = (
        risk_checks.get("position_size_check", {})
        if isinstance(risk_checks.get("position_size_check"), dict)
        else {}
    )

    rejection_reasons = [str(row.get("rejection_reason", "")).strip() for row in recent_decisions]
    rejection_reasons = [text for text in rejection_reasons if text]
    reason_counter = Counter(rejection_reasons)
    category_counter = Counter()
    for reason in rejection_reasons:
        for category in _categorize_reason(reason):
            category_counter[category] += 1

    volume_ratios = [
        float(row["volume_ratio"])
        for row in recent_decisions
        if isinstance(row.get("volume_ratio"), (int, float))
    ]
    low_liquidity_events = sum(1 for ratio in volume_ratios if ratio < min_liquidity_volume_ratio)
    avg_volume_ratio = round(sum(volume_ratios) / len(volume_ratios), 4) if volume_ratios else None

    dte_raw = _safe_nested_dict(options_chain, "data").get("recommended_dte")
    dte_value = _as_int(dte_raw, 0) if dte_raw is not None else None

    regime_pass_signal: bool | None = None
    if isinstance(regime_check.get("passed"), bool):
        regime_pass_signal = bool(regime_check.get("passed"))
    elif isinstance(iron_regime.get("passed"), bool):
        regime_pass_signal = bool(iron_regime.get("passed"))

    risk_pass_signal: bool | None = None
    if isinstance(position_size_check.get("passed"), bool):
        risk_pass_signal = bool(position_size_check.get("passed"))

    def _status(pass_signal: bool | None) -> str:
        if pass_signal is None:
            return "unknown"
        return "pass" if pass_signal else "blocked"

    gate_status = {
        "regime": {
            "status": _status(regime_pass_signal),
            "detail": str(
                regime_check.get("note") or iron_regime.get("regime") or "No regime evidence"
            ),
            "evidence_date": str(
                iron_condor_state.get("last_updated") or swarm_state.get("last_updated") or ""
            ),
        },
        "vix": {
            "status": _status(regime_pass_signal),
            "value": regime_check.get("vix"),
            "detail": str(regime_check.get("note") or "No VIX evidence"),
        },
        "dte": {
            "status": (
                "unknown"
                if dte_value is None
                else (
                    "pass"
                    if DEFAULT_MIN_TARGET_DTE <= dte_value <= DEFAULT_MAX_TARGET_DTE
                    else "blocked"
                )
            ),
            "value": dte_value,
            "target_range": f"{DEFAULT_MIN_TARGET_DTE}-{DEFAULT_MAX_TARGET_DTE}",
        },
        "risk_caps": {
            "status": _status(risk_pass_signal),
            "detail": (
                "position_size_check unavailable"
                if risk_pass_signal is None
                else (
                    f"requested={position_size_check.get('requested')} max={position_size_check.get('max_allowed')}"
                )
            ),
        },
        "liquidity": {
            "status": (
                "unknown"
                if not recent_decisions
                else (
                    "blocked"
                    if low_liquidity_events
                    >= max(1, len(volume_ratios) // 2 if volume_ratios else 1)
                    else "pass"
                )
            ),
            "avg_volume_ratio": avg_volume_ratio,
            "low_liquidity_events": low_liquidity_events,
            "threshold_min_volume_ratio": round(min_liquidity_volume_ratio, 4),
        },
    }

    ai_credit_stress_signal = _load_ai_credit_stress_signal(data_dir, state)
    ai_status = _normalize_ai_credit_stress_status(ai_credit_stress_signal)
    ai_reasons = ai_credit_stress_signal.get("reasons", [])
    ai_reason_text = ""
    if isinstance(ai_reasons, list) and ai_reasons:
        ai_reason_text = str(ai_reasons[0])
    if not ai_reason_text:
        ai_reason_text = str(ai_credit_stress_signal.get("note") or "No AI credit stress evidence")
    ai_score = ai_credit_stress_signal.get("severity_score")
    gate_status["ai_credit_stress"] = {
        "status": ai_status,
        "signal_status": str(ai_credit_stress_signal.get("status") or "unknown"),
        "severity_score": _as_float(ai_score, 0.0) if ai_score is not None else None,
        "signal_date": ai_credit_stress_signal.get("latest_data_date"),
        "source": ai_credit_stress_signal.get("source", "none"),
        "detail": ai_reason_text,
    }

    usd_macro_signal = _load_usd_macro_sentiment_signal(data_dir, state)
    usd_status = _normalize_usd_macro_status(usd_macro_signal)
    usd_score = usd_macro_signal.get("bearish_score")
    usd_multiplier = _as_float(usd_macro_signal.get("position_size_multiplier"), 0.0)
    if usd_multiplier <= 0:
        if usd_status == "blocked":
            usd_multiplier = DEFAULT_USD_MACRO_BLOCK_MULTIPLIER
        elif usd_status == "watch":
            usd_multiplier = DEFAULT_USD_MACRO_WATCH_MULTIPLIER
        else:
            usd_multiplier = 1.0
    usd_reasons = usd_macro_signal.get("reasons", [])
    usd_reason_text = ""
    if isinstance(usd_reasons, list) and usd_reasons:
        usd_reason_text = str(usd_reasons[0])
    if not usd_reason_text:
        usd_reason_text = str(usd_macro_signal.get("note") or "No USD macro sentiment evidence")
    gate_status["usd_macro"] = {
        "status": usd_status,
        "signal_status": str(usd_macro_signal.get("status") or "unknown"),
        "bearish_score": _as_float(usd_score, 0.0) if usd_score is not None else None,
        "position_size_multiplier": round(min(1.0, max(0.1, usd_multiplier)), 4),
        "signal_date": usd_macro_signal.get("latest_data_date"),
        "source": usd_macro_signal.get("source", "none"),
        "detail": usd_reason_text,
    }

    ai_cycle_signal = _load_ai_cycle_signal(data_dir, state)
    ai_cycle_status = _normalize_ai_cycle_status(ai_cycle_signal)
    ai_cycle_score = ai_cycle_signal.get("severity_score")
    ai_cycle_multiplier = _as_float(ai_cycle_signal.get("position_size_multiplier"), 0.0)
    if ai_cycle_multiplier <= 0:
        if ai_cycle_status == "blocked":
            ai_cycle_multiplier = DEFAULT_AI_CYCLE_BLOCK_MULTIPLIER
        elif ai_cycle_status == "watch":
            ai_cycle_multiplier = DEFAULT_AI_CYCLE_WATCH_MULTIPLIER
        else:
            ai_cycle_multiplier = 1.0
    ai_cycle_reasons = ai_cycle_signal.get("reasons", [])
    ai_cycle_reason_text = ""
    if isinstance(ai_cycle_reasons, list) and ai_cycle_reasons:
        ai_cycle_reason_text = str(ai_cycle_reasons[0])
    if not ai_cycle_reason_text:
        ai_cycle_reason_text = str(ai_cycle_signal.get("note") or "No AI cycle evidence")
    gate_status["ai_cycle"] = {
        "status": ai_cycle_status,
        "signal_status": str(ai_cycle_signal.get("status") or "unknown"),
        "severity_score": _as_float(ai_cycle_score, 0.0) if ai_cycle_score is not None else None,
        "position_size_multiplier": round(min(1.0, max(0.1, ai_cycle_multiplier)), 4),
        "regime": str(ai_cycle_signal.get("regime") or "unknown"),
        "confidence": _as_float(ai_cycle_signal.get("confidence"), None),
        "capex_deceleration_shock": bool(ai_cycle_signal.get("capex_deceleration_shock")),
        "signal_date": ai_cycle_signal.get("latest_data_date"),
        "source": ai_cycle_signal.get("source", "none"),
        "detail": ai_cycle_reason_text,
    }

    blocked_categories = [
        name for name, payload in gate_status.items() if payload.get("status") == "blocked"
    ]

    if closed_trades_recent > 0:
        summary = (
            "Closed trades exist in lookback window; no-trade root cause not currently active."
        )
    elif qualified_setups_recent == 0:
        summary = (
            "No qualified setups captured in lookback window. "
            "Focus on setup generation cadence before adjusting execution."
        )
    elif blocked_categories:
        summary = f"No closed trades detected; likely blocked by: {', '.join(blocked_categories)}."
    else:
        summary = (
            "No closed trades detected and no single blocking gate identified. "
            "Investigate strategy cadence and execution conversion."
        )

    top_reasons = [
        {"reason": reason, "count": count} for reason, count in reason_counter.most_common(5)
    ]
    gate_block_counts = {
        category: int(count) for category, count in sorted(category_counter.items())
    }

    return {
        "lookback_days": DEFAULT_LOOKBACK_DAYS,
        "decision_records_observed": len(recent_decisions),
        "closed_trades_observed": closed_trades_recent,
        "qualified_setups_observed": qualified_setups_recent,
        "gate_status": gate_status,
        "blocked_categories": blocked_categories,
        "gate_block_counts": gate_block_counts,
        "top_rejection_reasons": top_reasons,
        "summary": summary,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _extract_recent_closed_trades(
    trades_payload: dict[str, Any],
    *,
    today: date,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> list[dict[str, Any]]:
    all_trades = trades_payload.get("trades", [])
    if not isinstance(all_trades, list):
        return []

    start_date = today - timedelta(days=max(1, lookback_days) - 1)
    rows: list[dict[str, Any]] = []
    for raw in all_trades:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("status", "")).lower() != "closed":
            continue

        closed_at = _parse_date(
            raw.get("exit_date")
            or raw.get("exit_time")
            or raw.get("closed_at")
            or raw.get("timestamp")
        )
        if closed_at is None or closed_at < start_date or closed_at > today:
            continue

        pnl = _as_float(raw.get("realized_pnl", raw.get("pnl", raw.get("pl", 0.0))), 0.0)
        outcome = str(raw.get("outcome", "")).lower()
        if outcome not in {"win", "loss", "breakeven"}:
            if pnl > 0:
                outcome = "win"
            elif pnl < 0:
                outcome = "loss"
            else:
                outcome = "breakeven"

        rows.append({"closed_at": closed_at.isoformat(), "pnl": pnl, "outcome": outcome})
    return rows


def _sync_paper_win_rate_from_trades_payload(
    state: dict[str, Any], trades_payload: dict[str, Any]
) -> None:
    """Mirror ledger-derived win rate into system_state.paper_account."""
    stats = trades_payload.get("stats", {}) if isinstance(trades_payload, dict) else {}
    closed_trades = _as_int(stats.get("closed_trades"), 0)
    win_rate_raw = stats.get("win_rate_pct")
    win_rate_val = _as_float(win_rate_raw, 0.0) if win_rate_raw is not None else 0.0

    state.setdefault("paper_account", {})
    state["paper_account"]["win_rate"] = round(win_rate_val, 2)
    state["paper_account"]["win_rate_sample_size"] = closed_trades


def _compute_ic_win_rate_from_history(state: dict[str, Any]) -> dict[str, Any]:
    """Compute win rate from complete SPY iron condor round-trips in trade_history.

    Groups individual legs by expiry date (encoded in the symbol, e.g. "260313").
    An iron condor round-trip has >= 8 legs (4 open + 4 close). For each complete
    round-trip, net cash flow = sum(SELL prices) - sum(BUY prices). Positive = win.

    Expiry groups with still-open positions are excluded — only fully settled ICs count.
    """
    trade_history = state.get("trade_history", []) if isinstance(state, dict) else []
    if not isinstance(trade_history, list):
        trade_history = []

    # Identify expiry dates that still have open positions (not settled yet)
    open_expiries: set[str] = set()
    for pos in state.get("positions", []):
        if not isinstance(pos, dict):
            continue
        m = _SPY_OPTION_RE.match(str(pos.get("symbol", "")))
        if m:
            open_expiries.add(m.group(1))

    # Group legs by expiry date extracted from symbol
    expiry_groups: dict[str, list[dict[str, Any]]] = {}
    for t in trade_history:
        if not isinstance(t, dict):
            continue
        symbol = str(t.get("symbol", ""))
        m = _SPY_OPTION_RE.match(symbol)
        if not m:
            continue
        expiry_key = m.group(1)  # e.g. "260220"
        expiry_groups.setdefault(expiry_key, []).append(t)

    wins = 0
    losses = 0
    total_pnl = 0.0

    for expiry_key, legs in expiry_groups.items():
        # Skip if this expiry still has open positions (IC not fully settled)
        if expiry_key in open_expiries:
            continue

        # A complete IC round-trip needs >= 8 legs (4 open + 4 close).
        # Groups with fewer legs are partial — skip them.
        if len(legs) < 8:
            continue

        # Net cash flow: SELL = credit (+), BUY = debit (-)
        net = 0.0
        for leg in legs:
            # trade_history stores option premiums as per-share price strings.
            # Convert to dollars with contract multiplier (100) and quantity.
            price = _as_float(leg.get("price"), 0.0)
            qty = _as_float(leg.get("qty", leg.get("quantity", 1.0)), 1.0)
            cash = price * qty * 100.0

            side = str(leg.get("side", "")).upper()
            if "SELL" in side:
                net += cash
            elif "BUY" in side:
                net -= cash

        total_pnl += net
        if net > 0:
            wins += 1
        elif net < 0:
            losses += 1

    samples = wins + losses
    if samples == 0:
        return {
            "samples": 0,
            "wins": 0,
            "win_rate_pct": 0.0,
            "expectancy": 0.0,
            "evidence_source": "no_completed_ic_trades",
        }

    win_rate_pct = round((wins / samples) * 100.0, 2)
    expectancy = round(total_pnl / samples, 4)

    return {
        "samples": samples,
        "wins": wins,
        "win_rate_pct": win_rate_pct,
        "expectancy": expectancy,
        "evidence_source": "trade_history_ic_only",
    }


def compute_weekly_gate(
    state: dict[str, Any],
    *,
    trades_path: Path = DEFAULT_TRADES_PATH,
    weekly_history_path: Path = DEFAULT_WEEKLY_HISTORY_PATH,
    today: date | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Compute weekly risk gate and persist week-over-week quality history."""
    today = today or date.today()
    trades_payload = _load_json_dict(trades_path)
    recent_closed = _extract_recent_closed_trades(trades_payload, today=today)
    data_dir = trades_path.parent
    min_liquidity_volume_ratio = _resolve_min_liquidity_volume_ratio(data_dir)
    recent_decisions = _extract_recent_session_decisions(
        data_dir=data_dir,
        today=today,
        lookback_days=DEFAULT_LOOKBACK_DAYS,
    )
    qualified_setups = sum(1 for row in recent_decisions if row.get("qualified") is True)

    samples = len(recent_closed)
    wins = sum(1 for row in recent_closed if row.get("outcome") == "win")
    total_pnl = sum(_as_float(row.get("pnl"), 0.0) for row in recent_closed)
    lifetime_closed_trades = _as_int(
        _safe_nested_dict(trades_payload, "stats").get("closed_trades"),
        0,
    )

    if samples > 0:
        win_rate_pct = round((wins / samples) * 100.0, 2)
        expectancy = round(total_pnl / samples, 4)
        evidence_source = "trades.json"
    else:
        # Fallback: compute IC-only win rate from trade_history in system_state.
        # The blended paper_account.win_rate includes non-IC trades (REITs, stocks,
        # individual puts) which pollute the iron condor strategy signal.
        ic_stats = _compute_ic_win_rate_from_history(state)
        samples = ic_stats["samples"]
        wins = ic_stats["wins"]
        win_rate_pct = ic_stats["win_rate_pct"]
        expectancy = ic_stats["expectancy"]
        evidence_source = ic_stats["evidence_source"]
        if lifetime_closed_trades <= 0:
            lifetime_closed_trades = samples

    mode = "validation"
    recommended_max = 0.02
    block_new_positions = False
    reason = "Insufficient recent weekly evidence; keep conservative sizing."

    if samples >= DEFAULT_WEEKLY_MIN_SAMPLES and expectancy <= 0:
        mode = "defensive"
        recommended_max = 0.01
        block_new_positions = True
        reason = (
            f"Weekly expectancy ${expectancy:.2f}/trade over {samples} samples is non-positive."
        )
    elif samples >= DEFAULT_WEEKLY_MIN_SAMPLES and win_rate_pct < 65.0:
        mode = "defensive"
        recommended_max = 0.01
        # Only block if BOTH win rate is poor AND expectancy is non-positive.
        # A strategy with positive expectancy is net profitable even with
        # sub-55% win rate (common for iron condors with favorable risk/reward).
        block_new_positions = win_rate_pct < 55.0 and samples >= 8 and expectancy <= 0
        reason = f"Weekly win rate {win_rate_pct:.1f}% is below 65% safety threshold."
    elif samples >= 12 and win_rate_pct >= 80.0 and expectancy > 0:
        mode = "expansion_candidate"
        recommended_max = 0.03
        reason = "Weekly edge is healthy; candidate for gradual scaling."
    elif samples >= DEFAULT_WEEKLY_MIN_SAMPLES:
        mode = "cautious"
        recommended_max = 0.015
        reason = "Weekly edge mixed; stay cautious while collecting more evidence."

    cadence_kpi = {
        "enabled": True,
        "min_qualified_setups_per_week": DEFAULT_MIN_QUALIFIED_SETUPS_PER_WEEK,
        "min_closed_trades_per_week": DEFAULT_MIN_CLOSED_TRADES_PER_WEEK,
        "qualified_setups_observed": qualified_setups,
        "closed_trades_observed": samples,
        "meets_qualified_setups": qualified_setups >= DEFAULT_MIN_QUALIFIED_SETUPS_PER_WEEK,
        "meets_closed_trades": samples >= DEFAULT_MIN_CLOSED_TRADES_PER_WEEK,
    }
    cadence_kpi["passed"] = bool(
        cadence_kpi["meets_qualified_setups"] and cadence_kpi["meets_closed_trades"]
    )
    if cadence_kpi["passed"]:
        cadence_kpi["alert_level"] = "ok"
        cadence_kpi["summary"] = "Cadence KPI met."
    elif not cadence_kpi["meets_qualified_setups"] and not cadence_kpi["meets_closed_trades"]:
        cadence_kpi["alert_level"] = "critical"
        cadence_kpi["summary"] = (
            "Cadence KPI miss: qualified setups and closed trades are both below weekly minimum."
        )
    else:
        cadence_kpi["alert_level"] = "warning"
        cadence_kpi["summary"] = "Cadence KPI miss: one or more weekly minimums not met."

    no_trade_diagnostic = _compute_no_trade_diagnostic(
        data_dir=data_dir,
        state=state,
        recent_decisions=recent_decisions,
        closed_trades_recent=samples,
        qualified_setups_recent=qualified_setups,
        min_liquidity_volume_ratio=min_liquidity_volume_ratio,
    )

    ai_credit_gate = _safe_nested_dict(no_trade_diagnostic, "gate_status", "ai_credit_stress")
    ai_credit_status = str(ai_credit_gate.get("status") or "unknown").lower()
    ai_credit_score = _as_float(ai_credit_gate.get("severity_score"), 0.0)
    if ai_credit_status == "blocked":
        mode = "defensive"
        recommended_max = min(recommended_max, 0.01)
        block_new_positions = (
            block_new_positions or ai_credit_score >= DEFAULT_AI_CREDIT_HARD_BLOCK_SCORE
        )
        reason = f"{reason} AI credit stress blocked: score={ai_credit_score:.1f}."
    elif ai_credit_status == "watch":
        if mode == "expansion_candidate":
            mode = "cautious"
        recommended_max = min(recommended_max, 0.015)
        reason = f"{reason} AI credit stress elevated; hold cautious sizing."

    usd_macro_gate = _safe_nested_dict(no_trade_diagnostic, "gate_status", "usd_macro")
    usd_macro_status = str(usd_macro_gate.get("status") or "unknown").lower()
    usd_macro_multiplier = _as_float(usd_macro_gate.get("position_size_multiplier"), 1.0)
    if usd_macro_multiplier <= 0:
        usd_macro_multiplier = 1.0
    usd_macro_multiplier = min(1.0, max(0.1, usd_macro_multiplier))
    if usd_macro_status in {"watch", "blocked"} and usd_macro_multiplier < 1.0:
        adjusted_limit = round(recommended_max * usd_macro_multiplier, 4)
        recommended_max = min(recommended_max, adjusted_limit)
        if mode == "expansion_candidate":
            mode = "cautious"
        score_text = usd_macro_gate.get("bearish_score")
        score_suffix = (
            f" score={_as_float(score_text, 0.0):.1f}"
            if isinstance(score_text, (int, float))
            else ""
        )
        reason = (
            f"{reason} USD macro sentiment {usd_macro_status}; "
            f"applied size multiplier {usd_macro_multiplier:.2f}.{score_suffix}"
        )

    ai_cycle_gate = _safe_nested_dict(no_trade_diagnostic, "gate_status", "ai_cycle")
    ai_cycle_status = str(ai_cycle_gate.get("status") or "unknown").lower()
    ai_cycle_score = _as_float(ai_cycle_gate.get("severity_score"), 0.0)
    ai_cycle_multiplier = _as_float(ai_cycle_gate.get("position_size_multiplier"), 1.0)
    if ai_cycle_multiplier <= 0:
        ai_cycle_multiplier = 1.0
    ai_cycle_multiplier = min(1.0, max(0.1, ai_cycle_multiplier))
    ai_cycle_shock = bool(ai_cycle_gate.get("capex_deceleration_shock"))
    if ai_cycle_status in {"watch", "blocked"} and ai_cycle_multiplier < 1.0:
        adjusted_limit = round(recommended_max * ai_cycle_multiplier, 4)
        recommended_max = min(recommended_max, adjusted_limit)
        if mode == "expansion_candidate":
            mode = "cautious"
        reason = (
            f"{reason} AI cycle {ai_cycle_status}; "
            f"applied size multiplier {ai_cycle_multiplier:.2f}."
        )
    if ai_cycle_status == "blocked":
        mode = "defensive"
        recommended_max = min(recommended_max, 0.01)
    if ai_cycle_shock or ai_cycle_score >= DEFAULT_AI_CYCLE_HARD_BLOCK_SCORE:
        mode = "defensive"
        recommended_max = min(recommended_max, 0.01)
        block_new_positions = True
        reason = (
            f"{reason} AI cycle capex deceleration shock detected; "
            "blocking new positions until signal normalizes."
        )

    weekly_history = _load_json_list(weekly_history_path)
    week_start = today - timedelta(days=today.weekday())
    week_start_iso = week_start.isoformat()
    weekly_entry_fields = {
        "week_start": week_start_iso,
        "sample_size": samples,
        "win_rate_pct": win_rate_pct,
        "expectancy_per_trade": expectancy,
        "mode": mode,
        "qualified_setups": qualified_setups,
        "cadence_passed": cadence_kpi["passed"],
    }

    replaced = False
    for idx, row in enumerate(weekly_history):
        if str(row.get("week_start")) == week_start_iso:
            unchanged = (
                _as_int(row.get("sample_size"), -1) == samples
                and _as_float(row.get("win_rate_pct"), -1.0) == win_rate_pct
                and _as_float(row.get("expectancy_per_trade"), -999999.0) == expectancy
                and str(row.get("mode", "")) == mode
                and _as_int(row.get("qualified_setups"), -1) == qualified_setups
                and bool(row.get("cadence_passed")) is cadence_kpi["passed"]
            )
            if unchanged:
                # Keep historical timestamp untouched when nothing changed.
                weekly_entry = row
            else:
                weekly_entry = {
                    **weekly_entry_fields,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            weekly_history[idx] = weekly_entry
            replaced = True
            break
    if not replaced:
        weekly_history.append(
            {
                **weekly_entry_fields,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    weekly_history.sort(key=lambda row: str(row.get("week_start", "")))
    weekly_history = weekly_history[-DEFAULT_HISTORY_WEEKS:]

    positive_streak = 0
    for row in reversed(weekly_history):
        s = _as_int(row.get("sample_size"), 0)
        wr = _as_float(row.get("win_rate_pct"), 0.0)
        ex = _as_float(row.get("expectancy_per_trade"), 0.0)
        if s >= DEFAULT_WEEKLY_MIN_SAMPLES and wr >= 75.0 and ex > 0:
            positive_streak += 1
            continue
        break

    if mode == "expansion_candidate" and positive_streak < 2:
        recommended_max = min(recommended_max, 0.02)
        reason = (
            f"Weekly edge improved but only {positive_streak} qualifying positive week(s); "
            "require >=2 before scaling."
        )

    scaling_sample_gate = {
        "enabled": True,
        "min_closed_trades_for_scaling": DEFAULT_MIN_CLOSED_TRADES_FOR_SCALING,
        "closed_trades_observed": lifetime_closed_trades,
        "passed": lifetime_closed_trades >= DEFAULT_MIN_CLOSED_TRADES_FOR_SCALING,
    }

    if mode == "expansion_candidate" and not scaling_sample_gate["passed"]:
        mode = "cautious"
        recommended_max = min(recommended_max, 0.02)
        reason = (
            f"Scaling blocked: {lifetime_closed_trades} closed trades < "
            f"{DEFAULT_MIN_CLOSED_TRADES_FOR_SCALING} minimum for statistically valid scaling."
        )

    if not cadence_kpi["passed"]:
        recommended_max = min(recommended_max, 0.015)
        if mode == "expansion_candidate":
            mode = "cautious"
        reason = (
            f"{reason} Cadence KPI miss: setups {qualified_setups}/"
            f"{DEFAULT_MIN_QUALIFIED_SETUPS_PER_WEEK}, closed trades {samples}/"
            f"{DEFAULT_MIN_CLOSED_TRADES_PER_WEEK}."
        )

    weekly_history_path.parent.mkdir(parents=True, exist_ok=True)
    new_weekly_payload = json.dumps(weekly_history, indent=2) + "\n"
    current_weekly_payload = (
        weekly_history_path.read_text(encoding="utf-8") if weekly_history_path.exists() else ""
    )
    if current_weekly_payload != new_weekly_payload:
        weekly_history_path.write_text(new_weekly_payload, encoding="utf-8")

    gate = {
        "enabled": True,
        "lookback_days": DEFAULT_LOOKBACK_DAYS,
        "mode": mode,
        "sample_size": samples,
        "win_rate_pct": win_rate_pct,
        "expectancy_per_trade": expectancy,
        "recommended_max_position_pct": round(recommended_max, 4),
        "block_new_positions": block_new_positions,
        "reason": reason,
        "positive_weeks_streak": positive_streak,
        "evidence_source": evidence_source,
        "cadence_kpi": cadence_kpi,
        "scale_blocked_by_cadence": not cadence_kpi["passed"],
        "ai_credit_stress": ai_credit_gate,
        "scale_blocked_by_ai_credit_stress": ai_credit_status == "blocked",
        "usd_macro_sentiment": usd_macro_gate,
        "scale_multiplier_from_usd_macro": round(usd_macro_multiplier, 4),
        "ai_cycle": ai_cycle_gate,
        "scale_blocked_by_ai_cycle": ai_cycle_status == "blocked" or ai_cycle_shock,
        "scale_multiplier_from_ai_cycle": round(ai_cycle_multiplier, 4),
        "scaling_sample_gate": scaling_sample_gate,
        "liquidity_min_volume_ratio": round(min_liquidity_volume_ratio, 4),
        "no_trade_diagnostic": no_trade_diagnostic,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return gate, weekly_history


def compute_contribution_plan(
    state: dict[str, Any],
    *,
    today: date | None = None,
) -> dict[str, Any]:
    """Compute ASAP monthly-income progress tracking for North Star."""
    today = today or date.today()
    paper = state.get("paper_account", {}) if isinstance(state, dict) else {}
    live = state.get("live_account", {}) if isinstance(state, dict) else {}
    existing = state.get("north_star_contributions", {}) if isinstance(state, dict) else {}

    current_equity = _as_float(
        paper.get("equity"),
        _as_float(state.get("account", {}).get("current_equity"), 0.0),
    )

    month_key = today.strftime("%Y-%m")
    existing_month = str(existing.get("month", ""))
    if existing_month == month_key:
        month_start_equity = _as_float(existing.get("month_start_equity"), current_equity)
        live_month_start_equity = _as_float(
            existing.get("live_month_start_equity"),
            _as_float(live.get("equity"), 0.0),
        )
    else:
        month_start_equity = current_equity
        live_month_start_equity = _as_float(live.get("equity"), 0.0)

    equity_change_this_month = round(current_equity - month_start_equity, 2)
    live_current_equity = _as_float(live.get("equity"), 0.0)
    live_change_this_month = round(live_current_equity - live_month_start_equity, 2)
    live_positions = _as_int(live.get("positions_count"), 0)

    estimated_live_contribution = None
    contribution_confidence = "low"
    inference_note = (
        "Cannot separate deposits from trading P/L in broker snapshots; "
        "using equity deltas as directional signal only."
    )
    if live_positions == 0:
        estimated_live_contribution = round(max(0.0, live_change_this_month), 2)
        contribution_confidence = "medium"
        inference_note = "Live account has no open positions; live equity change is treated as estimated contribution."

    monthly_target = max(0.0, float(NORTH_STAR_MONTHLY_AFTER_TAX))
    daily_target = max(0.0, float(NORTH_STAR_DAILY_AFTER_TAX))
    progress_pct = (
        (equity_change_this_month / monthly_target * 100.0) if monthly_target > 0 else 0.0
    )
    remaining_to_monthly_target = max(0.0, monthly_target - equity_change_this_month)
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_elapsed = max(1, today.day)
    days_remaining = max(0, days_in_month - today.day)
    projected_month_end_pnl = round((equity_change_this_month / days_elapsed) * days_in_month, 2)
    projected_gap_at_month_end = round(max(0.0, monthly_target - projected_month_end_pnl), 2)
    required_daily_from_now = (
        round(remaining_to_monthly_target / days_remaining, 2) if days_remaining > 0 else 0.0
    )

    return {
        "enabled": True,
        "target_mode": "asap_monthly_income",
        "month": month_key,
        "target_date": None,
        "months_remaining": None,
        "target_capital": NORTH_STAR_TARGET_CAPITAL,
        "monthly_after_tax_target": round(monthly_target, 2),
        "daily_after_tax_target": round(daily_target, 2),
        "current_equity": round(current_equity, 2),
        "required_cagr_without_contributions": None,
        "required_monthly_contribution_by_return": {},
        "assumed_return": None,
        "required_monthly_contribution_at_assumed_return": None,
        "month_start_equity": round(month_start_equity, 2),
        "equity_change_this_month": equity_change_this_month,
        "monthly_target_progress_pct": round(max(0.0, progress_pct), 2),
        "remaining_to_monthly_target": round(remaining_to_monthly_target, 2),
        "days_elapsed_this_month": days_elapsed,
        "days_remaining_this_month": days_remaining,
        "required_daily_after_tax_from_now": required_daily_from_now,
        "projected_month_end_after_tax_pnl": projected_month_end_pnl,
        "projected_gap_to_monthly_target": projected_gap_at_month_end,
        "live_month_start_equity": round(live_month_start_equity, 2),
        "live_equity_change_this_month": live_change_this_month,
        "estimated_live_contribution_this_month": estimated_live_contribution,
        "contribution_estimate_confidence": contribution_confidence,
        "inference_note": inference_note,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def apply_operating_plan_to_state(
    state: dict[str, Any],
    *,
    trades_path: Path = DEFAULT_TRADES_PATH,
    weekly_history_path: Path = DEFAULT_WEEKLY_HISTORY_PATH,
    today: date | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Apply weekly gate + contribution plan to mutable system_state payload."""
    today = today or date.today()
    trades_payload = _load_json_dict(trades_path)
    _sync_paper_win_rate_from_trades_payload(state, trades_payload)

    weekly_gate, weekly_history = compute_weekly_gate(
        state,
        trades_path=trades_path,
        weekly_history_path=weekly_history_path,
        today=today,
    )
    contributions = compute_contribution_plan(state, today=today)

    state["north_star_weekly_gate"] = weekly_gate
    state["north_star_contributions"] = contributions

    state.setdefault("risk", {})
    state["risk"]["weekly_gate_mode"] = weekly_gate.get("mode")
    state["risk"]["weekly_gate_recommended_max_position_pct"] = weekly_gate.get(
        "recommended_max_position_pct"
    )
    state["risk"]["weekly_cadence_kpi_passed"] = bool(
        _safe_nested_dict(weekly_gate, "cadence_kpi").get("passed")
    )
    state["risk"]["weekly_scaling_sample_gate_passed"] = bool(
        _safe_nested_dict(weekly_gate, "scaling_sample_gate").get("passed")
    )
    state["risk"]["weekly_ai_credit_stress_status"] = str(
        _safe_nested_dict(weekly_gate, "ai_credit_stress").get("status") or "unknown"
    )
    state["risk"]["weekly_ai_credit_stress_score"] = _safe_nested_dict(
        weekly_gate, "ai_credit_stress"
    ).get("severity_score")
    state["risk"]["weekly_usd_macro_status"] = str(
        _safe_nested_dict(weekly_gate, "usd_macro_sentiment").get("status") or "unknown"
    )
    state["risk"]["weekly_usd_macro_score"] = _safe_nested_dict(
        weekly_gate, "usd_macro_sentiment"
    ).get("bearish_score")
    state["risk"]["weekly_usd_macro_multiplier"] = _safe_nested_dict(
        weekly_gate, "usd_macro_sentiment"
    ).get("position_size_multiplier")
    state["risk"]["weekly_ai_cycle_status"] = str(
        _safe_nested_dict(weekly_gate, "ai_cycle").get("status") or "unknown"
    )
    state["risk"]["weekly_ai_cycle_score"] = _safe_nested_dict(weekly_gate, "ai_cycle").get(
        "severity_score"
    )
    state["risk"]["weekly_ai_cycle_multiplier"] = _safe_nested_dict(
        weekly_gate, "ai_cycle"
    ).get("position_size_multiplier")
    state["risk"]["weekly_ai_cycle_regime"] = _safe_nested_dict(weekly_gate, "ai_cycle").get(
        "regime"
    )
    state["risk"]["weekly_ai_cycle_capex_deceleration_shock"] = bool(
        _safe_nested_dict(weekly_gate, "ai_cycle").get("capex_deceleration_shock")
    )
    return state, weekly_history
