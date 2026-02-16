"""Tests for scripts/generate_dashboard_snapshot.py."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from scripts.generate_dashboard_snapshot import generate_snapshot_report


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_generate_snapshot_contains_answer_block_and_evidence(tmp_path: Path) -> None:
    state_path = tmp_path / "data" / "system_state.json"
    dashboard_path = tmp_path / "wiki" / "Progress-Dashboard.md"
    out_dir = tmp_path / "docs" / "_reports"

    _write_json(
        state_path,
        {
            "live_account": {
                "equity": 20.0,
                "total_pl": 0.0,
                "total_pl_pct": 0.0,
                "synced_at": "2026-02-16T17:00:00Z",
            },
            "paper_account": {
                "equity": 101500.0,
                "total_pl": 1500.0,
                "total_pl_pct": 1.5,
                "daily_change": 25.0,
                "win_rate": 82.0,
                "win_rate_sample_size": 31,
                "positions_count": 3,
            },
            "north_star": {
                "probability_score": 41.5,
                "probability_label": "watch",
                "target_date": "2029-11-14",
            },
            "risk": {
                "weekly_cadence_kpi_passed": True,
                "weekly_gate_mode": "normal",
                "weekly_gate_recommended_max_position_pct": 5.0,
            },
        },
    )
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard_path.write_text("# Dashboard", encoding="utf-8")

    out_path, changed = generate_snapshot_report(
        state_path=state_path,
        dashboard_path=dashboard_path,
        out_dir=out_dir,
        snapshot_date=date(2026, 2, 16),
    )

    assert changed is True
    assert out_path.name == "2026-02-16-dashboard-snapshot.md"
    text = out_path.read_text(encoding="utf-8")
    assert "## Answer Block" in text
    assert "## Evidence" in text
    assert "github.com/IgorGanapolsky/trading/blob/main/data/system_state.json" in text


def test_generate_snapshot_is_idempotent(tmp_path: Path) -> None:
    state_path = tmp_path / "data" / "system_state.json"
    dashboard_path = tmp_path / "wiki" / "Progress-Dashboard.md"
    out_dir = tmp_path / "docs" / "_reports"

    _write_json(state_path, {})
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard_path.write_text("# Dashboard", encoding="utf-8")

    _, changed_first = generate_snapshot_report(
        state_path=state_path,
        dashboard_path=dashboard_path,
        out_dir=out_dir,
        snapshot_date=date(2026, 2, 16),
    )
    _, changed_second = generate_snapshot_report(
        state_path=state_path,
        dashboard_path=dashboard_path,
        out_dir=out_dir,
        snapshot_date=date(2026, 2, 16),
    )

    assert changed_first is True
    assert changed_second is False
