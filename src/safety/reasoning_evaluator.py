"""
Reasoning Evaluator - Lightweight TruLens Pattern
Quantifies the quality of trade reasoning using the RAG Triad:
1. Groundedness (Source verification)
2. Context Relevance (Market data alignment)
3. Signal Relevance (Strategy adherence)
"""

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class EvaluationScore:
    groundedness: float  # 0.0 to 1.0
    context_relevance: float
    signal_relevance: float
    reasoning_trace: str
    is_hallucination_risk: bool


class ReasoningEvaluator:
    """
    Evaluates LLM reasoning traces against RAG context and market data.
    """

    def __init__(self, threshold: float = 0.8):
        self.threshold = threshold

    def evaluate(
        self, proposal: dict[str, Any], reasoning: str, retrieved_context: list[str]
    ) -> EvaluationScore:
        """
        Calculates RAG Triad scores for a trade proposal.
        """
        logger.info("🧪 Instrumenting trade reasoning for evaluation...")

        # 1. Calculate Groundedness (Does reasoning match RAG lessons + protocol?)
        context_text = " ".join(retrieved_context).lower()
        reasoning_lower = reasoning.lower()
        strategy = str(proposal.get("strategy") or "").strip().lower()

        # Strategy-aware protocol keywords (must appear in reasoning AND retrieved context)
        if strategy in {
            "spy_put_credit",
            "bull_put",
            "bull_put_credit",
            "put_credit",
            "credit_spread",
        }:
            checks = [
                "rule #1",
                "stop-loss",
                "15-delta",
                "7 dte",
                "1-lot",
                "credit",
            ]
        else:
            checks = ["rule #1", "stop-loss", "vix", "15-delta", "50% profit", "7 dte"]

        grounded_points = 0
        for check in checks:
            if check in context_text and check in reasoning_lower:
                grounded_points += 1

        groundedness = grounded_points / len(checks) if len(checks) > 0 else 1.0

        # 2. Context Relevance (Is the market data used relevant to the strategy?)
        context_relevance = 1.0  # Default high for now
        if "vix" not in reasoning_lower and strategy == "iron_condor":
            context_relevance = 0.5  # Major signal missing
        if not context_text.strip():
            context_relevance = 0.0  # openings require retrieved lessons

        # 3. Signal Relevance (Does the proposal match the reasoning?)
        signal_relevance = 1.0
        if "reject" in reasoning_lower and proposal.get("side") == "SELL":
            signal_relevance = 0.0  # Contradictory logic

        is_risk = (
            groundedness < self.threshold
            or context_relevance < self.threshold
            or signal_relevance < self.threshold
        )

        score = EvaluationScore(
            groundedness=groundedness,
            context_relevance=context_relevance,
            signal_relevance=signal_relevance,
            reasoning_trace=f"G:{groundedness:.2f} | C:{context_relevance:.2f} | S:{signal_relevance:.2f}",
            is_hallucination_risk=is_risk,
        )

        if is_risk:
            logger.warning(f"🚨 Hallucination Risk Detected: {score.reasoning_trace}")
        else:
            logger.info(f"✅ Reasoning Validated: {score.reasoning_trace}")

        return score
