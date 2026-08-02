from src.execution.position_sizer import DynamicPositionSizer


def test_position_sizer_zero_balance():
    sizer = DynamicPositionSizer(target_after_tax_monthly=1000.0)
    plan = sizer.calculate_sizing(account_equity=0.0)

    assert plan.recommended_contracts == 0
    assert plan.expected_monthly_gross == 0.0
    assert plan.expected_monthly_after_tax == 0.0


def test_position_sizer_scaling():
    sizer = DynamicPositionSizer(target_after_tax_monthly=1000.0)
    plan_10k = sizer.calculate_sizing(
        account_equity=10000.0, spread_width=5.0, credit_received=0.75
    )
    plan_50k = sizer.calculate_sizing(
        account_equity=50000.0, spread_width=5.0, credit_received=0.75
    )

    assert plan_10k.recommended_contracts >= 1
    assert plan_50k.recommended_contracts > plan_10k.recommended_contracts
    assert plan_50k.expected_monthly_after_tax >= 1000.0
