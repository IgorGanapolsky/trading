"""Tests for local read-only ops snapshot."""

from __future__ import annotations

import json
from pathlib import Path

from src.analytics.local_ops_snapshot import build_local_ops_snapshot, render_local_ops_markdown


def test_build_local_ops_snapshot_reads_expected_sources(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    (data_dir / "rag").mkdir(parents=True)
    (data_dir / "analytics").mkdir(parents=True)
    lessons_dir = tmp_path / "rag_knowledge" / "lessons_learned"
    lessons_dir.mkdir(parents=True)
    (lessons_dir / "ll_1.md").write_text("# lesson", encoding="utf-8")

    (data_dir / "system_state.json").write_text(
        json.dumps(
            {
                "last_updated": "2026-02-21T15:06:54.528387+00:00",
                "paper_account": {
                    "equity": 101357.32,
                    "cash": 101000.00,
                    "daily_change": -8.08,
                },
                "positions": [{"symbol": "SPY"}],
            }
        ),
        encoding="utf-8",
    )
    (data_dir / "verification_reports.json").write_text(
        json.dumps(
            [
                {"date": "2026-02-20", "daily_pnl": -8.08, "orders": 1, "fills": 4},
                {"date": "2026-02-21", "daily_pnl": 2.0, "orders": 0, "fills": 0},
            ]
        ),
        encoding="utf-8",
    )
    (data_dir / "rag" / "lessons_query.json").write_text(
        json.dumps({"rows": []}),
        encoding="utf-8",
    )
    (data_dir / "analytics" / "publication-status-history.jsonl").write_text(
        json.dumps(
            {
                "date": "2026-02-21",
                "generated_at_utc": "2026-02-21T20:00:00Z",
                "platforms": {"devto": {"status": "success"}},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    snapshot = build_local_ops_snapshot(tmp_path)
    assert snapshot["trading"]["equity"] == 101357.32
    assert snapshot["trading"]["positions_count"] == 1
    assert snapshot["verification"]["latest_date"] == "2026-02-21"
    assert snapshot["rag"]["lessons_count"] == 1
    assert snapshot["publishing"]["latest_date"] == "2026-02-21"
    assert snapshot["health_flags"]["verification_missing"] is False


def test_render_local_ops_markdown_contains_sections() -> None:
    markdown = render_local_ops_markdown(
        {
            "generated_at_utc": "2026-02-21T00:00:00Z",
            "trading": {"equity": 1, "cash": 2, "daily_pnl": 3, "positions_count": 4},
            "verification": {"latest_date": "2026-02-21"},
            "rag": {"lessons_count": 5},
            "publishing": {"latest_date": "2026-02-21"},
            "health_flags": {"system_state_stale": False},
        }
    )
    assert "# Local Ops Snapshot" in markdown
    assert "## Trading" in markdown
    assert "## RAG" in markdown
    assert "## Publishing" in markdown
