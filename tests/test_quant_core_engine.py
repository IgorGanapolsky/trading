import pytest
from scripts.quant_core_engine import QuantConfig, QuantCoreEngine, MarketRegime
from scripts.historical_options_backtest import (
    black_scholes_put_price,
    black_scholes_put_delta,
    find_strike_for_delta,
)


def test_black_scholes_put_price():
    S = 500.0
    K = 480.0
    T = 30 / 365.0
    r = 0.02
    sigma = 0.20
    price = black_scholes_put_price(S, K, T, r, sigma)
    assert price > 0.0
    assert price < (K - 0.0)


def test_black_scholes_delta_inversion():
    S = 600.0
    target_delta = 0.15
    T = 45 / 365.0
    r = 0.02
    sigma = 0.18
    strike = find_strike_for_delta(S, target_delta, T, r, sigma)
    assert strike < S
    delta = black_scholes_put_delta(S, strike, T, r, sigma)
    assert pytest.approx(delta, abs=0.03) == target_delta


def test_quant_engine_entry_evaluation():
    config = QuantConfig(min_iv_rank=25.0)
    engine = QuantCoreEngine(config)

    # Bullish regime with high IV Rank
    regime_bullish = MarketRegime(
        spy_price=550.0,
        sma200=520.0,
        sma50=540.0,
        trend_bullish=True,
        vix=22.0,
        iv_rank=35.0,
        captured_at="2026-09-14T12:00:00Z",
    )
    eval_res = engine.evaluate_entry(regime_bullish, current_positions_count=0)
    assert eval_res["is_eligible"] is True
    assert eval_res["target_spread"]["short_strike"] < 550.0

    # Bearish regime (below 200 SMA)
    regime_bearish = MarketRegime(
        spy_price=500.0,
        sma200=520.0,
        sma50=510.0,
        trend_bullish=False,
        vix=25.0,
        iv_rank=40.0,
        captured_at="2026-09-14T12:00:00Z",
    )
    eval_bearish = engine.evaluate_entry(regime_bearish, current_positions_count=0)
    assert eval_bearish["is_eligible"] is False
    assert any("Trend bearish" in r for r in eval_bearish["reasons"])
