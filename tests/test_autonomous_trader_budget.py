from scripts.autonomous_trader import calc_daily_input


def test_calc_daily_input_baseline():
    assert calc_daily_input(1000) == 10.0


def test_calc_daily_input_scales_up():
    low = calc_daily_input(2_500)
    mid = calc_daily_input(6_000)
    high = calc_daily_input(12_000)
    assert low > 10.0
    assert mid > low
    assert high > mid


def test_calc_daily_input_caps():
    assert calc_daily_input(250_000) == 1000.0
