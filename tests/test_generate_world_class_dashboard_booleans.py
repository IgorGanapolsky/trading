from __future__ import annotations

import json
from pathlib import Path

from scripts import generate_world_class_dashboard_enhanced as dashboard


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_parse_bool_handles_common_string_values() -> None:
    assert dashboard.parse_bool("true") is True
    assert dashboard.parse_bool("FALSE") is False
    assert dashboard.parse_bool("passed") is True
    assert dashboard.parse_bool("failed") is False
    assert dashboard.parse_bool("1") is True
    assert dashboard.parse_bool("0") is False


def test_calculate_basic_metrics_parses_boolean_like_strings(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(dashboard, "DATA_DIR", data_dir)

    _write_json(
        data_dir / "system_state.json",
        {
            "challenge": {"start_date": "2025-10-29", "total_days": 90},
            "live_account": {
                "current_equity": 20.0,
                "starting_balance": 20.0,
                "total_pl": 0.0,
                "total_pl_pct": 0.0,
            },
            "paper_account": {
                "equity": 100000.0,
                "starting_balance": 100000.0,
                "total_pl": 0.0,
                "total_pl_pct": 0.0,
            },
            "north_star": {"probability_score": 10, "probability_label": "low"},
            "strategy_milestones": {"enabled": "false"},
            "risk": {"weekly_cadence_kpi_passed": "false"},
        },
    )
    _write_json(
        data_dir / "trades.json",
        {
            "stats": {"win_rate_pct": 0.0, "total_trades": 0, "closed_trades": 0, "open_trades": 0},
            "meta": {"decision_thresholds": {"min_trades_for_decision": 30}},
        },
    )
    _write_json(data_dir / "performance_log.json", [])

    metrics = dashboard.calculate_basic_metrics()

    assert metrics["weekly_cadence_kpi_passed"] is False
    assert metrics["milestone_enabled"] is False
