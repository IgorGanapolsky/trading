"""Tests for AI cycle signal updater."""

from scripts.update_ai_cycle_signal import evaluate_ai_cycle_signal


def test_evaluate_ai_cycle_signal_blocks_on_capex_deceleration_shock() -> None:
    status, score, multiplier, regime, shock, gm_trend_bps, confidence, reasons = (
        evaluate_ai_cycle_signal(
            capex_ret_20d=-0.11,
            capex_ret_5d=-0.08,
            infra_ret_20d=-0.12,
            edge_ret_20d=-0.03,
            nvda_gross_margin_pct=73.0,
            prior_nvda_gross_margin_pct=75.0,
        )
    )

    assert status == "blocked"
    assert score >= 60.0
    assert multiplier < 1.0
    assert regime == "capex_deceleration"
    assert shock is True
    assert gm_trend_bps == -200.0
    assert confidence >= 0.2
    assert reasons


def test_evaluate_ai_cycle_signal_passes_on_edge_monetization_strength() -> None:
    status, score, multiplier, regime, shock, gm_trend_bps, _confidence, reasons = (
        evaluate_ai_cycle_signal(
            capex_ret_20d=0.03,
            capex_ret_5d=0.02,
            infra_ret_20d=0.04,
            edge_ret_20d=0.10,
            nvda_gross_margin_pct=76.0,
            prior_nvda_gross_margin_pct=75.0,
        )
    )

    assert status == "pass"
    assert score < 30.0
    assert multiplier == 1.0
    assert regime == "edge_monetization"
    assert shock is False
    assert gm_trend_bps == 100.0
    assert reasons


def test_evaluate_ai_cycle_signal_unknown_when_no_data() -> None:
    status, score, multiplier, regime, shock, gm_trend_bps, confidence, reasons = (
        evaluate_ai_cycle_signal(
            capex_ret_20d=None,
            capex_ret_5d=None,
            infra_ret_20d=None,
            edge_ret_20d=None,
            nvda_gross_margin_pct=None,
            prior_nvda_gross_margin_pct=None,
        )
    )

    assert status == "unknown"
    assert score == 0.0
    assert multiplier == 1.0
    assert regime == "unknown"
    assert shock is False
    assert gm_trend_bps is None
    assert confidence == 0.0
    assert reasons
