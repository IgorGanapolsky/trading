"""Tests for strategy kill switch and active put-credit successor."""

from __future__ import annotations

import json
from contextlib import nullcontext
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


def test_find_put_credit_scans_chain_once_and_uses_put_side_only(monkeypatch):
    import sys
    import types

    from scripts import spy_put_credit as pcs

    expiry = "2026-08-28"
    chain = [
        {
            "expiration": expiry,
            "type": "put",
            "strike": 700.0,
            "bid": 1.20,
            "ask": 1.25,
            "delta": -0.15,
        },
        {
            "expiration": expiry,
            "type": "put",
            "strike": 695.0,
            "bid": 0.35,
            "ask": 0.40,
            "delta": -0.12,
        },
        {
            "expiration": expiry,
            "type": "call",
            "strike": 800.0,
            "bid": 3.00,
            "ask": 3.10,
            "delta": 0.15,
        },
    ]
    provider = MagicMock()
    provider.get_options_chain_with_greeks.return_value = chain

    # Inject a stub module so the late import inside find_put_credit_opportunity
    # does not pull real pandas/alpaca deps in unit tests.
    stub = types.ModuleType("src.data.iv_data_provider")
    stub.IVDataProvider = lambda: provider
    monkeypatch.setitem(sys.modules, "src.data.iv_data_provider", stub)
    monkeypatch.setattr(pcs, "_friday_expiries", lambda *_: [expiry])
    opp = pcs.find_put_credit_opportunity(747.0)

    assert opp is not None
    assert opp["short_put"] == 700.0
    assert opp["long_put"] == 695.0
    assert opp["est_credit"] == 0.80
    assert opp["method"] == "live_delta_band_scan"
    assert "short_call" not in opp
    provider.get_options_chain_with_greeks.assert_called_once_with(
        symbol="SPY",
        min_open_interest=0,
    )


def test_find_put_credit_prefers_higher_credit_then_target_delta(monkeypatch):
    """Fillability first: higher natural credit ranks above closer-to-target delta."""
    from scripts import spy_put_credit as pcs

    expiry = "2026-08-28"
    chain = [
        {
            "expiration": expiry,
            "type": "put",
            "strike": 700.0,
            "bid": 1.10,
            "ask": 1.20,
            "delta": -0.15,
        },
        {
            "expiration": expiry,
            "type": "put",
            "strike": 695.0,
            "bid": 0.40,
            "ask": 0.50,
            "delta": -0.12,
        },
        {
            "expiration": expiry,
            "type": "put",
            "strike": 690.0,
            "bid": 1.50,
            "ask": 1.60,
            "delta": -0.19,
        },
        {
            "expiration": expiry,
            "type": "put",
            "strike": 685.0,
            "bid": 0.25,
            "ask": 0.30,
            "delta": -0.16,
        },
    ]
    provider = MagicMock()
    provider.get_options_chain_with_greeks.return_value = chain
    monkeypatch.setattr("src.data.iv_data_provider.IVDataProvider", lambda: provider)
    monkeypatch.setattr(pcs, "_friday_expiries", lambda *_: [expiry])

    opp = pcs.find_put_credit_opportunity(747.0)

    assert opp is not None
    # short=690 / long=685 → natural credit 1.50-0.30=1.20 beats 700/695 at 0.60
    assert opp["short_put"] == 690.0
    assert opp["put_delta"] == 0.19
    assert opp["est_credit"] == 1.20


def test_find_put_credit_keeps_minimum_credit_fail_closed(monkeypatch):
    from scripts import spy_put_credit as pcs

    expiry = "2026-08-28"
    provider = MagicMock()
    provider.get_options_chain_with_greeks.return_value = [
        {
            "expiration": expiry,
            "type": "put",
            "strike": 700.0,
            "bid": 0.80,
            "ask": 0.85,
            "delta": -0.15,
        },
        {
            "expiration": expiry,
            "type": "put",
            "strike": 695.0,
            "bid": 0.40,
            "ask": 0.45,
            "delta": -0.12,
        },
    ]
    monkeypatch.setattr("src.data.iv_data_provider.IVDataProvider", lambda: provider)
    monkeypatch.setattr(pcs, "_friday_expiries", lambda *_: [expiry])

    assert pcs.find_put_credit_opportunity(747.0) is None


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


