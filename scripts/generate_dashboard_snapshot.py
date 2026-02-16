#!/usr/bin/env python3
"""
Generate a crawlable daily dashboard snapshot report in docs/_reports.

Why this exists:
- AI crawlers and search engines index static markdown reliably.
- The live dashboard is useful for humans, but this report gives a stable
  canonical text artifact for discoverability and citation.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

# Allow `python scripts/...` execution where sys.path[0] == scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.content.blog_seo import canonical_url_for_collection_item, render_frontmatter

REPO_URL = "https://github.com/IgorGanapolsky/trading"
SITE_URL = "https://igorganapolsky.github.io/trading"


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _fmt_currency(value: float | int | None) -> str:
    if value is None:
        return "N/A"
    return f"${value:,.2f}"


def _fmt_pct(value: float | int | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2f}%"


def _safe_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _write_if_changed(path: Path, content: str) -> bool:
    existing = path.read_text(encoding="utf-8") if path.exists() else None
    if existing == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def _build_report_content(state: dict, snapshot_date: date) -> str:
    live = state.get("live_account", {}) if isinstance(state.get("live_account"), dict) else {}
    paper = state.get("paper_account", {}) if isinstance(state.get("paper_account"), dict) else {}
    north_star = state.get("north_star", {}) if isinstance(state.get("north_star"), dict) else {}
    risk = state.get("risk", {}) if isinstance(state.get("risk"), dict) else {}

    live_equity = _safe_float(live.get("current_equity")) or _safe_float(live.get("equity"))
    live_total_pl = _safe_float(live.get("total_pl"))
    live_total_pl_pct = _safe_float(live.get("total_pl_pct"))
    live_synced_at = live.get("synced_at") if isinstance(live.get("synced_at"), str) else "unknown"

    paper_equity = _safe_float(paper.get("current_equity")) or _safe_float(paper.get("equity"))
    paper_total_pl = _safe_float(paper.get("total_pl"))
    paper_total_pl_pct = _safe_float(paper.get("total_pl_pct"))
    paper_daily_change = _safe_float(paper.get("daily_change"))
    paper_win_rate = _safe_float(paper.get("win_rate"))
    paper_win_rate_sample = paper.get("win_rate_sample_size")
    paper_positions = paper.get("positions_count")

    probability_score = _safe_float(north_star.get("probability_score"))
    probability_label = (
        north_star.get("probability_label")
        if isinstance(north_star.get("probability_label"), str)
        else "unknown"
    )
    target_date = (
        north_star.get("target_date") if isinstance(north_star.get("target_date"), str) else ""
    )

    cadence_passed = risk.get("weekly_cadence_kpi_passed")
    cadence_text = (
        "PASS"
        if cadence_passed is True
        else "FAIL"
        if cadence_passed is False
        else "unknown (insufficient data)"
    )
    gate_mode = (
        risk.get("weekly_gate_mode") if isinstance(risk.get("weekly_gate_mode"), str) else "normal"
    )
    recommended_max_pos = _safe_float(risk.get("weekly_gate_recommended_max_position_pct"))

    snapshot_day = snapshot_date.isoformat()
    report_slug = f"{snapshot_day}-dashboard-snapshot"
    canonical = canonical_url_for_collection_item("reports", report_slug)

    summary = (
        f"Daily snapshot for {snapshot_day}: paper equity {_fmt_currency(paper_equity)}, "
        f"paper daily P/L {_fmt_currency(paper_daily_change)}, cadence gate {cadence_text}."
    )

    questions = [
        {
            "question": "What is the current state of the trading system today?",
            "answer": summary,
        },
        {
            "question": "Are cadence and risk gates passing this week?",
            "answer": (
                f"Cadence gate is {cadence_text}. Risk mode is {gate_mode}"
                + (
                    f" with recommended max position size {recommended_max_pos:.1f}%."
                    if recommended_max_pos is not None
                    else "."
                )
            ),
        },
        {
            "question": "What is the North Star probability right now?",
            "answer": (
                f"North Star probability is {_fmt_pct(probability_score)} ({probability_label})"
                + (f", target date {target_date}." if target_date else ".")
            ),
        },
    ]

    frontmatter = render_frontmatter(
        {
            "layout": "post",
            "title": f"Daily Dashboard Snapshot - {snapshot_day}",
            "description": summary,
            "date": snapshot_day,
            "last_modified_at": snapshot_day,
            "tags": ["dashboard", "north-star", "ai-discoverability", "ops"],
            "image": "/assets/og-image.png",
            "canonical_url": canonical,
        },
        questions=questions,
    )

    body = f"""# Daily Dashboard Snapshot | {snapshot_day}

