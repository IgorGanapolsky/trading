"""Tests for Verified Performance Badge generator."""

from __future__ import annotations


from src.evals.verified_performance_badge import (
    generate_milestone_badge,
)


def test_badge_with_empty_trades():
    badge = generate_milestone_badge("spy_put_credit", [])
    assert badge.stage == "PAPER_VALIDATION"
    assert badge.verified_status == "IN_PROGRESS"
    assert badge.metrics.total_trades == 0
    assert "Cohort incomplete" in badge.blockers[0]


def test_badge_with_winning_cohort():
    # Simulate 30 winning paper trades ($20 profit each)
    trades = [{"trade_id": f"T{i}", "pnl": 20.0} for i in range(30)]
    badge = generate_milestone_badge("spy_put_credit", trades, target_cohort_size=30)

    assert badge.stage == "COHORT_PROVEN"
    assert badge.verified_status == "PASS"
    assert badge.metrics.total_trades == 30
    assert badge.metrics.win_rate_pct == 100.0
    assert badge.metrics.total_realized_pnl == 600.0
    assert badge.metrics.expectancy_per_trade == 20.0
    assert len(badge.blockers) == 0
    assert "Green Jacket Tier 1" in badge.milestone_name
    assert badge.badge_hash != ""


def test_badge_with_negative_expectancy_fails():
    # 30 trades with net negative PNL
    trades = [{"trade_id": f"T{i}", "pnl": -50.0} for i in range(30)]
    badge = generate_milestone_badge("ic_simple", trades, target_cohort_size=30)

    assert badge.stage == "PAPER_VALIDATION" or badge.stage == "COHORT_PROVEN"
    assert badge.verified_status != "PASS"
    assert any("Non-positive expectancy" in b for b in badge.blockers)
