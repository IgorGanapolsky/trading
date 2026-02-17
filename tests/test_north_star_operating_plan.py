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
            "paper_account": {"equity": 10_000.0},
            "live_account": {"equity": 30.0, "positions_count": 0},
        },
        today=date(2026, 2, 12),
    )

    by_return = plan["required_monthly_contribution_by_return"]
    assert "20%" in by_return
    assert "30%" in by_return
    assert by_return["20%"] >= by_return["30%"]
    assert by_return["20%"] > 0.0
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


def test_weekly_gate_adds_cadence_kpi_and_no_trade_diagnostic(tmp_path):
    trades_path = tmp_path / "trades.json"
    history_path = tmp_path / "weekly_history.json"
    today = date(2026, 2, 16)
    _write_json(trades_path, {"trades": []})

    session_path = tmp_path / "session_decisions_2026-02-16.json"
    _write_json(
        session_path,
        {
            "session": "paper",
            "decisions": [
                {
                    "ticker": "SPY",
                    "timestamp": "2026-02-16T15:00:00+00:00",
                    "gate_reached": 1,
                    "decision": "REJECTED",
                    "rejection_reason": "Vol=0.1x (low)",
                    "indicators": {"volume_ratio": 0.1},
                },
                {
                    "ticker": "SPY",
                    "timestamp": "2026-02-16T16:00:00+00:00",
                    "gate_reached": 1,
                    "decision": "REJECTED",
                    "rejection_reason": "Vol=0.2x (low)",
                    "indicators": {"volume_ratio": 0.2},
                },
            ],
        },
    )

    workflow_state_dir = tmp_path / "workflow_state"
    workflow_state_dir.mkdir(parents=True, exist_ok=True)
    market_signals_dir = tmp_path / "market_signals"
    market_signals_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        market_signals_dir / "ai_credit_stress_signal.json",
        {
            "signal": "ai_credit_stress",
            "status": "blocked",
            "severity_score": 72.5,
            "latest_data_date": "2026-02-16",
            "source": "fred_public",
            "reasons": ["HY OAS elevated: 4.60"],
        },
    )
    _write_json(
        workflow_state_dir / "swarm_integrated_pipeline_state.json",
        {
            "last_updated": "2026-02-16T16:01:00+00:00",
            "results": {
                "risk_gate": {
                    "output": {
                        "risk_checks": {
                            "regime_check": {"passed": True, "vix": 18, "note": "VIX < 25"},
                            "position_size_check": {
                                "passed": True,
                                "requested": 0,
                                "max_allowed": 5000,
                            },
                        }
                    }
                }
            },
        },
    )
    _write_json(
        workflow_state_dir / "iron_condor_pipeline_state.json",
        {
            "last_updated": "2026-02-16T16:02:00+00:00",
            "results": {
                "regime_gate": {"output": {"passed": True, "regime": "normal"}},
                "options_chain": {"output": {"data": {"recommended_dte": 60}}},
            },
        },
    )

    gate, _history = compute_weekly_gate(
        {"paper_account": {"win_rate": 60.0, "win_rate_sample_size": 0, "total_pl": 0}},
        trades_path=trades_path,
        weekly_history_path=history_path,
        today=today,
    )

    cadence = gate.get("cadence_kpi", {})
    assert cadence.get("enabled") is True
    assert cadence.get("qualified_setups_observed") == 2
    assert cadence.get("closed_trades_observed") == 0
    assert cadence.get("passed") is False

    diagnostic = gate.get("no_trade_diagnostic", {})
    gate_status = diagnostic.get("gate_status", {})
    assert gate_status.get("liquidity", {}).get("status") == "blocked"
    assert gate_status.get("dte", {}).get("status") == "blocked"
    assert gate_status.get("ai_credit_stress", {}).get("status") == "blocked"
    assert "liquidity" in diagnostic.get("blocked_categories", [])
    assert "ai_credit_stress" in diagnostic.get("blocked_categories", [])
    assert gate.get("scale_blocked_by_ai_credit_stress") is True
    assert gate.get("recommended_max_position_pct", 1) <= 0.01


def test_expansion_mode_requires_thirty_closed_trades_for_scaling(tmp_path):
    trades_path = tmp_path / "trades.json"
    history_path = tmp_path / "weekly_history.json"
    today = date(2026, 2, 20)
    trades = []
    for idx in range(12):
        exit_day = today - timedelta(days=idx)
        trades.append(
            {
                "status": "closed",
                "strategy": "iron_condor",
                "realized_pnl": 30.0,
                "outcome": "win",
                "exit_date": exit_day.isoformat(),
            }
        )
    _write_json(trades_path, {"stats": {"closed_trades": 12}, "trades": trades})

    gate, _history = compute_weekly_gate(
        {"paper_account": {"win_rate": 90.0, "win_rate_sample_size": 12, "total_pl": 360.0}},
        trades_path=trades_path,
        weekly_history_path=history_path,
        today=today,
    )

    assert gate["mode"] == "cautious"
    assert gate["scaling_sample_gate"]["passed"] is False
    assert gate["scaling_sample_gate"]["closed_trades_observed"] == 12
    assert gate["scaling_sample_gate"]["min_closed_trades_for_scaling"] == 30


def test_ai_credit_stress_watch_caps_expansion_to_cautious(tmp_path):
    trades_path = tmp_path / "trades.json"
    history_path = tmp_path / "weekly_history.json"
    today = date(2026, 2, 20)
    trades = []
    for idx in range(12):
        exit_day = today - timedelta(days=idx)
        trades.append(
            {
                "status": "closed",
                "strategy": "iron_condor",
                "realized_pnl": 40.0,
                "outcome": "win",
                "exit_date": exit_day.isoformat(),
            }
        )
    _write_json(trades_path, {"stats": {"closed_trades": 40}, "trades": trades})

    market_signals_dir = tmp_path / "market_signals"
    market_signals_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        market_signals_dir / "ai_credit_stress_signal.json",
        {
            "signal": "ai_credit_stress",
            "status": "watch",
            "severity_score": 45.0,
            "latest_data_date": "2026-02-20",
            "source": "fred_public",
            "reasons": ["HY OAS watch: 4.10"],
        },
    )

    gate, _history = compute_weekly_gate(
        {"paper_account": {"win_rate": 95.0, "win_rate_sample_size": 40, "total_pl": 480.0}},
        trades_path=trades_path,
        weekly_history_path=history_path,
        today=today,
    )

    assert gate["mode"] == "cautious"
    assert gate["recommended_max_position_pct"] <= 0.015
    assert gate["ai_credit_stress"]["status"] == "watch"
    assert gate["scale_blocked_by_ai_credit_stress"] is False
