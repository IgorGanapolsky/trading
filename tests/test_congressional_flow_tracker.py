"""Tests for src/analytics/congressional_flow_tracker.py."""

from __future__ import annotations

from src.analytics.congressional_flow_tracker import (
    OptionsFlowSignal,
    PoliticianTrade,
    analyze_congressional_flow,
    calculate_disclosure_decay,
    derive_trade_direction,
    evaluate_committee_conflict,
)


def test_derive_trade_direction():
    assert derive_trade_direction("purchase", "stock") == "bullish"
    assert derive_trade_direction("purchase", "call_option") == "bullish"
    assert derive_trade_direction("purchase", "put_option") == "bearish"
    assert derive_trade_direction("sale", "stock") == "bearish"
    assert derive_trade_direction("sale", "call_option") == "bearish"
    assert derive_trade_direction("sale", "put_option") == "bullish"
    assert derive_trade_direction("purchase", "other") == "neutral"


def test_politician_trade_init_default_roster():
    trade = PoliticianTrade(
        ticker="  lmt  ",
        politician="Tommy Tuberville",
        chamber="senate",
        party="R",
        transaction_type="purchase",
        trade_date="2026-09-01",
        disclosure_date="2026-09-15",
        amount_min=500_000,
        amount_max=1_000_000,
    )
    assert trade.ticker == "LMT"
    assert "Armed Services" in trade.committees
    assert "Agriculture" in trade.committees
    assert trade.direction == "bullish"


def test_politician_trade_init_custom_committees():
    trade = PoliticianTrade(
        ticker="LMT",
        politician="Unknown Member",
        chamber="senate",
        party="R",
        transaction_type="purchase",
        trade_date="2026-09-01",
        disclosure_date="2026-09-10",
        amount_min=15_000,
        amount_max=50_000,
        instrument="put_option",
        committees=("Armed Services",),
    )
    assert trade.ticker == "LMT"
    assert trade.committees == ("Armed Services",)
    assert trade.direction == "bearish"


def test_options_flow_signal_init():
    flow = OptionsFlowSignal(
        ticker=" pltr ",
        option_type="call",
        strike=45.0,
        expiration="2026-10-16",
        premium=350_000.0,
        volume_oi_ratio=2.4,
        side="ask",
        sweep=True,
    )
    assert flow.ticker == "PLTR"
    assert flow.sweep is True


def test_calculate_disclosure_decay_normal_and_as_of_date():
    # 0 days delay -> 1.0
    decay_0 = calculate_disclosure_decay("2026-09-01", "2026-09-01", half_life_days=30.0)
    assert decay_0 == 1.0

    # 30 days delay -> 0.5
    decay_30 = calculate_disclosure_decay("2026-09-01", "2026-10-01", half_life_days=30.0)
    assert decay_30 == 0.5

    # 60 days delay -> 0.25
    decay_60 = calculate_disclosure_decay("2026-09-01", "2026-10-31", half_life_days=30.0)
    assert decay_60 == 0.25

    # Elapsed age via as_of_date discounts prompt filing from 2024
    decay_elapsed = calculate_disclosure_decay(
        "2024-01-01",
        "2024-01-02",
        as_of_date_str="2026-09-29",
        half_life_days=30.0,
    )
    assert decay_elapsed == 0.05  # hits floor due to 900+ days elapsed


def test_calculate_disclosure_decay_edge_cases():
    # Invalid dates -> default 30 days -> 0.5
    decay_invalid = calculate_disclosure_decay("bad-date", "2026-09-15")
    assert decay_invalid == 0.5

    # Negative delay (disclosure before trade date anomaly) -> delay = 0 -> 1.0
    decay_negative = calculate_disclosure_decay("2026-09-20", "2026-09-10")
    assert decay_negative == 1.0

    # half_life_days <= 0 -> 0.0
    assert calculate_disclosure_decay("2026-09-01", "2026-09-15", half_life_days=0) == 0.0
    assert calculate_disclosure_decay("2026-09-01", "2026-09-15", half_life_days=-10) == 0.0


def test_evaluate_committee_conflict_match_and_aliases():
    trade = PoliticianTrade(
        ticker="LMT",
        politician="Tommy Tuberville",
        chamber="senate",
        party="R",
        transaction_type="purchase",
        trade_date="2026-09-01",
        disclosure_date="2026-09-10",
        amount_min=500_000,
        amount_max=1_000_000,
        committees=("Senate Armed Services",),
    )
    score, matches = evaluate_committee_conflict(trade)
    assert "Armed Services" in matches
    assert score > 0.80  # size boost applied


def test_evaluate_committee_conflict_blank_regression():
    # Blank or whitespace-only committee must NOT match any jurisdiction
    trade = PoliticianTrade(
        ticker="LMT",
        politician="Anonymous",
        chamber="house",
        party="D",
        transaction_type="purchase",
        trade_date="2026-09-01",
        disclosure_date="2026-09-15",
        amount_min=500_000,
        amount_max=1_000_000,
        committees=("", "   "),
    )
    score, matches = evaluate_committee_conflict(trade)
    assert matches == ()
    assert score == 0.20


def test_evaluate_committee_conflict_no_match():
    trade = PoliticianTrade(
        ticker="XYZNONEXISTENT",
        politician="Tommy Tuberville",
        chamber="senate",
        party="R",
        transaction_type="purchase",
        trade_date="2026-09-01",
        disclosure_date="2026-09-15",
        amount_min=1_000,
        amount_max=5_000,
    )
    score, matches = evaluate_committee_conflict(trade)
    assert matches == ()
    assert score == 0.20


