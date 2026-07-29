"""Unit tests for 4-tier graded relevance and native nDCG@k evaluation."""

from __future__ import annotations

from src.rag.evaluation import EvaluationQuery, RAGEvaluator


def test_evaluation_query_graded_relevance_defaults():
    """Verify EvaluationQuery populates default grades (3 for expected, 0 for avoid)."""
    q = EvaluationQuery(
        query="test query",
        expected_lesson_ids=["LL-100", "LL-101"],
        avoid_lesson_ids=["LL-999"],
    )
    assert q.graded_relevance["ll-100"] == 3
    assert q.graded_relevance["ll-101"] == 3
    assert q.graded_relevance["ll-999"] == 0


def test_evaluation_query_explicit_4tier_graded_relevance():
    """Verify explicit 4-tier graded relevance (3=CRITICAL, 2=HIGH, 1=Context, 0=Irrelevant)."""
    q = EvaluationQuery(
        query="iron condor exit",
        expected_lesson_ids=["LL-268", "LL-301"],
        graded_relevance={
            "LL-268": 3,  # CRITICAL Block
            "LL-301": 2,  # HIGH Advisory
            "LL-100": 1,  # Context
            "LL-999": 0,  # Irrelevant
        },
    )
    assert q.graded_relevance["ll-268"] == 3
    assert q.graded_relevance["ll-301"] == 2
    assert q.graded_relevance["ll-100"] == 1
    assert q.graded_relevance["ll-999"] == 0


def test_ndcg_at_k_calculation_perfect_vs_suboptimal():
    """Verify ndcg_at_k returns 1.0 for ideal ranking and < 1.0 when critical doc is demoted."""
    evaluator = RAGEvaluator(test_queries=[])
    grades = {"ll-critical": 3, "ll-high": 2, "ll-context": 1}

    # Ideal ranking: critical (3), high (2), context (1)
    ideal_retrieved = ["ll-critical", "ll-high", "ll-context"]
    score_ideal = evaluator.ndcg_at_k(ideal_retrieved, grades, k=3)
    assert score_ideal == 1.0

    # Sub-optimal ranking: context (1), high (2), critical (3)
    sub_retrieved = ["ll-context", "ll-high", "ll-critical"]
    score_sub = evaluator.ndcg_at_k(sub_retrieved, grades, k=3)
    assert 0.0 < score_sub < 1.0
