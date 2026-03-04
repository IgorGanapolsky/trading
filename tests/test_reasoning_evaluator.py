from src.safety.reasoning_evaluator import ReasoningEvaluator


def test_evaluator_high_groundedness():
    evaluator = ReasoningEvaluator(threshold=0.7)
    proposal = {"strategy": "iron_condor", "side": "BUY"}
    reasoning = "Following Phil Town Rule #1, utilizing a 100% stop-loss, checking VIX, and 15-delta strikes for 50% profit or 7 dte exit."
    context = [
        "Rule #1 is to not lose money. Use 15-delta, check VIX, and 100% stop-loss for 50% profit or 7 dte exit."
    ]

    score = evaluator.evaluate(proposal, reasoning, context)

    assert score.is_hallucination_risk is False
    assert score.groundedness > 0.6  # Matches multiple keywords
    assert score.signal_relevance == 1.0


def test_evaluator_low_groundedness_hallucination():
    evaluator = ReasoningEvaluator(threshold=0.7)
    proposal = {"strategy": "iron_condor"}
    # Reasoning has no connection to the context keywords
    reasoning = "I think the market will go up because of moon phases."
    context = ["Rule #1 is to not lose money. Use 15-delta and 100% stop-loss."]

    score = evaluator.evaluate(proposal, reasoning, context)

    assert score.is_hallucination_risk is True
    assert score.groundedness < 0.7


def test_evaluator_context_relevance_missing_vix():
    evaluator = ReasoningEvaluator(threshold=0.7)
    proposal = {"strategy": "iron_condor"}
    reasoning = "Entering iron condor based on moving average."
    context = ["VIX needs to be checked."]

    score = evaluator.evaluate(proposal, reasoning, context)

    assert score.is_hallucination_risk is True
    assert score.context_relevance == 0.5  # Penalty for missing VIX on Iron Condor


def test_evaluator_signal_contradiction():
    evaluator = ReasoningEvaluator(threshold=0.7)
    proposal = {"strategy": "iron_condor", "side": "SELL"}
    reasoning = "I am going to reject this trade."
    context = ["Rule #1 is important."]

    score = evaluator.evaluate(proposal, reasoning, context)

    assert score.is_hallucination_risk is True
    assert score.signal_relevance == 0.0  # Contradiction between SELL side and 'reject' reasoning
