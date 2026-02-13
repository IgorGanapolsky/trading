#!/usr/bin/env python3
"""
Auto-refresh docs/index.md from data/system_state.json using explicit markers.

This prevents stale snapshots from persisting on GitHub Pages.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SYSTEM_STATE_PATH = Path("data/system_state.json")
DOCS_INDEX_PATH = Path("docs/index.md")
STATUS_START = "<!-- AUTO_STATUS_START -->"
STATUS_END = "<!-- AUTO_STATUS_END -->"


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


def _load_state() -> dict[str, Any]:
    if not SYSTEM_STATE_PATH.exists():
        return {}
    try:
        with SYSTEM_STATE_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _pick_latest_timestamp(*candidates: Any) -> datetime | None:
    parsed = [dt for dt in (_parse_iso(v) for v in candidates) if dt is not None]
    if not parsed:
        return None
    return max(parsed)


def _calculate_day(state: dict[str, Any]) -> tuple[int, int]:
    paper = state.get("paper_trading", {}) if isinstance(state, dict) else {}
    target_days = _as_int(paper.get("target_duration_days"), 90)

    explicit_day = _as_int(paper.get("current_day"), 0)
    if explicit_day > 0:
        return explicit_day, target_days

    start = _parse_iso(paper.get("start_date"))
    if start is None:
        return 0, target_days

    now = datetime.now(timezone.utc)
    return max(0, (now.date() - start.date()).days), target_days


def _position_summary(state: dict[str, Any]) -> tuple[int, int]:
    positions = state.get("positions", []) if isinstance(state, dict) else []
    if not isinstance(positions, list):
        positions = []
    legs = len(positions)
    structures = 1 if legs >= 4 else legs
    return structures, legs


def _north_star_gate(win_rate: float, target_win_rate: float, sample_size: int, day: int, target_days: int) -> tuple[str, str]:
    if sample_size >= 30 and day >= target_days and win_rate >= target_win_rate:
        return "PASS", "ON_TRACK_TO_SCALE"
    if sample_size >= 30 and win_rate < target_win_rate:
        return "ACTIVE", "OFF_TRACK_WIN_RATE"
    return "ACTIVE", "VALIDATING"


def _format_money(amount: float) -> str:
    sign = "+" if amount >= 0 else "-"
    return f"{sign}${abs(amount):,.2f}"


def build_status_block(state: dict[str, Any]) -> str:
    portfolio = state.get("portfolio", {}) if isinstance(state, dict) else {}
    paper = state.get("paper_account", {}) if isinstance(state, dict) else {}
    paper_trading = state.get("paper_trading", {}) if isinstance(state, dict) else {}
    risk = state.get("risk", {}) if isinstance(state, dict) else {}
    meta = state.get("meta", {}) if isinstance(state, dict) else {}
    sync_health = state.get("sync_health", {}) if isinstance(state, dict) else {}

    equity = _as_float(portfolio.get("equity"), _as_float(paper.get("equity"), 0.0))
    daily_pl = _as_float(paper.get("daily_change"), 0.0)
    win_rate = _as_float(paper.get("win_rate"), 0.0)
    sample_size = _as_int(paper.get("win_rate_sample_size"), 0)
    target_win_rate = _as_float(paper_trading.get("target_win_rate"), 0.8)
    if target_win_rate <= 1.0:
        target_win_rate *= 100

    day, target_days = _calculate_day(state)
    structures, legs = _position_summary(state)
    unrealized = _as_float(risk.get("unrealized_pl"), 0.0)

    gate, status = _north_star_gate(win_rate, target_win_rate, sample_size, day, target_days)

    latest_sync = _pick_latest_timestamp(
        meta.get("last_updated"),
        meta.get("last_sync"),
        sync_health.get("last_successful_sync"),
    )
    if latest_sync:
        sync_text = latest_sync.strftime("%Y-%m-%d %H:%M UTC")
    else:
        sync_text = "unknown"

    focus = (
        "Do not scale risk until validation passes."
        if gate == "ACTIVE"
        else "Maintain discipline while scaling in fixed increments."
    )

    return "\n".join(
        [
            STATUS_START,
            f"_Last Sync: {sync_text} (source: `data/system_state.json`)_",
            "",
            "| What | Status |",
            "| ---- | ------ |",
            f"| Account Equity | ${equity:,.2f} |",
            f"| Daily P/L | {_format_money(daily_pl)} |",
            f"| Win Rate | {win_rate:.1f}% ({sample_size} trades; target {target_win_rate:.1f}%) |",
            f"| Paper Phase | Day {day}/{target_days} |",
            f"| North Star Gate | {gate} ({status}) |",
            f"| Open Positions | {structures} structure(s), {legs} option leg(s) |",
            f"| Unrealized P/L | {_format_money(unrealized)} |",
            "",
            f"**Execution Focus:** {focus}",
            STATUS_END,
        ]
    )


def replace_marked_block(content: str, new_block: str) -> str:
    start = content.find(STATUS_START)
    end = content.find(STATUS_END)
    if start != -1 and end != -1 and end > start:
        end += len(STATUS_END)
        return content[:start] + new_block + content[end:]
    return content


def update_docs_index() -> bool:
    if not DOCS_INDEX_PATH.exists():
        raise FileNotFoundError(f"{DOCS_INDEX_PATH} not found")

    state = _load_state()
    original = DOCS_INDEX_PATH.read_text(encoding="utf-8")
    new_block = build_status_block(state)
    updated = replace_marked_block(original, new_block)

    if updated == original:
        print("No marker block found or no changes made to docs/index.md")
        return False

    DOCS_INDEX_PATH.write_text(updated, encoding="utf-8")
    print("Updated docs/index.md auto status block")
    return True


if __name__ == "__main__":
    update_docs_index()
