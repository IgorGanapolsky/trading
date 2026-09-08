"""Tests for Airbnb-FORMAT entry challenge matrix."""

from __future__ import annotations

from src.risk.entry_challenge_matrix import evaluate_entry_challenges


def _ok_snap(**overrides):
    base = {
        "paper": True,
        "trading_mode": "paper",
        "active_family": "spy_put_credit",
        "live_blocked": True,
        "ic_entries_killed": True,
        "inventory_clean": True,
        "iv_rank_proxy": 40.0,
        "min_iv_rank": 30.0,
        "lot_size": 1,
        "open_put_credits": 0,
        "structures_today": 0,
    }
    base.update(overrides)
    return base


def test_all_pass_allows_entry():
    result = evaluate_entry_challenges(_ok_snap())
    assert result.allowed is True
    assert result.first_blocker is None
    assert result.passed_count == result.challenge_count == 7


def test_first_blocker_is_paper_mode():
    result = evaluate_entry_challenges(_ok_snap(paper=False, trading_mode="live"))
    assert result.allowed is False
    assert result.first_blocker == "paper_mode"


def test_regime_blocks_before_lot_when_ivr_low():
    result = evaluate_entry_challenges(_ok_snap(iv_rank_proxy=12.3))
    assert result.first_blocker == "regime_ivr"


def test_missing_ivr_fail_closed():
    snap = _ok_snap()
    snap.pop("iv_rank_proxy")
    result = evaluate_entry_challenges(snap)
    assert result.first_blocker == "regime_ivr"


def test_concurrency_cap():
    result = evaluate_entry_challenges(_ok_snap(open_put_credits=2, max_concurrent_put_credits=2))
    assert result.first_blocker == "concurrency"


def test_daily_cap():
    result = evaluate_entry_challenges(_ok_snap(structures_today=3, max_daily_structures=3))
    assert result.first_blocker == "daily_cap"


def test_inventory_unclean():
    result = evaluate_entry_challenges(_ok_snap(inventory_clean=False))
    assert result.first_blocker == "inventory_clean"
