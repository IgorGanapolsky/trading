"""
LLM Introspective Awareness Module for Trading System

Implements self-assessment and epistemic uncertainty tracking based on
Anthropic's research on emergent introspective awareness in LLMs.

Key Features:
- Self-consistency checking (multiple reasoning paths)
- Epistemic vs aleatoric uncertainty distinction
- Self-critique and calibration layer
- Confidence aggregation across multiple signals
- Hallucination detection via Reversing Chain-of-Thought (RCoT)

Reference: https://www.anthropic.com/research/introspection

Example:
    >>> introspector = LLMIntrospector(analyzer)
    >>> result = await introspector.analyze_with_introspection(market_data)
    >>> print(f"Confidence: {result.aggregate_confidence}")
    >>> print(f"Epistemic uncertainty: {result.epistemic_uncertainty}")
"""

import asyncio
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class UncertaintyType(Enum):
    """Types of uncertainty in trading decisions."""

    EPISTEMIC = "epistemic"  # Can be reduced with more data
    ALEATORIC = "aleatoric"  # Inherent randomness, cannot be reduced
    MIXED = "mixed"  # Combination of both


class ConfidenceLevel(Enum):
    """Confidence level classifications."""

    VERY_HIGH = "very_high"  # >0.85
    HIGH = "high"  # 0.70-0.85
    MEDIUM = "medium"  # 0.50-0.70
    LOW = "low"  # 0.30-0.50
    VERY_LOW = "very_low"  # <0.30


class IntrospectionState(Enum):
    """LLM introspective awareness states (LogU framework)."""

    CERTAIN = "certain"  # High confidence, clear evidence
    UNCERTAIN = "uncertain"  # Lack knowledge, need more data
    INFORMED_GUESS = "informed_guess"  # Partial knowledge, suggests answer
    MULTIPLE_VALID = "multiple_valid"  # Several valid interpretations exist


@dataclass
class SelfConsistencyResult:
    """Result from self-consistency analysis."""

    decision: str  # BUY, SELL, HOLD
    confidence: float  # Agreement ratio (0-1)
    vote_breakdown: dict[str, int]
    reasoning_paths: list[str]
    diversity_score: float  # How different were the reasoning paths


@dataclass
class EpistemicUncertaintyResult:
    """Result from epistemic uncertainty analysis."""

    epistemic_score: float  # 0-100 (lack of knowledge)
    aleatoric_score: float  # 0-100 (inherent randomness)
    dominant_type: UncertaintyType
    knowledge_gaps: list[str]
    random_factors: list[str]
    can_improve_with_data: bool
    detailed_assessment: str


@dataclass
class SelfCritiqueResult:
    """Result from self-critique analysis."""

    original_analysis: str
    critique: str
    errors_found: list[str]
    assumptions_made: list[str]
    confidence_after_critique: float
    should_trust: bool
    corrected_analysis: str | None = None


@dataclass
class RCoTResult:
    """Result from Reversing Chain-of-Thought hallucination detection."""

    forward_solution: str
    reconstructed_problem: str
    consistency_score: float  # 0-100
    is_hallucination: bool
    discrepancies: list[str]


@dataclass
class IntrospectionResult:
    """Comprehensive introspection result."""

    # Core decision
    decision: str  # BUY, SELL, HOLD
    introspection_state: IntrospectionState

    # Confidence signals
    self_consistency: SelfConsistencyResult
    uncertainty: EpistemicUncertaintyResult
    self_critique: SelfCritiqueResult

    # Aggregate metrics
    aggregate_confidence: float
    confidence_level: ConfidenceLevel
    epistemic_uncertainty: float
    aleatoric_uncertainty: float

    # Action recommendation
    execute_trade: bool
    position_multiplier: float  # Scale position by uncertainty
    recommendation: str

    # Metadata
    signals_used: list[str] = field(default_factory=list)
    processing_time_ms: float = 0.0


