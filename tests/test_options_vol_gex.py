"""Unit tests for Options Volatility, GEX, and Market Tide Analytics."""

from __future__ import annotations

import pytest

from src.analytics.options_vol_gex import (
    black_scholes_gamma,
    calculate_expected_hedging_flow,
    calculate_gex_levels,
    calculate_iv_term_structure,
    calculate_market_tide,
    calculate_max_pain,
    detect_zero_dte_risk_pockets,
    evaluate_dealer_defense_levels,
)


def test_black_scholes_gamma_standard_and_boundaries() -> None:
    # Standard ATM SPY option
    gamma_atm = black_scholes_gamma(
        spot=500.0, strike=500.0, time_to_expiry_years=30 / 365, iv=0.18
    )
    assert gamma_atm > 0.0

    # Far OTM option has lower gamma than ATM
    gamma_otm = black_scholes_gamma(
        spot=500.0, strike=550.0, time_to_expiry_years=30 / 365, iv=0.18
    )
    assert 0.0 < gamma_otm < gamma_atm

    # Boundary values return 0.0 safely without raising
    assert black_scholes_gamma(spot=0.0, strike=500.0, time_to_expiry_years=0.1, iv=0.2) == 0.0
    assert black_scholes_gamma(spot=500.0, strike=0.0, time_to_expiry_years=0.1, iv=0.2) == 0.0
    assert black_scholes_gamma(spot=500.0, strike=500.0, time_to_expiry_years=0.0, iv=0.2) == 0.0
    assert black_scholes_gamma(spot=500.0, strike=500.0, time_to_expiry_years=0.1, iv=0.0) == 0.0


def test_calculate_gex_levels_validation_and_empty() -> None:
    with pytest.raises(ValueError, match="equal length"):
        calculate_gex_levels(
            spot_price=500.0,
            strikes=[490.0, 500.0],
            call_gammas=[0.02],
            put_gammas=[0.02, 0.02],
            call_ois=[100, 100],
            put_ois=[100, 100],
        )

    empty_res = calculate_gex_levels(
        spot_price=500.0,
        strikes=[],
        call_gammas=[],
        put_gammas=[],
        call_ois=[],
        put_ois=[],
    )
    assert empty_res.net_gamma == 0.0
    assert empty_res.call_wall is None
    assert empty_res.put_wall is None
    assert empty_res.gamma_flip is None


def test_calculate_gex_levels_positive_and_negative_regimes() -> None:
    strikes = [480.0, 490.0, 500.0, 510.0, 520.0]
    spot = 500.0

    # Dominated by calls: positive net gamma
    call_gammas = [0.01, 0.02, 0.03, 0.02, 0.01]
    put_gammas = [0.01, 0.02, 0.03, 0.02, 0.01]
    call_ois = [500, 1000, 2000, 1500, 800]
    put_ois = [100, 200, 300, 200, 100]

    res_pos = calculate_gex_levels(
        spot_price=spot,
        strikes=strikes,
        call_gammas=call_gammas,
        put_gammas=put_gammas,
        call_ois=call_ois,
        put_ois=put_ois,
    )
    assert res_pos.net_gamma > 0.0
    assert res_pos.gamma_regime == "positive_gamma"
    assert res_pos.call_wall == 510.0
    assert res_pos.put_wall == 490.0
    assert res_pos.gamma_magnet == 500.0

    # Dominated by puts: negative net gamma
    put_ois_heavy = [5000, 10000, 20000, 15000, 8000]
    res_neg = calculate_gex_levels(
        spot_price=spot,
        strikes=strikes,
        call_gammas=call_gammas,
        put_gammas=put_gammas,
        call_ois=call_ois,
        put_ois=put_ois_heavy,
    )
    assert res_neg.net_gamma < 0.0
    assert res_neg.gamma_regime == "negative_gamma"


def test_calculate_gex_flip_linear_interpolation() -> None:
    # Construct scenario where Net GEX crosses from negative to positive between 495 and 505
    strikes = [490.0, 495.0, 505.0, 510.0]
    spot = 500.0

    # Net GEX = (Call - Put) * multiplier
    # At 495: Call=10, Put=50 => Net GEX < 0
    # At 505: Call=50, Put=10 => Net GEX > 0
    call_gammas = [0.02, 0.02, 0.02, 0.02]
    put_gammas = [0.02, 0.02, 0.02, 0.02]
    call_ois = [10, 10, 50, 50]
    put_ois = [50, 50, 10, 10]

    res = calculate_gex_levels(
        spot_price=spot,
        strikes=strikes,
        call_gammas=call_gammas,
        put_gammas=put_gammas,
        call_ois=call_ois,
        put_ois=put_ois,
    )
    assert res.gamma_flip is not None
    # Flip must be strictly between 495.0 and 505.0
    assert 495.0 < res.gamma_flip < 505.0
    assert len(res.nearby_flips) >= 1


