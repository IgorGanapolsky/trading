"""Tests for strategy kill switch and active put-credit successor."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

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
    monkeypatch.setattr("src.core.active_strategy.KILL_FILE", runtime / "strategy_kill_switch.json")
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
    monkeypatch.setattr("src.core.active_strategy.KILL_FILE", runtime / "strategy_kill_switch.json")
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


def test_put_credit_inventory_gate_uses_broker_reconstruction(monkeypatch):
    from scripts import spy_put_credit as pcs

    clean = {
        "broken": 0,
        "reconciled": 2,
        "unresolved": {},
        "pcs_inventory_excluded": {},
    }
    manage = MagicMock(return_value=clean)
    monkeypatch.setattr("scripts.residual_ic_manager.manage_residual_ics", manage)
    client = object()

    assert pcs._inventory_ok(client) is True
    manage.assert_called_once_with(client, dry_run=True)


def test_put_credit_inventory_gate_fails_closed_on_unexplained_leg(monkeypatch):
    from scripts import spy_put_credit as pcs

    broken = {
        "broken": 1,
        "reconciled": 2,
        "unresolved": {"SPY260821P00695000": 1.0},
        "pcs_inventory_excluded": {},
    }
    monkeypatch.setattr(
        "scripts.residual_ic_manager.manage_residual_ics", MagicMock(return_value=broken)
    )

    assert pcs._inventory_ok(object()) is False


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


def _put_credit_opp() -> dict:
    return {
        "expiry": "2026-08-21",
        "short_put": 700.0,
        "long_put": 695.0,
        "est_credit": 1.0,
        "put_delta": 0.15,
        "method": "live_delta",
        "quantity": 1,
    }


def test_put_credit_journal_uses_unique_order_identity(tmp_path, monkeypatch):
    from scripts import spy_put_credit as pcs

    entries_path = tmp_path / "put_credit_entries.json"
    monkeypatch.setattr(pcs, "ENTRIES_FILE", entries_path)

    pcs._record_entry(_put_credit_opp(), "order-1")
    pcs._record_entry(_put_credit_opp(), "order-2")

    entries = json.loads(entries_path.read_text(encoding="utf-8"))
    assert set(entries) == {"PCS_260821_order1", "PCS_260821_order2"}
    assert entries["PCS_260821_order1"]["credit_source"] == "limit_estimate_unconfirmed"
    assert entries["PCS_260821_order2"]["expiry"] == "2026-08-21"


def test_put_credit_entry_builds_supported_bull_put_order_id(tmp_path, monkeypatch):
    from scripts import spy_put_credit as pcs
    from src.utils.order_intent import parse_client_order_id

    captured = {}

    def fake_submit(client, request, strategy=None):
        captured["request"] = request
        captured["strategy"] = strategy
        return SimpleNamespace(id="order-1", status="FILLED")

    monkeypatch.setattr(pcs, "ENTRIES_FILE", tmp_path / "put_credit_entries.json")
    monkeypatch.setattr(pcs.time, "sleep", lambda _: None)
    monkeypatch.setattr("src.safety.mandatory_trade_gate.safe_submit_order", fake_submit)
    client = MagicMock()
    client.get_order_by_id.return_value = SimpleNamespace(status="FILLED")

    order_id = pcs.place_put_credit(client, _put_credit_opp())

    assert order_id == "order-1"
    assert captured["strategy"] == "spy_put_credit"
    assert float(captured["request"].limit_price) == -0.95
    parsed = parse_client_order_id(captured["request"].client_order_id)
    assert parsed is not None
    assert parsed["role"] == "OPEN"
    assert parsed["intent"] == "BPS"


def test_put_credit_resolves_to_options_income_milestone_family():
    from src.safety.milestone_controller import resolve_strategy_family

    assert resolve_strategy_family("spy_put_credit") == "options_income"


def test_put_credit_entry_limits_enforce_daily_concurrent_and_signature():
    from scripts import spy_put_credit as pcs

    now = datetime(2026, 7, 22, 16, 0, tzinfo=timezone.utc)
    entries = {
        "PCS_1": {
            "status": "open",
            "entry_time": now.isoformat(),
            "signature": "same",
        }
    }

    report = pcs.evaluate_entry_limits(entries, candidate_signature="same", now=now)

    assert report["allowed"] is False
    assert report["today_count"] == 1
    assert any("Daily" in blocker for blocker in report["blockers"])
    assert any("signature" in blocker for blocker in report["blockers"])

    entries["PCS_2"] = {
        "status": "open",
        "entry_time": (now - timedelta(days=1)).isoformat(),
        "signature": "different",
    }
    report = pcs.evaluate_entry_limits(entries, now=now)
    assert report["active_count"] == 2
    assert any("Concurrent" in blocker for blocker in report["blockers"])


def test_put_credit_exit_rules_cover_profit_stop_hold_and_dte():
    from scripts import spy_put_credit as pcs

    now = datetime(2026, 7, 22, 16, 0, tzinfo=timezone.utc)
    entry = {
        "expiry": "2026-08-21",
        "entry_time": (now - timedelta(days=2)).isoformat(),
        "credit": 1.0,
        "quantity": 1,
    }

    profit = pcs.evaluate_put_credit_exit(entry, short_price=0.60, long_price=0.10, now=now)
    assert profit["should_exit"] is True
    assert profit["exit_reason"] == "profit_target"

    stop = pcs.evaluate_put_credit_exit(entry, short_price=3.40, long_price=0.10, now=now)
    assert stop["should_exit"] is True
    assert stop["exit_reason"] == "stop_loss"

    young_entry = {**entry, "entry_time": (now - timedelta(hours=2)).isoformat()}
    young = pcs.evaluate_put_credit_exit(young_entry, short_price=0.60, long_price=0.10, now=now)
    assert young["should_exit"] is False

    dte_entry = {**entry, "expiry": "2026-07-29"}
    dte = pcs.evaluate_put_credit_exit(dte_entry, short_price=1.0, long_price=0.20, now=now)
    assert dte["exit_reason"] == "dte_exit"


def test_put_credit_exit_manager_dry_run_never_submits(tmp_path, monkeypatch):
    from scripts import spy_put_credit as pcs

    now = datetime.now(timezone.utc)
    entries_path = tmp_path / "put_credit_entries.json"
    entries_path.write_text(
        json.dumps(
            {
                "PCS_260821_order1": {
                    "status": "open",
                    "expiry": "2026-08-21",
                    "entry_time": (now - timedelta(days=2)).isoformat(),
                    "credit": 1.0,
                    "credit_source": "broker_fill",
                    "quantity": 1,
                    "strikes": {"short_put": 700.0, "long_put": 695.0},
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(pcs, "ENTRIES_FILE", entries_path)
    client = MagicMock()
    client.get_all_positions.return_value = [
        SimpleNamespace(
            symbol="SPY260821P00700000",
            qty="-1",
            current_price="0.60",
            avg_entry_price="1.20",
        ),
        SimpleNamespace(
            symbol="SPY260821P00695000",
            qty="1",
            current_price="0.10",
            avg_entry_price="0.20",
        ),
    ]
    monkeypatch.setattr(
        pcs,
        "_submit_spread_close",
        MagicMock(side_effect=AssertionError("dry run submitted an order")),
    )

    report = pcs.manage_put_credit_exits(client, dry_run=True)

    assert report["would_exit"] == 1
    assert report["submitted"] == 0


def test_put_credit_spread_close_never_uses_zero_debit(monkeypatch):
    from scripts import spy_put_credit as pcs

    captured = {}

    def fake_submit(client, request, strategy=None):
        captured["request"] = request
        return SimpleNamespace(id="close-1")

    monkeypatch.setattr("src.safety.mandatory_trade_gate.safe_submit_order", fake_submit)
    entry = {
        "expiry": "2026-08-21",
        "quantity": 1,
        "strikes": {"short_put": 700.0, "long_put": 695.0},
    }

    pcs._submit_spread_close(object(), entry, {"current_debit": -0.05})

    assert float(captured["request"].limit_price) == 0.01


def test_put_credit_exit_manager_distinguishes_pending_entry_from_broken(tmp_path, monkeypatch):
    from scripts import spy_put_credit as pcs

    entries_path = tmp_path / "put_credit_entries.json"
    entries_path.write_text(
        json.dumps(
            {
                "PCS_260821_order1": {
                    "status": "submitted_unconfirmed",
                    "order_id": "order-1",
                    "expiry": "2026-08-21",
                    "entry_time": datetime.now(timezone.utc).isoformat(),
                    "credit": 1.0,
                    "quantity": 1,
                    "strikes": {"short_put": 700.0, "long_put": 695.0},
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(pcs, "ENTRIES_FILE", entries_path)
    client = MagicMock()
    client.get_all_positions.return_value = []
    client.get_order_by_id.return_value = SimpleNamespace(status="NEW")

    report = pcs.manage_put_credit_exits(client, dry_run=False)

    assert report["pending"] == 1
    assert report["broken"] == 0
    saved = json.loads(entries_path.read_text(encoding="utf-8"))
    assert saved["PCS_260821_order1"]["status"] == "entry_pending"


def test_put_credit_exit_manager_dry_run_flags_orphan_cleanup(tmp_path, monkeypatch):
    from scripts import spy_put_credit as pcs

    entries_path = tmp_path / "put_credit_entries.json"
    entries_path.write_text(
        json.dumps(
            {
                "PCS_260821_order1": {
                    "status": "open",
                    "order_id": "order-1",
                    "expiry": "2026-08-21",
                    "entry_time": datetime.now(timezone.utc).isoformat(),
                    "credit": 1.0,
                    "quantity": 1,
                    "strikes": {"short_put": 700.0, "long_put": 695.0},
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(pcs, "ENTRIES_FILE", entries_path)
    client = MagicMock()
    client.get_all_positions.return_value = [
        SimpleNamespace(
            symbol="SPY260821P00700000",
            qty="-1",
            current_price="1.00",
            avg_entry_price="1.20",
        )
    ]
    client.get_order_by_id.return_value = SimpleNamespace(status="FILLED")

    report = pcs.manage_put_credit_exits(client, dry_run=True)

    assert report["broken"] == 1
    assert report["would_exit"] == 1
    assert report["details"][0]["status"] == "would_close_orphan"


def test_schedule_manages_put_credit_exits_every_weekday_slot():
    workflow = (
        Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ic-simple.yml"
    ).read_text(encoding="utf-8")
    assert "Manage put-credit exits" in workflow
    assert "--manage-exits" in workflow
