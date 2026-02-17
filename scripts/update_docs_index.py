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
SNAPSHOT_MANIFEST_PATH = Path("docs/data/alpaca_snapshots.json")
DOCS_INDEX_PATH = Path("docs/index.md")
STATUS_START = "<!-- AUTO_STATUS_START -->"
STATUS_END = "<!-- AUTO_STATUS_END -->"
SNAPSHOT_START = "<!-- AUTO_SNAPSHOT_START -->"
SNAPSHOT_END = "<!-- AUTO_SNAPSHOT_END -->"


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


def _load_snapshot_manifest() -> dict[str, Any]:
    if not SNAPSHOT_MANIFEST_PATH.exists():
        return {}
    try:
        with SNAPSHOT_MANIFEST_PATH.open("r", encoding="utf-8") as f:
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


def _north_star_gate(
    win_rate: float, target_win_rate: float, sample_size: int, day: int, target_days: int
) -> tuple[str, str]:
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


def build_snapshot_block(manifest: dict[str, Any]) -> str:
    latest = manifest.get("latest", {}) if isinstance(manifest, dict) else {}
    if not isinstance(latest, dict):
        latest = {}

    progress = latest.get("progress", {}) if isinstance(latest.get("progress"), dict) else {}
    progress_url = progress.get("url", "/trading/assets/snapshots/progress_latest.png")
    progress_time = progress.get("captured_at_utc", "pending")

    return "\n".join(
        [
            SNAPSHOT_START,
            "Latest snapshot is refreshed by automation and published to GitHub Pages.",
            "",
            "### Progress Dashboard (Most Relevant)",
            "[Open full live dashboard](/trading/)",
            "",
            f"[![Progress Dashboard Snapshot]({progress_url})](/trading/)",
            "",
            f"Captured: `{progress_time}`",
            "",
            "Raw manifest: [`/trading/data/alpaca_snapshots.json`](/trading/data/alpaca_snapshots.json)",
            SNAPSHOT_END,
        ]
    )


def replace_marked_block(content: str, start_marker: str, end_marker: str, new_block: str) -> str:
    start = content.find(start_marker)
    end = content.find(end_marker)
    if start != -1 and end != -1 and end > start:
        end += len(end_marker)
        return content[:start] + new_block + content[end:]
    return content


def update_docs_index() -> bool:
    if not DOCS_INDEX_PATH.exists():
        raise FileNotFoundError(f"{DOCS_INDEX_PATH} not found")

    state = _load_state()
    snapshot_manifest = _load_snapshot_manifest()
    original = DOCS_INDEX_PATH.read_text(encoding="utf-8")
    status_block = build_status_block(state)
    snapshot_block = build_snapshot_block(snapshot_manifest)
    updated = replace_marked_block(original, STATUS_START, STATUS_END, status_block)
    updated = replace_marked_block(updated, SNAPSHOT_START, SNAPSHOT_END, snapshot_block)

    if updated == original:
        print("No marker block found or no changes made to docs/index.md")
        return False

    DOCS_INDEX_PATH.write_text(updated, encoding="utf-8")
    print("Updated docs/index.md auto status block")
    return True


if __name__ == "__main__":
    update_docs_index()
