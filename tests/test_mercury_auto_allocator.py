import pytest
from src.adapters.mercury_auto_allocator import MercuryAutoAllocator


def test_mercury_auto_allocator_tax_reserve():
    allocator = MercuryAutoAllocator(tax_rate=0.20, safety_buffer_usd=500.0)
    plan = allocator.plan_allocation(incoming_revenue_usd=1000.0, available_checking_usd=500.0)

    assert plan.tax_reserve_usd == 200.0
    assert plan.safety_buffer_usd == 500.0
    assert plan.trading_collateral_usd == 480.0  # 60% of $800 surplus
    assert plan.profit_sweep_usd == 320.0  # 40% of $800 surplus


def test_mercury_auto_allocator_zero_revenue():
    allocator = MercuryAutoAllocator(tax_rate=0.20, safety_buffer_usd=500.0)
    plan = allocator.plan_allocation(incoming_revenue_usd=0.0, available_checking_usd=300.0)

    assert plan.tax_reserve_usd == 0.0
    assert plan.trading_collateral_usd == 0.0
    assert plan.profit_sweep_usd == 0.0
