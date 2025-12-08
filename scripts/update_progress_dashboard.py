#!/usr/bin/env python3
"""
Regenerate the dynamic sections of the Progress Dashboard wiki page.

Reads `data/system_state.json` and rewrites the Recent Executions and
Current Positions sections so the wiki always reflects the latest trades,
open positions, and key notes.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


def _load_system_state() -> dict[str, Any]:
    path = Path("data/system_state.json")
    return json.loads(path.read_text())


def _format_currency(value: float) -> str:
    return f"${value:,.2f}"


def _parse_note(note: str) -> tuple[datetime, str]:
    match = re.match(r"\[(?P<ts>[^]]+)\]\s*(?P<text>.+)", note)
    if not match:
        return datetime.now(), note
    ts = datetime.fromisoformat(match.group("ts"))
    return ts, match.group("text")


def _build_execution_rows(notes: list[str], max_rows: int = 5) -> list[str]:
    executions: list[tuple[datetime, str]] = []
    for note in reversed(notes):  # most recent first
        if "trade" in note.lower() or "execution" in note.lower():
            executions.append(_parse_note(note))
        if len(executions) >= max_rows:
            break
    rows = []
    for ts, text in sorted(executions, key=lambda x: x[0], reverse=True):
        rows.append(
            f"| {ts.strftime('%Y-%m-%d %H:%M UTC')} | {text.split(':', 1)[1] if ':' in text else text} | {text} |"
        )
    return rows


def _build_positions_rows(positions: list[dict[str, Any]]) -> list[str]:
    rows = []
    for pos in positions:
        unrealized = pos.get("unrealized_pl", 0.0)
        unrealized_pct = pos.get("unrealized_pl_pct", 0.0)
        rows.append(
            "| "
            + " | ".join(
                [
                    pos.get("symbol", "—"),
                    f"{pos.get('tier', 'unknown').title()}",
                    f"{pos.get('quantity', 0):,.2f}",
                    _format_currency(unrealized),
                    f"{unrealized_pct:+.2f}%",
                    str(pos.get("notes", pos.get("entry_price", ""))),
                ]
            )
            + " |"
        )
    return rows


def _replace_section(text: str, start_marker: str, end_marker: str, new_lines: list[str]) -> str:
    pattern = re.compile(
        rf"({re.escape(start_marker)})(.*?)(?={re.escape(end_marker)})",
        re.DOTALL,
    )
    content = "\n".join(new_lines).strip() or "No data available"
    replacement = f"{start_marker}\n{content}\n"
    return pattern.sub(replacement, text)


def main() -> None:
    state = _load_system_state()
    notes = state.get("notes", [])
    position_rows = _build_positions_rows(state.get("performance", {}).get("open_positions", []))
    execution_rows = _build_execution_rows(notes)

    dashboard_path = Path("wiki/Progress-Dashboard.md")
    text = dashboard_path.read_text()

    text = _replace_section(
        text,
        "<!-- RECENT_EXECUTIONS_START -->",
        "<!-- RECENT_EXECUTIONS_END -->",
        ["| Date (UTC) | Actions | Notes |", "|------------|---------|-------|"] + execution_rows,
    )

    text = _replace_section(
        text,
        "<!-- CURRENT_POSITIONS_START -->",
        "<!-- CURRENT_POSITIONS_END -->",
        [
            "| Symbol | Tier | Quantity | Unrealized | Unrealized % | Notes |",
            "|--------|------|----------|-------------|---------------|-------|",
        ]
        + position_rows,
    )

    dashboard_path.write_text(text)


if __name__ == "__main__":
    import json

    main()