def test_reconcile_put_credit_entries_recovers_exact_filled_structure(tmp_path, monkeypatch):
    from scripts import spy_put_credit as pcs

    entries_path = tmp_path / "put_credit_entries.json"
    audit_dir = tmp_path / "audit"
    monkeypatch.setattr(pcs, "ENTRIES_FILE", entries_path)
    monkeypatch.setattr(pcs, "AUDIT_DIR", audit_dir)
    pcs.write_plan(
        {
            "dry_run": False,
            "planned_at": "2026-07-23T15:37:05.285607+00:00",
            "opportunity": {
                "expiry": "2026-08-28",
                "short_put": 696.0,
                "long_put": 691.0,
                "est_credit": 0.54,
                "put_delta": 0.1843,
                "method": "live_delta_band_scan",
                "spy_price": 736.6,
            },
        }
    )
    pcs.write_plan(
        {
            "dry_run": True,
            "planned_at": "2026-07-23T16:00:00+00:00",
            "opportunity": None,
        }
    )
    pcs.write_plan(
        {
            "dry_run": False,
            "planned_at": "2026-07-23T15:47:08.050702+00:00",
            "opportunity": {
                "expiry": "2026-08-28",
                "short_put": 696.0,
                "long_put": 691.0,
                "est_credit": 0.80,
                "put_delta": 0.2999,
                "method": "later_execution_attempt",
                "spy_price": 735.0,
            },
        }
    )
    order = SimpleNamespace(
        id="4fc04e47-a2da-4fe9-ab28-14cdad69ab44",
        client_order_id="IC-OPEN-BPS--1784821027308661000000",
        status="FILLED",
        qty="1",
        filled_qty="1",
        filled_avg_price="-0.53",
        limit_price="-0.50",
        submitted_at=datetime.fromisoformat("2026-07-23T15:37:08.002050+00:00"),
        filled_at=datetime.fromisoformat("2026-07-23T15:37:08.050702+00:00"),
        legs=[
            SimpleNamespace(
                symbol="SPY260828P00691000",
                side="BUY",
                filled_avg_price="4.68",
            ),
            SimpleNamespace(
                symbol="SPY260828P00696000",
                side="SELL",
                filled_avg_price="5.21",
            ),
        ],
    )
    client = MagicMock()
    client.get_orders.return_value = [order]
    client.get_all_positions.return_value = [
        SimpleNamespace(symbol="SPY260828P00691000", qty="1"),
        SimpleNamespace(symbol="SPY260828P00696000", qty="-1"),
    ]

    report = pcs.reconcile_put_credit_entries(client)

    assert report["recovered"] == 1
    assert report["broken"] == 0
    saved = json.loads(entries_path.read_text(encoding="utf-8"))
    entry = saved["PCS_260828_4fc04e47a2da4fe9ab2814cdad69ab44"]
    assert entry["credit"] == 0.53
    assert entry["limit_credit"] == 0.5
    assert entry["put_delta"] == 0.1843
    assert entry["put_delta_source"] == "execution_plan_snapshot"
    assert entry["selection_method"] == "live_delta_band_scan"
    assert entry["strikes"] == {"short_put": 696.0, "long_put": 691.0}
    assert entry["status"] == "open"

    second = pcs.reconcile_put_credit_entries(client)
    assert second["existing"] == 1
    assert second["recovered"] == 0