def test_analyze_congressional_flow_purchase_bullish_sweep_negative_gamma():
    trade = PoliticianTrade(
        ticker="NVDA",
        politician="Dan Crenshaw",
        chamber="house",
        party="R",
        transaction_type="purchase",
        trade_date="2026-09-20",
        disclosure_date="2026-09-22",
        amount_min=1_000_000,
        amount_max=5_000_000,
    )
    flow = OptionsFlowSignal(
        ticker="NVDA",
        option_type="call",
        strike=130.0,
        expiration="2026-10-16",
        premium=500_000.0,
        volume_oi_ratio=3.0,
        side="ask",
        sweep=True,
    )
    signal = analyze_congressional_flow(trade, flow=flow, gex_regime="negative_gamma")

    assert signal.ticker == "NVDA"
    assert signal.direction == "bullish"
    assert signal.action == "BUY_CALL_SPREAD"
    assert signal.flow_confirmation is True
    assert signal.composite_score >= 0.50
    assert signal.gex_regime == "negative_gamma"
    assert "Institutional CALL flow confirmed" in signal.rationale
    assert signal.flow_details is not None
    assert signal.flow_details["sweep"] is True


def test_analyze_congressional_flow_purchase_positive_gamma():
    trade = PoliticianTrade(
        ticker="NVDA",
        politician="Dan Crenshaw",
        chamber="house",
        party="R",
        transaction_type="purchase",
        trade_date="2026-09-20",
        disclosure_date="2026-09-21",
        amount_min=500_000,
        amount_max=1_000_000,
    )
    signal = analyze_congressional_flow(trade, flow=None, gex_regime="positive_gamma")

    # In positive gamma, high conviction bullish signals SELL_PUT_CREDIT
    assert signal.direction == "bullish"
    assert signal.action == "SELL_PUT_CREDIT"
    assert signal.flow_confirmation is False
    assert signal.flow_details is None
    assert "positive_gamma" in signal.rationale


def test_analyze_congressional_flow_put_option_purchase_is_bearish():
    # Purchasing put option is BEARISH economic direction
    trade = PoliticianTrade(
        ticker="XOM",
        politician="Dan Crenshaw",
        chamber="house",
        party="R",
        transaction_type="purchase",
        instrument="put_option",
        trade_date="2026-09-20",
        disclosure_date="2026-09-22",
        amount_min=250_000,
        amount_max=500_000,
    )
    assert trade.direction == "bearish"

    flow = OptionsFlowSignal(
        ticker="XOM",
        option_type="put",
        strike=110.0,
        expiration="2026-10-16",
        premium=300_000.0,
        volume_oi_ratio=2.0,
        side="ask",
        sweep=False,  # non-sweep multiplier 1.20
    )
    signal = analyze_congressional_flow(trade, flow=flow, gex_regime=None)

    assert signal.ticker == "XOM"
    assert signal.direction == "bearish"
    assert signal.action == "BUY_PUT_SPREAD"
    assert signal.flow_confirmation is True


def test_analyze_congressional_flow_neutral_instrument():
    trade = PoliticianTrade(
        ticker="NVDA",
        politician="Dan Crenshaw",
        chamber="house",
        party="R",
        transaction_type="purchase",
        instrument="other",
        trade_date="2026-09-20",
        disclosure_date="2026-09-22",
        amount_min=500_000,
        amount_max=1_000_000,
    )
    signal = analyze_congressional_flow(trade)
    assert signal.direction == "neutral"
    assert signal.action == "NEUTRAL_HOLD"


def test_analyze_congressional_flow_neutral_hold_low_conviction():
    trade = PoliticianTrade(
        ticker="UNKNOWN",
        politician="Anonymous Member",
        chamber="house",
        party="I",
        transaction_type="purchase",
        trade_date="2025-01-01",
        disclosure_date="2026-09-01",
        amount_min=1_000,
        amount_max=5_000,
        committees=(),
    )
    signal = analyze_congressional_flow(trade, flow=None)
    assert signal.action == "NEUTRAL_HOLD"
    assert signal.composite_score < 0.50
    assert "NEUTRAL_HOLD" in signal.rationale


def test_analyze_congressional_flow_mismatched_ticker_or_unconfirmed_flow():
    trade = PoliticianTrade(
        ticker="NVDA",
        politician="Dan Crenshaw",
        chamber="house",
        party="R",
        transaction_type="purchase",
        trade_date="2026-09-20",
        disclosure_date="2026-09-22",
        amount_min=100_000,
        amount_max=250_000,
    )
    # Flow for AAPL, not NVDA
    flow_mismatch = OptionsFlowSignal(
        ticker="AAPL",
        option_type="call",
        strike=230.0,
        expiration="2026-10-16",
        premium=500_000.0,
        volume_oi_ratio=3.0,
        side="ask",
    )
    signal1 = analyze_congressional_flow(trade, flow=flow_mismatch)
    assert signal1.flow_confirmation is False
    assert signal1.flow_details is None

    # Flow is put (bearish) on bullish trade -> does not confirm
    flow_unconfirmed = OptionsFlowSignal(
        ticker="NVDA",
        option_type="put",
        strike=110.0,
        expiration="2026-10-16",
        premium=500_000.0,
        volume_oi_ratio=3.0,
        side="ask",
    )
    signal2 = analyze_congressional_flow(trade, flow=flow_unconfirmed)
    assert signal2.flow_confirmation is False

    # Flow on bid side -> does not confirm
    flow_bid = OptionsFlowSignal(
        ticker="NVDA",
        option_type="call",
        strike=130.0,
        expiration="2026-10-16",
        premium=500_000.0,
        volume_oi_ratio=3.0,
        side="bid",
    )
    signal3 = analyze_congressional_flow(trade, flow=flow_bid)
    assert signal3.flow_confirmation is False
