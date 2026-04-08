"""Tests for milestone controller family gating and North Star scoring."""

import json

from src.safety.milestone_controller import compute_milestone_snapshot, get_milestone_context


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_milestone_snapshot_pauses_underperforming_options_family(tmp_path):
    state_path = tmp_path / "system_state.json"
    trades_path = tmp_path / "trades.json"

    _write_json(
        state_path,
        {
            "paper_account": {"equity": 101000, "win_rate": 37.5, "win_rate_sample_size": 32},
            "paper_trading": {"current_day": 12, "target_duration_days": 90},
        },
    )

    closed_trades = []
    for idx in range(12):
        is_win = idx < 3
        closed_trades.append(
            {
                "id": f"t{idx}",
                "strategy": "iron_condor",
                "status": "closed",
                "realized_pnl": 40.0 if is_win else -60.0,
                "outcome": "win" if is_win else "loss",
                "exit_date": f"2026-02-{idx + 1:02d}",
            }
        )

    _write_json(trades_path, {"trades": closed_trades})

    snapshot = compute_milestone_snapshot(state_path=state_path, trades_path=trades_path)
    options_state = snapshot["strategy_families"]["options_income"]

    assert options_state["paused"] is True
    assert options_state["status"] == "paused"
    assert "options_income" in snapshot["paused_families"]
    assert isinstance(snapshot["north_star_probability"]["score"], float)
    assert snapshot["north_star_probability"]["score"] <= 35.0
    assert snapshot["north_star_probability"]["target_date"] is None
    assert snapshot["north_star_probability"]["target_mode"] == "asap_monthly_income"
    assert snapshot["north_star_probability"]["monthly_after_tax_target"] == 6000.0


def test_milestone_context_blocks_buy_for_paused_family(tmp_path):
    state_path = tmp_path / "system_state.json"
    trades_path = tmp_path / "trades.json"

    _write_json(
        state_path,
        {"paper_account": {"equity": 100000}, "paper_trading": {"current_day": 30}},
    )
    _write_json(
        trades_path,
        {
            "trades": [
                {
                    "strategy": "iron_condor",
                    "status": "closed",
                    "realized_pnl": -50,
                    "outcome": "loss",
                    "exit_date": "2026-02-01",
                }
                for _ in range(12)
            ]
        },
    )

    context = get_milestone_context(
        strategy="iron_condor",
        state_path=state_path,
        trades_path=trades_path,
    )
    assert context["strategy_family"] == "options_income"
    assert context["pause_buy_for_family"] is True
    assert "blocked" in context["block_reason"].lower()


def test_milestone_snapshot_activates_family_with_positive_edge(tmp_path):
    state_path = tmp_path / "system_state.json"
    trades_path = tmp_path / "trades.json"

    _write_json(
        state_path,
        {
            "paper_account": {"equity": 450000, "win_rate": 82.0, "win_rate_sample_size": 45},
            "paper_trading": {"current_day": 95, "target_duration_days": 90},
        },
    )

    trades = []
    for idx in range(15):
        is_win = idx < 12
        trades.append(
            {
                "id": f"x{idx}",
                "strategy": "iron_condor",
                "status": "closed",
                "realized_pnl": 80.0 if is_win else -25.0,
                "outcome": "win" if is_win else "loss",
                "exit_date": f"2026-02-{idx + 1:02d}",
            }
        )
    _write_json(trades_path, {"trades": trades})

    snapshot = compute_milestone_snapshot(state_path=state_path, trades_path=trades_path)
    options_state = snapshot["strategy_families"]["options_income"]

    assert options_state["paused"] is False
    assert options_state["status"] == "active"
    assert 0.0 <= snapshot["north_star_probability"]["score"] <= 100.0
    assert snapshot["north_star_probability"]["target_date"] is None