def test_calculate_max_pain() -> None:
    with pytest.raises(ValueError, match="equal length"):
        calculate_max_pain(strikes=[500.0], call_ois=[100], put_ois=[])

    assert calculate_max_pain([], [], []) == 0.0

    # Symmetrical distribution centered at 500
    strikes = [490.0, 495.0, 500.0, 505.0, 510.0]
    call_ois = [100, 200, 1000, 200, 100]
    put_ois = [100, 200, 1000, 200, 100]

    max_pain = calculate_max_pain(strikes, call_ois, put_ois)
    assert max_pain == 500.0

    # Asymmetric distribution: huge Put OI at 490 forces dealer pain lower
    put_ois_skewed = [10000, 200, 100, 50, 10]
    call_ois_skewed = [10, 50, 100, 200, 10000]
    # At 500, both puts and calls payout heavily; pinning near center balances payout
    pain_skewed = calculate_max_pain(strikes, call_ois_skewed, put_ois_skewed)
    assert pain_skewed in strikes


def test_calculate_iv_term_structure() -> None:
    # Identical DTE edge case
    res_flat = calculate_iv_term_structure(
        front_dte=10.0, front_iv=0.20, back_dte=10.0, back_iv=0.20
    )
    assert res_flat.slope == 0.0

    # Backwardation case (front elevated above back)
    # Slope = (0.15 - 0.25) / (45 - 10) = -0.10 / 35 = -0.002857 (not quite -0.00406)
    res_moderate = calculate_iv_term_structure(
        front_dte=10.0, front_iv=0.25, back_dte=45.0, back_iv=0.15
    )
    assert res_moderate.slope < 0.0
    assert res_moderate.is_backwardated is False

    # Severe backwardation: front IV 0.35, back IV 0.15 over 35 days: slope = -0.20 / 35 = -0.00571
    res_severe = calculate_iv_term_structure(
        front_dte=10.0,
        front_iv=0.35,
        back_dte=45.0,
        back_iv=0.15,
        rv30=0.20,
    )
    assert res_severe.slope <= -0.00406
    assert res_severe.is_backwardated is True
    assert res_severe.iv_rv_ratio == 0.35 / 0.20
    assert res_severe.is_rich is True
    assert res_severe.credit_spread_favorable is True


def test_calculate_market_tide() -> None:
    # Empty trades
    res_empty = calculate_market_tide([])
    assert res_empty.net_call_premium == 0.0
    assert res_empty.sentiment == "neutral"
    assert res_empty.ask_side_ratio == 0.0
    assert res_empty.aggressive_buying_detected is False

    # Bullish aggressive flow: calls bought at ask
    trades = [
        {"side": "ask", "type": "call", "premium": 50000.0, "volume": 500},
        {"side": "ask", "type": "call", "premium": 30000.0, "volume": 300},
        {"side": "bid", "type": "put", "premium": 20000.0, "volume": 100},
        {"side": "bid", "type": "call", "premium": 5000.0, "volume": 50},
    ]
    res = calculate_market_tide(trades)
    # Net call premium = 50000 + 30000 - 5000 = 75000
    assert res.net_call_premium == 75000.0
    # Net put premium = -20000 (sold at bid)
    assert res.net_put_premium == -20000.0
    # Market tide delta = 75000 - (-20000) = 95000
    assert res.market_tide_delta == 95000.0
    assert res.sentiment == "bullish"

    # Ask volume = 800, Bid volume = 150 -> 800 / 950 = 84.2% (>70%)
    assert res.ask_side_ratio > 0.70
    assert res.aggressive_buying_detected is True

    # Bearish flow: puts bought at ask, calls sold at bid
    bearish_trades = [
        {"side": "ask", "type": "put", "premium": 50000.0, "volume": 500},
        {"side": "bid", "type": "call", "premium": 20000.0, "volume": 200},
        {"side": "other", "type": "call", "premium": 1000.0, "volume": 10},
    ]
    res_bear = calculate_market_tide(bearish_trades)
    assert res_bear.net_put_premium == 50000.0
    assert res_bear.net_call_premium == -20000.0
    assert res_bear.market_tide_delta == -70000.0
    assert res_bear.sentiment == "bearish"


