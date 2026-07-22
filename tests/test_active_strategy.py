"""Tests for strategy kill switch and active put-credit successor."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.active_strategy import (
    assert_entry_allowed,
    entry_block_message,
    load_kill_state,
)
from src.core.trading_profiles import get_active_strategy_config, get_put_credit_profile


def test_kill_state_defaults_ic_dead(tmp_path: Path, monkeypatch):
    runtime = tmp_path / "data" / "runtime"
    runtime.mkdir(parents=True)
    kill = {
        "active_family": "spy_put_credit",
        "killed_families": ["ic_simple", "iron_condor"],
        "successor_family": "spy_put_credit",
        "reason": "test kill",
        "paper_only": True,
        "live_blocked": True,
    }
    (runtime / "strategy_kill_switch.json").write_text(json.dumps(kill), encoding="utf-8")
    monkeypatch.setattr("src.core.active_strategy.RUNTIME_DIR", runtime)
    monkeypatch.setattr(
        "src.core.active_strategy.KILL_FILE", runtime / "strategy_kill_switch.json"
    )
    monkeypatch.setattr(
        "src.core.active_strategy.HYPOTHESIS_FILE",
        runtime / "strategy_validation_hypothesis.json",
    )
    monkeypatch.delenv("ACTIVE_STRATEGY_FAMILY", raising=False)

    state = load_kill_state()
    assert state.active_family == "spy_put_credit"
    assert state.is_killed("ic_simple")
    assert state.is_killed("iron_condor")
    assert state.allows_new_entries("spy_put_credit")
    assert not state.allows_new_entries("ic_simple")


def test_assert_entry_allowed_blocks_ic(tmp_path: Path, monkeypatch):
    runtime = tmp_path / "data" / "runtime"
    runtime.mkdir(parents=True)
    (runtime / "strategy_kill_switch.json").write_text(
        json.dumps(
            {
                "active_family": "spy_put_credit",
                "killed_families": ["ic_simple", "iron_condor"],
                "successor_family": "spy_put_credit",
                "reason": "IC dead",
                "paper_only": True,
                "live_blocked": True,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("src.core.active_strategy.RUNTIME_DIR", runtime)
    monkeypatch.setattr(
        "src.core.active_strategy.KILL_FILE", runtime / "strategy_kill_switch.json"
    )
    monkeypatch.setattr(
        "src.core.active_strategy.HYPOTHESIS_FILE",
        runtime / "missing.json",
    )
    monkeypatch.delenv("ACTIVE_STRATEGY_FAMILY", raising=False)

    with pytest.raises(RuntimeError, match="STRATEGY_KILLED"):
        assert_entry_allowed("ic_simple")
    assert entry_block_message("ic_simple")
    assert entry_block_message("spy_put_credit") is None
    assert_entry_allowed("spy_put_credit")


def test_put_credit_profile_is_one_lot_spy():
    p = get_put_credit_profile()
    assert p.underlying == "SPY"
    assert p.max_contracts_per_trade == 1
    assert p.wing_width == 5.0
    assert p.take_profit_pct == 0.25
    assert p.stop_loss_pct == 2.0
    cfg = get_active_strategy_config()
    assert cfg["strategy_family"] == "spy_put_credit"
    assert cfg["structure"] == "bull_put_credit"


def test_find_put_credit_uses_put_side_only(monkeypatch):
    from scripts import spy_put_credit as pcs

    class Sel:
        method = "live_delta"
        put_delta = 0.15
        short_put = 700.0
        long_put = 695.0
        put_bid = 1.20
        long_put_ask = 0.40
        expiry = "2026-08-21"

    monkeypatch.setattr(
        "src.markets.option_chain.select_strikes_by_delta",
        lambda **kwargs: Sel(),
    )
    # ensure import path inside function sees the patch
    import src.markets.option_chain as oc

    monkeypatch.setattr(oc, "select_strikes_by_delta", lambda **kwargs: Sel())
    opp = pcs.find_put_credit_opportunity(747.0)
    assert opp is not None
    assert opp["short_put"] == 700.0
    assert opp["long_put"] == 695.0
    assert opp["est_credit"] == 0.80
    assert "short_call" not in opp


def test_repo_kill_switch_file_present():
    root = Path(__file__).resolve().parents[1]
    path = root / "data" / "runtime" / "strategy_kill_switch.json"
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "ic_simple" in data.get("killed_families", [])
    assert data.get("active_family") == "spy_put_credit"
    hyp = json.loads(
        (root / "data" / "runtime" / "strategy_validation_hypothesis.json").read_text(
            encoding="utf-8"
        )
    )
    assert hyp.get("strategy_family") == "spy_put_credit"
    assert hyp.get("enabled") is True
    rehab = json.loads(
        (root / "data" / "runtime" / "edge_rehabilitation_plan.json").read_text(encoding="utf-8")
    )
    assert rehab.get("status") == "killed"
