"""Tests for surgical open-inventory reconcile planner."""

from scripts.reconcile_open_inventory import (
    _expected_from_ic_entries,
    plan_reductions,
)


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
