"""Tests for put-credit regime gate and counterfactuals."""

from __future__ import annotations

from src.risk.put_credit_regime import (
    RegimeSnapshot,
    attach_counterfactuals,
    evaluate_entry_operating_system,
    evaluate_regime_gate,
)


def _snap(**kwargs) -> RegimeSnapshot:
    base = dict(
        captured_at="2026-07-24T00:00:00+00:00",
        spy_price=740.0,
        vix=18.0,
        iv_rank_proxy=45.0,
        iv_rank_method="test",
        spy_sma_200=700.0,
        spy_above_200dma=True,
        spy_sma_50=720.0,
        spy_above_50dma=True,
        source_errors=(),
    )
    base.update(kwargs)
    return RegimeSnapshot(**base)


def test_regime_allows_healthy_short_premium():
    gate = evaluate_regime_gate(_snap())
    assert gate["allowed"] is True
    assert gate["blockers"] == []


def test_regime_blocks_high_vix():
    gate = evaluate_regime_gate(_snap(vix=35.0))
    assert gate["allowed"] is False
    assert any("VIX" in b for b in gate["blockers"])


def test_regime_blocks_low_ivr():
    gate = evaluate_regime_gate(_snap(iv_rank_proxy=10.0))
    assert gate["allowed"] is False
    assert any("IV rank" in b for b in gate["blockers"])


def test_regime_allows_lean_premium_above_paper_floor():
    """Paper floor may be below research preferred IVR; soft-flag lean premium."""
    gate = evaluate_regime_gate(_snap(iv_rank_proxy=18.0), min_iv_rank=10.0)
    assert gate["allowed"] is True
    assert gate["blockers"] == []
    assert any("research preferred" in f for f in gate["soft_flags"])
    assert gate["thresholds"]["research_preferred_ivr"] == 30.0


def test_regime_still_blocks_below_paper_floor():
    gate = evaluate_regime_gate(_snap(iv_rank_proxy=5.0), min_iv_rank=10.0)
    assert gate["allowed"] is False
    assert any("IV rank" in b for b in gate["blockers"])


def test_regime_paper_floor_zero_soft_flags_low_ivr():
    """AGENT-566: paper MIN_IVR=0 must not freeze on VIX-percentile 4.9 when VIX=14.61."""
    gate = evaluate_regime_gate(_snap(vix=14.61, iv_rank_proxy=4.9), min_iv_rank=0.0)
    assert gate["allowed"] is True
    assert gate["blockers"] == []
    assert any("research preferred" in f for f in gate["soft_flags"])


def test_regime_paper_floor_zero_missing_ivr_is_soft_flag():
    """Greptile #4471 P2: paper floor 0 changes only the iv_rank_proxy=None branch."""
    gate = evaluate_regime_gate(_snap(vix=14.61, iv_rank_proxy=None), min_iv_rank=0.0)
    assert gate["allowed"] is True
    assert gate["blockers"] == []
    assert any("IV rank proxy unavailable" in f for f in gate["soft_flags"])


def test_regime_missing_vix_fail_closed():
    gate = evaluate_regime_gate(_snap(vix=None), fail_closed_on_missing=True)
    assert gate["allowed"] is False
    assert any("VIX unavailable" in b for b in gate["blockers"])


def test_regime_missing_ivr_fail_closed():
    """Greptile #4280: unavailable IVR must block, not invent IVR=50."""
    gate = evaluate_regime_gate(_snap(iv_rank_proxy=None), fail_closed_on_missing=True)
    assert gate["allowed"] is False
    assert any("IV rank" in b for b in gate["blockers"])


def test_regime_missing_vix_fail_open():
    gate = evaluate_regime_gate(_snap(vix=None), fail_closed_on_missing=False)
    assert gate["allowed"] is True
    assert any("VIX unavailable" in f for f in gate["soft_flags"])


def test_trend_soft_flag_by_default():
    gate = evaluate_regime_gate(_snap(spy_above_200dma=False), require_above_200dma=False)
    assert gate["allowed"] is True
    assert any("200-day" in f for f in gate["soft_flags"])


def test_trend_hard_when_required():
    gate = evaluate_regime_gate(_snap(spy_above_200dma=False), require_above_200dma=True)
    assert gate["allowed"] is False


def test_50dma_soft_flag_by_default():
    gate = evaluate_regime_gate(_snap(spy_above_50dma=False), require_above_50dma=False)
    assert gate["allowed"] is True
    assert any("50-day" in f for f in gate["soft_flags"])
    assert gate["thresholds"]["require_above_50dma"] is False


