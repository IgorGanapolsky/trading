from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from scripts.residual_ic_manager import (
    _close_signature,
    _order_signature,
    active_pcs_expected,
    evaluate_residual_exit,
    manage_residual_ics,
    recover_active_structures,
    unresolved_after_pcs,
)


def _leg(symbol, side, fill):
    return SimpleNamespace(
        symbol=symbol,
        side=side,
        qty="1",
        filled_qty="1",
        filled_avg_price=str(fill),
    )


def _open(order_id, when, put_long, put_short, credit_parts):
    lp, sp, sc, lc = credit_parts
    return SimpleNamespace(
        id=order_id,
        client_order_id=f"IC-OPEN-IC--{int(when.timestamp() * 1_000_000_000)}",
        status="FILLED",
        qty="1",
        filled_qty="1",
        created_at=when,
        filled_at=when,
        legs=[
            _leg(f"SPY260821P{int(put_long * 1000):08d}", "BUY", lp),
            _leg(f"SPY260821P{int(put_short * 1000):08d}", "SELL", sp),
            _leg("SPY260821C00776000", "SELL", sc),
            _leg("SPY260821C00781000", "BUY", lc),
        ],
    )


def _position(symbol, qty, current):
    return SimpleNamespace(symbol=symbol, qty=str(qty), current_price=str(current))


def test_recovers_two_same_expiry_structures_with_shared_call_vertical():
    older = datetime(2026, 7, 17, 15, 36, tzinfo=timezone.utc)
    newer = datetime(2026, 7, 21, 15, 40, tzinfo=timezone.utc)
    orders = [
        _open("38126b7550dd49e5939f", older, 695, 700, (3.40, 3.80, 2.04, 1.32)),
        _open("12d3f8817beb46a0b445", newer, 703, 708, (2.96, 3.37, 1.85, 1.15)),
    ]
    positions = [
        _position("SPY260821P00695000", 1, 2.0),
        _position("SPY260821P00700000", -1, 2.3),
        _position("SPY260821P00703000", 1, 2.5),
        _position("SPY260821P00708000", -1, 2.9),
        _position("SPY260821C00776000", -2, 1.2),
        _position("SPY260821C00781000", 2, 0.7),
    ]

    recovered, unresolved = recover_active_structures(positions, orders)

    assert len(recovered) == 2
    assert unresolved == {}
    assert sorted(item["credit"] for item in recovered) == [1.11, 1.12]


def test_recovery_reports_unexplained_live_leg():
    positions = [_position("SPY260821P00695000", 1, 2.0)]
    recovered, unresolved = recover_active_structures(positions, [])
    assert recovered == []
    assert unresolved == {"SPY260821P00695000": 1.0}


def test_active_pcs_legs_are_not_residual_ic_breakage():
    entries = {
        "PCS_260821_open": {
            "status": "open",
            "expiry": "2026-08-21",
            "quantity": 1,
            "strikes": {"short_put": 700.0, "long_put": 695.0},
        },
        "PCS_260821_closed": {
            "status": "closed",
            "expiry": "2026-08-21",
            "quantity": 1,
            "strikes": {"short_put": 690.0, "long_put": 685.0},
        },
    }
    expected = active_pcs_expected(entries)
    unresolved = {
        "SPY260821P00700000": -1.0,
        "SPY260821P00695000": 1.0,
    }

    unexplained, matched = unresolved_after_pcs(unresolved, expected)

    assert unexplained == {}
    assert matched == unresolved
    assert "SPY260821P00690000" not in expected


def test_residual_manager_allows_active_pcs_inventory(tmp_path, monkeypatch):
    import scripts.residual_ic_manager as manager

    positions = [
        _position("SPY260821P00700000", -1, 1.0),
        _position("SPY260821P00695000", 1, 0.2),
    ]
    expected = {
        "SPY260821P00700000": -1.0,
        "SPY260821P00695000": 1.0,
    }
    client = SimpleNamespace(get_all_positions=lambda: positions)
    monkeypatch.setattr(manager, "ROOT", tmp_path)
    monkeypatch.setattr(manager, "AUDIT_PATH", tmp_path / "residual.json")
    monkeypatch.setattr(manager, "_get_orders", lambda *args, **kwargs: [])
    monkeypatch.setattr(manager, "_load_active_pcs_expected", lambda: expected)

    report = manage_residual_ics(client, dry_run=True)

    assert report["broken"] == 0
    assert report["unresolved"] == {}
    assert report["pcs_inventory_excluded"] == expected


