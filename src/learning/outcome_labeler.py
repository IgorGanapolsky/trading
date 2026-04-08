"""Normalize trade outcomes into compact labels for ML/RLHF pipelines."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


def _safe_float(value: Any) -> float | None:
    """Convert value to float when possible."""
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _pick_first(payload: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    """Return first non-None value for key candidates."""
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return None


def _parse_timestamp(value: Any) -> datetime | None:
    """Parse datetime-like values into timezone-aware UTC datetimes."""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            return None
    else:
        return None

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _compute_return_pct(payload: Mapping[str, Any], reward: float) -> float | None:
    """Compute return percentage from explicit value or available bases."""
    explicit_return = _safe_float(
        _pick_first(payload, ("return_pct", "pl_pct", "pnl_pct", "profit_pct", "return_percentage"))
    )
    if explicit_return is not None:
        return round(explicit_return, 4)

    credit_base = _safe_float(
        _pick_first(payload, ("credit_received", "credit", "cost_basis", "invested_capital"))
    )
    if credit_base is not None and credit_base != 0:
        return round((reward / credit_base) * 100.0, 4)

    entry_price = _safe_float(_pick_first(payload, ("entry_price", "avg_entry_price")))
    exit_price = _safe_float(
        _pick_first(payload, ("exit_price", "avg_exit_price", "current_price"))
    )
    if entry_price is not None and exit_price is not None and entry_price != 0:
        return round(((exit_price - entry_price) / entry_price) * 100.0, 4)

    return None


def _compute_holding_minutes(payload: Mapping[str, Any]) -> int | None:
    """Return holding minutes when both entry and exit timestamps are parseable."""
    entry_raw = _pick_first(
        payload,
        ("entry_time", "entry_timestamp", "opened_at", "entry_at", "start_time"),
    )
    exit_raw = _pick_first(
        payload,
        ("exit_time", "exit_timestamp", "closed_at", "exit_at", "end_time"),
    )

    entry_ts = _parse_timestamp(entry_raw)
    exit_ts = _parse_timestamp(exit_raw)
    if entry_ts is None or exit_ts is None:
        return None

    delta_minutes = int((exit_ts - entry_ts).total_seconds() // 60)
    if delta_minutes < 0:
        return None
    return delta_minutes


def build_outcome_label(
    trade: Mapping[str, Any] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    """Build normalized outcome labels from trade/iron-condor style payloads."""
    payload: dict[str, Any] = dict(trade or {})
    payload.update(overrides)

    reward_source = _pick_first(
        payload,
        ("reward", "pnl", "pl", "total_pl", "realized_pl", "unrealized_pl"),
    )
    reward_value = _safe_float(reward_source)
    reward = round(reward_value, 4) if reward_value is not None else 0.0

    return_pct = _compute_return_pct(payload, reward)
    holding_minutes = _compute_holding_minutes(payload)

    explicit_won = payload.get("won")
    explicit_lost = payload.get("lost")

    if explicit_won is not None:
        won = bool(explicit_won)
        lost = not won
    elif explicit_lost is not None:
        lost = bool(explicit_lost)
        won = not lost
    elif reward > 0 or (return_pct is not None and return_pct > 0):
        won, lost = True, False
    elif reward < 0 or (return_pct is not None and return_pct < 0):
        won, lost = False, True
    else:
        won, lost = False, False

    if won:
        outcome = "won"
    elif lost:
        outcome = "lost"
    elif reward_source is None and return_pct is None:
        outcome = "unknown"
    else:
        outcome = "flat"

    summary = {
        "symbol": _pick_first(payload, ("symbol", "underlying", "ticker")),
        "strategy": _pick_first(payload, ("strategy", "strategy_type")),
        "outcome": outcome,
        "reward": reward,
        "return_pct": return_pct,
        "holding_minutes": holding_minutes,
        "exit_reason": _pick_first(payload, ("exit_reason", "reason")),
    }
    compact_summary = {key: value for key, value in summary.items() if value is not None}

    return {
        "reward": reward,
        "return_pct": return_pct,
        "won": won,
        "lost": lost,
        "holding_minutes": holding_minutes,
        "outcome": outcome,
        "summary": compact_summary,
    }
