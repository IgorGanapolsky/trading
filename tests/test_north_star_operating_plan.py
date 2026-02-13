"""Tests for weekly North Star gate and contribution plan tracking."""

import json
from datetime import date, timedelta

from src.safety.north_star_operating_plan import (
    apply_operating_plan_to_state,
    compute_contribution_plan,
    compute_weekly_gate,
)


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_weekly_gate_blocks_when_recent_expectancy_negative(tmp_path):
    trades_path = tmp_path / "trades.json"
    history_path = tmp_path / "weekly_history.json"

    today = date(2026, 2, 12)
    trades = []
    for idx in range(8):
        exit_day = today - timedelta(days=idx)
        trades.append(
            {
                "status": "closed",
                "strategy": "iron_condor",
                "realized_pnl": -25.0,
                "outcome": "loss",
                "exit_date": exit_day.isoformat(),
            }
        )
    _write_json(trades_path, {"trades": trades})

    gate, history = compute_weekly_gate(
        {"paper_account": {"win_rate": 50.0, "win_rate_sample_size": 8, "total_pl": -200}},
        trades_path=trades_path,
        weekly_history_path=history_path,
        today=today,
    )

    assert gate["mode"] == "defensive"
    assert gate["block_new_positions"] is True
    assert gate["recommended_max_position_pct"] <= 0.01
    assert len(history) == 1
    assert history_path.exists()


def test_contribution_plan_contains_return_scenarios():
    plan = compute_contribution_plan(
        {
            "paper_account": {"equity": 101443.56},
            "live_account": {"equity": 30.0, "positions_count": 0},
        },
        today=date(2026, 2, 12),
    )

    by_return = plan["required_monthly_contribution_by_return"]
    assert "20%" in by_return
    assert "30%" in by_return
    assert by_return["20%"] > by_return["30%"]
    assert plan["estimated_live_contribution_this_month"] is not None


def test_apply_operating_plan_writes_state_fields(tmp_path):
    state = {
        "paper_account": {"equity": 100000.0, "win_rate": 75.0, "win_rate_sample_size": 40},
        "live_account": {"equity": 20.0, "positions_count": 0},
        "risk": {},
    }
    trades_path = tmp_path / "trades.json"
    history_path = tmp_path / "weekly_history.json"
    _write_json(trades_path, {"trades": []})

    updated, _history = apply_operating_plan_to_state(
        state,
        trades_path=trades_path,
        weekly_history_path=history_path,
        today=date(2026, 2, 12),
    )

    assert "north_star_weekly_gate" in updated
    assert "north_star_contributions" in updated
    assert "weekly_gate_mode" in updated["risk"]

