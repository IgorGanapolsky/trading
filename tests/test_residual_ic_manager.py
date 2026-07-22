from datetime import datetime, timezone
from types import SimpleNamespace

from scripts.residual_ic_manager import (
    _close_signature,
    _order_signature,
    evaluate_residual_exit,
    recover_active_structures,
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
