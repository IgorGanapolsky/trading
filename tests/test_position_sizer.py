import math

from src.analytics.statistical_edge import calculate_edge_statistics
from src.execution.position_sizer import DynamicPositionSizer


def test_all_wins_keep_mathematical_profit_factor_in_process():
    stats = calculate_edge_statistics([25.0] * 100)
    assert stats.profit_factor is not None and math.isinf(stats.profit_factor)


def test_position_sizer_zero_balance():
    sizer = DynamicPositionSizer(target_after_tax_monthly=1000.0)
    plan = sizer.calculate_sizing(account_equity=0.0)

    assert plan.recommended_contracts == 0
    assert plan.expected_monthly_gross == 0.0
    assert plan.expected_monthly_after_tax == 0.0
    assert "equity" in plan.readiness_reason


def test_position_sizer_refuses_to_assume_edge():
    sizer = DynamicPositionSizer(target_after_tax_monthly=1000.0)
    plan = sizer.calculate_sizing(account_equity=50000.0)

    assert plan.recommended_contracts == 0
    assert plan.observed_sample_size == 0
    assert "insufficient realized sample" in plan.readiness_reason


def test_position_sizer_uses_realized_expectancy_and_risk_budget():
    sizer = DynamicPositionSizer(target_after_tax_monthly=1000.0)
    profitable_cohort = [40.0] * 95 + [-100.0] * 5
    plan_10k = sizer.calculate_sizing(
        account_equity=10000.0,
        spread_width=5.0,
        credit_received=0.75,
        realized_pnls=profitable_cohort,
        observed_trades_per_month=4.0,
    )
    plan_50k = sizer.calculate_sizing(
        account_equity=50000.0,
        spread_width=5.0,
        credit_received=0.75,
        realized_pnls=profitable_cohort,
        observed_trades_per_month=4.0,
    )

    assert plan_10k.recommended_contracts == 0
    assert plan_50k.recommended_contracts == 1
    assert plan_50k.observed_expectancy_per_trade == 33.0
    assert plan_50k.expectancy_lower_95 is not None
    assert plan_50k.expectancy_lower_95 > 0
    assert plan_50k.expected_monthly_gross == 132.0
    assert plan_50k.target_attainable_at_observed_edge is False


def test_position_sizer_rejects_negative_confidence_bound():
    sizer = DynamicPositionSizer()
    unstable = [100.0] * 51 + [-100.0] * 49
    plan = sizer.calculate_sizing(
        account_equity=100000.0,
        realized_pnls=unstable,
        observed_trades_per_month=10.0,
    )
    assert plan.observed_expectancy_per_trade == 2.0
    assert plan.expectancy_lower_95 is not None and plan.expectancy_lower_95 < 0
    assert plan.recommended_contracts == 0
