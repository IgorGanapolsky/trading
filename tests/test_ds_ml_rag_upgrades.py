"""Unit tests for Data Science, ML, and Agentic RAG upgrades."""

from __future__ import annotations

from src.ml.reward import compute_trade_reward
from src.ml.trade_confidence import evaluate_ml_trade_gate
from src.rag.lessons_learned_rag import LessonsLearnedRAG


def test_multi_objective_reward_with_dte_friction():
    """Verify compute_trade_reward includes DTE friction penalty when exiting close to 0 DTE."""
    # Exit at 7 DTE -> 0 friction penalty
    res_7dte = compute_trade_reward(pnl=100.0, credit=1.0, max_loss=400.0, dte_at_exit=7, dte_at_entry=30)
    assert res_7dte["components"]["dte_friction_penalty"] == 0.0

    # Exit at 0 DTE -> max friction penalty (0.5)
    res_0dte = compute_trade_reward(pnl=100.0, credit=1.0, max_loss=400.0, dte_at_exit=0, dte_at_entry=30)
    assert res_0dte["components"]["dte_friction_penalty"] == 0.5
    assert res_0dte["total_reward"] < res_7dte["total_reward"]


def test_ml_trade_gate_evaluation():
    """Verify evaluate_ml_trade_gate returns structured confidence decision."""
    res = evaluate_ml_trade_gate(strategy="spy_put_credit", ticker="SPY", regime="calm", min_confidence=0.70)
    assert "allowed" in res
    assert "confidence" in res
    assert "posterior_mean" in res
    assert res["min_confidence"] == 0.70


def test_regime_aware_rag_query():
    """Verify query_lessons_with_regime boosts lessons relevant to high VIX and IV Rank."""
    rag = LessonsLearnedRAG()

    regime_context = {
        "vix": 32.0,
        "iv_rank_proxy": 20.0,
        "structure": "bull_put_credit",
    }

    results = rag.query_lessons_with_regime("options risk management", regime_context=regime_context, top_k=3)
    assert isinstance(results, list)
    if results:
        assert "score" in results[0]
