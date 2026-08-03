"""Tests for near-term $1k/mo economics helpers (not forecasts)."""

from __future__ import annotations

from src.core.near_term_goal import (
    NEAR_TERM_MONTHLY_AFTER_TAX,
    path_economics,
    pre_tax_monthly_required,
    required_expectancy_per_trade,
    required_monthly_return_pct,
)


def test_pre_tax_at_30pct():
    pre = pre_tax_monthly_required(1000.0, 0.30)
    assert abs(pre - 1000.0 / 0.7) < 0.01


def test_required_return_on_equity():
    pct = required_monthly_return_pct(100_000.0, 1430.0)
    assert pct is not None
    assert abs(pct - 1.43) < 0.01


def test_path_economics_blocks_without_edge():
    eco = path_economics(
        paper_equity=94150.0,
        live_equity=0.0,
        closed_n=1,
        expectancy=17.0,
        profit_factor=None,
        kill_verdict="INSUFFICIENT_SAMPLE",
    )
    assert eco["near_term_after_tax_monthly"] == NEAR_TERM_MONTHLY_AFTER_TAX
    assert eco["edge_proven"] is False
    assert eco["live_deposit_consideration_allowed"] is False
    assert any("n=1/30" in b or "n=" in b for b in eco["blockers"])
    assert eco["required_expectancy_usd_per_trade_at_plan_cadence"] is not None


def test_edge_candidate_flags():
    eco = path_economics(
        paper_equity=100_000.0,
        live_equity=0.0,
        closed_n=30,
        expectancy=20.0,
        profit_factor=1.2,
        kill_verdict="EDGE_CANDIDATE",
    )
    assert eco["edge_proven"] is True


def test_expectancy_per_trade():
    e = required_expectancy_per_trade(1430.0, trades_per_month=10)
    assert e is not None
    assert abs(e - 143.0) < 0.01