def test_reconcile_put_credit_entries_keeps_unknown_selection_unverified(tmp_path, monkeypatch):
    from scripts import spy_put_credit as pcs

    monkeypatch.setattr(pcs, "ENTRIES_FILE", tmp_path / "put_credit_entries.json")
    monkeypatch.setattr(pcs, "AUDIT_DIR", tmp_path / "missing-audit")
    order = SimpleNamespace(
        id="order-no-plan",
        client_order_id="IC-OPEN-BPS--1784821027308661000001",
        status="FILLED",
        qty="1",
        filled_qty="1",
        filled_avg_price="-0.60",
        limit_price="-0.55",
        submitted_at=datetime.fromisoformat("2026-07-23T15:37:08+00:00"),
        filled_at=datetime.fromisoformat("2026-07-23T15:37:09+00:00"),
        legs=[
            SimpleNamespace(symbol="SPY260828P00690000", side="BUY", filled_avg_price="4.60"),
            SimpleNamespace(symbol="SPY260828P00695000", side="SELL", filled_avg_price="5.20"),
        ],
    )
    client = MagicMock()
    client.get_orders.return_value = [order]
    client.get_all_positions.return_value = [
        SimpleNamespace(symbol="SPY260828P00690000", qty="1"),
        SimpleNamespace(symbol="SPY260828P00695000", qty="-1"),
    ]

    report = pcs.reconcile_put_credit_entries(client)

    assert report["recovered"] == 1
    entry = next(iter(json.loads(pcs.ENTRIES_FILE.read_text(encoding="utf-8")).values()))
    assert entry["put_delta"] is None
    assert entry["put_delta_source"] == "unavailable_after_broker_reconstruction"
    assert entry["selection_method"] == "broker_reconstructed_unverified"

    closed_path = tmp_path / "closed_put_credit_entries.json"
    monkeypatch.setattr(pcs, "ENTRIES_FILE", closed_path)
    client.get_all_positions.return_value = []
    inactive = pcs.reconcile_put_credit_entries(client)
    assert inactive["inactive_filled_orders"] == 1
    assert inactive["recovered"] == 0
    assert not closed_path.exists()


def test_malformed_historical_put_credit_does_not_block_exit_workflow(tmp_path, monkeypatch):
    from scripts import spy_put_credit as pcs

    monkeypatch.setattr(pcs, "ENTRIES_FILE", tmp_path / "put_credit_entries.json")
    malformed = SimpleNamespace(
        id="malformed-history",
        client_order_id="IC-OPEN-BPS--1784821027308661000002",
        status="FILLED",
        filled_at=datetime.fromisoformat("2026-07-20T15:37:09+00:00"),
        legs=[],
    )
    client = MagicMock()
    client.get_orders.return_value = [malformed]
    client.get_all_positions.return_value = []

    report = pcs.reconcile_put_credit_entries(client)

    assert report["invalid_filled_orders"] == 1
    assert report["broken"] == 0
    assert report["recovered"] == 0


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
    # limit starts at natural est_credit (1.00), not est-0.05 — improves fill rate
    assert float(captured["request"].limit_price) == -1.0
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
        },
        "PCS_2": {
            "status": "open",
            "entry_time": now.isoformat(),
            "signature": "same2",
        },
        "PCS_3": {
            "status": "open",
            "entry_time": now.isoformat(),
            "signature": "same3",
        },
    }

    report = pcs.evaluate_entry_limits(entries, candidate_signature="same", now=now)

    assert report["allowed"] is False
    assert report["today_count"] == 3
    assert any("Daily" in blocker for blocker in report["blockers"])
    assert any("signature" in blocker for blocker in report["blockers"])

    entries["PCS_4"] = {
        "status": "open",
        "entry_time": (now - timedelta(days=1)).isoformat(),
        "signature": "different",
    }
    report = pcs.evaluate_entry_limits(entries, now=now)
    assert report["active_count"] == 4
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


def test_partial_exit_fill_remains_managed_as_pending():
    from scripts import spy_put_credit as pcs

    entry = {"status": "exit_pending", "exit_order_id": "close-1"}
    client = MagicMock()
    client.get_order_by_id.return_value = SimpleNamespace(status="PARTIALLY_FILLED")

    assert pcs._pending_exit_is_active(client, entry) is True
    assert entry["status"] == "exit_pending"
    assert "exit_filled_at" not in entry

    client.get_order_by_id.return_value = SimpleNamespace(status="FILLED")
    assert pcs._pending_exit_is_active(client, entry) is True
    assert entry["status"] == "closed"
    assert entry["exit_filled_at"]


