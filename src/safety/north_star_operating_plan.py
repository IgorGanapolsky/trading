"""North Star weekly operating plan and contribution tracking.

This module keeps the North Star execution loop practical:
- Weekly gate: cap/lock risk when edge deteriorates.
- Contribution plan: quantify required monthly capital support by return scenario.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.core.trading_constants import NORTH_STAR_TARGET_CAPITAL, NORTH_STAR_TARGET_DATE

DEFAULT_TRADES_PATH = Path("data/trades.json")
DEFAULT_WEEKLY_HISTORY_PATH = Path("data/north_star_weekly_history.json")
DEFAULT_LOOKBACK_DAYS = 7
DEFAULT_WEEKLY_MIN_SAMPLES = 5
DEFAULT_HISTORY_WEEKS = 104

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

    samples = len(recent_closed)
    wins = sum(1 for row in recent_closed if row.get("outcome") == "win")
    total_pnl = sum(_as_float(row.get("pnl"), 0.0) for row in recent_closed)

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

    weekly_history = _load_json_list(weekly_history_path)
    week_start = today - timedelta(days=today.weekday())
    week_start_iso = week_start.isoformat()
    weekly_entry_fields = {
        "week_start": week_start_iso,
        "sample_size": samples,
        "win_rate_pct": win_rate_pct,
        "expectancy_per_trade": expectancy,
        "mode": mode,
    }

    replaced = False
    for idx, row in enumerate(weekly_history):
        if str(row.get("week_start")) == week_start_iso:
            unchanged = (
                _as_int(row.get("sample_size"), -1) == samples
                and _as_float(row.get("win_rate_pct"), -1.0) == win_rate_pct
                and _as_float(row.get("expectancy_per_trade"), -999999.0) == expectancy
                and str(row.get("mode", "")) == mode
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
    return state, weekly_history
