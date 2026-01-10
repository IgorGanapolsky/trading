"""
Introspective Council Integration

Combines LLM Council consensus with introspective awareness capabilities
to create a more robust trading decision system.

Architecture:
    Market Data → Multi-LLM Ensemble → LLM Council Validation
                                     → Introspective Awareness Layer
                                     → Confidence-Adjusted Position Sizing

Reference: Anthropic's Emergent Introspective Awareness in LLMs (2025)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from src.core.llm_introspection import (
    ConfidenceLevel,
    EpistemicUncertaintyResult,
    IntrospectionResult,
    IntrospectionState,
    LLMIntrospector,
    SelfConsistencyResult,
)

logger = logging.getLogger(__name__)


class TradeDecision(Enum):
    """Final trade decision types."""

    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"
    SKIP = "skip"  # Insufficient confidence


@dataclass
class IntrospectiveTradeRecommendation:
    """Complete trade recommendation with introspective analysis."""

    # Decision
    symbol: str
    decision: TradeDecision
    action: str  # BUY, SELL, HOLD, SKIP

    # Confidence metrics
    ensemble_confidence: float  # From Multi-LLM consensus
    introspective_confidence: float  # From introspection layer
    combined_confidence: float  # Weighted combination

    # Uncertainty breakdown
    epistemic_uncertainty: float  # Knowledge gaps (0-100)
    aleatoric_uncertainty: float  # Market randomness (0-100)
    introspection_state: IntrospectionState

    # Position sizing
    position_multiplier: float  # 0.0 to 1.0
    max_position_pct: float  # Suggested max portfolio %

    # Reasoning
    recommendation: str
    reasoning_summary: str
    knowledge_gaps: list[str]
    risk_factors: list[str]

    # Execution guidance
    execute: bool
    stop_loss_adjustment: float  # Tighter stops for uncertain trades
    take_profit_adjustment: float

    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)
    processing_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/storage."""
        return {
            "symbol": self.symbol,
            "decision": self.decision.value,
            "action": self.action,
            "ensemble_confidence": self.ensemble_confidence,
            "introspective_confidence": self.introspective_confidence,
            "combined_confidence": self.combined_confidence,
            "epistemic_uncertainty": self.epistemic_uncertainty,
            "aleatoric_uncertainty": self.aleatoric_uncertainty,
            "introspection_state": self.introspection_state.value,
            "position_multiplier": self.position_multiplier,
            "max_position_pct": self.max_position_pct,
            "recommendation": self.recommendation,
            "execute": self.execute,
            "timestamp": self.timestamp.isoformat(),
            "processing_time_ms": self.processing_time_ms,
        }