def test_50dma_hard_when_required():
    gate = evaluate_regime_gate(_snap(spy_above_50dma=False), require_above_50dma=True)
    assert gate["allowed"] is False
    assert any("50-day" in b for b in gate["blockers"])


def test_entry_os_passes_when_all_four_yes():
    gate = evaluate_regime_gate(_snap())
    opp = {
        "expiry": "2026-10-23",
        "short_put": 725.0,
        "long_put": 720.0,
        "est_credit": 0.67,
        "quantity": 1,
        "put_delta": 0.18,
        "dte": 40,
    }
    risk = {
        "entry": {"expiry": "2026-10-23"},
        "quantity": 1,
        "stop_loss": 2.0,
        "take_profit": 0.25,
        "time_exit": 7,
    }
    os_result = evaluate_entry_operating_system(regime_gate=gate, opportunity=opp, risk_plan=risk)
    assert os_result["pass"] is True
    assert os_result["fails"] == []
    assert os_result["answers"]["market_healthy"]["yes"] is True
    assert os_result["answers"]["structure_strong"]["yes"] is True
    assert os_result["answers"]["clean_technical_setup"]["yes"] is True
    assert os_result["answers"]["predefined_risk"]["yes"] is True


def test_entry_os_fails_without_predefined_risk():
    gate = evaluate_regime_gate(_snap())
    opp = {
        "expiry": "2026-10-23",
        "short_put": 725.0,
        "long_put": 720.0,
        "est_credit": 0.67,
        "quantity": 1,
        "put_delta": 0.18,
        "dte": 40,
    }
    os_result = evaluate_entry_operating_system(regime_gate=gate, opportunity=opp, risk_plan=None)
    assert os_result["pass"] is False
    assert "predefined_risk=no" in os_result["fails"]


def test_entry_os_fails_when_market_unhealthy():
    gate = evaluate_regime_gate(_snap(vix=40.0))
    opp = {
        "expiry": "2026-10-23",
        "short_put": 725.0,
        "long_put": 720.0,
        "est_credit": 0.67,
        "quantity": 1,
        "put_delta": 0.18,
        "dte": 40,
    }
    risk = {
        "entry": {"expiry": "2026-10-23"},
        "quantity": 1,
        "stop_loss": 2.0,
        "take_profit": 0.25,
        "time_exit": 7,
    }
    os_result = evaluate_entry_operating_system(regime_gate=gate, opportunity=opp, risk_plan=risk)
    assert os_result["pass"] is False
    assert "market_healthy=no" in os_result["fails"]


def test_ignore_regime_gate_only_bypasses_market_healthy_failure():
    """CodeRabbit #4579: --ignore-regime-gate must not waive structure/risk OS fails."""
    fails = ["market_healthy=no", "predefined_risk=no"]
    ignore_regime_gate = True
    blocking = [
        failure for failure in fails if failure != "market_healthy=no" or not ignore_regime_gate
    ]
    assert blocking == ["predefined_risk=no"]

    ignore_regime_gate = False
    blocking = [
        failure for failure in fails if failure != "market_healthy=no" or not ignore_regime_gate
    ]
    assert blocking == ["market_healthy=no", "predefined_risk=no"]


def test_counterfactuals_tp50_and_21dte():
    base = {
        "should_exit": False,
        "exit_reason": None,
        "estimated_pnl": 20.0,
        "credit": 0.80,
    }
    out = attach_counterfactuals(base, credit=0.80, quantity=1, dte=15)
    cf = out["counterfactuals"]
    assert cf["tp_50_target"] == 40.0
    assert cf["would_hit_tp_25_now"] is True  # 20 >= 20
    assert cf["would_hit_tp_50_now"] is False  # 20 < 40
    assert cf["would_trigger_public_21dte_exit"] is True  # dte 15 <= 21


def test_exit_eval_includes_counterfactuals():
    from scripts.spy_put_credit import evaluate_put_credit_exit

    entry = {
        "expiry": "2026-08-28",
        "credit": 1.0,
        "quantity": 1,
        "entry_time": "2026-07-01T15:00:00+00:00",
        "signature": "SPY_2026-08-28_P690-695",
    }
    # short - long = debit; credit 1.0, debit 0.5 → pnl 50, max profit 100 → 50% TP
    detail = evaluate_put_credit_exit(entry, short_price=1.0, long_price=0.5)
    assert "counterfactuals" in detail
    assert detail["counterfactuals"]["would_hit_tp_50_now"] is True
