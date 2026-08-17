"""Tests for Freedom Number + 3-bucket + 30-day sprint."""

from __future__ import annotations

import pytest

from src.analytics.freedom_capital_plan import (
    allocate_three_buckets,
    build_30_day_sprint,
    build_freedom_capital_report,
    compute_freedom_number,
)


def test_freedom_number_defaults():
    fn = compute_freedom_number(6000)
    assert fn.monthly_after_tax == 6000
    assert fn.annual_after_tax == 72000
    assert fn.capital_at_assumed_yield == 900_000.0  # 72k / 0.08
    assert fn.monthly_pre_tax_approx == pytest.approx(6000 / 0.7)


def test_three_buckets_sum_and_live_gate():
    out = allocate_three_buckets(100_000, live_edge_candidate=False)
    total = sum(b["allocated"] for b in out["buckets"])
    assert total == pytest.approx(100_000)
    field = next(b for b in out["buckets"] if b["id"] == "field_or_passive")
    assert "live_blocked" in field["status"] or "EDGE_CANDIDATE" in field["status"]
    assert out["honesty"]["not_signal_service"] is True

    open_live = allocate_three_buckets(50_000, live_edge_candidate=True)
    field2 = next(b for b in open_live["buckets"] if b["id"] == "field_or_passive")
    assert "allowed" in field2["status"]


def test_fractions_must_sum():
    with pytest.raises(ValueError):
        allocate_three_buckets(10_000, ops_fraction=0.5, lab_fraction=0.5, field_fraction=0.5)


def test_sprint_pacing_unlocks_by_week():
    s1 = build_30_day_sprint(day_index=3)
    assert s1["week"] == 1
    assert s1["modules_unlocked"] == 2
    assert s1["modules_locked"] == 6

    s3 = build_30_day_sprint(day_index=15)
    assert s3["week"] == 3
    assert s3["modules_unlocked"] == 6


def test_full_report():
    r = build_freedom_capital_report(
        monthly_after_tax=6000,
        total_liquid=100_000,
        paper_equity=30_000,
        day_index=10,
    )
    assert r["freedom_number"]["monthly_after_tax"] == 6000
    assert len(r["three_buckets"]["buckets"]) == 3
    assert r["sprint_30_day"]["day_index"] == 10
    assert r["honesty"]["not_stock_picks"] is True
