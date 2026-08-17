"""Tests for DistributionCalendarEngine and Windfall Sweep rules."""

from __future__ import annotations


from src.strategies.distribution_calendar import (
    DistributionCalendarEngine,
)


def test_calendar_with_empty_holdings():
    engine = DistributionCalendarEngine()
    summary = engine.generate_12_month_calendar({})
    assert summary.total_portfolio_value == 0.0
    assert summary.annual_gross_distributions == 0.0
    assert len(summary.monthly_breakdown) == 0


def test_calendar_with_3_bucket_portfolio():
    engine = DistributionCalendarEngine()
    holdings = {
        "SGOV": 90000.0,
        "SPYI": 165000.0,
        "QQQI": 165000.0,
        "SCHD": 180000.0,
    }
    summary = engine.generate_12_month_calendar(holdings)
    assert summary.total_portfolio_value == 600000.0
    assert summary.annual_gross_distributions > 40000.0
    assert summary.average_monthly_net > 3000.0
    assert len(summary.monthly_breakdown) == 12

    # Quarterly bump in month 3, 6, 9, 12 due to SCHD
    m3 = next(m for m in summary.monthly_breakdown if m["month_index"] == 3)
    m2 = next(m for m in summary.monthly_breakdown if m["month_index"] == 2)
    assert m3["gross_usd"] > m2["gross_usd"]


def test_windfall_sweep_calculation():
    engine = DistributionCalendarEngine()
    # Scenario: Account equity is $45,000, cap is $25,000, monthly profit surplus $5,000
    sweep = engine.calculate_windfall_sweep(
        trading_account_equity_usd=45000.0,
        trading_working_capital_cap_usd=25000.0,
        monthly_profit_surplus_usd=5000.0,
    )
    assert sweep["excess_capital_usd"] == 20000.0
    assert sweep["total_windfall_sweep_usd"] == 25000.0
    assert sweep["sweep_recommended"] is True
    assert sweep["suggested_destinations"]["bucket_2_cashflow"] == 13750.0  # 55% of 25k