def test_north_star_score_is_stable_across_lifetime_day_growth(tmp_path):
    state_path = tmp_path / "system_state.json"
    trades_path = tmp_path / "trades.json"

    trades = []
    for idx in range(20):
        is_win = idx < 16
        trades.append(
            {
                "id": f"s{idx}",
                "strategy": "iron_condor",
                "status": "closed",
                "realized_pnl": 55.0 if is_win else -20.0,
                "outcome": "win" if is_win else "loss",
                "exit_date": f"2026-02-{(idx % 20) + 1:02d}",
            }
        )
    _write_json(trades_path, {"trades": trades})

    _write_json(
        state_path,
        {
            "paper_account": {"equity": 125000, "win_rate": 80.0, "win_rate_sample_size": 20},
            "paper_trading": {"current_day": 90},
            "north_star_weekly_gate": {
                "cadence_kpi": {
                    "passed": True,
                    "qualified_setups_observed": 4,
                    "closed_trades_observed": 3,
                    "min_qualified_setups_per_week": 4,
                    "min_closed_trades_per_week": 3,
                }
            },
        },
    )
    snapshot_90 = compute_milestone_snapshot(state_path=state_path, trades_path=trades_path)

    _write_json(
        state_path,
        {
            "paper_account": {"equity": 125000, "win_rate": 80.0, "win_rate_sample_size": 20},
            "paper_trading": {"current_day": 180},
            "north_star_weekly_gate": {
                "cadence_kpi": {
                    "passed": True,
                    "qualified_setups_observed": 4,
                    "closed_trades_observed": 3,
                    "min_qualified_setups_per_week": 4,
                    "min_closed_trades_per_week": 3,
                }
            },
        },
    )
    snapshot_180 = compute_milestone_snapshot(state_path=state_path, trades_path=trades_path)

    score_90 = snapshot_90["north_star_probability"]["score"]
    score_180 = snapshot_180["north_star_probability"]["score"]
    assert abs(score_90 - score_180) < 2.0


def test_cadence_score_changes_gradually_near_threshold(tmp_path):
    state_path = tmp_path / "system_state.json"
    trades_path = tmp_path / "trades.json"

    _write_json(
        trades_path,
        {
            "trades": [
                {
                    "strategy": "iron_condor",
                    "status": "closed",
                    "realized_pnl": 40.0,
                    "outcome": "win",
                    "exit_date": f"2026-02-{idx + 1:02d}",
                }
                for idx in range(10)
            ]
        },
    )

    base_state = {
        "paper_account": {"equity": 110000, "win_rate": 80.0, "win_rate_sample_size": 10},
        "paper_trading": {"current_day": 80},
    }

    below = dict(base_state)
    below["north_star_weekly_gate"] = {
        "cadence_kpi": {
            "passed": False,
            "qualified_setups_observed": 3,
            "closed_trades_observed": 2,
            "min_qualified_setups_per_week": 4,
            "min_closed_trades_per_week": 3,
        }
    }
    _write_json(state_path, below)
    score_below = compute_milestone_snapshot(state_path=state_path, trades_path=trades_path)[
        "north_star_probability"
    ]["score"]

    near = dict(base_state)
    near["north_star_weekly_gate"] = {
        "cadence_kpi": {
            "passed": False,
            "qualified_setups_observed": 4,
            "closed_trades_observed": 2,
            "min_qualified_setups_per_week": 4,
            "min_closed_trades_per_week": 3,
        }
    }
    _write_json(state_path, near)
    score_near = compute_milestone_snapshot(state_path=state_path, trades_path=trades_path)[
        "north_star_probability"
    ]["score"]

    assert 0 <= score_near - score_below < 8.0


def test_milestone_snapshot_does_not_infer_family_edge_from_paper_account_summary(tmp_path):
    state_path = tmp_path / "system_state.json"
    trades_path = tmp_path / "trades.json"

    _write_json(
        state_path,
        {
            "paper_account": {"equity": 101000, "win_rate": 80.0, "win_rate_sample_size": 40},
            "paper_trading": {"current_day": 12, "target_duration_days": 90},
        },
    )
    _write_json(trades_path, {"trades": []})

    snapshot = compute_milestone_snapshot(state_path=state_path, trades_path=trades_path)
    options_state = snapshot["strategy_families"]["options_income"]

    assert options_state["metrics"]["samples"] == 0
    assert options_state["metrics"]["evidence_source"] == "none"
    assert options_state["status"] == "validation"