class IntrospectiveCouncil:
    """
    Enhanced LLM Council with introspective awareness.

    Combines:
    1. Multi-LLM ensemble sentiment analysis
    2. LLM Council peer-review consensus
    3. Introspective self-assessment layer

    The introspection layer adds:
    - Self-consistency checking
    - Epistemic vs aleatoric uncertainty distinction
    - Self-critique and error detection
    - Confidence calibration
    """

    # Weights for combining confidence signals
    ENSEMBLE_WEIGHT = 0.35
    COUNCIL_WEIGHT = 0.35
    INTROSPECTION_WEIGHT = 0.30

    # Position sizing based on confidence
    POSITION_SIZING = {
        ConfidenceLevel.VERY_HIGH: 1.0,
        ConfidenceLevel.HIGH: 0.75,
        ConfidenceLevel.MEDIUM: 0.50,
        ConfidenceLevel.LOW: 0.25,
        ConfidenceLevel.VERY_LOW: 0.0,
    }

    def __init__(
        self,
        multi_llm_analyzer: Any,
        llm_council: Any | None = None,
        enable_introspection: bool = True,
        strict_mode: bool = True,
        consistency_samples: int = 5,
    ):
        """
        Initialize the Introspective Council.

        Args:
            multi_llm_analyzer: MultiLLMAnalyzer instance
            llm_council: Optional TradingCouncil instance
            enable_introspection: Enable introspective layer
            strict_mode: Require higher confidence for trades
            consistency_samples: Samples for self-consistency
        """
        self.analyzer = multi_llm_analyzer
        self.council = llm_council
        self.enable_introspection = enable_introspection
        self.strict_mode = strict_mode

        # Initialize introspector
        if enable_introspection:
            self.introspector = LLMIntrospector(
                analyzer=multi_llm_analyzer,
                consistency_samples=consistency_samples,
                strict_mode=strict_mode,
            )
        else:
            self.introspector = None

        # Tracking metrics
        self.recommendations_made = 0
        self.trades_skipped_low_confidence = 0
        self.average_confidence = 0.0

    async def analyze_trade(
        self,
        symbol: str,
        market_data: dict[str, Any],
        news: str | None = None,
    ) -> IntrospectiveTradeRecommendation:
        """
        Perform comprehensive trade analysis with introspection.

        Args:
            symbol: Ticker symbol
            market_data: Market data dictionary
            news: Optional news context

        Returns:
            IntrospectiveTradeRecommendation with full analysis
        """
        import time

        start_time = time.time()

        # Step 1: Get ensemble sentiment from Multi-LLM
        ensemble_result = await self._get_ensemble_sentiment(symbol, market_data, news)

        # Step 2: Run introspective analysis (if enabled)
        if self.enable_introspection and self.introspector:
            introspection = await self.introspector.analyze_with_introspection(
                market_data=market_data,
                symbol=symbol,
                context=news,
            )
        else:
            introspection = self._default_introspection()

        # Step 3: Get council validation (if available)
        council_result = await self._get_council_validation(symbol, ensemble_result, introspection)

        # Step 4: Combine all signals
        recommendation = self._synthesize_recommendation(
            symbol=symbol,
            ensemble=ensemble_result,
            introspection=introspection,
            council=council_result,
        )

        processing_time = (time.time() - start_time) * 1000
        recommendation.processing_time_ms = processing_time

        # Update tracking
        self._update_metrics(recommendation)

        return recommendation

    async def _get_ensemble_sentiment(
        self,
        symbol: str,
        market_data: dict[str, Any],
        news: str | None,
    ) -> dict[str, Any]:
        """Get ensemble sentiment from Multi-LLM analyzer."""
        try:
            # Format data for analyzer
            data_str = self._format_data(market_data)
            news_str = news or "No recent news available"

            # Call ensemble sentiment
            if hasattr(self.analyzer, "get_ensemble_sentiment_detailed"):
                result = await self.analyzer.get_ensemble_sentiment_detailed(
                    market_data=data_str, news=news_str
                )
                return {
                    "sentiment": result.score if hasattr(result, "score") else 0.0,
                    "confidence": (result.confidence if hasattr(result, "confidence") else 0.5),
                    "reasoning": (result.reasoning if hasattr(result, "reasoning") else ""),
                    "individual_scores": (
                        result.individual_scores if hasattr(result, "individual_scores") else {}
                    ),
                }
            else:
                # Fallback to simple sentiment
                sentiment = await self.analyzer.get_ensemble_sentiment(
                    market_data=data_str, news=news_str
                )
                return {
                    "sentiment": sentiment,
                    "confidence": 0.5,  # Default confidence
                    "reasoning": "Simple ensemble analysis",
                    "individual_scores": {},
                }
        except Exception as e:
            logger.warning(f"Ensemble sentiment failed for {symbol}: {e}")
            return {
                "sentiment": 0.0,
                "confidence": 0.0,
                "reasoning": f"Analysis failed: {e}",
                "individual_scores": {},
            }

    def _anonymize_responses(self, individual_scores: dict[str, Any]) -> dict[str, Any]:
        """
        Anonymize model responses for peer review to prevent self-preference bias.

        Based on Karpathy's LLM Council insight: models favor their own output.
        By labeling as "Response A", "Response B", etc., we force evaluation
        based on semantic content, not model reputation.

        Reference: https://github.com/karpathy/llm-council
        """
        if not individual_scores:
            return {}

        anonymized = {}
        labels = ["A", "B", "C", "D", "E", "F", "G", "H"]
        for i, (model_name, score) in enumerate(individual_scores.items()):
            label = labels[i] if i < len(labels) else str(i + 1)
            anonymized[f"Response_{label}"] = score
            # Store mapping for internal logging only (not sent to peer review)
            logger.debug(f"Anonymized {model_name} -> Response_{label}")

        return anonymized

    async def _get_council_validation(
        self,
        symbol: str,
        ensemble: dict[str, Any],
        introspection: IntrospectionResult,
    ) -> dict[str, Any]:
        """Get validation from LLM Council if available."""
        if not self.council:
            return {
                "validated": True,
                "confidence": 0.5,
                "reasoning": "No council validation (disabled)",
            }

        try:
            # Anonymize individual model scores for peer review (prevents bias)
            anonymized_scores = self._anonymize_responses(
                ensemble.get("individual_scores", {})
            )

            # Create trade request for council
            proposed_action = self._sentiment_to_action(ensemble["sentiment"])

            # Pass anonymized scores to council for unbiased peer review
            validation = await self.council.validate_trade(
                symbol=symbol,
                action=proposed_action,
                sentiment=ensemble["sentiment"],
                confidence=introspection.aggregate_confidence,
                peer_responses=anonymized_scores,  # Anonymized for bias prevention
            )

            return {
                "validated": validation.get("approved", True),
                "confidence": validation.get("confidence", 0.5),
                "reasoning": validation.get("reasoning", ""),
            }
        except Exception as e:
            logger.warning(f"Council validation failed for {symbol}: {e}")
            return {
                "validated": True,  # Default to allow
                "confidence": 0.3,
                "reasoning": f"Validation failed: {e}",
            }

    def _synthesize_recommendation(
        self,
        symbol: str,
        ensemble: dict[str, Any],
        introspection: IntrospectionResult,
        council: dict[str, Any],
    ) -> IntrospectiveTradeRecommendation:
        """Synthesize all signals into final recommendation."""

        # Calculate combined confidence
        ensemble_conf = ensemble.get("confidence", 0.5)
        introspection_conf = introspection.aggregate_confidence
        council_conf = council.get("confidence", 0.5)

        combined_confidence = (
            self.ENSEMBLE_WEIGHT * ensemble_conf
            + self.INTROSPECTION_WEIGHT * introspection_conf
            + self.COUNCIL_WEIGHT * council_conf
        )

        # Determine decision based on sentiment + confidence
        sentiment = ensemble.get("sentiment", 0.0)
        decision, action = self._determine_decision(sentiment, combined_confidence, introspection)

        # Position sizing based on confidence level
        confidence_level = self._classify_confidence(combined_confidence)
        base_multiplier = self.POSITION_SIZING.get(confidence_level, 0.5)

        # Adjust for uncertainty
        uncertainty = introspection.uncertainty
        if uncertainty.epistemic_score > 50:
            base_multiplier *= 0.75  # Reduce for knowledge gaps
        if uncertainty.aleatoric_score > 60:
            base_multiplier *= 0.80  # Reduce for market randomness

        # Council rejection overrides
        if not council.get("validated", True):
            decision = TradeDecision.SKIP
            action = "SKIP"
            base_multiplier = 0.0

        # Calculate stop/take profit adjustments
        stop_loss_adj, take_profit_adj = self._calculate_risk_adjustments(
            combined_confidence, uncertainty
        )

        # Generate recommendation text
        recommendation = self._generate_recommendation_text(
            decision, combined_confidence, introspection.introspection_state
        )

        # Build reasoning summary
        reasoning_summary = self._build_reasoning_summary(ensemble, introspection, council)

        return IntrospectiveTradeRecommendation(
            symbol=symbol,
            decision=decision,
            action=action,
            ensemble_confidence=ensemble_conf,
            introspective_confidence=introspection_conf,
            combined_confidence=combined_confidence,
            epistemic_uncertainty=uncertainty.epistemic_score,
            aleatoric_uncertainty=uncertainty.aleatoric_score,
            introspection_state=introspection.introspection_state,
            position_multiplier=base_multiplier,
            max_position_pct=15.0 * base_multiplier,  # Max 15% per position
            recommendation=recommendation,
            reasoning_summary=reasoning_summary,
            knowledge_gaps=uncertainty.knowledge_gaps,
            risk_factors=uncertainty.random_factors,
            execute=decision not in [TradeDecision.SKIP, TradeDecision.HOLD],
            stop_loss_adjustment=stop_loss_adj,
            take_profit_adjustment=take_profit_adj,
        )

    def _determine_decision(
        self,
        sentiment: float,
        confidence: float,
        introspection: IntrospectionResult,
    ) -> tuple[TradeDecision, str]:
        """Determine trade decision from sentiment and confidence."""

        # Check for skip conditions
        if confidence < 0.40:
            return TradeDecision.SKIP, "SKIP"

        if introspection.introspection_state == IntrospectionState.UNCERTAIN:
            return TradeDecision.SKIP, "SKIP"

        if introspection.introspection_state == IntrospectionState.MULTIPLE_VALID:
            return TradeDecision.HOLD, "HOLD"

        # Strong signals
        if sentiment > 0.6 and confidence > 0.7:
            return TradeDecision.STRONG_BUY, "BUY"
        elif sentiment > 0.3 and confidence > 0.5:
            return TradeDecision.BUY, "BUY"
        elif sentiment < -0.6 and confidence > 0.7:
            return TradeDecision.STRONG_SELL, "SELL"
        elif sentiment < -0.3 and confidence > 0.5:
            return TradeDecision.SELL, "SELL"
        else:
            return TradeDecision.HOLD, "HOLD"

    def _calculate_risk_adjustments(
        self,
        confidence: float,
        uncertainty: EpistemicUncertaintyResult,
    ) -> tuple[float, float]:
        """
        Calculate stop-loss and take-profit adjustments.

        Lower confidence = tighter stops (risk management)
        Higher uncertainty = tighter stops
        """
        # Base adjustments (1.0 = no change)
        stop_adjustment = 1.0
        profit_adjustment = 1.0

        # Tighten stops for low confidence
        if confidence < 0.5:
            stop_adjustment *= 0.7  # 30% tighter
        elif confidence < 0.7:
            stop_adjustment *= 0.85  # 15% tighter

        # Tighten for high epistemic uncertainty
        if uncertainty.epistemic_score > 60:
            stop_adjustment *= 0.8

        # Widen take profit for high conviction
        if confidence > 0.8:
            profit_adjustment *= 1.2  # 20% wider

        return stop_adjustment, profit_adjustment

    def _classify_confidence(self, confidence: float) -> ConfidenceLevel:
        """Classify confidence into levels."""
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

    def _sentiment_to_action(self, sentiment: float) -> str:
        """Convert sentiment to action string."""
        if sentiment > 0.3:
            return "BUY"
        elif sentiment < -0.3:
            return "SELL"
        else:
            return "HOLD"

    def _generate_recommendation_text(
        self,
        decision: TradeDecision,
        confidence: float,
        state: IntrospectionState,
    ) -> str:
        """Generate human-readable recommendation."""
        state_desc = {
            IntrospectionState.CERTAIN: "high certainty",
            IntrospectionState.INFORMED_GUESS: "informed analysis",
            IntrospectionState.UNCERTAIN: "insufficient data",
            IntrospectionState.MULTIPLE_VALID: "conflicting signals",
        }

        decision_desc = {
            TradeDecision.STRONG_BUY: "Strong buy signal",
            TradeDecision.BUY: "Buy signal",
            TradeDecision.HOLD: "Hold position",
            TradeDecision.SELL: "Sell signal",
            TradeDecision.STRONG_SELL: "Strong sell signal",
            TradeDecision.SKIP: "Skip - conditions not favorable",
        }

        return f"{decision_desc[decision]} with {state_desc[state]} (confidence: {confidence:.1%})"

    def _build_reasoning_summary(
        self,
        ensemble: dict[str, Any],
        introspection: IntrospectionResult,
        council: dict[str, Any],
    ) -> str:
        """Build concise reasoning summary."""
        parts = []

        # Ensemble sentiment
        sentiment = ensemble.get("sentiment", 0)
        if sentiment > 0.3:
            parts.append(f"Bullish sentiment ({sentiment:.2f})")
        elif sentiment < -0.3:
            parts.append(f"Bearish sentiment ({sentiment:.2f})")
        else:
            parts.append(f"Neutral sentiment ({sentiment:.2f})")

        # Introspection state
        state = introspection.introspection_state
        if state == IntrospectionState.CERTAIN:
            parts.append("High model agreement")
        elif state == IntrospectionState.UNCERTAIN:
            parts.append("Knowledge gaps detected")
        elif state == IntrospectionState.MULTIPLE_VALID:
            parts.append("Mixed signals")

        # Uncertainty
        if introspection.uncertainty.epistemic_score > 50:
            parts.append(f"Epistemic uncertainty: {introspection.uncertainty.epistemic_score:.0f}%")

        # Council
        if not council.get("validated", True):
            parts.append("Council rejected trade")

        return ". ".join(parts)

    def _format_data(self, data: dict[str, Any]) -> str:
        """Format data dictionary to string."""
        if isinstance(data, str):
            return data

        lines = []
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{key}: {value}")
            else:
                lines.append(f"{key}: {value}")
        return "\n".join(lines)

    def _default_introspection(self) -> IntrospectionResult:
        """Default introspection result when disabled."""
        from src.core.llm_introspection import (
            SelfCritiqueResult,
            UncertaintyType,
        )

        return IntrospectionResult(
            decision="HOLD",
            introspection_state=IntrospectionState.INFORMED_GUESS,
            self_consistency=SelfConsistencyResult(
                decision="HOLD",
                confidence=0.5,
                vote_breakdown={"HOLD": 1},
                reasoning_paths=[],
                diversity_score=0.0,
            ),
            uncertainty=EpistemicUncertaintyResult(
                epistemic_score=50.0,
                aleatoric_score=50.0,
                dominant_type=UncertaintyType.MIXED,
                knowledge_gaps=[],
                random_factors=[],
                can_improve_with_data=True,
                detailed_assessment="Introspection disabled",
            ),
            self_critique=SelfCritiqueResult(
                original_analysis="N/A",
                critique="Introspection disabled",
                errors_found=[],
                assumptions_made=[],
                confidence_after_critique=50.0,
                should_trust=True,
            ),
            aggregate_confidence=0.5,
            confidence_level=ConfidenceLevel.MEDIUM,
            epistemic_uncertainty=50.0,
            aleatoric_uncertainty=50.0,
            execute_trade=True,
            position_multiplier=1.0,
            recommendation="Introspection disabled - using defaults",
            signals_used=[],
            processing_time_ms=0.0,
        )

    def _update_metrics(self, recommendation: IntrospectiveTradeRecommendation) -> None:
        """Update tracking metrics."""
        self.recommendations_made += 1

        if recommendation.decision == TradeDecision.SKIP:
            self.trades_skipped_low_confidence += 1

        # Update rolling average confidence
        prev_avg = self.average_confidence
        new_val = recommendation.combined_confidence
        self.average_confidence = prev_avg + (new_val - prev_avg) / self.recommendations_made

    def get_metrics(self) -> dict[str, Any]:
        """Get current metrics."""
        return {
            "recommendations_made": self.recommendations_made,
            "trades_skipped": self.trades_skipped_low_confidence,
            "skip_rate": (self.trades_skipped_low_confidence / max(1, self.recommendations_made)),
            "average_confidence": self.average_confidence,
            "introspection_enabled": self.enable_introspection,
            "strict_mode": self.strict_mode,
        }


# Factory function
def create_introspective_council(
    api_key: str | None = None,
    enable_introspection: bool = True,
    strict_mode: bool = True,
) -> IntrospectiveCouncil:
    """
    Factory function to create an IntrospectiveCouncil.

    Args:
        api_key: OpenRouter API key
        enable_introspection: Enable introspective analysis
        strict_mode: Require higher confidence

    Returns:
        Configured IntrospectiveCouncil instance
    """
    try:
        from src.core.multi_llm_analysis import MultiLLMAnalyzer
    except ImportError as e:
        logger.error(f"Cannot create IntrospectiveCouncil: MultiLLMAnalyzer not available: {e}")
        raise ImportError(
            "MultiLLMAnalyzer is required for IntrospectiveCouncil. "
            "Please ensure src.core.multi_llm_analysis module exists."
        ) from e

    analyzer = MultiLLMAnalyzer(api_key=api_key)

    return IntrospectiveCouncil(
        multi_llm_analyzer=analyzer,
        enable_introspection=enable_introspection,
        strict_mode=strict_mode,
    )
