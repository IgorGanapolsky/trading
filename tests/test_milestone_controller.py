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
