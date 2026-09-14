"""Unit tests for Ralph Loop 24/7 & GSD Autonomous Trading Engine."""

from __future__ import annotations

import json
from pathlib import Path

from src.core.trading_profiles import PUT_CREDIT_PROFILE_REGISTRY, get_put_credit_profile
from src.ops.ralph_gsd_trading_runner import (
    GSDActionType,
    RalphGSDTradingRunner,
)

REPO = Path(__file__).resolve().parents[1]


def test_put_credit_profile_capacity_and_multi_asset():
    profile = get_put_credit_profile()
    # 5 concurrent positions for accelerated paper validation velocity
    assert profile.max_concurrent_positions == 5
    assert profile.max_daily_structures == 3
    # Multi-asset registry covers SPY, QQQ, IWM, XSP
    assert "spy-put-credit" in PUT_CREDIT_PROFILE_REGISTRY
    assert "qqq-put-credit" in PUT_CREDIT_PROFILE_REGISTRY
    assert "iwm-put-credit" in PUT_CREDIT_PROFILE_REGISTRY
    assert "xsp-put-credit" in PUT_CREDIT_PROFILE_REGISTRY


def test_ralph_sense_pipeline_state():
    runner = RalphGSDTradingRunner(REPO)
    sense = runner.sense_pipeline_state()
    assert sense["max_capacity"] == 5
    assert sense["capacity_headroom"] >= 0
    assert sense["regime_allowed"] is True
    assert "vix" in sense
    assert "iv_rank" in sense


def test_ralph_decide_take_profit_priority():
    runner = RalphGSDTradingRunner(REPO)
    # Simulate a position with >= 25% profit
    sense = {
        "vix": 17.67,
        "iv_rank": 56.38,
        "spy_above_200dma": True,
        "regime_allowed": True,
        "max_capacity": 5,
        "capacity_used": 2,
        "capacity_headroom": 3,
        "open_positions": [
            {"key": "PCS_261016_WIN", "unrealized_pct": 0.28},
            {"key": "PCS_261023_NORMAL", "unrealized_pct": 0.05},
        ],
    }
    plan = runner.decide_gsd_action(sense)
    assert plan.action_type == GSDActionType.TAKE_PROFIT_EXIT
    assert "PCS_261016_WIN" in plan.target_structure


def test_ralph_decide_new_entry_when_headroom_available():
    runner = RalphGSDTradingRunner(REPO)
    sense = {
        "vix": 17.67,
        "iv_rank": 56.38,
        "spy_above_200dma": True,
        "regime_allowed": True,
        "max_capacity": 5,
        "capacity_used": 2,
        "capacity_headroom": 3,
        "open_positions": [
            {"key": "PCS_261016_A", "unrealized_pct": 0.10},
            {"key": "PCS_261023_B", "unrealized_pct": 0.05},
        ],
    }
    plan = runner.decide_gsd_action(sense)
    assert plan.action_type == GSDActionType.NEW_STRUCTURE_ENTRY
    assert plan.capacity_headroom == 3


def test_ralph_execute_gsd_tick_receipt():
    runner = RalphGSDTradingRunner(REPO)
    receipt = runner.execute_gsd_tick()
    assert receipt.tick_id.startswith("TICK_")
    assert receipt.status == "SUCCESS"
    assert receipt.max_capacity == 5
    assert len(receipt.receipt_hash) == 16
    # State file updated
    state = json.loads(runner.state_file.read_text(encoding="utf-8"))
    assert state["active"] is True
    assert state["status"] == "running_24_7"
    assert state["framework"] == "ralph+gsd-24-7"


def test_cli_runner_execution(capsys):
    import importlib.util

    cli_path = REPO / "scripts" / "ralph_gsd_trading_runner.py"
    spec = importlib.util.spec_from_file_location("ralph_gsd_trading_runner", cli_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Doctor
    rc = mod.main(["--doctor", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["max_capacity_slots"] == 5

    # Sense
    rc = mod.main(["--sense", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert "sense" in out
    assert "decide" in out

    # Single Tick
    rc = mod.main(["--tick", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "SUCCESS"
