"""Tests for Freedom Number & Milestone Calculator."""

from __future__ import annotations

from datetime import date

from src.strategies.freedom_number_calculator import (
    FreedomBudget,
    FreedomNumberCalculator,
)


def test_freedom_budget_computations():
    budget = FreedomBudget(
        base_living_expenses_usd=4000.0,
        healthcare_buffer_usd=1000.0,
        lifestyle_travel_buffer_usd=1000.0,
        tax_contingency_pct=0.20,
    )
    assert budget.total_net_monthly_need == 6000.0
    assert budget.required_gross_monthly_distribution == 7500.0


def test_months_remaining_calculation():
    calc = FreedomNumberCalculator()
    # Test from Aug 17, 2026 to Nov 14, 2029
    ref_date = date(2026, 8, 17)
    months = calc.calculate_months_remaining(ref_date)
    assert months == 39


def test_projection_achieves_freedom_with_strong_savings():
    calc = FreedomNumberCalculator()
    # If business deposits $15,000/month from enterprise retainers
    proj = calc.compute_projection(
        current_capital_usd=100000.0,
        monthly_business_savings_usd=15000.0,
        annual_portfolio_yield_pct=0.10,
        annual_trading_alpha_pct=0.12,
        current_date=date(2026, 8, 17),
    )
    assert proj.on_track_for_north_star
    assert proj.projected_capital_at_deadline > proj.target_capital_usd
    assert proj.months_to_freedom_achieved <= 39
