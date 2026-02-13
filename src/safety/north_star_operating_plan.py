"""North Star weekly operating plan and contribution tracking.

This module keeps the North Star execution loop practical:
- Weekly gate: cap/lock risk when edge deteriorates.
- Contribution plan: quantify required monthly capital support by return scenario.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.core.trading_constants import NORTH_STAR_TARGET_CAPITAL, NORTH_STAR_TARGET_DATE

DEFAULT_TRADES_PATH = Path("data/trades.json")
DEFAULT_WEEKLY_HISTORY_PATH = Path("data/north_star_weekly_history.json")
DEFAULT_LOOKBACK_DAYS = 7
DEFAULT_WEEKLY_MIN_SAMPLES = 5
DEFAULT_HISTORY_WEEKS = 104


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
        return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []
    except Exception:
        return []


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

    samples = len(recent_closed)
    wins = sum(1 for row in recent_closed if row.get("outcome") == "win")
    total_pnl = sum(_as_float(row.get("pnl"), 0.0) for row in recent_closed)

    if samples > 0:
        win_rate_pct = round((wins / samples) * 100.0, 2)
        expectancy = round(total_pnl / samples, 4)
        evidence_source = "trades.json"
    else:
        paper = state.get("paper_account", {}) if isinstance(state, dict) else {}
        paper_samples = _as_int(paper.get("win_rate_sample_size"), 0)
        paper_win_rate = _as_float(paper.get("win_rate"), 0.0)
        paper_total_pl = _as_float(paper.get("total_pl"), 0.0)

        samples = paper_samples
        wins = round((paper_win_rate / 100.0) * paper_samples) if paper_samples > 0 else 0
        win_rate_pct = round(paper_win_rate, 2) if paper_samples > 0 else 0.0
        expectancy = round(paper_total_pl / paper_samples, 4) if paper_samples > 0 else 0.0
        evidence_source = "paper_account_fallback"

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
        block_new_positions = win_rate_pct < 55.0 and samples >= 8
        reason = f"Weekly win rate {win_rate_pct:.1f}% is below 65% safety threshold."
    elif samples >= 12 and win_rate_pct >= 80.0 and expectancy > 0:
        mode = "expansion_candidate"
        recommended_max = 0.03
        reason = "Weekly edge is healthy; candidate for gradual scaling."
    elif samples >= DEFAULT_WEEKLY_MIN_SAMPLES:
        mode = "cautious"
        recommended_max = 0.015
        reason = "Weekly edge mixed; stay cautious while collecting more evidence."

    weekly_history = _load_json_list(weekly_history_path)
    week_start = today - timedelta(days=today.weekday())
    week_start_iso = week_start.isoformat()
    weekly_entry = {
        "week_start": week_start_iso,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "sample_size": samples,
        "win_rate_pct": win_rate_pct,
        "expectancy_per_trade": expectancy,
        "mode": mode,
    }

    replaced = False
    for idx, row in enumerate(weekly_history):
        if str(row.get("week_start")) == week_start_iso:
            weekly_history[idx] = weekly_entry
            replaced = True
            break
    if not replaced:
        weekly_history.append(weekly_entry)

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

    weekly_history_path.parent.mkdir(parents=True, exist_ok=True)
    weekly_history_path.write_text(json.dumps(weekly_history, indent=2), encoding="utf-8")

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
        inference_note = (
            "Live account has no open positions; live equity change is treated as estimated contribution."
        )

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
    return state, weekly_history
