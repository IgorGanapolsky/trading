"""Milestone controller for strategy-family gating and North Star probability.

This module enforces a simple policy:
- Auto-pause strategy families when rolling win-rate/expectancy are below thresholds.
- Keep only the primary family in validation mode when samples are insufficient.
- Publish a daily North Star probability score from current edge + capital trajectory.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from src.core.trading_constants import (
        NORTH_STAR_MONTHLY_AFTER_TAX,
        NORTH_STAR_TARGET_CAPITAL,
        NORTH_STAR_TARGET_WIN_RATE_PCT,
    )
except Exception:
    NORTH_STAR_MONTHLY_AFTER_TAX = 6_000.0
    NORTH_STAR_TARGET_CAPITAL = 300_000.0
    NORTH_STAR_TARGET_WIN_RATE_PCT = 80.0

DEFAULT_STATE_PATH = Path("data/system_state.json")
DEFAULT_TRADES_PATH = Path("data/trades.json")
DEFAULT_TARGET_MODE = "asap_monthly_income"
DEFAULT_MONTHLY_AFTER_TAX_TARGET = NORTH_STAR_MONTHLY_AFTER_TAX
DEFAULT_TARGET_CAPITAL = NORTH_STAR_TARGET_CAPITAL
DEFAULT_TARGET_WIN_RATE_PCT = NORTH_STAR_TARGET_WIN_RATE_PCT
DEFAULT_ROLLING_WINDOW = int(os.getenv("MILESTONE_ROLLING_WINDOW", "50"))
DEFAULT_PRIMARY_FAMILY = os.getenv("PRIMARY_STRATEGY_FAMILY", "options_income")

KNOWN_FAMILIES = ("options_income", "equity_momentum", "alternatives", "other")
FAMILY_THRESHOLDS: dict[str, dict[str, float | int]] = {
    # Keep options income in validation mode until there is a real paired-trade sample.
    # Paper-account summaries and raw fills are too noisy to certify edge.
    "options_income": {"min_win_rate_pct": 60.0, "min_expectancy": 0.0, "min_samples": 12},
    "equity_momentum": {"min_win_rate_pct": 55.0, "min_expectancy": 0.0, "min_samples": 12},
    "alternatives": {"min_win_rate_pct": 55.0, "min_expectancy": 0.0, "min_samples": 12},
    "other": {"min_win_rate_pct": 55.0, "min_expectancy": 0.0, "min_samples": 12},
}


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


def _as_bool(value: Any, default: bool | None = None) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on", "passed", "pass"}:
            return True
        if normalized in {"false", "0", "no", "n", "off", "failed", "fail"}:
            return False
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _load_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def resolve_strategy_family(strategy: str) -> str:
    """Map a strategy label to a coarse family for gating."""
    text = (strategy or "").strip().lower()
    if not text:
        return "other"

    options_tokens = (
        "iron_condor",
        "credit_spread",
        "put_spread",
        "call_spread",
        "vertical_spread",
        "csp",
        "covered_call",
        "option",
    )
    momentum_tokens = ("momentum", "trend", "swing", "dca", "core_strategy")
    alt_tokens = ("reit", "metals", "precious", "income")

    if any(token in text for token in options_tokens):
        return "options_income"
    if any(token in text for token in momentum_tokens):
        return "equity_momentum"
    if any(token in text for token in alt_tokens):
        return "alternatives"
    return "other"


def _extract_closed_trades(
    trades_data: dict[str, Any], rolling_window: int
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    trades = trades_data.get("trades", [])
    if not isinstance(trades, list):
        return rows

    for raw in trades:
        if not isinstance(raw, dict):
            continue
        status = str(raw.get("status", "")).lower()
        if status != "closed":
            continue

        strategy = str(raw.get("strategy") or raw.get("strategy_name") or "")
        symbol = str(raw.get("symbol") or "")
        family = resolve_strategy_family(strategy or symbol)
        pnl = _as_float(raw.get("realized_pnl", raw.get("pnl", raw.get("pl", 0.0))), 0.0)

        outcome = str(raw.get("outcome", "")).lower()
        if outcome not in {"win", "loss", "breakeven"}:
            if pnl > 0:
                outcome = "win"
            elif pnl < 0:
                outcome = "loss"
            else:
                outcome = "breakeven"

        closed_at = str(
            raw.get("exit_date")
            or raw.get("exit_time")
            or raw.get("closed_at")
            or raw.get("timestamp")
            or ""
        )
        rows.append(
            {
                "family": family,
                "strategy": strategy,
                "symbol": symbol,
                "pnl": pnl,
                "outcome": outcome,
                "closed_at": closed_at,
            }
        )

    rows.sort(key=lambda item: item.get("closed_at", ""))
    if rolling_window > 0:
        rows = rows[-rolling_window:]
    return rows


def _parse_closed_at(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
            return datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _metrics_for_family(
    family: str,
    closed_trades: list[dict[str, Any]],
    state: dict[str, Any],
) -> dict[str, Any]:
    family_rows = [row for row in closed_trades if row.get("family") == family]
    samples = len(family_rows)
    wins = sum(1 for row in family_rows if row.get("outcome") == "win")
    losses = sum(1 for row in family_rows if row.get("outcome") == "loss")
    total_pnl = sum(_as_float(row.get("pnl"), 0.0) for row in family_rows)

    closed_times = [_parse_closed_at(row.get("closed_at")) for row in family_rows]
    closed_times = [value for value in closed_times if value is not None]
    window_days = 0.0
    if closed_times:
        earliest = min(closed_times)
        latest = max(closed_times)
        # Include both boundary days to avoid dividing by 0 on same-day closures.
        window_days = max(1.0, ((latest - earliest).total_seconds() / 86400.0) + 1.0)

    metrics: dict[str, Any] = {
        "samples": samples,
        "wins": wins,
        "losses": losses,
        "total_pnl": round(total_pnl, 2),
        "win_rate_pct": round((wins / samples) * 100.0, 2) if samples > 0 else None,
        "expectancy": round(total_pnl / samples, 4) if samples > 0 else None,
        "window_days": round(window_days, 2) if samples > 0 else None,
        "evidence_source": "trades.json" if samples > 0 else "none",
    }

    return metrics


def _thresholds_for_family(family: str) -> dict[str, float | int]:
    base = FAMILY_THRESHOLDS.get(family, FAMILY_THRESHOLDS["other"]).copy()
    return {
        "min_win_rate_pct": _as_float(base.get("min_win_rate_pct"), 55.0),
        "min_expectancy": _as_float(base.get("min_expectancy"), 0.0),
        "min_samples": _as_int(base.get("min_samples"), 12),
    }


def _evaluate_family_status(family: str, metrics: dict[str, Any]) -> dict[str, Any]:
    thresholds = _thresholds_for_family(family)
    samples = _as_int(metrics.get("samples"), 0)
    win_rate = metrics.get("win_rate_pct")
    expectancy = metrics.get("expectancy")
    min_samples = _as_int(thresholds.get("min_samples"), 12)
    min_win_rate = _as_float(thresholds.get("min_win_rate_pct"), 55.0)
    min_expectancy = _as_float(thresholds.get("min_expectancy"), 0.0)

    if samples < min_samples:
        paused = family != DEFAULT_PRIMARY_FAMILY
        status = "paused" if paused else "validation"
        reason = (
            f"{family} paused until {min_samples} closed trades (have {samples})."
            if paused
            else f"{family} validation mode ({samples}/{min_samples} closed trades)."
        )
        return {"status": status, "paused": paused, "reason": reason, "thresholds": thresholds}

    if win_rate is None or _as_float(win_rate) < min_win_rate:
        value = "N/A" if win_rate is None else f"{_as_float(win_rate):.1f}%"
        reason = f"{family} paused: win rate {value} below {min_win_rate:.1f}% threshold."
        return {"status": "paused", "paused": True, "reason": reason, "thresholds": thresholds}

    if expectancy is None:
        reason = f"{family} paused: expectancy unavailable with {samples} closed trades."
        return {"status": "paused", "paused": True, "reason": reason, "thresholds": thresholds}

    expectancy_val = _as_float(expectancy, 0.0)
    if expectancy_val <= min_expectancy:
        reason = (
            f"{family} paused: expectancy ${expectancy_val:.2f}/trade "
            f"<= ${min_expectancy:.2f} threshold."
        )
        return {"status": "paused", "paused": True, "reason": reason, "thresholds": thresholds}

    return {
        "status": "active",
        "paused": False,
        "reason": (
            f"{family} active: rolling win rate {float(win_rate):.1f}% and "
            f"expectancy ${expectancy_val:.2f}/trade meet thresholds."
        ),
        "thresholds": thresholds,
    }


def _estimate_annual_edge_from_expectancy(
    expectancy: float | None,
    samples: int,
    paper_day: int,
    equity: float,
    window_days: float | None = None,
) -> float:
    if expectancy is None or samples <= 0 or paper_day <= 0 or equity <= 0:
        return 0.0
    if window_days and window_days > 0:
        # Use rolling-window cadence with a 7-day floor to avoid one-trade overreaction.
        trades_per_day = samples / max(7.0, float(window_days))
    else:
        trades_per_day = samples / max(1, paper_day)
    expected_daily_pnl = float(expectancy) * trades_per_day
    return (expected_daily_pnl * 252.0) / equity


def _estimate_monthly_after_tax_from_expectancy(
    expectancy: float | None,
    samples: int,
    paper_day: int,
    window_days: float | None = None,
) -> float:
    if expectancy is None or samples <= 0 or paper_day <= 0:
        return 0.0
    if window_days and window_days > 0:
        trades_per_day = samples / max(7.0, float(window_days))
    else:
        trades_per_day = samples / max(1, paper_day)
    expected_daily_pnl = float(expectancy) * trades_per_day
    return max(0.0, expected_daily_pnl * 21.0)


def _north_star_probability(
    state: dict[str, Any],
    primary_metrics: dict[str, Any],
    primary_status: dict[str, Any],
) -> dict[str, Any]:
    paper = state.get("paper_account", {}) if isinstance(state, dict) else {}
    portfolio = state.get("portfolio", {}) if isinstance(state, dict) else {}
    paper_trading = state.get("paper_trading", {}) if isinstance(state, dict) else {}

    equity = _as_float(paper.get("equity"), 0.0)
    if equity <= 0:
        equity = _as_float(portfolio.get("equity"), 0.0)

    paper_day = _as_int(paper_trading.get("current_day"), 0)
    win_rate = primary_metrics.get("win_rate_pct")
    expectancy = primary_metrics.get("expectancy")
    samples = _as_int(primary_metrics.get("samples"), 0)
    window_days = _as_float(primary_metrics.get("window_days"), 0.0)
    weekly_gate = state.get("north_star_weekly_gate", {}) if isinstance(state, dict) else {}
    cadence_kpi = weekly_gate.get("cadence_kpi") if isinstance(weekly_gate, dict) else {}
    if not isinstance(cadence_kpi, dict):
        cadence_kpi = {}
    cadence_passed = (
        _as_bool(cadence_kpi.get("passed"), default=False)
        if isinstance(cadence_kpi, dict)
        else False
    )
    cadence_setups = (
        _as_int(cadence_kpi.get("qualified_setups_observed"), 0)
        if isinstance(cadence_kpi, dict)
        else 0
    )

    estimated_cagr = _estimate_annual_edge_from_expectancy(
        expectancy, samples, paper_day, equity, window_days=window_days
    )
    estimated_monthly_after_tax = _estimate_monthly_after_tax_from_expectancy(
        expectancy, samples, paper_day, window_days=window_days
    )
    monthly_progress_ratio = (
        estimated_monthly_after_tax / DEFAULT_MONTHLY_AFTER_TAX_TARGET
        if DEFAULT_MONTHLY_AFTER_TAX_TARGET > 0
        else 0.0
    )
    trajectory_score = max(0.0, min(100.0, monthly_progress_ratio * 100.0))

    if win_rate is None:
        win_score = 25.0
    else:
        win_score = max(
            0.0, min(100.0, (_as_float(win_rate) / DEFAULT_TARGET_WIN_RATE_PCT) * 100.0)
        )

    expectancy_val = _as_float(expectancy, 0.0) if expectancy is not None else None
    if expectancy_val is None:
        edge_score = 20.0
    elif expectancy_val <= 0:
        edge_score = 0.0
    else:
        edge_score = max(0.0, min(100.0, (expectancy_val / 50.0) * 100.0))

    min_setups = _as_int(cadence_kpi.get("min_qualified_setups_per_week"), 0)
    min_closes = _as_int(cadence_kpi.get("min_closed_trades_per_week"), 0)
    close_obs = _as_int(cadence_kpi.get("closed_trades_observed"), 0)
    setup_ratio = cadence_setups / max(1, min_setups) if min_setups > 0 else 0.0
    close_ratio = close_obs / max(1, min_closes) if min_closes > 0 else 0.0
    cadence_progress = min(1.0, 0.5 * min(1.0, setup_ratio) + 0.5 * min(1.0, close_ratio))
    if cadence_passed:
        cadence_score = 100.0
    else:
        cadence_score = 15.0 + (cadence_progress * 70.0)

    score = round(
        (0.4 * trajectory_score) + (0.25 * win_score) + (0.2 * edge_score) + (0.15 * cadence_score),
        1,
    )

    # Hard cap probability when primary strategy family is explicitly paused.
    if primary_status.get("paused"):
        score = min(score, 35.0)

    if score >= 75:
        label = "high"
    elif score >= 55:
        label = "medium"
    elif score >= 35:
        label = "low"
    else:
        label = "critical"

    return {
        "score": score,
        "label": label,
        "target_mode": DEFAULT_TARGET_MODE,
        "monthly_after_tax_target": round(DEFAULT_MONTHLY_AFTER_TAX_TARGET, 2),
        "estimated_monthly_after_tax_from_expectancy": round(estimated_monthly_after_tax, 2),
        "monthly_target_progress_pct": round(max(0.0, monthly_progress_ratio * 100.0), 2),
        "required_cagr": None,
        "estimated_cagr_from_expectancy": round(estimated_cagr, 4),
        "win_rate_pct": round(_as_float(win_rate, 0.0), 2) if win_rate is not None else None,
        "expectancy_per_trade": round(_as_float(expectancy, 0.0), 4)
        if expectancy is not None
        else None,
        "samples": samples,
        "target_capital": DEFAULT_TARGET_CAPITAL,
        "target_date": None,
    }


def compute_milestone_snapshot(
    state: dict[str, Any] | None = None,
    *,
    state_path: Path = DEFAULT_STATE_PATH,
    trades_path: Path = DEFAULT_TRADES_PATH,
) -> dict[str, Any]:
    """Compute full milestone status and North Star probability snapshot."""
    loaded_state = state if isinstance(state, dict) else _load_json_dict(state_path)
    trades_data = _load_json_dict(trades_path)
    closed = _extract_closed_trades(trades_data, rolling_window=DEFAULT_ROLLING_WINDOW)

    families: dict[str, Any] = {}
    paused: list[str] = []

    for family in KNOWN_FAMILIES:
        metrics = _metrics_for_family(family, closed, loaded_state)
        status = _evaluate_family_status(family, metrics)
        family_state = {
            "status": status["status"],
            "paused": status["paused"],
            "reason": status["reason"],
            "thresholds": status["thresholds"],
            "metrics": metrics,
        }
        families[family] = family_state
        if family_state["paused"]:
            paused.append(family)

    primary = (
        DEFAULT_PRIMARY_FAMILY if DEFAULT_PRIMARY_FAMILY in KNOWN_FAMILIES else "options_income"
    )
    primary_state = families.get(primary, families["options_income"])
    north_star = _north_star_probability(
        loaded_state,
        primary_state.get("metrics", {}),
        primary_state,
    )

    return {
        "enabled": True,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "primary_family": primary,
        "rolling_window": DEFAULT_ROLLING_WINDOW,
        "strategy_families": families,
        "paused_families": paused,
        "north_star_probability": north_star,
    }


def get_milestone_context(
    strategy: str,
    *,
    state_path: Path = DEFAULT_STATE_PATH,
    trades_path: Path = DEFAULT_TRADES_PATH,
) -> dict[str, Any]:
    """Return gate-ready context for a specific strategy."""
    snapshot = compute_milestone_snapshot(state_path=state_path, trades_path=trades_path)
    family = resolve_strategy_family(strategy)
    family_state = snapshot.get("strategy_families", {}).get(family, {})
    paused = bool(_as_bool(family_state.get("paused"), default=False))

    block_reason = ""
    if paused:
        reason = str(family_state.get("reason") or "").strip()
        block_reason = (
            f"Milestone controller blocked '{family}' family: {reason}"
            if reason
            else f"Milestone controller blocked '{family}' family."
        )

    return {
        "enabled": True,
        "strategy_family": family,
        "family_status": family_state.get("status", "unknown"),
        "pause_buy_for_family": paused,
        "paused_families": snapshot.get("paused_families", []),
        "family_metrics": family_state.get("metrics", {}),
        "family_thresholds": family_state.get("thresholds", {}),
        "block_reason": block_reason,
        "north_star_probability_score": snapshot.get("north_star_probability", {}).get("score"),
    }


def apply_snapshot_to_state(state: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    """Write milestone snapshot fields into mutable system_state payload."""
    state["strategy_milestones"] = {
        "enabled": snapshot.get("enabled", True),
        "generated_at": snapshot.get("generated_at"),
        "primary_family": snapshot.get("primary_family"),
        "rolling_window": snapshot.get("rolling_window"),
        "paused_families": snapshot.get("paused_families", []),
        "strategy_families": snapshot.get("strategy_families", {}),
    }

    north_star = state.setdefault("north_star", {})
    probability = snapshot.get("north_star_probability", {})
    north_star["probability_score"] = probability.get("score")
    north_star["probability_label"] = probability.get("label")
    north_star["target_mode"] = probability.get("target_mode")
    north_star["monthly_after_tax_target"] = probability.get("monthly_after_tax_target")
    north_star["estimated_monthly_after_tax_from_expectancy"] = probability.get(
        "estimated_monthly_after_tax_from_expectancy"
    )
    north_star["monthly_target_progress_pct"] = probability.get("monthly_target_progress_pct")
    north_star["required_cagr"] = probability.get("required_cagr")
    north_star["estimated_cagr_from_expectancy"] = probability.get("estimated_cagr_from_expectancy")
    north_star["target_capital"] = probability.get("target_capital")
    north_star["target_date"] = probability.get("target_date")
    north_star["updated_at"] = snapshot.get("generated_at")
    return state
