"""North Star risk guard for trade sizing and risk-on gating.

This module converts live paper metrics in ``data/system_state.json`` into
runtime constraints that the mandatory trade gate can enforce.

Intent:
- Keep validation mode conservative until paper evidence is strong.
- Block new risk when observed performance is materially below target.
- Allow manual override when operator explicitly opts in.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

try:
    from src.core.trading_constants import (
        NORTH_STAR_PAPER_VALIDATION_DAYS,
        NORTH_STAR_TARGET_CAPITAL,
        NORTH_STAR_TARGET_DATE,
        NORTH_STAR_TARGET_WIN_RATE_PCT,
    )
except Exception:
    NORTH_STAR_TARGET_DATE = date(2029, 11, 14)
    NORTH_STAR_TARGET_CAPITAL = 600_000.0
    NORTH_STAR_TARGET_WIN_RATE_PCT = 80.0
    NORTH_STAR_PAPER_VALIDATION_DAYS = 90

DEFAULT_STATE_PATH = Path("data/system_state.json")
DEFAULT_TARGET_DATE = NORTH_STAR_TARGET_DATE
DEFAULT_TARGET_CAPITAL = NORTH_STAR_TARGET_CAPITAL
DEFAULT_TARGET_WIN_RATE = NORTH_STAR_TARGET_WIN_RATE_PCT
DEFAULT_MIN_SAMPLE_SIZE = 30
DEFAULT_PAPER_DAYS = NORTH_STAR_PAPER_VALIDATION_DAYS


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


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


def _load_state(path: Path = DEFAULT_STATE_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        import json

        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _resolve_current_day(paper_trading: dict[str, Any]) -> int:
    explicit = _as_int(paper_trading.get("current_day"), 0)
    if explicit > 0:
        return explicit

    start_raw = paper_trading.get("start_date")
    if not start_raw:
        return 0

    try:
        start = datetime.fromisoformat(str(start_raw)).date()
        return max(0, (date.today() - start).days)
    except Exception:
        return 0


def _required_cagr(current_equity: float, target_capital: float, years_left: float) -> float:
    if current_equity <= 0 or target_capital <= 0 or years_left <= 0:
        return 0.0
    return (target_capital / current_equity) ** (1.0 / years_left) - 1.0


def get_guard_context(state_path: Path = DEFAULT_STATE_PATH) -> dict[str, Any]:
    """Return dynamic risk constraints for mandatory trade validation."""
    state = _load_state(state_path)

    if _truthy(os.getenv("NORTH_STAR_GUARD_OVERRIDE", "")):
        return {
            "enabled": True,
            "mode": "override",
            "max_position_pct": 0.05,
            "block_new_positions": False,
            "block_reason": "",
            "reasons": ["NORTH_STAR_GUARD_OVERRIDE enabled"],
        }

    paper_account = state.get("paper_account", {}) if isinstance(state, dict) else {}
    paper_trading = state.get("paper_trading", {}) if isinstance(state, dict) else {}
    portfolio = state.get("portfolio", {}) if isinstance(state, dict) else {}
    weekly_gate = state.get("north_star_weekly_gate", {}) if isinstance(state, dict) else {}

    equity = _as_float(paper_account.get("equity"), 0.0)
    if equity <= 0:
        equity = _as_float(portfolio.get("equity"), 0.0)

    win_rate = _as_float(paper_account.get("win_rate"), 0.0)
    sample_size = _as_int(paper_account.get("win_rate_sample_size"), 0)
    current_day = _resolve_current_day(paper_trading)
    target_days = _as_int(paper_trading.get("target_duration_days"), DEFAULT_PAPER_DAYS)

    years_left = max(0.0, (DEFAULT_TARGET_DATE - date.today()).days / 365.25)
    req_cagr = _required_cagr(equity, DEFAULT_TARGET_CAPITAL, years_left)

    # Default guard = conservative validation mode.
    mode = "validation"
    max_position_pct = 0.025
    block_new_positions = False
    reasons: list[str] = []

    if sample_size >= DEFAULT_MIN_SAMPLE_SIZE and win_rate < 75.0:
        mode = "capital_preservation"
        max_position_pct = 0.01
        block_new_positions = True
        reasons.append(
            f"Win rate {win_rate:.1f}% across {sample_size} trades is below 75% hard floor."
        )
    elif sample_size >= DEFAULT_MIN_SAMPLE_SIZE and win_rate < DEFAULT_TARGET_WIN_RATE:
        mode = "under_target"
        max_position_pct = 0.02
        reasons.append(
            f"Win rate {win_rate:.1f}% across {sample_size} trades is below {DEFAULT_TARGET_WIN_RATE:.0f}% target."
        )
    elif current_day < target_days or sample_size < DEFAULT_MIN_SAMPLE_SIZE:
        mode = "validation"
        max_position_pct = 0.025
        reasons.append(
            f"Paper validation incomplete (day {current_day}/{target_days}, samples {sample_size}/{DEFAULT_MIN_SAMPLE_SIZE})."
        )
    else:
        mode = "scale_ready"
        max_position_pct = 0.05
        reasons.append("Paper validation passed (days + sample size + win-rate threshold).")

    # If target requires extreme CAGR, stay conservative even when not blocked.
    if req_cagr > 0.35 and not block_new_positions:
        max_position_pct = min(max_position_pct, 0.02)
        reasons.append(
            f"Required CAGR to target is {req_cagr * 100:.1f}%/yr; keeping risk-on size conservative."
        )

    # Weekly operating gate can further cap risk-on size or pause new entries.
    if isinstance(weekly_gate, dict):
        weekly_mode = str(weekly_gate.get("mode", "unknown"))
        weekly_limit = _as_float(weekly_gate.get("recommended_max_position_pct"), 0.0)
        if weekly_limit > 0:
            max_position_pct = min(max_position_pct, weekly_limit)
            reasons.append(
                f"Weekly gate ({weekly_mode}) caps max position size at {weekly_limit * 100:.1f}%."
            )

        if weekly_gate.get("block_new_positions"):
            block_new_positions = True
            weekly_reason = str(weekly_gate.get("reason") or "").strip()
            if weekly_reason:
                reasons.append(f"Weekly gate block: {weekly_reason}")

    block_reason = ""
    if block_new_positions:
        if isinstance(weekly_gate, dict) and weekly_gate.get("block_new_positions"):
            block_reason = (
                "North Star guard: weekly operating gate blocked new position openings "
                f"({weekly_gate.get('mode', 'unknown')})."
            )
        else:
            block_reason = (
                "North Star guard: new position openings blocked in capital preservation mode "
                f"(win_rate={win_rate:.1f}%, sample_size={sample_size})."
            )

    return {
        "enabled": True,
        "mode": mode,
        "max_position_pct": round(max_position_pct, 4),
        "block_new_positions": block_new_positions,
        "block_reason": block_reason,
        "win_rate": win_rate,
        "sample_size": sample_size,
        "paper_day": current_day,
        "paper_target_days": target_days,
        "equity": equity,
        "required_cagr_to_target_capital": round(req_cagr, 4),
        "target_capital": DEFAULT_TARGET_CAPITAL,
        "target_date": DEFAULT_TARGET_DATE.isoformat(),
        "weekly_gate_mode": weekly_gate.get("mode")
        if isinstance(weekly_gate, dict)
        else "unavailable",
        "reasons": reasons,
    }
