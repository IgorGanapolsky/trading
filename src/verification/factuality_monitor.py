"""
Factuality Monitor for LLM Council

Based on Google DeepMind's FACTS Benchmark (Dec 2025), which revealed that
no top LLM achieves >70% factuality. This module:

1. Weights LLM votes by their FACTS benchmark scores
2. Validates LLM claims against ground truth (Alpaca API, technical indicators)
3. Logs hallucination incidents to RAG for pattern learning
4. Integrates with ML anomaly detector for continuous monitoring

Reference: https://deepmind.google/blog/facts-benchmark-suite
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# FACTS Benchmark scores (Dec 2025 release)
# Source: Google DeepMind FACTS Grounding Leaderboard
# All scores below 70% - the "factuality ceiling"
FACTS_BENCHMARK_SCORES = {
    # Model identifier -> FACTS score (0.0 to 1.0)
    "google/gemini-3-pro-preview": 0.688,  # Leads at 68.8%
    "google/gemini-2.5-flash": 0.652,  # Estimated from family
    "anthropic/claude-sonnet-4": 0.665,  # Estimated ~66.5%
    "anthropic/claude-opus-4": 0.670,  # Estimated ~67%
    "openai/gpt-4o": 0.658,  # Estimated ~65.8%
    "openai/gpt-4-turbo": 0.645,  # Estimated ~64.5%
    "deepseek/deepseek-r1": 0.640,  # Estimated ~64%
    # Default for unknown models
    "default": 0.600,
}

HALLUCINATION_LOG_PATH = Path("data/hallucination_log.json")
FACTUALITY_METRICS_PATH = Path("data/factuality_metrics.json")


class HallucinationType(Enum):
    """Types of hallucinations detected."""

    PRICE_MISMATCH = "price_mismatch"  # LLM price != API price
    POSITION_MISMATCH = "position_mismatch"  # Claimed position doesn't exist
    SIGNAL_CONTRADICTION = "signal_contradiction"  # LLM signal contradicts technicals
    DATA_FABRICATION = "data_fabrication"  # LLM invented non-existent data
    STALE_REFERENCE = "stale_reference"  # LLM used outdated information
    CONFIDENCE_OVERESTIMATE = "confidence_overestimate"  # High confidence, wrong answer


class VerificationSource(Enum):
    """Ground truth sources for verification."""

    ALPACA_API = "alpaca_api"
    TECHNICAL_INDICATORS = "technical_indicators"
    USER_HOOK = "user_hook"
    SYSTEM_STATE = "system_state"


@dataclass
class HallucinationIncident:
    """Records a detected hallucination incident."""

    incident_id: str
    timestamp: str
    model: str
    hallucination_type: HallucinationType
    claimed_value: Any
    actual_value: Any
    verification_source: VerificationSource
    context: dict[str, Any]
    severity: str  # "low", "medium", "high", "critical"

    def to_dict(self) -> dict:
        return {
            "incident_id": self.incident_id,
            "timestamp": self.timestamp,
            "model": self.model,
            "hallucination_type": self.hallucination_type.value,
            "claimed_value": str(self.claimed_value),
            "actual_value": str(self.actual_value),
            "verification_source": self.verification_source.value,
            "context": self.context,
            "severity": self.severity,
        }


@dataclass
class FactualityMetrics:
    """Tracks factuality metrics over time for each model."""

    model: str
    total_claims: int = 0
    verified_claims: int = 0
    hallucinations: int = 0
    facts_score: float = 0.0
    observed_accuracy: float = 0.0
    last_updated: str = ""

    @property
    def accuracy_rate(self) -> float:
        if self.total_claims == 0:
            return self.facts_score  # Fall back to benchmark
        return self.verified_claims / self.total_claims

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "total_claims": self.total_claims,
            "verified_claims": self.verified_claims,
            "hallucinations": self.hallucinations,
            "facts_score": self.facts_score,
            "observed_accuracy": self.accuracy_rate,
            "last_updated": self.last_updated,
        }


@dataclass
class FactualityWeightedVote:
    """A vote weighted by factuality score."""

    model: str
    vote: str  # "BUY", "SELL", "HOLD"
    confidence: float
    facts_weight: float
    weighted_score: float
    reasoning: str


class FactualityMonitor:
    """
    Monitors and improves LLM factuality in trading decisions.

    Key features:
    1. FACTS benchmark-weighted voting
    2. Ground truth validation against Alpaca API
    3. Technical indicator cross-validation
    4. Hallucination incident logging to RAG
    5. Continuous accuracy tracking per model
    """

    def __init__(
        self,
        rag_system: Optional[Any] = None,
        anomaly_detector: Optional[Any] = None,
    ):
        """
        Initialize the factuality monitor.

        Args:
            rag_system: LessonsLearnedRAG instance for storing incidents
            anomaly_detector: TradingAnomalyDetector for ML integration
        """
        self.rag_system = rag_system
        self.anomaly_detector = anomaly_detector
        self.metrics: dict[str, FactualityMetrics] = {}
        self.incidents: list[HallucinationIncident] = []

        # Load historical metrics
        self._load_metrics()

        logger.info("FactualityMonitor initialized with FACTS benchmark integration")

    def get_facts_score(self, model: str) -> float:
        """Get FACTS benchmark score for a model."""
        return FACTS_BENCHMARK_SCORES.get(model, FACTS_BENCHMARK_SCORES["default"])

    def get_factuality_weight(self, model: str) -> float:
        """
        Calculate factuality weight combining FACTS score and observed accuracy.

        Uses Bayesian-style combination:
        - Prior: FACTS benchmark score
        - Posterior: Observed accuracy from our system
        - Weight shifts toward observed as sample size increases
        """
        facts_score = self.get_facts_score(model)

        if model not in self.metrics:
            return facts_score

        metrics = self.metrics[model]
        if metrics.total_claims < 10:
            # Not enough data, use FACTS score
            return facts_score

        # Blend FACTS score with observed accuracy
        # Weight observed more heavily as we get more samples
        sample_weight = min(0.7, metrics.total_claims / 100)
        return (1 - sample_weight) * facts_score + sample_weight * metrics.accuracy_rate

    def weight_council_votes(
        self,
        votes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Apply factuality weights to LLM council votes.

        Args:
            votes: List of vote dicts with keys: model, vote, confidence, reasoning

        Returns:
            Weighted consensus result with factuality adjustments
        """
        weighted_votes: list[FactualityWeightedVote] = []

        for vote in votes:
            model = vote.get("model", "unknown")
            raw_confidence = vote.get("confidence", 0.5)
            facts_weight = self.get_factuality_weight(model)

            # Adjust confidence by factuality weight
            # High factuality models get their confidence preserved
            # Low factuality models get dampened
            adjusted_confidence = raw_confidence * facts_weight

            weighted_votes.append(
                FactualityWeightedVote(
                    model=model,
                    vote=vote.get("vote", "HOLD"),
                    confidence=raw_confidence,
                    facts_weight=facts_weight,
                    weighted_score=adjusted_confidence,
                    reasoning=vote.get("reasoning", ""),
                )
            )

        # Calculate weighted consensus
        vote_scores = {"BUY": 0.0, "SELL": 0.0, "HOLD": 0.0}
        total_weight = 0.0

        for wv in weighted_votes:
            vote_scores[wv.vote] += wv.weighted_score
            total_weight += wv.facts_weight

        # Normalize
        if total_weight > 0:
            for k in vote_scores:
                vote_scores[k] /= total_weight

        # Determine consensus
        consensus_vote = max(vote_scores, key=vote_scores.get)
        consensus_confidence = vote_scores[consensus_vote]

        # Apply factuality ceiling warning
        # If best model is at 68.8%, max confidence should be ~0.69
        max_facts_score = max(wv.facts_weight for wv in weighted_votes)
        factuality_ceiling = max_facts_score

        if consensus_confidence > factuality_ceiling:
            logger.warning(
                f"Confidence {consensus_confidence:.2f} exceeds factuality ceiling "
                f"{factuality_ceiling:.2f}. Capping to ceiling."
            )
            consensus_confidence = factuality_ceiling

        return {
            "consensus_vote": consensus_vote,
            "consensus_confidence": consensus_confidence,
            "factuality_ceiling": factuality_ceiling,
            "vote_breakdown": vote_scores,
            "weighted_votes": [
                {
                    "model": wv.model,
                    "vote": wv.vote,
                    "raw_confidence": wv.confidence,
                    "facts_weight": wv.facts_weight,
                    "weighted_score": wv.weighted_score,
                }
                for wv in weighted_votes
            ],
            "warning": "70% factuality ceiling applies - all LLMs have <70% accuracy"
            if consensus_confidence > 0.5
            else None,
        }

    def validate_against_technicals(
        self,
        llm_signal: str,
        symbol: str,
        macd_signal: Optional[str] = None,
        rsi_signal: Optional[str] = None,
        volume_signal: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Cross-validate LLM signal against technical indicators.

        Args:
            llm_signal: LLM's recommendation (BUY/SELL/HOLD)
            symbol: Stock symbol
            macd_signal: MACD indicator signal
            rsi_signal: RSI indicator signal
            volume_signal: Volume indicator signal

        Returns:
            Validation result with agreement score
        """
        signals = {
            "llm": llm_signal.upper(),
            "macd": macd_signal.upper() if macd_signal else None,
            "rsi": rsi_signal.upper() if rsi_signal else None,
            "volume": volume_signal.upper() if volume_signal else None,
        }

        # Count agreements
        tech_signals = [s for k, s in signals.items() if k != "llm" and s is not None]

        if not tech_signals:
            return {
                "validated": None,
                "agreement_score": 0.5,
                "message": "No technical signals available for validation",
                "signals": signals,
            }

        agreements = sum(1 for s in tech_signals if s == signals["llm"])
        agreement_score = agreements / len(tech_signals)

        # Detect contradiction
        is_contradiction = agreement_score < 0.5 and len(tech_signals) >= 2

        if is_contradiction:
            logger.warning(
                f"LLM signal {signals['llm']} contradicts technicals for {symbol}: "
                f"MACD={macd_signal}, RSI={rsi_signal}, Volume={volume_signal}"
            )

            # Record potential hallucination
            self._record_signal_contradiction(
                symbol=symbol,
                llm_signal=signals["llm"],
                tech_signals=tech_signals,
            )

        return {
            "validated": not is_contradiction,
            "agreement_score": agreement_score,
            "llm_signal": signals["llm"],
            "tech_signals": {k: v for k, v in signals.items() if k != "llm"},
            "is_contradiction": is_contradiction,
            "recommendation": (
                "PROCEED"
                if agreement_score >= 0.5
                else "REVIEW - LLM contradicts technical analysis"
            ),
        }

    def validate_against_api(
        self,
        claimed_data: dict[str, Any],
        api_data: dict[str, Any],
        tolerance: float = 0.01,
    ) -> dict[str, Any]:
        """
        Validate LLM claims against Alpaca API ground truth.

        Args:
            claimed_data: Data claimed by LLM (price, position, P/L, etc.)
            api_data: Actual data from Alpaca API
            tolerance: Acceptable deviation (1% default)

        Returns:
            Validation result with discrepancies
        """
        discrepancies = []
        verified = []

        for key, claimed_value in claimed_data.items():
            if key not in api_data:
                continue

            actual_value = api_data[key]

            # Handle numeric comparison
            if isinstance(claimed_value, (int, float)) and isinstance(actual_value, (int, float)):
                if actual_value != 0:
                    deviation = abs(claimed_value - actual_value) / abs(actual_value)
                else:
                    deviation = abs(claimed_value - actual_value)

                if deviation > tolerance:
                    discrepancies.append(
                        {
                            "field": key,
                            "claimed": claimed_value,
                            "actual": actual_value,
                            "deviation": deviation,
                        }
                    )
                else:
                    verified.append(key)
            # Handle string comparison
            elif str(claimed_value).lower() != str(actual_value).lower():
                discrepancies.append(
                    {
                        "field": key,
                        "claimed": claimed_value,
                        "actual": actual_value,
                        "deviation": None,
                    }
                )
            else:
                verified.append(key)

        has_hallucination = len(discrepancies) > 0

        if has_hallucination:
            for disc in discrepancies:
                self._record_hallucination(
                    hallucination_type=HallucinationType.PRICE_MISMATCH
                    if "price" in disc["field"].lower()
                    else HallucinationType.POSITION_MISMATCH
                    if "position" in disc["field"].lower()
                    else HallucinationType.DATA_FABRICATION,
                    model="unknown",  # Would need to track which model made claim
                    claimed_value=disc["claimed"],
                    actual_value=disc["actual"],
                    verification_source=VerificationSource.ALPACA_API,
                    context={"field": disc["field"], "tolerance": tolerance},
                )

        return {
            "validated": not has_hallucination,
            "verified_fields": verified,
            "discrepancies": discrepancies,
            "hallucination_detected": has_hallucination,
        }

    def record_verification(
        self,
        model: str,
        claim_verified: bool,
        context: dict[str, Any] = None,
    ) -> None:
        """
        Record a verification result to update model metrics.

        Args:
            model: Model identifier
            claim_verified: Whether the claim was verified as true
            context: Additional context about the verification
        """
        if model not in self.metrics:
            self.metrics[model] = FactualityMetrics(
                model=model,
                facts_score=self.get_facts_score(model),
            )

        metrics = self.metrics[model]
        metrics.total_claims += 1

        if claim_verified:
            metrics.verified_claims += 1
        else:
            metrics.hallucinations += 1

        metrics.last_updated = datetime.now(timezone.utc).isoformat()

        # Save updated metrics
        self._save_metrics()

        # Log to anomaly detector if available
        if not claim_verified and self.anomaly_detector:
            try:
                import uuid

                from src.ml.anomaly_detector import AlertLevel, Anomaly, AnomalyType

                anomaly = Anomaly(
                    anomaly_id=f"hallucination_{uuid.uuid4().hex[:8]}",
                    anomaly_type=AnomalyType.DATA_STALENESS,  # Closest type
                    alert_level=AlertLevel.WARNING,
                    message=f"LLM hallucination detected for {model}",
                    details={"model": model, "context": context or {}},
                    detected_at=datetime.now(timezone.utc),
                    context=context or {},
                )
                self.anomaly_detector._save_anomaly(anomaly)
            except Exception as e:
                logger.warning(f"Failed to log to anomaly detector: {e}")

    def _record_hallucination(
        self,
        hallucination_type: HallucinationType,
        model: str,
        claimed_value: Any,
        actual_value: Any,
        verification_source: VerificationSource,
        context: dict[str, Any],
    ) -> None:
        """Record a hallucination incident."""
        import uuid

        incident = HallucinationIncident(
            incident_id=f"hall_{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            model=model,
            hallucination_type=hallucination_type,
            claimed_value=claimed_value,
            actual_value=actual_value,
            verification_source=verification_source,
            context=context,
            severity=self._assess_severity(hallucination_type, claimed_value, actual_value),
        )

        self.incidents.append(incident)
        self._save_incident(incident)

        # Store in RAG for pattern learning
        if self.rag_system:
            try:
                self.rag_system.add_lesson(
                    {
                        "id": incident.incident_id,
                        "timestamp": incident.timestamp,
                        "category": "hallucination",
                        "title": f"LLM Hallucination: {hallucination_type.value}",
                        "description": f"Model {model} claimed {claimed_value} but actual was {actual_value}",
                        "root_cause": "LLM factuality limitation (<70% accuracy per FACTS benchmark)",
                        "prevention": "Always verify LLM claims against API ground truth",
                        "tags": ["hallucination", hallucination_type.value, model],
                        "severity": incident.severity,
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to store hallucination in RAG: {e}")

        logger.warning(
            f"Hallucination recorded: {hallucination_type.value} by {model} - "
            f"claimed={claimed_value}, actual={actual_value}"
        )

    def _record_signal_contradiction(
        self,
        symbol: str,
        llm_signal: str,
        tech_signals: list[str],
    ) -> None:
        """Record when LLM signal contradicts technical analysis."""
        self._record_hallucination(
            hallucination_type=HallucinationType.SIGNAL_CONTRADICTION,
            model="council",
            claimed_value=llm_signal,
            actual_value=f"Technicals: {tech_signals}",
            verification_source=VerificationSource.TECHNICAL_INDICATORS,
            context={"symbol": symbol, "tech_signals": tech_signals},
        )

    def _assess_severity(
        self,
        hallucination_type: HallucinationType,
        claimed: Any,
        actual: Any,
    ) -> str:
        """Assess severity of a hallucination."""
        # Price/position mismatches are more severe
        if hallucination_type in (
            HallucinationType.PRICE_MISMATCH,
            HallucinationType.POSITION_MISMATCH,
        ):
            try:
                claimed_num = float(claimed)
                actual_num = float(actual)
                if actual_num != 0:
                    deviation = abs(claimed_num - actual_num) / abs(actual_num)
                    if deviation > 0.10:  # >10% off
                        return "critical"
                    elif deviation > 0.05:  # >5% off
                        return "high"
            except (ValueError, TypeError):
                pass
            return "medium"

        if hallucination_type == HallucinationType.SIGNAL_CONTRADICTION:
            return "high"  # Could lead to wrong trade

        return "low"

    def _save_incident(self, incident: HallucinationIncident) -> None:
        """Save incident to log file."""
        HALLUCINATION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

        try:
            existing = []
            if HALLUCINATION_LOG_PATH.exists():
                with open(HALLUCINATION_LOG_PATH) as f:
                    existing = json.load(f).get("incidents", [])

            existing.append(incident.to_dict())

            with open(HALLUCINATION_LOG_PATH, "w") as f:
                json.dump({"incidents": existing[-500:]}, f, indent=2)  # Keep last 500
        except Exception as e:
            logger.error(f"Failed to save hallucination incident: {e}")

    def _load_metrics(self) -> None:
        """Load historical factuality metrics."""
        if FACTUALITY_METRICS_PATH.exists():
            try:
                with open(FACTUALITY_METRICS_PATH) as f:
                    data = json.load(f)
                    for model, metrics_dict in data.get("models", {}).items():
                        self.metrics[model] = FactualityMetrics(
                            model=model,
                            total_claims=metrics_dict.get("total_claims", 0),
                            verified_claims=metrics_dict.get("verified_claims", 0),
                            hallucinations=metrics_dict.get("hallucinations", 0),
                            facts_score=metrics_dict.get(
                                "facts_score", self.get_facts_score(model)
                            ),
                            last_updated=metrics_dict.get("last_updated", ""),
                        )
            except Exception as e:
                logger.warning(f"Failed to load factuality metrics: {e}")

    def _save_metrics(self) -> None:
        """Save factuality metrics to disk."""
        FACTUALITY_METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)

        try:
            data = {
                "models": {model: metrics.to_dict() for model, metrics in self.metrics.items()},
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "facts_benchmark_reference": "Google DeepMind FACTS Grounding (Dec 2025)",
            }

            with open(FACTUALITY_METRICS_PATH, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save factuality metrics: {e}")

    def get_factuality_report(self) -> dict[str, Any]:
        """Generate a factuality report across all models."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "facts_benchmark_scores": FACTS_BENCHMARK_SCORES,
            "model_metrics": {model: metrics.to_dict() for model, metrics in self.metrics.items()},
            "total_hallucinations": sum(m.hallucinations for m in self.metrics.values()),
            "overall_accuracy": (
                sum(m.verified_claims for m in self.metrics.values())
                / max(1, sum(m.total_claims for m in self.metrics.values()))
            ),
            "recent_incidents": [i.to_dict() for i in self.incidents[-10:]],
            "factuality_ceiling_warning": (
                "Per FACTS benchmark (Dec 2025), no LLM achieves >70% factuality. "
                "Always verify critical claims against API ground truth."
            ),
        }


# Convenience function for integration
def create_factuality_monitor() -> FactualityMonitor:
    """Create a factuality monitor with RAG and anomaly detector integration."""
    rag_system = None
    anomaly_detector = None

    try:
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        rag_system = LessonsLearnedRAG()
    except Exception as e:
        logger.warning(f"Could not initialize RAG system: {e}")

    try:
        from src.ml.anomaly_detector import TradingAnomalyDetector

        anomaly_detector = TradingAnomalyDetector()
    except Exception as e:
        logger.warning(f"Could not initialize anomaly detector: {e}")

    return FactualityMonitor(
        rag_system=rag_system,
        anomaly_detector=anomaly_detector,
    )