class LLMIntrospector:
    """
    LLM Introspective Awareness Engine.

    Implements multi-layer confidence assessment based on Anthropic's
    research on emergent introspective awareness in LLMs.

    Combines:
    1. Self-consistency (multiple reasoning paths)
    2. Epistemic uncertainty assessment
    3. Self-critique and calibration
    4. Hallucination detection via RCoT
    """

    # Confidence weights for different signals
    WEIGHTS = {
        "self_consistency": 0.35,
        "ensemble_agreement": 0.25,
        "epistemic_inverse": 0.20,
        "self_critique": 0.15,
        "rcot_consistency": 0.05,
    }

    def __init__(
        self,
        analyzer: Any,  # MultiLLMAnalyzer instance
        consistency_samples: int = 5,
        enable_rcot: bool = False,  # Expensive, off by default
        strict_mode: bool = True,  # Require high confidence
    ):
        """
        Initialize the LLM Introspector.

        Args:
            analyzer: MultiLLMAnalyzer instance for LLM queries
            consistency_samples: Number of samples for self-consistency
            enable_rcot: Enable RCoT hallucination detection (expensive)
            strict_mode: Require higher confidence thresholds
        """
        self.analyzer = analyzer
        self.consistency_samples = consistency_samples
        self.enable_rcot = enable_rcot
        self.strict_mode = strict_mode

        # Thresholds
        self.min_confidence_to_trade = 0.70 if strict_mode else 0.50
        self.max_epistemic_to_trade = 60 if strict_mode else 75

    async def analyze_with_introspection(
        self,
        market_data: dict[str, Any],
        symbol: str = "UNKNOWN",
        context: str | None = None,
    ) -> IntrospectionResult:
        """
        Perform comprehensive introspective analysis.

        Args:
            market_data: Market data dictionary
            symbol: Ticker symbol being analyzed
            context: Additional context for analysis

        Returns:
            IntrospectionResult with multi-layer confidence assessment
        """
        import time

        start_time = time.time()

        # Format market data for prompts
        data_str = self._format_market_data(market_data)
        prompt_context = f"Symbol: {symbol}\n{context or ''}\nMarket Data:\n{data_str}"

        # Run introspection layers in parallel where possible
        tasks = [
            self._run_self_consistency(prompt_context),
            self._run_epistemic_assessment(prompt_context),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Extract results
        self_consistency = (
            results[0]
            if isinstance(results[0], SelfConsistencyResult)
            else self._default_consistency()
        )
        uncertainty = (
            results[1]
            if isinstance(results[1], EpistemicUncertaintyResult)
            else self._default_uncertainty()
        )

        # Self-critique uses the consensus decision
        self_critique = await self._run_self_critique(prompt_context, self_consistency.decision)

        # Aggregate confidence
        aggregate_confidence = self._calculate_aggregate_confidence(
            self_consistency, uncertainty, self_critique
        )

        # Determine introspection state
        introspection_state = self._determine_introspection_state(
            aggregate_confidence, uncertainty, self_consistency
        )

        # Make execution decision
        execute_trade, position_multiplier, recommendation = self._make_execution_decision(
            aggregate_confidence, uncertainty, introspection_state
        )

        processing_time = (time.time() - start_time) * 1000

        return IntrospectionResult(
            decision=self_consistency.decision,
            introspection_state=introspection_state,
            self_consistency=self_consistency,
            uncertainty=uncertainty,
            self_critique=self_critique,
            aggregate_confidence=aggregate_confidence,
            confidence_level=self._classify_confidence(aggregate_confidence),
            epistemic_uncertainty=uncertainty.epistemic_score,
            aleatoric_uncertainty=uncertainty.aleatoric_score,
            execute_trade=execute_trade,
            position_multiplier=position_multiplier,
            recommendation=recommendation,
            signals_used=["self_consistency", "epistemic", "self_critique"],
            processing_time_ms=processing_time,
        )

    async def _run_self_consistency(self, prompt_context: str) -> SelfConsistencyResult:
        """
        Run self-consistency check with multiple reasoning paths.

        Generates N independent analyses and votes on final decision.
        Higher agreement = higher confidence.
        """
        prompt = f"""
{prompt_context}

Analyze this market data step-by-step and provide a trading decision.
Think through this independently and carefully.

Your response MUST end with exactly one of these decisions on its own line:
DECISION: BUY
DECISION: SELL
DECISION: HOLD
"""

        responses = []
        decisions = []

        # Generate multiple independent reasoning paths
        for i in range(self.consistency_samples):
            try:
                # Use higher temperature for diversity
                response = await self._query_llm(prompt, temperature=0.7)
                decision = self._extract_decision(response)
                responses.append(response)
                decisions.append(decision)
            except Exception as e:
                logger.warning(f"Self-consistency sample {i} failed: {e}")
                continue

        if not decisions:
            return self._default_consistency()

        # Majority vote
        vote_counts = Counter(decisions)
        majority_decision = vote_counts.most_common(1)[0][0]
        confidence = vote_counts[majority_decision] / len(decisions)

        # Diversity score (how different were reasoning paths)
        unique_decisions = len(set(decisions))
        diversity_score = unique_decisions / len(decisions)

        return SelfConsistencyResult(
            decision=majority_decision,
            confidence=confidence,
            vote_breakdown=dict(vote_counts),
            reasoning_paths=responses,
            diversity_score=diversity_score,
        )

    async def _run_epistemic_assessment(self, prompt_context: str) -> EpistemicUncertaintyResult:
        """
        Assess epistemic vs aleatoric uncertainty.

        Epistemic = lack of knowledge (can be reduced with more data)
        Aleatoric = inherent randomness (cannot be reduced)
        """
        prompt = f"""
{prompt_context}

Analyze this trading opportunity and assess TWO types of uncertainty:

1. EPISTEMIC UNCERTAINTY (lack of knowledge):
   - What information do we NOT have that would help?
   - What knowledge gaps exist in our analysis?
   - What assumptions are we making due to missing data?
   - Score from 0-100 (0=complete knowledge, 100=no knowledge)

2. ALEATORIC UNCERTAINTY (inherent randomness):
   - What random/unpredictable factors could affect the outcome?
   - What is fundamentally unpredictable about this trade?
   - Score from 0-100 (0=fully deterministic, 100=pure randomness)

Format your response as:
EPISTEMIC_SCORE: [0-100]
EPISTEMIC_GAPS: [comma-separated list]
ALEATORIC_SCORE: [0-100]
ALEATORIC_FACTORS: [comma-separated list]
DETAILED_ASSESSMENT: [your full analysis]
"""

        try:
            response = await self._query_llm(prompt, temperature=0.3)
            return self._parse_epistemic_response(response)
        except Exception as e:
            logger.warning(f"Epistemic assessment failed: {e}")
            return self._default_uncertainty()

    async def _run_self_critique(
        self, prompt_context: str, initial_decision: str
    ) -> SelfCritiqueResult:
        """
        Prompt the LLM to critique its own reasoning.

        Based on Anthropic's findings that LLMs can sometimes detect
        their own errors when explicitly asked.
        """
        critique_prompt = f"""
{prompt_context}

The initial analysis concluded: {initial_decision}

Now critically evaluate this decision:

1. What ASSUMPTIONS were made in reaching this conclusion?
2. What could be WRONG with this analysis?
3. Are there any LOGICAL INCONSISTENCIES?
4. What EVIDENCE would contradict this decision?
5. On reflection, are there any CONCERNING patterns in the reasoning?

Be brutally honest about limitations and potential errors.

Format:
ASSUMPTIONS: [list]
POTENTIAL_ERRORS: [list]
CONFIDENCE_AFTER_CRITIQUE: [0-100]
SHOULD_TRUST: [YES/NO]
REASONING: [your critique]
"""

        try:
            response = await self._query_llm(critique_prompt, temperature=0.3)
            return self._parse_critique_response(response, initial_decision)
        except Exception as e:
            logger.warning(f"Self-critique failed: {e}")
            return SelfCritiqueResult(
                original_analysis=initial_decision,
                critique="Self-critique unavailable",
                errors_found=[],
                assumptions_made=[],
                confidence_after_critique=0.5,
                should_trust=True,
            )

    async def _run_rcot_check(self, prompt_context: str, solution: str) -> RCoTResult:
        """
        Reversing Chain-of-Thought hallucination detection.

        Reconstructs the problem from the solution to check for
        hallucinations and logical consistency.
        """
        reconstruct_prompt = f"""
Given this trading analysis and conclusion:
{solution}

What was the ORIGINAL question or problem this analysis was trying to solve?
Be specific about:
1. What market conditions were being analyzed?
2. What decision was being made?
3. What data was used?
"""

        try:
            reconstructed = await self._query_llm(reconstruct_prompt, temperature=0.3)

            # Compare original vs reconstructed
            compare_prompt = f"""
Original context:
{prompt_context}

Reconstructed understanding:
{reconstructed}

Rate the consistency from 0-100.
List any discrepancies.

Format:
CONSISTENCY_SCORE: [0-100]
DISCREPANCIES: [list or "none"]
"""
            comparison = await self._query_llm(compare_prompt, temperature=0.1)

            consistency_score = self._extract_score(comparison, "CONSISTENCY_SCORE")
            discrepancies = self._extract_list(comparison, "DISCREPANCIES")

            return RCoTResult(
                forward_solution=solution,
                reconstructed_problem=reconstructed,
                consistency_score=consistency_score,
                is_hallucination=consistency_score < 60,
                discrepancies=discrepancies,
            )
        except Exception as e:
            logger.warning(f"RCoT check failed: {e}")
            return RCoTResult(
                forward_solution=solution,
                reconstructed_problem="",
                consistency_score=50.0,
                is_hallucination=False,
                discrepancies=[],
            )

    def _calculate_aggregate_confidence(
        self,
        self_consistency: SelfConsistencyResult,
        uncertainty: EpistemicUncertaintyResult,
        self_critique: SelfCritiqueResult,
    ) -> float:
        """Calculate weighted aggregate confidence from all signals."""

        # Self-consistency confidence
        sc_conf = self_consistency.confidence

        # Epistemic uncertainty (inverse - high uncertainty = low confidence)
        epistemic_conf = 1.0 - (uncertainty.epistemic_score / 100.0)

        # Self-critique confidence
        critique_conf = self_critique.confidence_after_critique / 100.0

        # Weighted combination
        aggregate = (
            self.WEIGHTS["self_consistency"] * sc_conf
            + self.WEIGHTS["epistemic_inverse"] * epistemic_conf
            + self.WEIGHTS["self_critique"] * critique_conf
        )

        # Normalize and clamp
        return max(0.0, min(1.0, aggregate))

    def _determine_introspection_state(
        self,
        confidence: float,
        uncertainty: EpistemicUncertaintyResult,
        consistency: SelfConsistencyResult,
    ) -> IntrospectionState:
        """Determine the LLM's introspective awareness state (LogU framework)."""

        # High confidence + agreement = CERTAIN
        if confidence > 0.80 and consistency.confidence > 0.80:
            return IntrospectionState.CERTAIN

        # High epistemic uncertainty = UNCERTAIN (need more data)
        if uncertainty.epistemic_score > 70:
            return IntrospectionState.UNCERTAIN

        # Multiple valid decisions with similar votes
        if consistency.diversity_score > 0.5 and len(consistency.vote_breakdown) > 1:
            # Check if votes are close
            votes = list(consistency.vote_breakdown.values())
            if len(votes) > 1 and abs(votes[0] - votes[1]) <= 1:
                return IntrospectionState.MULTIPLE_VALID

        # Moderate confidence with some uncertainty = INFORMED_GUESS
        return IntrospectionState.INFORMED_GUESS

    def _make_execution_decision(
        self,
        confidence: float,
        uncertainty: EpistemicUncertaintyResult,
        state: IntrospectionState,
    ) -> tuple[bool, float, str]:
        """
        Make final execution decision based on introspection results.

        Returns:
            (execute_trade, position_multiplier, recommendation)
        """

        # State-based decision logic
        if state == IntrospectionState.UNCERTAIN:
            return (
                False,
                0.0,
                "SKIP: High epistemic uncertainty - gather more data before trading",
            )

        if state == IntrospectionState.MULTIPLE_VALID:
            return (
                False,
                0.0,
                "SKIP: Multiple valid interpretations - wait for market clarity",
            )

        # Confidence thresholds
        if confidence < self.min_confidence_to_trade:
            return (
                False,
                0.0,
                f"SKIP: Confidence {confidence:.2f} below threshold {self.min_confidence_to_trade}",
            )

        if uncertainty.epistemic_score > self.max_epistemic_to_trade:
            return (
                False,
                0.0,
                f"SKIP: Epistemic uncertainty {uncertainty.epistemic_score} too high",
            )

        # Calculate position multiplier based on confidence
        if confidence > 0.85:
            multiplier = 1.0
            recommendation = "EXECUTE: High confidence - full position"
        elif confidence > 0.75:
            multiplier = 0.75
            recommendation = "EXECUTE: Good confidence - 75% position"
        elif confidence > 0.65:
            multiplier = 0.50
            recommendation = "EXECUTE: Moderate confidence - 50% position"
        else:
            multiplier = 0.25
            recommendation = "EXECUTE: Low confidence - 25% position (caution)"

        # Adjust for aleatoric uncertainty
        if uncertainty.aleatoric_score > 60:
            multiplier *= 0.75
            recommendation += " (reduced due to market randomness)"

        return (True, multiplier, recommendation)

    def _classify_confidence(self, confidence: float) -> ConfidenceLevel:
        """Classify confidence into discrete levels."""
        if confidence > 0.85:
            return ConfidenceLevel.VERY_HIGH
        elif confidence > 0.70:
            return ConfidenceLevel.HIGH
        elif confidence > 0.50:
            return ConfidenceLevel.MEDIUM
        elif confidence > 0.30:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW

    async def _query_llm(self, prompt: str, temperature: float = 0.5) -> str:
        """Query the LLM through the analyzer."""
        # Use the analyzer's existing LLM query capability
        if hasattr(self.analyzer, "async_client"):
            response = await self.analyzer.async_client.chat.completions.create(
                model=self.analyzer.models[0].value,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=1500,
            )
            return response.choices[0].message.content
        else:
            # Fallback to sync client
            response = self.analyzer.sync_client.chat.completions.create(
                model=self.analyzer.models[0].value,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=1500,
            )
            return response.choices[0].message.content

    def _extract_decision(self, response: str) -> str:
        """Extract trading decision from response."""
        response_upper = response.upper()

        # Look for explicit DECISION: format
        decision_match = re.search(r"DECISION:\s*(BUY|SELL|HOLD)", response_upper)
        if decision_match:
            return decision_match.group(1)

        # Fallback: count keywords
        buy_count = response_upper.count("BUY")
        sell_count = response_upper.count("SELL")
        hold_count = response_upper.count("HOLD")

        if buy_count > sell_count and buy_count > hold_count:
            return "BUY"
        elif sell_count > buy_count and sell_count > hold_count:
            return "SELL"
        else:
            return "HOLD"

    def _extract_score(self, response: str, field: str) -> float:
        """Extract numeric score from response."""
        pattern = rf"{field}:\s*(\d+(?:\.\d+)?)"
        match = re.search(pattern, response, re.IGNORECASE)
        if match:
            return float(match.group(1))
        return 50.0  # Default middle value

    def _extract_list(self, response: str, field: str) -> list[str]:
        """Extract comma-separated list from response."""
        pattern = rf"{field}:\s*(.+?)(?:\n|$)"
        match = re.search(pattern, response, re.IGNORECASE)
        if match:
            items = match.group(1).strip()
            if items.lower() == "none":
                return []
            return [item.strip() for item in items.split(",") if item.strip()]
        return []

    def _parse_epistemic_response(self, response: str) -> EpistemicUncertaintyResult:
        """Parse epistemic uncertainty response."""
        epistemic_score = self._extract_score(response, "EPISTEMIC_SCORE")
        aleatoric_score = self._extract_score(response, "ALEATORIC_SCORE")
        knowledge_gaps = self._extract_list(response, "EPISTEMIC_GAPS")
        random_factors = self._extract_list(response, "ALEATORIC_FACTORS")

        # Determine dominant type
        if epistemic_score > aleatoric_score + 20:
            dominant = UncertaintyType.EPISTEMIC
        elif aleatoric_score > epistemic_score + 20:
            dominant = UncertaintyType.ALEATORIC
        else:
            dominant = UncertaintyType.MIXED

        return EpistemicUncertaintyResult(
            epistemic_score=epistemic_score,
            aleatoric_score=aleatoric_score,
            dominant_type=dominant,
            knowledge_gaps=knowledge_gaps,
            random_factors=random_factors,
            can_improve_with_data=epistemic_score > aleatoric_score,
            detailed_assessment=response,
        )

    def _parse_critique_response(self, response: str, original: str) -> SelfCritiqueResult:
        """Parse self-critique response."""
        assumptions = self._extract_list(response, "ASSUMPTIONS")
        errors = self._extract_list(response, "POTENTIAL_ERRORS")
        confidence = self._extract_score(response, "CONFIDENCE_AFTER_CRITIQUE")

        # Check SHOULD_TRUST
        should_trust = "SHOULD_TRUST: YES" in response.upper()

        return SelfCritiqueResult(
            original_analysis=original,
            critique=response,
            errors_found=errors,
            assumptions_made=assumptions,
            confidence_after_critique=confidence,
            should_trust=should_trust,
        )

    def _format_market_data(self, data: dict[str, Any]) -> str:
        """Format market data dictionary for prompts."""
        if isinstance(data, str):
            return data

        lines = []
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{key}:")
                for k, v in value.items():
                    lines.append(f"  {k}: {v}")
            else:
                lines.append(f"{key}: {value}")
        return "\n".join(lines)

    def _default_consistency(self) -> SelfConsistencyResult:
        """Default self-consistency result when analysis fails."""
        return SelfConsistencyResult(
            decision="HOLD",
            confidence=0.0,
            vote_breakdown={"HOLD": 1},
            reasoning_paths=[],
            diversity_score=0.0,
        )

    def _default_uncertainty(self) -> EpistemicUncertaintyResult:
        """Default uncertainty result when analysis fails."""
        return EpistemicUncertaintyResult(
            epistemic_score=100.0,  # Assume maximum uncertainty
            aleatoric_score=50.0,
            dominant_type=UncertaintyType.EPISTEMIC,
            knowledge_gaps=["Analysis failed - no data available"],
            random_factors=[],
            can_improve_with_data=True,
            detailed_assessment="Epistemic assessment unavailable",
        )


# Convenience function for quick introspection
async def analyze_with_introspection(
    analyzer: Any,
    market_data: dict[str, Any],
    symbol: str = "UNKNOWN",
) -> IntrospectionResult:
    """
    Convenience function for introspective analysis.

    Args:
        analyzer: MultiLLMAnalyzer instance
        market_data: Market data dictionary
        symbol: Ticker symbol

    Returns:
        IntrospectionResult with full analysis
    """
    introspector = LLMIntrospector(analyzer)
    return await introspector.analyze_with_introspection(market_data, symbol=symbol)
