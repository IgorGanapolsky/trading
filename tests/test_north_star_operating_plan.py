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


def test_contribution_plan_tracks_monthly_target_progress():
    plan = compute_contribution_plan(
        {
            "paper_account": {"equity": 10_000.0},
            "live_account": {"equity": 30.0, "positions_count": 0},
        },
        today=date(2026, 2, 12),
    )

    assert plan["target_mode"] == "asap_monthly_income"
    assert plan["target_date"] is None
    assert plan["monthly_after_tax_target"] == 6000.0
    assert plan["daily_after_tax_target"] == 200.0
    assert plan["required_monthly_contribution_by_return"] == {}
    assert plan["required_cagr_without_contributions"] is None
    assert plan["required_daily_after_tax_from_now"] >= 0.0
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


def test_weekly_gate_respects_liquidity_floor_override(tmp_path):
    trades_path = tmp_path / "trades.json"
    history_path = tmp_path / "weekly_history.json"
    today = date(2026, 2, 16)
    _write_json(trades_path, {"trades": []})

    _write_json(
        tmp_path / "session_decisions_2026-02-16.json",
        {
            "session": "paper",
            "decisions": [
                {
                    "ticker": "SPY",
                    "timestamp": "2026-02-16T15:00:00+00:00",
                    "gate_reached": 1,
                    "decision": "REJECTED",
                    "rejection_reason": "Vol=0.18x (low)",
                    "indicators": {"volume_ratio": 0.18},
                },
                {
                    "ticker": "SPY",
                    "timestamp": "2026-02-16T16:00:00+00:00",
                    "gate_reached": 1,
                    "decision": "REJECTED",
                    "rejection_reason": "Vol=0.19x (low)",
                    "indicators": {"volume_ratio": 0.19},
                },
            ],
        },
    )
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        runtime_dir / "north_star_gate_overrides.json", {"min_liquidity_volume_ratio": 0.18}
    )

    gate, _history = compute_weekly_gate(
        {"paper_account": {"win_rate": 60.0, "win_rate_sample_size": 0, "total_pl": 0}},
        trades_path=trades_path,
        weekly_history_path=history_path,
        today=today,
    )

    assert gate.get("liquidity_min_volume_ratio") == 0.18
    diagnostic = gate.get("no_trade_diagnostic", {})
    liquidity = diagnostic.get("gate_status", {}).get("liquidity", {})
    assert liquidity.get("threshold_min_volume_ratio") == 0.18
    assert liquidity.get("status") == "pass"


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


def test_usd_macro_watch_applies_soft_size_multiplier(tmp_path):
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
        market_signals_dir / "usd_macro_sentiment_signal.json",
        {
            "signal": "usd_macro_sentiment",
            "status": "watch",
            "bearish_score": 45.0,
            "position_size_multiplier": 0.95,
            "latest_data_date": "2026-02-20",
            "source": "fred_public",
            "reasons": ["Broad USD index below 50D average"],
        },
    )

    gate, _history = compute_weekly_gate(
        {"paper_account": {"win_rate": 95.0, "win_rate_sample_size": 40, "total_pl": 480.0}},
        trades_path=trades_path,
        weekly_history_path=history_path,
        today=today,
    )

    assert gate["usd_macro_sentiment"]["status"] == "watch"
    assert gate["scale_multiplier_from_usd_macro"] == 0.95
    assert gate["recommended_max_position_pct"] <= 0.019


def test_apply_operating_plan_sets_usd_macro_risk_fields(tmp_path):
    state = {
        "paper_account": {"equity": 100000.0, "win_rate": 75.0, "win_rate_sample_size": 40},
        "live_account": {"equity": 20.0, "positions_count": 0},
        "risk": {},
    }
    trades_path = tmp_path / "trades.json"
    history_path = tmp_path / "weekly_history.json"
    market_signals_dir = tmp_path / "market_signals"
    market_signals_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        market_signals_dir / "usd_macro_sentiment_signal.json",
        {
            "signal": "usd_macro_sentiment",
            "status": "watch",
            "bearish_score": 33.0,
            "position_size_multiplier": 0.95,
            "latest_data_date": "2026-02-20",
            "source": "fred_public",
            "reasons": ["USD softening"],
        },
    )
    _write_json(trades_path, {"trades": []})

    updated, _history = apply_operating_plan_to_state(
        state,
        trades_path=trades_path,
        weekly_history_path=history_path,
        today=date(2026, 2, 20),
    )

    assert updated["risk"]["weekly_usd_macro_status"] == "watch"
    assert updated["risk"]["weekly_usd_macro_score"] == 33.0
    assert updated["risk"]["weekly_usd_macro_multiplier"] == 0.95