This report is auto-generated from system state for search and AI discoverability.

## Answer Block

**Q: Did we make money today?**<br>
A: Paper daily P/L is {_fmt_currency(paper_daily_change)}. Live account total P/L is {_fmt_currency(live_total_pl)}.

**Q: Are we on track toward the North Star?**<br>
A: North Star probability is {_fmt_pct(probability_score)} ({probability_label}){f", target date {target_date}" if target_date else ""}.

**Q: Is execution cadence healthy?**<br>
A: Weekly cadence KPI is **{cadence_text}** with risk mode **{gate_mode}**.

## KPI Snapshot

| Metric | Value |
|---|---|
| Live Equity | {_fmt_currency(live_equity)} |
| Live Total P/L | {_fmt_currency(live_total_pl)} ({_fmt_pct(live_total_pl_pct)}) |
| Paper Equity | {_fmt_currency(paper_equity)} |
| Paper Total P/L | {_fmt_currency(paper_total_pl)} ({_fmt_pct(paper_total_pl_pct)}) |
| Paper Daily Change | {_fmt_currency(paper_daily_change)} |
| Paper Win Rate | {_fmt_pct(paper_win_rate)} (sample: {paper_win_rate_sample if paper_win_rate_sample is not None else "N/A"}) |
| Open Positions (Paper) | {paper_positions if paper_positions is not None else "N/A"} |
| Weekly Cadence KPI | {cadence_text} |
| Weekly Risk Mode | {gate_mode} |
| Recommended Max Position Size | {_fmt_pct(recommended_max_pos)} |
| North Star Probability | {_fmt_pct(probability_score)} ({probability_label}) |

## Evidence

- [System state source]({REPO_URL}/blob/main/data/system_state.json)
- [Dashboard source markdown]({REPO_URL}/blob/main/wiki/Progress-Dashboard.md)
- [Cadence gate checker]({REPO_URL}/blob/main/scripts/check_weekly_cadence_gate.py)
- [North Star operating plan updater]({REPO_URL}/blob/main/scripts/update_north_star_operating_plan.py)
- [Live site dashboard]({SITE_URL}/)

## Data Freshness

- Snapshot date: `{snapshot_day}`
- Live account sync timestamp: `{live_synced_at}`
"""
    return frontmatter + body


def generate_snapshot_report(
    state_path: Path,
    dashboard_path: Path,
    out_dir: Path,
    snapshot_date: date,
) -> tuple[Path, bool]:
    state = _load_json(state_path)
    _ = dashboard_path  # kept for future validation; markdown evidence links point to this file.
    report_name = f"{snapshot_date.isoformat()}-dashboard-snapshot.md"
    out_path = out_dir / report_name
    content = _build_report_content(state, snapshot_date)
    changed = _write_if_changed(out_path, content)
    return out_path, changed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate daily dashboard snapshot markdown report"
    )
    parser.add_argument("--state", default="data/system_state.json")
    parser.add_argument("--dashboard", default="wiki/Progress-Dashboard.md")
    parser.add_argument("--out-dir", default="docs/_reports")
    parser.add_argument("--date", help="Snapshot date in YYYY-MM-DD (default: today)")
    args = parser.parse_args()

    if args.date:
        snapshot_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        snapshot_date = date.today()

    out_path, changed = generate_snapshot_report(
        state_path=Path(args.state),
        dashboard_path=Path(args.dashboard),
        out_dir=Path(args.out_dir),
        snapshot_date=snapshot_date,
    )

    status = "updated" if changed else "up-to-date"
    print(f"Dashboard snapshot {status}: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