def test_exit_rules_respect_hold_and_trigger_profit_after_24h():
    structure = {
        "expiry_yymmdd": "260821",
        "entry_time": "2026-07-21T15:40:00+00:00",
        "credit": 1.0,
        "quantity": 1,
        "legs": [
            {"qty": -1, "current_price": 0.7},
            {"qty": 1, "current_price": 0.2},
            {"qty": -1, "current_price": 0.4},
            {"qty": 1, "current_price": 0.1},
        ],
    }
    held = evaluate_residual_exit(structure, now=datetime(2026, 7, 21, 20, 0, tzinfo=timezone.utc))
    profit = evaluate_residual_exit(
        structure, now=datetime(2026, 7, 22, 20, 0, tzinfo=timezone.utc)
    )
    assert held["should_exit"] is False
    assert profit["should_exit"] is False  # $20 P/L is below the $50 target

    structure["legs"][0]["current_price"] = 0.3
    profit = evaluate_residual_exit(
        structure, now=datetime(2026, 7, 22, 20, 0, tzinfo=timezone.utc)
    )
    assert profit["should_exit"] is True
    assert profit["exit_reason"] == "profit_target"


def test_pending_close_signature_matches_structure():
    structure = {
        "legs": [
            {"symbol": "SPY260821P00703000", "qty": 1},
            {"symbol": "SPY260821P00708000", "qty": -1},
        ]
    }
    order = SimpleNamespace(
        legs=[
            SimpleNamespace(symbol="SPY260821P00708000", side="BUY"),
            SimpleNamespace(symbol="SPY260821P00703000", side="SELL"),
        ]
    )
    assert _close_signature(structure) == _order_signature(order)


def _residual_structure(entry_order_id: str) -> dict:
    return {
        "entry_order_id": entry_order_id,
        "expiry_yymmdd": "260821",
        "entry_time": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
        "credit": 1.0,
        "quantity": 1,
        "legs": [
            {"symbol": "SPY260821P00700000", "qty": -1, "current_price": 0.6},
            {"symbol": "SPY260821P00695000", "qty": 1, "current_price": 0.1},
            {"symbol": "SPY260821C00776000", "qty": -1, "current_price": 0.4},
            {"symbol": "SPY260821C00781000", "qty": 1, "current_price": 0.1},
        ],
    }


def test_manager_covers_hold_pending_submit_and_submit_failure(tmp_path, monkeypatch):
    import scripts.residual_ic_manager as manager

    structures = [
        _residual_structure("hold"),
        _residual_structure("pending"),
        _residual_structure("submit"),
        _residual_structure("fail"),
    ]
    structures[2]["legs"][0]["symbol"] = "SPY260821P00690000"
    structures[3]["legs"][0]["symbol"] = "SPY260821P00680000"
    pending_order = SimpleNamespace(
        legs=[
            SimpleNamespace(symbol=leg["symbol"], side="BUY" if leg["qty"] < 0 else "SELL")
            for leg in structures[1]["legs"]
        ]
    )
    client = SimpleNamespace(get_all_positions=lambda: [])
    monkeypatch.setattr(manager, "ROOT", tmp_path)
    monkeypatch.setattr(manager, "AUDIT_PATH", tmp_path / "residual.json")
    monkeypatch.setattr(
        manager,
        "_get_orders",
        lambda _client, open_only=False: [pending_order] if open_only else [],
    )
    monkeypatch.setattr(manager, "recover_active_structures", lambda *_: (structures, {}))
    monkeypatch.setattr(manager, "_load_active_pcs_expected", lambda: {})
    monkeypatch.setattr(
        manager,
        "evaluate_residual_exit",
        lambda structure: {
            "should_exit": structure["entry_order_id"] != "hold",
            "exit_reason": "profit_target",
            "current_debit": 0.2,
        },
    )

    def submit(_client, structure, _decision):
        if structure["entry_order_id"] == "fail":
            raise RuntimeError("broker rejected close")
        return SimpleNamespace(id="close-submit")

    monkeypatch.setattr(manager, "_submit_close", submit)

    report = manager.manage_residual_ics(client, dry_run=False)

    assert report["holds"] == 1
    assert report["pending"] == 1
    assert report["submitted"] == 1
    assert report["broken"] == 1
    assert [detail["status"] for detail in report["details"]] == [
        "hold",
        "exit_pending",
        "exit_submitted",
        "exit_submit_failed",
    ]