def test_ai_cycle_watch_applies_soft_size_multiplier(tmp_path):
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
        market_signals_dir / "ai_cycle_signal.json",
        {
            "signal": "ai_cycle",
            "status": "watch",
            "severity_score": 41.0,
            "position_size_multiplier": 0.95,
            "capex_deceleration_shock": False,
            "regime": "transition",
            "latest_data_date": "2026-02-20",
            "source": "yfinance_public",
            "reasons": ["Capex momentum decelerating"],
        },
    )

    gate, _history = compute_weekly_gate(
        {"paper_account": {"win_rate": 95.0, "win_rate_sample_size": 40, "total_pl": 480.0}},
        trades_path=trades_path,
        weekly_history_path=history_path,
        today=today,
    )

    assert gate["ai_cycle"]["status"] == "watch"
    assert gate["scale_multiplier_from_ai_cycle"] == 0.95
    assert gate["recommended_max_position_pct"] <= 0.019
    assert gate["block_new_positions"] is False


def test_ai_cycle_shock_blocks_new_positions(tmp_path):
    trades_path = tmp_path / "trades.json"
    history_path = tmp_path / "weekly_history.json"
    today = date(2026, 2, 20)
    _write_json(trades_path, {"stats": {"closed_trades": 40}, "trades": []})

    market_signals_dir = tmp_path / "market_signals"
    market_signals_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        market_signals_dir / "ai_cycle_signal.json",
        {
            "signal": "ai_cycle",
            "status": "blocked",
            "severity_score": 82.0,
            "position_size_multiplier": 0.85,
            "capex_deceleration_shock": True,
            "regime": "capex_deceleration",
            "latest_data_date": "2026-02-20",
            "source": "yfinance_public",
            "reasons": ["Capex deceleration shock condition triggered"],
        },
    )

    gate, _history = compute_weekly_gate(
        {"paper_account": {"win_rate": 95.0, "win_rate_sample_size": 40, "total_pl": 480.0}},
        trades_path=trades_path,
        weekly_history_path=history_path,
        today=today,
    )

    assert gate["mode"] == "defensive"
    assert gate["block_new_positions"] is True
    assert gate["recommended_max_position_pct"] <= 0.01
    assert gate["scale_blocked_by_ai_cycle"] is True


def test_apply_operating_plan_sets_ai_cycle_risk_fields(tmp_path):
    state = {
        "paper_account": {"equity": 100000.0, "win_rate": 75.0, "win_rate_sample_size": 40},
        "live_account": {"equity": 20.0, "positions_count": 0},
        "risk": {},
    }
    trades_path = tmp_path / "trades.json"
    history_path = tmp_path / "weekly_history.json"
    market_signals_dir = tmp_path / "market_signals"
    market_signals_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        market_signals_dir / "ai_cycle_signal.json",
        {
            "signal": "ai_cycle",
            "status": "watch",
            "severity_score": 37.0,
            "position_size_multiplier": 0.95,
            "capex_deceleration_shock": False,
            "regime": "transition",
            "latest_data_date": "2026-02-20",
            "source": "yfinance_public",
            "reasons": ["Capex momentum decelerating"],
        },
    )
    _write_json(trades_path, {"trades": []})

    updated, _history = apply_operating_plan_to_state(
        state,
        trades_path=trades_path,
        weekly_history_path=history_path,
        today=date(2026, 2, 20),
    )

    assert updated["risk"]["weekly_ai_cycle_status"] == "watch"
    assert updated["risk"]["weekly_ai_cycle_score"] == 37.0
    assert updated["risk"]["weekly_ai_cycle_multiplier"] == 0.95
    assert updated["risk"]["weekly_ai_cycle_regime"] == "transition"
    assert updated["risk"]["weekly_ai_cycle_capex_deceleration_shock"] is False