def test_submitted_exit_is_saved_before_later_entry_failure(tmp_path, monkeypatch):
    from scripts import spy_put_credit as pcs

    now = datetime.now(timezone.utc)
    entries_path = tmp_path / "put_credit_entries.json"
    entries_path.write_text(
        json.dumps(
            {
                "PCS_260821_first": {
                    "status": "open",
                    "expiry": "2026-08-21",
                    "entry_time": (now - timedelta(days=2)).isoformat(),
                    "credit": 1.0,
                    "credit_source": "broker_fill",
                    "quantity": 1,
                    "strikes": {"short_put": 700.0, "long_put": 695.0},
                },
                "PCS_260821_second": {
                    "status": "open",
                    "expiry": "2026-08-21",
                    "entry_time": (now - timedelta(days=2)).isoformat(),
                    "credit": 1.0,
                    "credit_source": "broker_fill",
                    "quantity": 1,
                    "strikes": {"short_put": 690.0, "long_put": 685.0},
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(pcs, "ENTRIES_FILE", entries_path)
    client = MagicMock()
    client.get_all_positions.return_value = [
        SimpleNamespace(symbol="SPY260821P00700000", qty="-1", current_price="0.60"),
        SimpleNamespace(symbol="SPY260821P00695000", qty="1", current_price="0.10"),
        SimpleNamespace(symbol="SPY260821P00690000", qty="-1", current_price="0.60"),
        SimpleNamespace(symbol="SPY260821P00685000", qty="1", current_price="0.10"),
    ]
    monkeypatch.setattr(
        pcs,
        "_submit_spread_close",
        MagicMock(side_effect=[SimpleNamespace(id="close-first"), RuntimeError("later failure")]),
    )

    with pytest.raises(RuntimeError, match="later failure"):
        pcs.manage_put_credit_exits(client, dry_run=False)

    saved = json.loads(entries_path.read_text(encoding="utf-8"))
    assert saved["PCS_260821_first"]["status"] == "exit_pending"
    assert saved["PCS_260821_first"]["exit_order_id"] == "close-first"
    assert saved["PCS_260821_second"]["status"] == "open"


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
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "put-credit-validation.yml"
    ).read_text(encoding="utf-8")
    assert "Manage put-credit exits" in workflow
    assert "--manage-exits" in workflow
    assert "--reconcile-entries" in workflow
    assert workflow.index("--reconcile-entries") < workflow.index("residual_ic_manager.py")
    assert '"${{ steps.mode.outputs.dry_run }}"' not in workflow
    assert 'MODE="${{ github.event.inputs.mode' not in workflow


def test_schedule_preserves_trigger_intent_when_github_delivers_late():
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "put-credit-validation.yml"
    ).read_text(encoding="utf-8")
    determine_mode = workflow.split("- name: Determine mode", 1)[1].split(
        "- name: Reconcile filled put-credit journals", 1
    )[0]

    assert "SCHEDULE_EXPRESSION: ${{ github.event.schedule || '' }}" in determine_mode
    assert 'case "$SCHEDULE_EXPRESSION" in' in determine_mode
    assert '"0 15 * * 1-5")' in determine_mode
    assert "RUN_PUT_CREDIT=true" in determine_mode
    assert "date -u +%H" not in determine_mode
    assert "date -u +%u" not in determine_mode


def test_put_credit_inventory_gate_fails_closed_on_broker_exception(monkeypatch):
    from scripts import spy_put_credit as pcs

    monkeypatch.setattr(
        pcs, "_get_paper_client", MagicMock(side_effect=RuntimeError("broker offline"))
    )
    assert pcs._inventory_ok() is False


def test_put_credit_parsing_and_credit_confirmation_failure_paths(tmp_path, monkeypatch):
    from scripts import spy_put_credit as pcs

    entries = tmp_path / "put_credit_entries.json"
    entries.write_text("[]\n", encoding="utf-8")
    monkeypatch.setattr(pcs, "ENTRIES_FILE", entries)
    with pytest.raises(ValueError, match="Expected object"):
        pcs._load_entries()

    assert pcs._parse_timestamp(None) is None
    assert pcs._parse_timestamp("not-a-timestamp") is None
    assert pcs._parse_timestamp("2026-07-22T12:00:00").tzinfo == timezone.utc
    assert pcs._expiry_yymmdd({"expiry": "260821"}) == "260821"
    assert pcs._expiry_yymmdd({"signature": "SPY_2026-08-21_P695-700"}) == "260821"
    assert pcs._expiry_yymmdd({}) == ""

    with pytest.raises(ValueError, match="no parseable expiry"):
        pcs.evaluate_put_credit_exit({}, short_price=1.0, long_price=0.5)
    assignment = pcs.evaluate_put_credit_exit(
        {
            "expiry": "2026-07-23",
            "entry_time": "2026-07-20T12:00:00+00:00",
            "credit": 1.0,
        },
        short_price=1.0,
        long_price=0.5,
        now=datetime(2026, 7, 22, 12, 0),
    )
    assert assignment["exit_reason"] == "assignment_failsafe"

    short = SimpleNamespace(avg_entry_price="1.20")
    long = SimpleNamespace(avg_entry_price="0.20")
    filled = {"order_id": "entry-1"}
    client = MagicMock()
    client.get_order_by_id.return_value = SimpleNamespace(filled_avg_price="0.95")
    assert pcs._confirm_entry_credit(client, filled, short, long) is True
    assert filled["credit_source"] == "broker_fill"

    derived = {"order_id": "entry-2"}
    client.get_order_by_id.side_effect = RuntimeError("lookup failed")
    assert pcs._confirm_entry_credit(client, derived, short, long) is True
    assert derived["credit_source"] == "broker_position_derived"
    assert (
        pcs._confirm_entry_credit(
            client,
            {"order_id": "entry-3"},
            SimpleNamespace(avg_entry_price="0.10"),
            SimpleNamespace(avg_entry_price="0.20"),
        )
        is False
    )


def test_put_credit_pending_and_entry_status_failure_paths():
    from scripts import spy_put_credit as pcs

    client = MagicMock()
    assert pcs._pending_exit_is_active(client, {}) is False
    client.get_order_by_id.side_effect = RuntimeError("temporarily unavailable")
    assert pcs._pending_exit_is_active(client, {"exit_order_id": "close-1"}) is True

    cancelled = {"status": "exit_pending", "exit_order_id": "close-2"}
    client.get_order_by_id.side_effect = None
    client.get_order_by_id.return_value = SimpleNamespace(status="CANCELED")
    assert pcs._pending_exit_is_active(client, cancelled) is False
    assert cancelled == {"status": "open"}

    assert pcs._entry_order_status(client, {}) == "UNKNOWN"
    client.get_order_by_id.side_effect = RuntimeError("lookup failed")
    assert pcs._entry_order_status(client, {"order_id": "entry-1"}) == "UNKNOWN"


def _patch_put_credit_cli_basics(pcs, monkeypatch):
    state = SimpleNamespace(
        active_family="spy_put_credit",
        killed_families=("ic_simple",),
        live_blocked=True,
    )
    monkeypatch.setattr("src.core.active_strategy.load_kill_state", lambda: state)
    monkeypatch.setattr(pcs, "_assert_active", lambda: None)
    # Entry path always hits regime gate; keep unit tests independent of live IVR/VIX.
    from src.risk.put_credit_regime import RegimeSnapshot

    allowed_snap = RegimeSnapshot(
        captured_at="2026-08-02T00:00:00+00:00",
        spy_price=747.0,
        vix=16.0,
        iv_rank_proxy=55.0,
        iv_rank_method="test",
        spy_sma_200=700.0,
        spy_above_200dma=True,
        source_errors=(),
    )
    monkeypatch.setattr(
        "src.risk.put_credit_regime.capture_regime_snapshot",
        lambda *_a, **_k: allowed_snap,
    )
    monkeypatch.setattr(
        "src.risk.put_credit_regime.evaluate_regime_gate",
        lambda *_a, **_k: {
            "allowed": True,
            "blockers": [],
            "soft_flags": [],
            "thresholds": {},
            "snapshot": allowed_snap.as_dict(),
        },
    )
    return state


def test_put_credit_main_manage_exit_client_failure(monkeypatch):
    from scripts import spy_put_credit as pcs

    _patch_put_credit_cli_basics(pcs, monkeypatch)
    monkeypatch.setattr("sys.argv", ["spy_put_credit.py", "--manage-exits"])
    monkeypatch.setattr(
        pcs, "_get_paper_client", MagicMock(side_effect=RuntimeError("client failed"))
    )
    assert pcs.main() == 1


def test_put_credit_main_manage_exit_reports_broken(monkeypatch, capsys):
    from scripts import spy_put_credit as pcs

    _patch_put_credit_cli_basics(pcs, monkeypatch)
    monkeypatch.setattr("sys.argv", ["spy_put_credit.py", "--manage-exits", "--dry-run"])
    monkeypatch.setattr(pcs, "_get_paper_client", lambda: object())
    monkeypatch.setattr(pcs, "manage_put_credit_exits", lambda client, dry_run: {"broken": 1})
    assert pcs.main() == 2
    assert '"broken": 1' in capsys.readouterr().out


def test_put_credit_main_blocks_at_initial_entry_limit(monkeypatch, capsys):
    from scripts import spy_put_credit as pcs

    _patch_put_credit_cli_basics(pcs, monkeypatch)
    monkeypatch.setattr("sys.argv", ["spy_put_credit.py", "--dry-run"])
    monkeypatch.setattr(pcs, "_inventory_ok", lambda *_args: True)
    monkeypatch.setattr(pcs, "_load_entries", lambda: {})
    monkeypatch.setattr(
        pcs,
        "evaluate_entry_limits",
        lambda *_args, **_kwargs: {"allowed": False, "blockers": ["daily cap"]},
    )
    assert pcs.main() == 2
    assert "daily cap" in capsys.readouterr().out


def test_put_credit_main_blocks_duplicate_after_selection(tmp_path, monkeypatch, capsys):
    from scripts import spy_put_credit as pcs

    _patch_put_credit_cli_basics(pcs, monkeypatch)
    monkeypatch.setattr("sys.argv", ["spy_put_credit.py", "--dry-run"])
    monkeypatch.setattr(pcs, "AUDIT_DIR", tmp_path)
    monkeypatch.setattr(pcs, "_inventory_ok", lambda *_args: True)
    monkeypatch.setattr(pcs, "_load_entries", lambda: {})
    monkeypatch.setattr("src.utils.options_analysis.get_underlying_price", lambda _: 747.0)
    monkeypatch.setattr(pcs, "find_put_credit_opportunity", lambda _: _put_credit_opp())
    allowed = {"allowed": True, "blockers": []}
    blocked = {"allowed": False, "blockers": ["duplicate signature"]}
    monkeypatch.setattr(pcs, "evaluate_entry_limits", MagicMock(side_effect=[allowed, blocked]))

    assert pcs.main() == 2
    assert "duplicate signature" in capsys.readouterr().out


def test_put_credit_main_rechecks_limits_inside_trade_lock(tmp_path, monkeypatch):
    from scripts import spy_put_credit as pcs

    _patch_put_credit_cli_basics(pcs, monkeypatch)
    monkeypatch.setattr("sys.argv", ["spy_put_credit.py", "--execute-paper"])
    monkeypatch.setattr(pcs, "AUDIT_DIR", tmp_path)
    monkeypatch.setattr(pcs, "_inventory_ok", lambda *_args: True)
    monkeypatch.setattr(pcs, "_load_entries", lambda: {})
    monkeypatch.setattr("src.utils.options_analysis.get_underlying_price", lambda _: 747.0)
    monkeypatch.setattr(pcs, "find_put_credit_opportunity", lambda _: _put_credit_opp())
    monkeypatch.setattr(pcs, "_get_paper_client", lambda: object())
    monkeypatch.setattr("src.safety.trade_lock.acquire_trade_lock", lambda **_: nullcontext())
    allowed = {"allowed": True, "blockers": []}
    blocked = {"allowed": False, "blockers": ["concurrent cap"]}
    monkeypatch.setattr(
        pcs, "evaluate_entry_limits", MagicMock(side_effect=[allowed, allowed, blocked])
    )

    assert pcs.main() == 2
