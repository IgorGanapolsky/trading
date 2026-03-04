from __future__ import annotations

from datetime import datetime, timezone

from scripts.build_north_star_blocker_report import compute_report, render_markdown


def test_compute_report_marks_blocked_for_negative_expectancy_and_cadence_fail() -> None:
    now = datetime(2026, 2, 19, 18, 0, tzinfo=timezone.utc)
    state = {
        "meta": {"last_updated": "2026-02-19T17:30:00Z"},
        "last_updated": "2026-02-19T17:30:00Z",
        "north_star": {"probability_score": 70.4, "probability_label": "medium"},
        "trades": {"last_trade_date": "2026-02-09"},
        "north_star_weekly_gate": {
            "updated_at": "2026-02-19T17:30:00Z",
            "mode": "validation",
            "sample_size": 2,
            "expectancy_per_trade": -94.5,
            "block_new_positions": False,
            "scale_blocked_by_cadence": True,
            "cadence_kpi": {
                "passed": False,
                "summary": "Cadence KPI miss",
                "qualified_setups_observed": 0,
                "min_qualified_setups_per_week": 3,
                "closed_trades_observed": 2,
                "min_closed_trades_per_week": 1,
            },
        },
    }

    report = compute_report(
        state=state,
        weekly_history=[],
        halt_exists=False,
        now_utc=now,
    )

    assert report["blocked"] is True
    blocker_ids = {item["id"] for item in report["blockers"]}
    assert "negative_expectancy" in blocker_ids
    assert "cadence_failed" in blocker_ids
    assert "cadence_scale_block" in blocker_ids


def test_compute_report_not_blocked_when_gate_is_clean() -> None:
    now = datetime(2026, 2, 19, 18, 0, tzinfo=timezone.utc)
    state = {
        "meta": {"last_updated": "2026-02-19T17:30:00Z"},
        "last_updated": "2026-02-19T17:30:00Z",
        "north_star": {"probability_score": 82.0, "probability_label": "high"},
        "north_star_weekly_gate": {
            "updated_at": "2026-02-19T17:30:00Z",
            "mode": "normal",
            "sample_size": 10,
            "expectancy_per_trade": 22.0,
            "block_new_positions": False,
            "scale_blocked_by_cadence": False,
            "cadence_kpi": {
                "passed": True,
                "summary": "Cadence KPI met.",
                "qualified_setups_observed": 4,
                "min_qualified_setups_per_week": 3,
                "closed_trades_observed": 2,
                "min_closed_trades_per_week": 1,
            },
        },
    }

    report = compute_report(
        state=state,
        weekly_history=[],
        halt_exists=False,
        now_utc=now,
    )

    assert report["blocked"] is False
    assert report["blockers"] == []


def test_render_markdown_contains_absolute_dates_and_history_table() -> None:
    report = {
        "generated_at_utc": "2026-02-19T18:00:00Z",
        "trading_halted_file_exists": False,
        "last_trade_date": "2026-02-09",
        "state_timestamps": {
            "meta_last_updated": "2026-02-19T17:30:00Z",
            "weekly_gate_updated_at": "2026-02-19T17:35:00Z",
        },
        "current_gate": {
            "mode": "validation",
            "expectancy_per_trade": -94.5,
            "sample_size": 2,
            "qualified_setups_observed": 0,
            "min_qualified_setups_per_week": 3,
            "closed_trades_observed": 2,
            "min_closed_trades_per_week": 1,
            "cadence_summary": "Cadence KPI miss",
        },
        "north_star_probability": {"score": 70.4, "label": "medium"},
        "blockers": [
            {
                "id": "negative_expectancy",
                "severity": "high",
                "message": "Per-trade expectancy is non-positive.",
                "evidence": "expectancy_per_trade=-94.50, sample_size=2.",
            }
        ],
        "warnings": [],
        "root_causes": ["Trade quality/edge is below zero expectancy."],
        "recent_weekly_history": [
            {
                "week_start": "2026-02-16",
                "updated_at": "2026-02-19T17:35:00Z",
                "mode": "validation",
                "sample_size": 2,
                "expectancy_per_trade": -94.5,
                "cadence_passed": False,
            }
        ],
    }

    markdown = render_markdown(report)
    assert "Generated (UTC): `2026-02-19T18:00:00Z`" in markdown
    assert "System State Updated (UTC): `2026-02-19T17:30:00Z`" in markdown
    assert (
        "| Week Start | Updated At (UTC) | Mode | Sample | Expectancy | Cadence Passed |"
        in markdown
    )
    assert "2026-02-16" in markdown


def test_compute_report_parses_boolean_like_strings_in_weekly_gate() -> None:
    now = datetime(2026, 2, 19, 18, 0, tzinfo=timezone.utc)
    state = {
        "meta": {"last_updated": "2026-02-19T17:30:00Z"},
        "last_updated": "2026-02-19T17:30:00Z",
        "north_star_weekly_gate": {
            "updated_at": "2026-02-19T17:30:00Z",
            "mode": "validation",
            "sample_size": 2,
            "expectancy_per_trade": 10.0,
            "block_new_positions": "false",
            "scale_blocked_by_cadence": "false",
            "cadence_kpi": {
                "passed": "false",
                "summary": "Cadence KPI miss",
                "qualified_setups_observed": 0,
                "min_qualified_setups_per_week": 3,
                "closed_trades_observed": 0,
                "min_closed_trades_per_week": 1,
            },
        },
    }

    report = compute_report(state=state, weekly_history=[], halt_exists=False, now_utc=now)

    assert report["current_gate"]["block_new_positions"] is False
    assert report["current_gate"]["scale_blocked_by_cadence"] is False
    blocker_ids = {item["id"] for item in report["blockers"]}
    assert "cadence_failed" in blocker_ids
