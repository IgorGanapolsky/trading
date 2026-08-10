"""Unit tests for answer-level RAG metrics (faithfulness, groundedness, relevance)."""

from __future__ import annotations

from src.rag.answer_metrics import (
    AnswerScore,
    RAGAnswerMetrics,
    estimate_claims,
    measure_answer_metrics,
    recognize_supporting_facts,
)


def test_estimate_claims_basic():
    text = "SPY is an ETF tracking the S&P 500 index. Options expire on Fridays!"
    claims = estimate_claims(text)
    assert len(claims) == 2
    assert claims[0] == "SPY is an ETF tracking the S&P 500 index"
    assert claims[1] == "Options expire on Fridays"


def test_estimate_claims_empty():
    assert estimate_claims("") == []
    assert estimate_claims("   ") == []


def test_recognize_supporting_facts():
    context = [
        "SPY tracks the S&P 500 market index.",
        "Put credit spreads collect premium upfront.",
    ]
    facts = recognize_supporting_facts(context)
    assert "spy" in facts
    assert "tracks" in facts
    assert "credit" in facts
    assert "spreads" in facts
    assert "the" not in facts  # Stop word removed


def test_measure_answer_metrics_faithful_and_grounded():
    question = "What does SPY track?"
    answer = "SPY is an ETF that tracks the S&P 500 index."
    context = ["SPY tracks the S&P 500 index of large cap US equities."]

    score = measure_answer_metrics(
        question=question,
        answer=answer,
        context=context,
    )

    assert isinstance(score, AnswerScore)
    assert 0.0 <= score.faithfulness <= 1.0
    assert 0.0 <= score.groundedness <= 1.0
    assert 0.0 <= score.answer_relevance <= 1.0
    assert score.n_claims >= 1
    assert score.faithfulness > 0.5
    assert score.groundedness > 0.5

    d = score.to_dict()
    assert "faithfulness" in d
    assert "groundedness" in d
    assert "answer_relevance" in d
    assert "coverage" in d


def test_measure_answer_metrics_hallucinated():
    question = "What is the return of SPY?"
    answer = "Quantum computing yields 5000 percent annual profits on Bitcoin."
    context = ["SPY is an index fund tracking top US companies."]

    score = measure_answer_metrics(
        question=question,
        answer=answer,
        context=context,
    )

    assert score.faithfulness == 0.0
    assert score.groundedness == 0.0
    assert score.n_supported_claims == 0


def test_measure_answer_metrics_empty_inputs():
    score = measure_answer_metrics(
        question="",
        answer="",
        context=[],
    )
    assert score.faithfulness == 0.0
    assert score.groundedness == 0.0
    assert score.answer_relevance == 0.0
    assert score.n_claims == 0


def test_custom_claim_splitter():
    def custom_splitter(text: str) -> list[str]:
        return [c.strip() for c in text.split(";") if c.strip()]

    metrics = RAGAnswerMetrics(claim_splitter=custom_splitter)
    score = metrics.measure(
        question="Tell me about options.",
        answer="Options give rights; Spreads limit risk",
        context=["Options give rights to buyers and spreads limit total risk."],
    )
    assert score.n_claims == 2
    assert score.faithfulness > 0.5
