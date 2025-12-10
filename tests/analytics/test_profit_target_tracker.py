from __future__ import annotations

import json
from pathlib import Path

import pytest
from src.analytics.profit_target_tracker import ProfitTargetTracker


def sample_state(avg_return: float = 2.5) -> dict:
    return {
        "account": {"total_pl": 120.0},
        "challenge": {"current_day": 3},
        "performance": {"avg_return": avg_return, "win_rate": 62.0},
        "strategies": {
            "tier1": {"status": "active", "daily_amount": 10.0, "allocation": 0.6},
            "tier2": {"status": "active", "daily_amount": 5.0, "allocation": 0.4},
            "tier3": {"status": "tracking", "daily_amount": 1.0},
        },
    }


def test_generate_plan_with_positive_avg_return(tmp_path: Path) -> None:
    state = sample_state()
    tracker = ProfitTargetTracker(
        state_path=tmp_path / "state.json",
        target_daily_profit=100.0,
        state_override=state,
    )
    plan = tracker.generate_plan()

    assert pytest.approx(plan.current_daily_profit, rel=1e-3) == 40.0
    assert pytest.approx(plan.projected_daily_profit, rel=1e-3) == 0.375
    assert pytest.approx(plan.target_gap, rel=1e-3) == 99.625
    assert pytest.approx(plan.recommended_daily_budget, rel=1e-3) == 4000.0
    assert pytest.approx(plan.scaling_factor, rel=1e-3) == 266.6666667
    assert plan.recommended_allocations["tier1"] == pytest.approx(2400.0)
    assert plan.recommended_allocations["tier2"] == pytest.approx(1600.0)
    assert any("Increase blended daily budget" in action for action in plan.actions)


def test_generate_plan_when_avg_return_negative(tmp_path: Path) -> None:
    state = sample_state(avg_return=-1.0)
    tracker = ProfitTargetTracker(
        state_path=tmp_path / "state.json",
        target_daily_profit=100.0,
        state_override=state,
    )
    plan = tracker.generate_plan()

    assert plan.recommended_daily_budget is None
    assert plan.scaling_factor is None
    assert any("Improve strategy edge" in action for action in plan.actions)


def test_write_report_creates_file(tmp_path: Path) -> None:
    state = sample_state()
    tracker = ProfitTargetTracker(
        state_path=tmp_path / "state.json",
        target_daily_profit=100.0,
        state_override=state,
    )
    output = tmp_path / "report.json"
    tracker.write_report(output)

    assert output.exists()
    payload = json.loads(output.read_text())
    assert payload["target_daily_profit"] == 100.0
    assert "actions" in payload
