"""Tests for PLAN Framework ETF Evaluator and $10K Scenario."""

from __future__ import annotations


from src.evals.plan_etf_evaluator import (
    ETFProfile,
    PlanETFEvaluator,
)


def test_plan_evaluates_core_spyi():
    evaluator = PlanETFEvaluator()
    spyi = ETFProfile(
        symbol="SPYI",
        name="NEOS S&P 500 High Income ETF",
        headline_yield_pct=0.112,
        aum_millions_usd=1800.0,
        underlying_type="Broad Index",
        nav_1yr_change_pct=0.03,
        distribution_coverage_ratio=1.02,
        tax_treatment="Section 1256 60/40",
        expense_ratio_pct=0.0068,
    )
    score = evaluator.evaluate(spyi)
    assert score.passed
    assert score.verdict == "APPROVED_CORE"
    assert score.total_score >= 35.0
    assert score.ten_k_scenario is not None
    assert score.ten_k_scenario.monthly_net_distribution_usd > 70.0
    assert not score.ten_k_scenario.is_yield_trap


def test_plan_rejects_single_stock_yield_trap():
    evaluator = PlanETFEvaluator()
    # High-yield trap: 50% headline yield with -35% NAV collapse
    tsly_trap = ETFProfile(
        symbol="TSLY_TRAP",
        name="Synthetic Single Stock High Yield",
        headline_yield_pct=0.52,
        aum_millions_usd=120.0,
        underlying_type="Single Stock Synthetic",
        nav_1yr_change_pct=-0.38,
        distribution_coverage_ratio=0.55,
        tax_treatment="Ordinary",
        expense_ratio_pct=0.0099,
    )
    score = evaluator.evaluate(tsly_trap)
    assert not score.passed
    assert score.verdict == "REJECTED_YIELD_TRAP"
    assert score.ten_k_scenario.is_yield_trap
    assert any("SEVERE_NAV_EROSION" in f for f in score.findings)


def test_plan_evaluates_schd():
    evaluator = PlanETFEvaluator()
    schd = ETFProfile(
        symbol="SCHD",
        name="Schwab US Dividend Equity ETF",
        headline_yield_pct=0.034,
        aum_millions_usd=55000.0,
        underlying_type="Broad Index",
        nav_1yr_change_pct=0.08,
        distribution_coverage_ratio=1.10,
        tax_treatment="Qualified",
        expense_ratio_pct=0.0006,
    )
    score = evaluator.evaluate(schd)
    assert score.passed
    assert score.verdict == "APPROVED_CORE"
    assert score.total_score == 40.0
