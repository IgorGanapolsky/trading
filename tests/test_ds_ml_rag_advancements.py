import pytest
from src.analysis.iv_skew_analyzer import IVSkewAnalyzer
from src.ml.offline_policy_eval import OfflinePolicyEvaluator
from src.rag.rag_reranker import RAGReranker


def test_iv_skew_analyzer():
    analyzer = IVSkewAnalyzer(min_iv_rank_threshold=25.0)
    metrics = analyzer.calculate_metrics(
        symbol="SPY",
        current_iv=0.22,
        iv_52wk_low=0.12,
        iv_52wk_high=0.32,
    )

    assert metrics.symbol == "SPY"
    assert metrics.iv_rank == 50.0
    assert metrics.is_premium_rich is True


def test_offline_policy_evaluator():
    evaluator = OfflinePolicyEvaluator()
    trajectories = [
        {"reward": 10.0, "behavior_prob": 0.5},
        {"reward": 15.0, "behavior_prob": 0.6},
    ]
    res = evaluator.evaluate_policy(trajectories, lambda x: 0.55)

    assert res.total_episodes == 2
    assert res.raw_reward_mean > 0.0
    assert res.ips_value_estimate > 0.0


def test_rag_reranker():
    reranker = RAGReranker()
    candidates = [
        {"id": "LL-100", "title": "General Options Trade", "content": "Basic options overview", "score": 0.5},
        {"id": "LL-295", "title": "Drawdown & Circuit Breaker Rules", "content": "Halt trading if drawdown reaches 5%", "score": 0.6},
    ]
    results = reranker.rerank("circuit breaker drawdown", candidates)

    assert len(results) == 2
    assert results[0].lesson_id == "LL-295"
    assert results[0].reranked_score > results[1].reranked_score
