"""
Hallucination Prevention Pipeline

Comprehensive multi-stage verification to prevent LLM hallucinations
in trading decisions. Integrates with:
- RAG (lessons learned, vector search)
- ML pipeline (anomaly detection, pattern learning)
- Factuality monitor (FACTS benchmark)

Stages:
1. Pre-trade: Query RAG for similar past mistakes
2. Real-time: Validate LLM outputs against patterns
3. Post-trade: Compare predictions to actual outcomes

Created: Dec 11, 2025
Based on: Google DeepMind FACTS Benchmark (70% ceiling)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)

PREDICTION_LOG_PATH = Path("data/predictions_log.json")
HALLUCINATION_PATTERNS_PATH = Path("data/hallucination_patterns.json")


@dataclass
class Prediction:
    """A recorded prediction for later verification."""
    prediction_id: str
    timestamp: str
    model: str
    symbol: str
    predicted_action: str  # BUY/SELL/HOLD
    predicted_direction: str  # UP/DOWN/FLAT
    confidence: float
    reasoning: str
    context: dict[str, Any]
    # Outcome (filled in post-trade)
    actual_direction: Optional[str] = None
    actual_pnl: Optional[float] = None
    was_correct: Optional[bool] = None
    verified_at: Optional[str] = None


@dataclass
class HallucinationPattern:
    """A learned pattern of hallucination behavior."""
    pattern_id: str
    description: str
    trigger_conditions: dict[str, Any]
    frequency: int
    models_affected: list[str]
    severity: str
    mitigation: str
    examples: list[str] = field(default_factory=list)


class HallucinationPreventionPipeline:
    """
    Multi-stage pipeline to prevent LLM hallucinations in trading.

    Stage 1: Pre-Trade Verification
    - Query RAG for similar past mistakes
    - Check factuality scores
    - Validate against known hallucination patterns

    Stage 2: Real-Time Monitoring
    - Cross-check claims against API
    - Validate against technical indicators
    - Flag confidence > factuality ceiling

    Stage 3: Post-Trade Verification
    - Compare predicted vs actual outcomes
    - Update model accuracy metrics
    - Learn new hallucination patterns
    """

    def __init__(
        self,
        rag_system: Optional[Any] = None,
        factuality_monitor: Optional[Any] = None,
        anomaly_detector: Optional[Any] = None,
    ):
        self.rag_system = rag_system
        self.factuality_monitor = factuality_monitor
        self.anomaly_detector = anomaly_detector

        self.predictions: dict[str, Prediction] = {}
        self.patterns: list[HallucinationPattern] = []

        self._load_predictions()
        self._load_patterns()
        self._init_default_patterns()

        logger.info("HallucinationPreventionPipeline initialized")

    # =========================================================================
    # Stage 1: Pre-Trade Verification
    # =========================================================================

    def pre_trade_check(
        self,
        symbol: str,
        action: str,
        model: str,
        confidence: float,
        reasoning: str,
        context: Optional[dict] = None,
    ) -> dict[str, Any]:
        """
        Run pre-trade verification checks.

        Returns:
            Dict with:
            - approved: bool
            - risk_score: float (0-1, higher = more risky)
            - warnings: list of warnings
            - similar_mistakes: list of similar past mistakes from RAG
            - pattern_matches: list of matching hallucination patterns
        """
        warnings = []
        risk_score = 0.0

        # Check 1: Query RAG for similar past mistakes
        similar_mistakes = []
        if self.rag_system:
            try:
                query = f"{action} {symbol} {reasoning}"
                results = self.rag_system.search(query, top_k=3)
                for lesson, score in results:
                    if score > 0.6:  # Relevance threshold
                        similar_mistakes.append({
                            "id": lesson.id,
                            "title": lesson.title,
                            "description": lesson.description,
                            "prevention": lesson.prevention,
                            "severity": lesson.severity,
                            "relevance": score,
                        })
                        risk_score += 0.2 * score  # Add to risk
                        warnings.append(f"Similar past mistake found: {lesson.title}")
            except Exception as e:
                logger.warning(f"RAG query failed: {e}")

        # Check 2: Factuality ceiling
        if self.factuality_monitor:
            facts_score = self.factuality_monitor.get_facts_score(model)
            if confidence > facts_score:
                risk_score += 0.3
                warnings.append(
                    f"Confidence {confidence:.2f} exceeds FACTS ceiling {facts_score:.2f}"
                )

        # Check 3: Pattern matching
        pattern_matches = []
        for pattern in self.patterns:
            if self._matches_pattern(pattern, symbol, action, model, reasoning):
                pattern_matches.append({
                    "pattern_id": pattern.pattern_id,
                    "description": pattern.description,
                    "severity": pattern.severity,
                    "mitigation": pattern.mitigation,
                })
                risk_score += 0.15 if pattern.severity == "high" else 0.1
                warnings.append(f"Hallucination pattern match: {pattern.description}")

        # Check 4: Historical accuracy for this model + symbol
        model_accuracy = self._get_model_symbol_accuracy(model, symbol)
        if model_accuracy is not None and model_accuracy < 0.5:
            risk_score += 0.25
            warnings.append(
                f"Model {model} has {model_accuracy:.0%} accuracy on {symbol}"
            )

        # Final decision
        risk_score = min(1.0, risk_score)  # Cap at 1.0
        approved = risk_score < 0.6  # Block if risk > 60%

        return {
            "approved": approved,
            "risk_score": risk_score,
            "warnings": warnings,
            "similar_mistakes": similar_mistakes,
            "pattern_matches": pattern_matches,
            "recommendation": "PROCEED" if approved else "BLOCK - High hallucination risk",
        }

    # =========================================================================
    # Stage 2: Real-Time Monitoring
    # =========================================================================

    def record_prediction(
        self,
        model: str,
        symbol: str,
        predicted_action: str,
        predicted_direction: str,
        confidence: float,
        reasoning: str,
        context: Optional[dict] = None,
    ) -> str:
        """
        Record a prediction for later verification.

        Returns:
            Prediction ID
        """
        import uuid

        prediction_id = f"pred_{uuid.uuid4().hex[:12]}"

        prediction = Prediction(
            prediction_id=prediction_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            model=model,
            symbol=symbol,
            predicted_action=predicted_action,
            predicted_direction=predicted_direction,
            confidence=confidence,
            reasoning=reasoning,
            context=context or {},
        )

        self.predictions[prediction_id] = prediction
        self._save_predictions()

        logger.info(f"Recorded prediction {prediction_id}: {model} {predicted_action} {symbol}")
        return prediction_id

    def validate_claim(
        self,
        claim_type: str,
        claimed_value: Any,
        actual_value: Any,
        model: str,
        context: Optional[dict] = None,
    ) -> dict[str, Any]:
        """
        Validate a specific claim in real-time.

        Args:
            claim_type: Type of claim (price, position, sentiment, etc.)
            claimed_value: What the LLM claimed
            actual_value: Ground truth from API
            model: Model that made the claim
            context: Additional context

        Returns:
            Validation result
        """
        is_valid = False
        deviation = None

        # Numeric comparison
        if isinstance(claimed_value, (int, float)) and isinstance(actual_value, (int, float)):
            if actual_value != 0:
                deviation = abs(claimed_value - actual_value) / abs(actual_value)
            else:
                deviation = abs(claimed_value - actual_value)

            # Tolerance based on claim type
            tolerances = {
                "price": 0.01,        # 1% for prices
                "position": 0.001,    # 0.1% for positions
                "pnl": 0.05,          # 5% for P/L
                "sentiment": 0.2,     # 20% for sentiment scores
            }
            tolerance = tolerances.get(claim_type, 0.05)
            is_valid = deviation <= tolerance

        # String comparison
        elif isinstance(claimed_value, str) and isinstance(actual_value, str):
            is_valid = claimed_value.lower() == actual_value.lower()

        # Log to factuality monitor
        if self.factuality_monitor:
            self.factuality_monitor.record_verification(
                model=model,
                claim_verified=is_valid,
                context={
                    "claim_type": claim_type,
                    "claimed": claimed_value,
                    "actual": actual_value,
                    **(context or {}),
                },
            )

        # Learn pattern if hallucination
        if not is_valid:
            self._learn_from_hallucination(
                model=model,
                claim_type=claim_type,
                claimed=claimed_value,
                actual=actual_value,
                context=context,
            )

        return {
            "valid": is_valid,
            "claim_type": claim_type,
            "claimed": claimed_value,
            "actual": actual_value,
            "deviation": deviation,
            "model": model,
        }

    # =========================================================================
    # Stage 3: Post-Trade Verification
    # =========================================================================

    def verify_prediction(
        self,
        prediction_id: str,
        actual_direction: str,
        actual_pnl: float,
    ) -> dict[str, Any]:
        """
        Verify a prediction against actual outcome.

        Args:
            prediction_id: ID of the prediction to verify
            actual_direction: Actual price direction (UP/DOWN/FLAT)
            actual_pnl: Actual P/L from the trade

        Returns:
            Verification result with accuracy update
        """
        if prediction_id not in self.predictions:
            return {"error": f"Prediction {prediction_id} not found"}

        prediction = self.predictions[prediction_id]

        # Determine if prediction was correct
        was_correct = prediction.predicted_direction.upper() == actual_direction.upper()

        # Update prediction record
        prediction.actual_direction = actual_direction
        prediction.actual_pnl = actual_pnl
        prediction.was_correct = was_correct
        prediction.verified_at = datetime.now(timezone.utc).isoformat()

        self._save_predictions()

        # Update factuality metrics
        if self.factuality_monitor:
            self.factuality_monitor.record_verification(
                model=prediction.model,
                claim_verified=was_correct,
                context={
                    "symbol": prediction.symbol,
                    "predicted": prediction.predicted_direction,
                    "actual": actual_direction,
                    "pnl": actual_pnl,
                },
            )

        # Learn from mistake if wrong
        if not was_correct:
            self._learn_from_wrong_prediction(prediction, actual_direction, actual_pnl)

        # Calculate model's running accuracy
        model_accuracy = self._calculate_model_accuracy(prediction.model)

        logger.info(
            f"Verified prediction {prediction_id}: "
            f"{'CORRECT' if was_correct else 'WRONG'} "
            f"(model accuracy: {model_accuracy:.1%})"
        )

        return {
            "prediction_id": prediction_id,
            "was_correct": was_correct,
            "predicted_direction": prediction.predicted_direction,
            "actual_direction": actual_direction,
            "pnl": actual_pnl,
            "model": prediction.model,
            "model_accuracy": model_accuracy,
        }

    def get_model_accuracy_report(self) -> dict[str, Any]:
        """Get accuracy report for all models."""
        model_stats: dict[str, dict] = {}

        for pred in self.predictions.values():
            if pred.was_correct is None:
                continue  # Skip unverified

            if pred.model not in model_stats:
                model_stats[pred.model] = {
                    "total": 0,
                    "correct": 0,
                    "total_pnl": 0.0,
                    "symbols": {},
                }

            stats = model_stats[pred.model]
            stats["total"] += 1
            if pred.was_correct:
                stats["correct"] += 1
            if pred.actual_pnl:
                stats["total_pnl"] += pred.actual_pnl

            # Per-symbol stats
            if pred.symbol not in stats["symbols"]:
                stats["symbols"][pred.symbol] = {"total": 0, "correct": 0}
            stats["symbols"][pred.symbol]["total"] += 1
            if pred.was_correct:
                stats["symbols"][pred.symbol]["correct"] += 1

        # Calculate accuracies
        report = {}
        for model, stats in model_stats.items():
            report[model] = {
                "total_predictions": stats["total"],
                "correct_predictions": stats["correct"],
                "accuracy": stats["correct"] / stats["total"] if stats["total"] > 0 else 0,
                "total_pnl": stats["total_pnl"],
                "symbol_accuracy": {
                    sym: s["correct"] / s["total"] if s["total"] > 0 else 0
                    for sym, s in stats["symbols"].items()
                },
            }

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "models": report,
            "factuality_note": "Per FACTS Benchmark, expect ~30% error rate",
        }

    # =========================================================================
    # Pattern Learning
    # =========================================================================

    def _learn_from_hallucination(
        self,
        model: str,
        claim_type: str,
        claimed: Any,
        actual: Any,
        context: Optional[dict] = None,
    ) -> None:
        """Learn from a detected hallucination to improve future detection."""
        # Find or create pattern
        pattern_key = f"{model}_{claim_type}"

        existing = next(
            (p for p in self.patterns if p.pattern_id == pattern_key),
            None
        )

        if existing:
            existing.frequency += 1
            existing.examples.append(f"Claimed {claimed}, actual {actual}")
            existing.examples = existing.examples[-10:]  # Keep last 10
        else:
            self.patterns.append(HallucinationPattern(
                pattern_id=pattern_key,
                description=f"{model} frequently hallucinates {claim_type} values",
                trigger_conditions={
                    "model": model,
                    "claim_type": claim_type,
                },
                frequency=1,
                models_affected=[model],
                severity="medium",
                mitigation=f"Always verify {claim_type} claims from {model} against API",
                examples=[f"Claimed {claimed}, actual {actual}"],
            ))

        self._save_patterns()

        # Store in RAG if available
        if self.rag_system and existing and existing.frequency >= 3:
            try:
                self.rag_system.add_lesson(
                    category="hallucination",
                    title=f"Frequent {claim_type} hallucination by {model}",
                    description=f"Model {model} has hallucinated {claim_type} {existing.frequency} times",
                    root_cause="LLM factuality limitation (<70% per FACTS benchmark)",
                    prevention=existing.mitigation,
                    tags=["hallucination", claim_type, model],
                    severity="high" if existing.frequency >= 5 else "medium",
                )
            except Exception as e:
                logger.warning(f"Could not add lesson to RAG: {e}")

    def _learn_from_wrong_prediction(
        self,
        prediction: Prediction,
        actual_direction: str,
        actual_pnl: float,
    ) -> None:
        """Learn from a wrong prediction."""
        if self.rag_system:
            try:
                self.rag_system.add_lesson(
                    category="prediction_error",
                    title=f"Wrong {prediction.predicted_action} prediction on {prediction.symbol}",
                    description=(
                        f"Model {prediction.model} predicted {prediction.predicted_direction} "
                        f"with {prediction.confidence:.1%} confidence, "
                        f"but actual was {actual_direction}. P/L: ${actual_pnl:.2f}"
                    ),
                    root_cause=f"Reasoning: {prediction.reasoning[:200]}",
                    prevention="Cross-validate with technical indicators before acting",
                    tags=["prediction", prediction.model, prediction.symbol],
                    severity="high" if actual_pnl < -10 else "medium",
                    financial_impact=actual_pnl if actual_pnl < 0 else None,
                    symbol=prediction.symbol,
                )
            except Exception as e:
                logger.warning(f"Could not add prediction error to RAG: {e}")

    def _matches_pattern(
        self,
        pattern: HallucinationPattern,
        symbol: str,
        action: str,
        model: str,
        reasoning: str,
    ) -> bool:
        """Check if current context matches a hallucination pattern."""
        conditions = pattern.trigger_conditions

        if "model" in conditions and conditions["model"] != model:
            return False

        if "symbol" in conditions and conditions["symbol"] != symbol:
            return False

        if "action" in conditions and conditions["action"] != action:
            return False

        if "keywords" in conditions:
            if not any(kw.lower() in reasoning.lower() for kw in conditions["keywords"]):
                return False

        return True

    def _init_default_patterns(self) -> None:
        """Initialize default hallucination patterns."""
        default_patterns = [
            HallucinationPattern(
                pattern_id="overconfidence",
                description="LLM claims >80% confidence (impossible per FACTS)",
                trigger_conditions={"min_confidence": 0.8},
                frequency=0,
                models_affected=["all"],
                severity="high",
                mitigation="Cap confidence at model's FACTS score (~68%)",
            ),
            HallucinationPattern(
                pattern_id="price_fabrication",
                description="LLM invents specific price levels without data",
                trigger_conditions={"claim_type": "price", "keywords": ["exactly", "precisely"]},
                frequency=0,
                models_affected=["all"],
                severity="critical",
                mitigation="Always fetch real-time price from API",
            ),
            HallucinationPattern(
                pattern_id="false_certainty",
                description="LLM claims certainty about future market moves",
                trigger_conditions={"keywords": ["will definitely", "guaranteed", "certain to"]},
                frequency=0,
                models_affected=["all"],
                severity="high",
                mitigation="No market prediction is certain - cap confidence",
            ),
        ]

        for pattern in default_patterns:
            if not any(p.pattern_id == pattern.pattern_id for p in self.patterns):
                self.patterns.append(pattern)

        self._save_patterns()

    def _get_model_symbol_accuracy(self, model: str, symbol: str) -> Optional[float]:
        """Get historical accuracy for a model on a specific symbol."""
        relevant = [
            p for p in self.predictions.values()
            if p.model == model and p.symbol == symbol and p.was_correct is not None
        ]

        if len(relevant) < 5:
            return None  # Not enough data

        correct = sum(1 for p in relevant if p.was_correct)
        return correct / len(relevant)

    def _calculate_model_accuracy(self, model: str) -> float:
        """Calculate overall accuracy for a model."""
        verified = [
            p for p in self.predictions.values()
            if p.model == model and p.was_correct is not None
        ]

        if not verified:
            return 0.5  # No data, assume 50%

        correct = sum(1 for p in verified if p.was_correct)
        return correct / len(verified)

    # =========================================================================
    # Persistence
    # =========================================================================

    def _load_predictions(self) -> None:
        """Load predictions from disk."""
        if PREDICTION_LOG_PATH.exists():
            try:
                with open(PREDICTION_LOG_PATH) as f:
                    data = json.load(f)
                    for pred_dict in data.get("predictions", []):
                        pred = Prediction(
                            prediction_id=pred_dict["prediction_id"],
                            timestamp=pred_dict["timestamp"],
                            model=pred_dict["model"],
                            symbol=pred_dict["symbol"],
                            predicted_action=pred_dict["predicted_action"],
                            predicted_direction=pred_dict["predicted_direction"],
                            confidence=pred_dict["confidence"],
                            reasoning=pred_dict["reasoning"],
                            context=pred_dict.get("context", {}),
                            actual_direction=pred_dict.get("actual_direction"),
                            actual_pnl=pred_dict.get("actual_pnl"),
                            was_correct=pred_dict.get("was_correct"),
                            verified_at=pred_dict.get("verified_at"),
                        )
                        self.predictions[pred.prediction_id] = pred
            except Exception as e:
                logger.warning(f"Could not load predictions: {e}")

    def _save_predictions(self) -> None:
        """Save predictions to disk."""
        PREDICTION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Keep only last 1000 predictions
        recent = sorted(
            self.predictions.values(),
            key=lambda p: p.timestamp,
            reverse=True
        )[:1000]

        data = {
            "predictions": [
                {
                    "prediction_id": p.prediction_id,
                    "timestamp": p.timestamp,
                    "model": p.model,
                    "symbol": p.symbol,
                    "predicted_action": p.predicted_action,
                    "predicted_direction": p.predicted_direction,
                    "confidence": p.confidence,
                    "reasoning": p.reasoning,
                    "context": p.context,
                    "actual_direction": p.actual_direction,
                    "actual_pnl": p.actual_pnl,
                    "was_correct": p.was_correct,
                    "verified_at": p.verified_at,
                }
                for p in recent
            ],
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        try:
            with open(PREDICTION_LOG_PATH, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save predictions: {e}")

    def _load_patterns(self) -> None:
        """Load hallucination patterns from disk."""
        if HALLUCINATION_PATTERNS_PATH.exists():
            try:
                with open(HALLUCINATION_PATTERNS_PATH) as f:
                    data = json.load(f)
                    for pat_dict in data.get("patterns", []):
                        pattern = HallucinationPattern(
                            pattern_id=pat_dict["pattern_id"],
                            description=pat_dict["description"],
                            trigger_conditions=pat_dict["trigger_conditions"],
                            frequency=pat_dict.get("frequency", 0),
                            models_affected=pat_dict.get("models_affected", []),
                            severity=pat_dict.get("severity", "medium"),
                            mitigation=pat_dict["mitigation"],
                            examples=pat_dict.get("examples", []),
                        )
                        self.patterns.append(pattern)
            except Exception as e:
                logger.warning(f"Could not load patterns: {e}")

    def _save_patterns(self) -> None:
        """Save hallucination patterns to disk."""
        HALLUCINATION_PATTERNS_PATH.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "patterns": [
                {
                    "pattern_id": p.pattern_id,
                    "description": p.description,
                    "trigger_conditions": p.trigger_conditions,
                    "frequency": p.frequency,
                    "models_affected": p.models_affected,
                    "severity": p.severity,
                    "mitigation": p.mitigation,
                    "examples": p.examples,
                }
                for p in self.patterns
            ],
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        try:
            with open(HALLUCINATION_PATTERNS_PATH, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save patterns: {e}")


# Convenience function
def create_hallucination_pipeline() -> HallucinationPreventionPipeline:
    """Create a fully integrated hallucination prevention pipeline."""
    rag_system = None
    factuality_monitor = None
    anomaly_detector = None

    try:
        from src.rag.lessons_learned_rag import LessonsLearnedRAG
        rag_system = LessonsLearnedRAG()
    except Exception as e:
        logger.warning(f"Could not initialize RAG: {e}")

    try:
        from src.verification.factuality_monitor import create_factuality_monitor
        factuality_monitor = create_factuality_monitor()
    except Exception as e:
        logger.warning(f"Could not initialize factuality monitor: {e}")

    try:
        from src.ml.anomaly_detector import TradingAnomalyDetector
        anomaly_detector = TradingAnomalyDetector()
    except Exception as e:
        logger.warning(f"Could not initialize anomaly detector: {e}")

    return HallucinationPreventionPipeline(
        rag_system=rag_system,
        factuality_monitor=factuality_monitor,
        anomaly_detector=anomaly_detector,
    )