def test_black_scholes_zero_denom() -> None:
    # Extremely small iv and expiry producing zero denominator
    assert (
        black_scholes_gamma(spot=100.0, strike=100.0, time_to_expiry_years=1e-15, iv=1e-15) == 0.0
    )


def test_calculate_expected_hedging_flow() -> None:
    # Spot 500, positive net gamma -> market drops 1% -> dealers buy shares
    res_pos = calculate_expected_hedging_flow(spot_price=500.0, net_gamma=0.05, spot_move_pct=-0.01)
    assert res_pos.hedging_shares > 0.0
    assert res_pos.hedging_pressure == "supportive_buying"
    assert "supportive dip buying" in res_pos.description

    # Spot 500, positive net gamma -> market rises 1% -> dealers sell shares into rally
    res_pos_up = calculate_expected_hedging_flow(
        spot_price=500.0, net_gamma=0.05, spot_move_pct=0.01
    )
    assert res_pos_up.hedging_shares < 0.0
    assert "trims rally" in res_pos_up.description

    # Spot 500, negative net gamma -> market drops 1% -> dealers sell shares (accelerating dump)
    res_neg = calculate_expected_hedging_flow(
        spot_price=500.0, net_gamma=-0.05, spot_move_pct=-0.01
    )
    assert res_neg.hedging_shares < 0.0
    assert res_neg.hedging_pressure == "accelerating_selling"
    assert "cascading selling" in res_neg.description

    # Zero net gamma -> neutral
    res_neutral = calculate_expected_hedging_flow(
        spot_price=500.0, net_gamma=0.0, spot_move_pct=-0.01
    )
    assert res_neutral.hedging_pressure == "neutral"

    # Invalid spot -> safe zero result
    res_invalid = calculate_expected_hedging_flow(spot_price=0.0, net_gamma=0.05)
    assert res_invalid.hedging_flow_dollars == 0.0


def test_evaluate_dealer_defense_levels() -> None:
    # Spot 505, Put Wall 500, Call Wall 515, Gamma Flip 502 -> all defended, safe positive gamma
    safe = evaluate_dealer_defense_levels(
        spot_price=505.0, put_wall=500.0, call_wall=515.0, gamma_flip=502.0
    )
    assert safe.put_wall_status == "defended"
    assert safe.call_wall_status == "defended"
    assert safe.regime_safety == "safe_positive_gamma"

    # Spot 495, Put Wall 500 (breached) -> Put Wall abandoned, unhedged breakdown
    breached = evaluate_dealer_defense_levels(
        spot_price=495.0, put_wall=500.0, call_wall=515.0, gamma_flip=502.0
    )
    assert breached.put_wall_status == "abandoned"
    assert breached.regime_safety == "unhedged_breakdown"

    # Spot 501, Put Wall 490 (intact), but below Gamma Flip 502 -> hazardous negative gamma
    neg_gamma = evaluate_dealer_defense_levels(
        spot_price=501.0, put_wall=490.0, call_wall=515.0, gamma_flip=502.0
    )
    assert neg_gamma.put_wall_status == "defended"
    assert neg_gamma.regime_safety == "hazardous_negative_gamma"

    # Invalid spot
    invalid = evaluate_dealer_defense_levels(
        spot_price=-1.0, put_wall=500.0, call_wall=510.0, gamma_flip=500.0
    )
    assert invalid.put_wall_status == "unknown"


def test_detect_zero_dte_risk_pockets() -> None:
    strikes = [490.0, 495.0, 500.0, 505.0, 510.0]
    spot = 500.0
    z_puts = [100, 200, 3000, 150, 50]
    z_calls = [50, 100, 3000, 100, 50]
    t_puts = [500, 1000, 6000, 800, 500]
    t_calls = [500, 1000, 6000, 800, 500]

    pockets = detect_zero_dte_risk_pockets(
        spot_price=spot,
        strikes=strikes,
        zero_dte_put_ois=z_puts,
        zero_dte_call_ois=z_calls,
        total_put_ois=t_puts,
        total_call_ois=t_calls,
        threshold_pct=0.02,
    )
    # Strike 500 has 6000 0DTE OI out of 12000 total (50%) -> critical risk pocket
    assert len(pockets) >= 1
    atm_pocket = next(p for p in pockets if p.strike == 500.0)
    assert atm_pocket.risk_level == "critical"
    assert "Severe 0DTE concentration" in atm_pocket.hazard_description

    # Empty strikes
    assert (
        detect_zero_dte_risk_pockets(
            spot_price=500.0, strikes=[], zero_dte_put_ois=[], zero_dte_call_ois=[]
        )
        == []
    )
