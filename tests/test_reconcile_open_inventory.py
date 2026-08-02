"""Tests for surgical open-inventory reconcile planner."""

from types import SimpleNamespace

import pytest

from scripts.reconcile_open_inventory import (
    _expected_from_ic_entries,
    _expected_from_put_credit,
    broker_confirmed_expected,
    plan_reductions,
)
from tests.test_residual_ic_manager import _open, _position
from datetime import UTC


def test_plan_reduces_extra_call_lot_and_orphan_put():
    entries = {
        "IC_260821": {
            "quantity": 1,
            "strikes": {
                "short_put": 708.0,
                "long_put": 703.0,
                "short_call": 776.0,
                "long_call": 781.0,
            },
        }
    }
    expected = _expected_from_ic_entries(entries)
    # broker dirty book
    legs = [
        {"symbol": "SPY260821C00776000", "qty": -2.0},
        {"symbol": "SPY260821C00781000", "qty": 2.0},
        {"symbol": "SPY260821P00703000", "qty": 1.0},
        {"symbol": "SPY260821P00708000", "qty": -1.0},
        {"symbol": "SPY260821P00695000", "qty": 1.0},
        {"symbol": "SPY260821P00700000", "qty": -1.0},
    ]
    actions = plan_reductions(legs, expected)
    by_sym = {a["symbol"]: a for a in actions}
    # excess call short: buy 1
    assert by_sym["SPY260821C00776000"]["side"] == "buy"
    assert by_sym["SPY260821C00776000"]["qty"] == 1.0
    # excess call long: sell 1
    assert by_sym["SPY260821C00781000"]["side"] == "sell"
    assert by_sym["SPY260821C00781000"]["qty"] == 1.0
    # orphan put vertical fully closed
    assert by_sym["SPY260821P00700000"]["side"] == "buy"
    assert by_sym["SPY260821P00700000"]["qty"] == 1.0
    assert by_sym["SPY260821P00695000"]["side"] == "sell"
    assert by_sym["SPY260821P00695000"]["qty"] == 1.0
    # journaled puts not reduced
    assert "SPY260821P00708000" not in by_sym
    assert "SPY260821P00703000" not in by_sym


def test_clean_book_no_actions():
    entries = {
        "IC_260821": {
            "quantity": 1,
            "strikes": {
                "short_put": 708.0,
                "long_put": 703.0,
                "short_call": 776.0,
                "long_call": 781.0,
            },
        }
    }
    expected = _expected_from_ic_entries(entries)
    legs = [
        {"symbol": "SPY260821C00776000", "qty": -1.0},
        {"symbol": "SPY260821C00781000", "qty": 1.0},
        {"symbol": "SPY260821P00703000", "qty": 1.0},
        {"symbol": "SPY260821P00708000", "qty": -1.0},
    ]
    assert plan_reductions(legs, expected) == []


def test_broker_orders_preserve_two_valid_ics_with_shared_call_vertical():
    from datetime import datetime

    older = datetime(2026, 7, 17, 15, 36, tzinfo=UTC)
    newer = datetime(2026, 7, 21, 15, 40, tzinfo=UTC)
    orders = [
        _open("older", older, 695, 700, (3.40, 3.80, 2.04, 1.32)),
        _open("newer", newer, 703, 708, (2.96, 3.37, 1.85, 1.15)),
    ]
    positions = [
        _position("SPY260821P00695000", 1, 2.0),
        _position("SPY260821P00700000", -1, 2.3),
        _position("SPY260821P00703000", 1, 2.5),
        _position("SPY260821P00708000", -1, 2.9),
        _position("SPY260821C00776000", -2, 1.2),
        _position("SPY260821C00781000", 2, 0.7),
    ]

    expected, evidence = broker_confirmed_expected(positions, orders, [], {})
    actual = [{"symbol": pos.symbol, "qty": float(pos.qty)} for pos in positions]

    assert plan_reductions(actual, expected) == []
    assert expected["SPY260821C00776000"] == -2
    assert expected["SPY260821C00781000"] == 2
    assert evidence["recovered_ic_structures"] == 2


def test_broker_authority_fails_closed_on_unexplained_leg():
    positions = [_position("SPY260821P00695000", 1, 2.0)]
    with pytest.raises(RuntimeError, match="unexplained broker inventory"):
        broker_confirmed_expected(positions, [], [], {})


