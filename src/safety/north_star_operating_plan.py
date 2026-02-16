"""North Star weekly operating plan and contribution tracking.

This module keeps the North Star execution loop practical:
- Weekly gate: cap/lock risk when edge deteriorates.
- Contribution plan: quantify required monthly capital support by return scenario.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.core.trading_constants import NORTH_STAR_TARGET_CAPITAL, NORTH_STAR_TARGET_DATE

DEFAULT_TRADES_PATH = Path("data/trades.json")
DEFAULT_WEEKLY_HISTORY_PATH = Path("data/north_star_weekly_history.json")
DEFAULT_LOOKBACK_DAYS = 7
DEFAULT_WEEKLY_MIN_SAMPLES = 5
DEFAULT_HISTORY_WEEKS = 104
DEFAULT_MIN_QUALIFIED_SETUPS_PER_WEEK = 3
DEFAULT_MIN_CLOSED_TRADES_PER_WEEK = 1
DEFAULT_MIN_CLOSED_TRADES_FOR_SCALING = 30
DEFAULT_MIN_LIQUIDITY_VOLUME_RATIO = 0.20
DEFAULT_MAX_TARGET_DTE = 45
DEFAULT_MIN_TARGET_DTE = 21

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
    return categories


def _safe_nested_dict(payload: dict[str, Any], *keys: str) -> dict[str, Any]:
    cur: Any = payload
    for key in keys:
        if not isinstance(cur, dict):
            return {}
        cur = cur.get(key)
    return cur if isinstance(cur, dict) else {}


def _compute_no_trade_diagnostic(
    *,
    data_dir: Path,
    recent_decisions: list[dict[str, Any]],
    closed_trades_recent: int,
    qualified_setups_recent: int,
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
    low_liquidity_events = sum(
        1 for ratio in volume_ratios if ratio < DEFAULT_MIN_LIQUIDITY_VOLUME_RATIO
    )
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
            "threshold_min_volume_ratio": DEFAULT_MIN_LIQUIDITY_VOLUME_RATIO,
        },
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


def _calc_required_monthly_contribution(
    current_equity: float,
    annual_return: float,
    months_remaining: int,
    target_capital: float,
) -> float:
    if months_remaining <= 0 or current_equity <= 0 or target_capital <= 0:
        return 0.0

    r = annual_return / 12.0
    if r <= 0:
        return max(0.0, (target_capital - current_equity) / months_remaining)

    future_without_contrib = current_equity * ((1 + r) ** months_remaining)
    if future_without_contrib >= target_capital:
        return 0.0

    annuity_factor = ((1 + r) ** months_remaining - 1) / r
    if annuity_factor <= 0:
        return 0.0
    return max(0.0, (target_capital - future_without_contrib) / annuity_factor)


def _required_cagr_without_contrib(current_equity: float, years_remaining: float) -> float:
    if current_equity <= 0 or years_remaining <= 0:
        return 0.0
    return (NORTH_STAR_TARGET_CAPITAL / current_equity) ** (1.0 / years_remaining) - 1.0


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
        recent_decisions=recent_decisions,
        closed_trades_recent=samples,
        qualified_setups_recent=qualified_setups,
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
        "scaling_sample_gate": scaling_sample_gate,
        "no_trade_diagnostic": no_trade_diagnostic,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return gate, weekly_history


def compute_contribution_plan(
    state: dict[str, Any],
    *,
    today: date | None = None,
) -> dict[str, Any]:
    """Compute monthly contribution requirements and current-month progress tracking."""
    today = today or date.today()
    paper = state.get("paper_account", {}) if isinstance(state, dict) else {}
    live = state.get("live_account", {}) if isinstance(state, dict) else {}
    existing = state.get("north_star_contributions", {}) if isinstance(state, dict) else {}

    current_equity = _as_float(
        paper.get("equity"),
        _as_float(state.get("account", {}).get("current_equity"), 0.0),
    )

    months_remaining = (NORTH_STAR_TARGET_DATE.year - today.year) * 12 + (
        NORTH_STAR_TARGET_DATE.month - today.month
    )
    if today.day > NORTH_STAR_TARGET_DATE.day:
        months_remaining -= 1
    months_remaining = max(1, months_remaining)

    years_remaining = max(0.01, (NORTH_STAR_TARGET_DATE - today).days / 365.25)
    required_cagr = _required_cagr_without_contrib(current_equity, years_remaining)

    annual_scenarios = [0.20, 0.25, 0.30, 0.35]
    required_by_return: dict[str, float] = {}
    for annual_return in annual_scenarios:
        monthly = _calc_required_monthly_contribution(
            current_equity=current_equity,
            annual_return=annual_return,
            months_remaining=months_remaining,
            target_capital=NORTH_STAR_TARGET_CAPITAL,
        )
        required_by_return[f"{int(annual_return * 100)}%"] = round(monthly, 2)

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

    assumed_return = 0.30
    required_at_assumed = _calc_required_monthly_contribution(
        current_equity=current_equity,
        annual_return=assumed_return,
        months_remaining=months_remaining,
        target_capital=NORTH_STAR_TARGET_CAPITAL,
    )

    return {
        "enabled": True,
        "month": month_key,
        "months_remaining": months_remaining,
        "target_date": NORTH_STAR_TARGET_DATE.isoformat(),
        "target_capital": NORTH_STAR_TARGET_CAPITAL,
        "current_equity": round(current_equity, 2),
        "required_cagr_without_contributions": round(required_cagr, 4),
        "required_monthly_contribution_by_return": required_by_return,
        "assumed_return": assumed_return,
        "required_monthly_contribution_at_assumed_return": round(required_at_assumed, 2),
        "month_start_equity": round(month_start_equity, 2),
        "equity_change_this_month": equity_change_this_month,
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
    return state, weekly_history
