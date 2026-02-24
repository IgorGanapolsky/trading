"""Tests for profit target tracker and scaling recommendations."""

import json
from pathlib import Path

from src.analytics.profit_target_tracker import ProfitTargetTracker


def _write_state(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_profit_target_tracker_recommends_budget_when_edge_positive(tmp_path):
    state_path = tmp_path / "system_state.json"
    _write_state(
        state_path,
        {
            "paper_account": {
                "daily_change": 120.0,
                "total_pl": 1200.0,
                "win_rate": 82.0,
                "win_rate_sample_size": 30,
            },
            "paper_trading": {"current_day": 12},
            "north_star_weekly_gate": {
                "sample_size": 30,
                "expectancy_per_trade": 25.0,
            },
            "risk": {"daily_budget": 100.0},
        },
    )

    tracker = ProfitTargetTracker(target_daily_profit=200.0, state_path=state_path)
    plan = tracker.generate_plan()

    assert plan.current_daily_profit == 120.0
    assert plan.avg_return_pct > 0
    assert plan.recommended_daily_budget is not None
    assert plan.scaling_factor is not None
    assert "options_income" in plan.recommended_allocations


def test_profit_target_tracker_blocks_scaling_when_edge_non_positive(tmp_path):
    state_path = tmp_path / "system_state.json"
    _write_state(
        state_path,
        {
            "paper_account": {
                "daily_change": -10.0,
                "total_pl": -50.0,
                "win_rate": 45.0,
            },
            "paper_trading": {"current_day": 10},
            "risk": {"daily_budget": 100.0},
        },
    )

    tracker = ProfitTargetTracker(target_daily_profit=200.0, state_path=state_path)
    plan = tracker.generate_plan()

    assert plan.avg_return_pct <= 0
    assert plan.recommended_daily_budget is None
    assert any("Do not scale budget yet" in action for action in plan.actions)


def test_profit_target_tracker_blocks_scaling_when_sample_too_small(tmp_path):
    state_path = tmp_path / "system_state.json"
    _write_state(
        state_path,
        {
            "paper_account": {
                "daily_change": 120.0,
                "total_pl": 1200.0,
                "win_rate": 82.0,
                "win_rate_sample_size": 2,
            },
            "paper_trading": {"current_day": 12},
            "north_star_weekly_gate": {
                "sample_size": 2,
                "expectancy_per_trade": 25.0,
            },
            "risk": {"daily_budget": 100.0},
        },
    )

    tracker = ProfitTargetTracker(target_daily_profit=200.0, state_path=state_path)
    plan = tracker.generate_plan()

    assert plan.avg_return_pct > 0
    assert plan.recommended_daily_budget is None
    assert any("insufficient closed-trade sample" in action for action in plan.actions)


def test_profit_target_tracker_blocks_scaling_when_expectancy_non_positive(tmp_path):
    state_path = tmp_path / "system_state.json"
    _write_state(
        state_path,
        {
            "paper_account": {
                "daily_change": 120.0,
                "total_pl": 1200.0,
                "win_rate": 82.0,
                "win_rate_sample_size": 30,
            },
            "paper_trading": {"current_day": 12},
            "north_star_weekly_gate": {
                "sample_size": 30,
                "expectancy_per_trade": 0.0,
            },
            "risk": {"daily_budget": 100.0},
        },
    )

    tracker = ProfitTargetTracker(target_daily_profit=200.0, state_path=state_path)
    plan = tracker.generate_plan()

    assert plan.avg_return_pct > 0
    assert plan.recommended_daily_budget is None
    assert any("expectancy per trade must be positive" in action for action in plan.actions)