def test_broker_authority_fails_closed_on_pending_option_order():
    pending = SimpleNamespace(
        id="pending-close",
        symbol=None,
        legs=[SimpleNamespace(symbol="SPY260821P00695000")],
    )
    with pytest.raises(RuntimeError, match="pending option orders"):
        broker_confirmed_expected([], [], [pending], {})


def test_reconcile_pcs_expectations_use_unique_key_and_ignore_closed_rows():
    entries = {
        "PCS_260821_order1": {
            "status": "open",
            "expiry": "2026-08-21",
            "quantity": 1,
            "strikes": {"short_put": 700.0, "long_put": 695.0},
        },
        "PCS_260821_order2": {
            "status": "closed",
            "expiry": "2026-08-21",
            "quantity": 1,
            "strikes": {"short_put": 690.0, "long_put": 685.0},
        },
    }

    expected = _expected_from_put_credit(entries)

    assert expected == {
        "SPY260821P00700000": -1.0,
        "SPY260821P00695000": 1.0,
    }


def _isolate_reconcile_files(module, tmp_path, monkeypatch):
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "ENTRIES", tmp_path / "ic_entries.json")
    monkeypatch.setattr(module, "PCS_ENTRIES", tmp_path / "put_credit_entries.json")


def test_main_rejects_execution_from_untrusted_state(monkeypatch):
    from scripts import reconcile_open_inventory as reconcile

    monkeypatch.setattr(
        "sys.argv", ["reconcile_open_inventory.py", "--execute-paper", "--from-state"]
    )
    assert reconcile.main() == 2


def test_main_from_state_with_no_legs_is_clean(tmp_path, monkeypatch):
    from scripts import reconcile_open_inventory as reconcile

    _isolate_reconcile_files(reconcile, tmp_path, monkeypatch)
    monkeypatch.setattr("sys.argv", ["reconcile_open_inventory.py", "--from-state"])
    monkeypatch.setattr(reconcile, "load_legs_from_state", lambda: [])

    assert reconcile.main() == 0


def test_main_broker_failure_falls_back_only_for_dry_run(tmp_path, monkeypatch):
    from scripts import reconcile_open_inventory as reconcile

    _isolate_reconcile_files(reconcile, tmp_path, monkeypatch)
    monkeypatch.setattr("sys.argv", ["reconcile_open_inventory.py", "--dry-run"])
    monkeypatch.setattr(
        reconcile,
        "load_legs_from_broker",
        lambda: (_ for _ in ()).throw(RuntimeError("broker unavailable")),
    )
    monkeypatch.setattr(
        reconcile,
        "load_legs_from_state",
        lambda: [{"symbol": "SPY260821P00700000", "qty": -1.0}],
    )

    assert reconcile.main() == 0
    assert (tmp_path / "data" / "audit" / "inventory_reconcile_plan.json").exists()


def test_main_broker_failure_blocks_execution(tmp_path, monkeypatch):
    from scripts import reconcile_open_inventory as reconcile

    _isolate_reconcile_files(reconcile, tmp_path, monkeypatch)
    monkeypatch.setattr("sys.argv", ["reconcile_open_inventory.py", "--execute-paper"])
    monkeypatch.setattr(
        reconcile,
        "load_legs_from_broker",
        lambda: (_ for _ in ()).throw(RuntimeError("broker unavailable")),
    )

    assert reconcile.main() == 2


def test_main_blocks_when_broker_reconstruction_is_unexplained(tmp_path, monkeypatch):
    from scripts import reconcile_open_inventory as reconcile
    from scripts import residual_ic_manager

    _isolate_reconcile_files(reconcile, tmp_path, monkeypatch)
    monkeypatch.setattr("sys.argv", ["reconcile_open_inventory.py", "--dry-run"])
    monkeypatch.setattr(
        reconcile,
        "load_legs_from_broker",
        lambda: (
            object(),
            [{"symbol": "SPY260821P00700000", "qty": -1.0}],
            [SimpleNamespace(symbol="SPY260821P00700000", qty="-1")],
        ),
    )
    monkeypatch.setattr(residual_ic_manager, "_get_orders", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        reconcile,
        "broker_confirmed_expected",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("unexplained")),
    )

    assert reconcile.main() == 2