def test_manager_dry_run_records_exit_without_submit(tmp_path, monkeypatch):
    import scripts.residual_ic_manager as manager

    structure = _residual_structure("dry")
    client = SimpleNamespace(get_all_positions=lambda: [])
    monkeypatch.setattr(manager, "ROOT", tmp_path)
    monkeypatch.setattr(manager, "AUDIT_PATH", tmp_path / "residual.json")
    monkeypatch.setattr(manager, "_get_orders", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(manager, "recover_active_structures", lambda *_: ([structure], {}))
    monkeypatch.setattr(manager, "_load_active_pcs_expected", lambda: {})
    monkeypatch.setattr(
        manager,
        "evaluate_residual_exit",
        lambda *_: {"should_exit": True, "exit_reason": "dte_exit", "current_debit": 0.5},
    )
    monkeypatch.setattr(
        manager, "_submit_close", MagicMock(side_effect=AssertionError("dry run submitted"))
    )

    report = manager.manage_residual_ics(client, dry_run=True)

    assert report["would_exit"] == 1
    assert report["details"][0]["status"] == "would_exit"


def test_manager_rejects_audit_write_outside_root(tmp_path, monkeypatch):
    import scripts.residual_ic_manager as manager

    monkeypatch.setattr(manager, "ROOT", tmp_path / "root")
    monkeypatch.setattr(manager, "AUDIT_PATH", tmp_path / "outside.json")
    monkeypatch.setattr(manager, "_get_orders", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(manager, "recover_active_structures", lambda *_: ([], {}))
    monkeypatch.setattr(manager, "_load_active_pcs_expected", lambda: {})
    client = SimpleNamespace(get_all_positions=lambda: [])

    with pytest.raises(ValueError, match="inside repository root"):
        manager.manage_residual_ics(client, dry_run=True)


@pytest.mark.parametrize(("broken", "expected"), [(0, 0), (1, 2)])
def test_residual_manager_main_returns_broker_health(monkeypatch, capsys, broken, expected):
    import scripts.residual_ic_manager as manager

    monkeypatch.setattr("sys.argv", ["residual_ic_manager.py", "--dry-run"])
    monkeypatch.setattr(manager, "_client", lambda: object())
    monkeypatch.setattr(
        manager,
        "manage_residual_ics",
        lambda client, dry_run: {"broken": broken, "dry_run": dry_run},
    )

    assert manager.main() == expected
    assert f'"broken": {broken}' in capsys.readouterr().out


def test_residual_client_requires_paper_credentials(monkeypatch):
    import scripts.residual_ic_manager as manager

    monkeypatch.setattr("src.utils.alpaca_client.get_alpaca_credentials", lambda: (None, None))
    with pytest.raises(RuntimeError, match="credentials missing"):
        manager._client()


def test_residual_helpers_cover_invalid_pcs_and_urgent_exit_rules():
    entries = {
        "not-pcs": {},
        "PCS_bad_expiry": {"expiry": "bad", "strikes": {}},
        "PCS_zero": {
            "expiry": "260821",
            "quantity": 0,
            "strikes": {"short_put": 700, "long_put": 695},
        },
    }
    assert active_pcs_expected(entries) == {}

    now = datetime(2026, 8, 20, 12, 0)
    structure = _residual_structure("urgent")
    assignment = evaluate_residual_exit(structure, now=now)
    assert assignment["exit_reason"] == "assignment_failsafe"

    structure["expiry_yymmdd"] = "260825"
    dte = evaluate_residual_exit(structure, now=datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc))
    assert dte["exit_reason"] == "dte_exit"
