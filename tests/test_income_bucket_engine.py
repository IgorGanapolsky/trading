"""Tests for Three-Bucket Income Engine (Freedom Builder model)."""

from __future__ import annotations

import pytest

from src.strategies.income_bucket_engine import (
    IncomeBucketEngine,
)


def test_income_engine_allocation_weights_sum():
    engine = IncomeBucketEngine()
    total_weights = sum(b.target_weight for b in engine.buckets.values())
    assert 0.999 <= total_weights <= 1.001


def test_income_engine_evaluates_target_capital():
    engine = IncomeBucketEngine()
    # Test on target capital $600,000
    plan = engine.evaluate_portfolio(capital_usd=600000.0, target_monthly_income_usd=6000.0)

    assert plan.total_capital_usd == 600000.0
    assert len(plan.allocations) == 3
    # Check bucket distributions
    b1 = next(a for a in plan.allocations if a.bucket_key == "bucket_1_liquidity")
    b2 = next(a for a in plan.allocations if a.bucket_key == "bucket_2_cashflow")
    b3 = next(a for a in plan.allocations if a.bucket_key == "bucket_3_compounder")

    assert b1.allocated_usd == 90000.0  # 15%
    assert b2.allocated_usd == 330000.0  # 55%
    assert b3.allocated_usd == 180000.0  # 30%

    # Monthly net should be positive and realistic
    assert plan.net_monthly_income_usd > 3000.0
    assert plan.effective_blended_yield > 0.06


def test_income_engine_rebalance_dca():
    engine = IncomeBucketEngine()
    # Scenario: Bucket 1 has 0, Bucket 2 has 200k, Bucket 3 has 100k
    current_holdings = {
        "bucket_1_liquidity": 0.0,
        "bucket_2_cashflow": 200000.0,
        "bucket_3_compounder": 100000.0,
    }
    # Deposit $50,000
    plan = engine.plan_rebalance_dca(current_holdings, deposit_usd=50000.0)

    # Bucket 1 should get the largest share because it has a huge deficit (target is 15% of $350k = $52.5k)
    assert plan["bucket_1_liquidity"] > plan["bucket_2_cashflow"]
    assert sum(plan.values()) == pytest.approx(50000.0, abs=0.05)


def test_income_engine_bear_market_survival():
    engine = IncomeBucketEngine()
    # 30% crash test over 12 months on $600k capital
    sim = engine.simulate_bear_market_survival(
        capital_usd=600000.0,
        monthly_expense_usd=6000.0,
        equity_drop_pct=0.30,
        months=12,
    )
    assert sim["bucket_1_initial_cash"] == 90000.0
    assert sim["monthly_cashflow_during_crash"] > 2000.0
    assert sim["survival_months_runway"] > 12.0
    assert not sim["forced_equity_sale_required"]
