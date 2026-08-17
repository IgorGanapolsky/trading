"""Tests for StrategyResearchCritic and JudgePanel research routing."""

from __future__ import annotations


from src.evals.judge_panel import TaskKind, run_panel
from src.evals.research_critic import StrategyResearchCritic, evaluate_strategy_candidate


def test_critic_rejects_empty_spec():
    critic = StrategyResearchCritic()
    verdict = critic.evaluate_text("")
    assert not verdict.passed
    assert verdict.vetoed
    assert verdict.score == 0.0
    assert any(f.code == "EMPTY_SPEC" for f in verdict.findings)


def test_critic_vetoes_ten_wide_wings():
    critic = StrategyResearchCritic()
    verdict = critic.evaluate_text(
        "Open 10-wide SPY put credit spread with 30 DTE, take profit 25%, stop loss 200%, exit 7 DTE."
    )
    assert not verdict.passed
    assert verdict.vetoed
    assert any(f.code == "TEN_WIDE_WINGS" for f in verdict.findings)


def test_critic_vetoes_killed_iron_condor():
    critic = StrategyResearchCritic()
    verdict = critic.evaluate_text(
        "Resume iron condor execution on SPY with 15 delta wings, take profit 50%, stop loss 200%."
    )
    assert not verdict.passed
    assert verdict.vetoed
    assert any(f.code == "KILLED_FAMILY_IC" for f in verdict.findings)


def test_critic_vetoes_multi_lot_scaling_prematurely():
    critic = StrategyResearchCritic()
    verdict = critic.evaluate_text(
        "Sell put spread and scale to 5 contracts on SPY, take profit 25%, stop loss 200%."
    )
    assert not verdict.passed
    assert verdict.vetoed
    assert any(f.code == "MULTI_LOT_SCALING" for f in verdict.findings)


def test_critic_vetoes_sub_24h_churn():
    critic = StrategyResearchCritic()
    verdict = critic.evaluate_text(
        "Sell 1-lot SPY credit spread with intraday exit when profit hits $10, stop loss 200%."
    )
    assert not verdict.passed
    assert verdict.vetoed
    assert any(f.code == "SUB_24H_CHURN" for f in verdict.findings)


def test_critic_vetoes_unhedged_shorts():
    critic = StrategyResearchCritic()
    verdict = critic.evaluate_text("Sell 1 naked put on SPY at 15 delta with stop loss 200%.")
    assert not verdict.passed
    assert verdict.vetoed
    assert any(f.code == "UNHEDGED_SHORT" for f in verdict.findings)


def test_critic_warns_missing_regime_gate():
    critic = StrategyResearchCritic()
    verdict = critic.evaluate_text(
        "Sell 1-lot 30-45 DTE SPY put credit spread, $5-wide wings, 15 delta, take profit 25%, stop loss 200%, exit 7 DTE."
    )
    assert verdict.passed
    assert not verdict.vetoed
    assert verdict.score == 0.7
    assert any(f.code == "MISSING_REGIME_GATE" for f in verdict.findings)


def test_critic_approves_fully_governed_put_credit():
    spec = {
        "strategy_id": "spy_put_credit",
        "hypothesis": "Defined-risk bull put credit on SPY captures equity drift safely.",
        "rules": {
            "entry": "Sell 1-lot 30-45 DTE SPY put at 15 delta, buy put $5 lower, min credit $0.50.",
            "exit": "Take profit 25%, stop loss 200%, exit by 7 DTE, min hold 24h.",
            "risk": "1 contract max, paper validation only.",
            "regime": "IVR >= 30, VIX <= 30, SPY > 200-DMA.",
        },
    }
    verdict = evaluate_strategy_candidate(spec)
    assert verdict.passed
    assert not verdict.vetoed
    assert verdict.score == 1.0
    assert len(verdict.findings) == 0


def test_judge_panel_strategy_research_routing():
    verdict = run_panel(
        kind=TaskKind.STRATEGY_RESEARCH,
        text=(
            "Sell 1-lot 30-45 DTE SPY put credit spread, $5-wide wings, 15-delta short leg, "
            "take profit 25%, stop loss 200%, exit by 7 DTE, regime filter IVR >= 30 and VIX <= 30."
        ),
    )
    assert verdict.passed
    assert not verdict.vetoed
    assert "research_critic" in verdict.experts_used
    assert "risk_rules" in verdict.experts_used
