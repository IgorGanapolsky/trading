"""Semantic Trade Anomaly Detector.

Uses vector similarity to detect trades similar to past failures before execution.
Queries LessonsLearnedRAG to find similar historical incidents.

Key Features:
- Semantic similarity search against past trading mistakes
- Financial impact-weighted risk scoring
- Pre-trade blocking for high-risk patterns
- Sub-50ms latency target for production use
- Graceful degradation if RAG unavailable

Author: Trading System
Created: 2025-12-11
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TradeContext:
    """Context for a proposed trade."""

    symbol: str
    side: str  # "buy" or "sell"
    amount: float
    strategy: str
    timestamp: Optional[str] = None
    additional_context: Optional[dict[str, Any]] = None

    def to_query_text(self) -> str:
        """Convert trade context to searchable text."""
        query_parts = [
            f"{self.side} {self.symbol}",
            f"amount ${self.amount:.2f}",
            f"strategy {self.strategy}",
        ]

        if self.additional_context:
            for key, value in self.additional_context.items():
                query_parts.append(f"{key} {value}")

        return " ".join(query_parts)


@dataclass
class AnomalyResult:
    """Result from anomaly detection."""

    safe: bool
    risk_score: float  # 0.0 (safe) to 1.0 (dangerous)
    similar_incidents: list[dict[str, Any]]
    recommendation: str
    latency_ms: float
    rag_available: bool


class SemanticTradeAnomalyDetector:
    """
    Detects trades similar to past failures using semantic similarity.

    Integrates with LessonsLearnedRAG to query historical incidents and
    block trades that match known failure patterns.

    Example:
        detector = SemanticTradeAnomalyDetector(
            similarity_threshold=0.7,
            financial_impact_threshold=100
        )

        result = detector.check_trade({
            "symbol": "SPY",
            "side": "buy",
            "amount": 1600,
            "strategy": "momentum"
        })

        if not result["safe"]:
            logger.error(f"Trade blocked: {result['recommendation']}")
    """

    def __init__(
        self,
        similarity_threshold: float = 0.7,
        financial_impact_threshold: float = 100,
        rag_db_path: Optional[str] = None,
        top_k: int = 5,
    ):
        """
        Initialize the semantic trade anomaly detector.

        Args:
            similarity_threshold: Block trades above this similarity (0.0-1.0)
            financial_impact_threshold: Dollar threshold for high-impact incidents
            rag_db_path: Path to RAG database (uses default if None)
            top_k: Number of similar incidents to return
        """
        self.similarity_threshold = similarity_threshold
        self.financial_impact_threshold = financial_impact_threshold
        self.top_k = top_k
        self.rag = None
        self.rag_available = False

        # Try to initialize RAG
        try:
            from src.rag.lessons_learned_rag import LessonsLearnedRAG

            if rag_db_path:
                self.rag = LessonsLearnedRAG(db_path=rag_db_path)
            else:
                self.rag = LessonsLearnedRAG()

            self.rag_available = True
            logger.info(
                f"Initialized SemanticTradeAnomalyDetector with {len(self.rag.lessons)} lessons"
            )
        except Exception as e:
            logger.warning(f"RAG not available, using safe fallback: {e}")
            self.rag_available = False

    def check_trade(self, trade_context: dict[str, Any]) -> dict[str, Any]:
        """
        Check if a trade is similar to past failures.

        Args:
            trade_context: Dict with keys:
                - symbol (str): Trading symbol
                - side (str): "buy" or "sell"
                - amount (float): Dollar amount
                - strategy (str): Strategy name
                - timestamp (str, optional): When trade is planned
                - additional_context (dict, optional): Extra context

        Returns:
            Dict with keys:
                - safe (bool): True if trade can proceed
                - risk_score (float): 0.0 (safe) to 1.0 (dangerous)
                - similar_incidents (list): Top-K similar past failures
                - recommendation (str): Human-readable recommendation
                - latency_ms (float): Detection time in milliseconds
                - rag_available (bool): Whether RAG was used

        Example:
            >>> detector = SemanticTradeAnomalyDetector()
            >>> result = detector.check_trade({
            ...     "symbol": "SPY",
            ...     "side": "buy",
            ...     "amount": 1600,
            ...     "strategy": "momentum"
            ... })
            >>> print(result["safe"])
            False  # Blocked due to similarity to 200x position size bug
        """
        start_time = time.time()

        # Build trade context
        try:
            context = TradeContext(
                symbol=trade_context["symbol"],
                side=trade_context["side"],
                amount=trade_context["amount"],
                strategy=trade_context["strategy"],
                timestamp=trade_context.get("timestamp"),
                additional_context=trade_context.get("additional_context"),
            )
        except KeyError as e:
            logger.error(f"Invalid trade context: missing {e}")
            return self._error_result(f"Invalid trade context: missing {e}", start_time)

        # If RAG unavailable, use safe fallback
        if not self.rag_available:
            return self._fallback_check(context, start_time)

        # Query RAG for similar incidents
        try:
            query_text = context.to_query_text()
            similar_lessons = self.rag.search(
                query_text,
                top_k=self.top_k,
            )

            # Also get context for the specific trade
            trade_specific_context = self.rag.get_context_for_trade(
                symbol=context.symbol,
                side=context.side,
                amount=context.amount,
            )

            # Build incident list
            incidents = self._build_incident_list(similar_lessons, trade_specific_context)

            # Calculate risk score
            risk_score = self._calculate_risk_score(incidents, context)

            # Determine if trade is safe
            safe, recommendation = self._evaluate_safety(risk_score, incidents, context)

            latency_ms = (time.time() - start_time) * 1000

            return {
                "safe": safe,
                "risk_score": risk_score,
                "similar_incidents": incidents[: self.top_k],
                "recommendation": recommendation,
                "latency_ms": latency_ms,
                "rag_available": True,
            }

        except Exception as e:
            logger.error(f"Error during semantic check: {e}", exc_info=True)
            return self._error_result(f"Detection error: {e}", start_time)

    def _build_incident_list(
        self, similar_lessons: list, trade_context: dict
    ) -> list[dict[str, Any]]:
        """Build list of similar incidents with metadata."""
        incidents = []
        seen_ids = set()

        # Add results from semantic search
        for lesson, similarity in similar_lessons:
            if lesson.id not in seen_ids:
                incidents.append(
                    {
                        "lesson_id": lesson.id,
                        "title": lesson.title,
                        "category": lesson.category,
                        "severity": lesson.severity,
                        "description": lesson.description,
                        "root_cause": lesson.root_cause,
                        "prevention": lesson.prevention,
                        "financial_impact": lesson.financial_impact or 0.0,
                        "similarity": float(similarity),
                        "tags": lesson.tags,
                    }
                )
                seen_ids.add(lesson.id)

        # Add warnings from trade-specific context
        for warning in trade_context.get("warnings", []):
            lesson_title = warning.get("title", "")
            # Simple deduplication by title
            if not any(inc["title"] == lesson_title for inc in incidents):
                incidents.append(
                    {
                        "lesson_id": f"warning_{len(incidents)}",
                        "title": lesson_title,
                        "category": "trade_specific",
                        "severity": warning.get("severity", "medium"),
                        "description": warning.get("prevention", ""),
                        "root_cause": "Similar to past incident",
                        "prevention": warning.get("prevention", ""),
                        "financial_impact": 0.0,
                        "similarity": float(warning.get("relevance", 0.0)),
                        "tags": [],
                    }
                )

        # Sort by similarity
        incidents.sort(key=lambda x: x["similarity"], reverse=True)

        return incidents

    def _calculate_risk_score(
        self, incidents: list[dict[str, Any]], context: TradeContext
    ) -> float:
        """
        Calculate overall risk score (0.0 = safe, 1.0 = dangerous).

        Risk factors:
        1. Similarity to past failures (weight: 0.4)
        2. Financial impact of past failures (weight: 0.3)
        3. Severity of past failures (weight: 0.2)
        4. Number of similar incidents (weight: 0.1)
        """
        if not incidents:
            return 0.0

        # Factor 1: Max similarity
        max_similarity = max(inc["similarity"] for inc in incidents)
        similarity_score = max_similarity

        # Factor 2: Financial impact
        max_impact = max(inc["financial_impact"] for inc in incidents)
        impact_score = min(max_impact / 1000.0, 1.0)  # Normalize to 0-1

        # Factor 3: Severity
        severity_weights = {
            "low": 0.25,
            "medium": 0.5,
            "high": 0.75,
            "critical": 1.0,
        }
        max_severity = max(severity_weights.get(inc["severity"], 0.5) for inc in incidents)
        severity_score = max_severity

        # Factor 4: Number of incidents
        incident_count_score = min(len(incidents) / 5.0, 1.0)

        # Weighted combination
        risk_score = (
            0.4 * similarity_score
            + 0.3 * impact_score
            + 0.2 * severity_score
            + 0.1 * incident_count_score
        )

        return min(risk_score, 1.0)

    def _evaluate_safety(
        self,
        risk_score: float,
        incidents: list[dict[str, Any]],
        context: TradeContext,
    ) -> tuple[bool, str]:
        """
        Determine if trade is safe and generate recommendation.

        Returns:
            (safe, recommendation) tuple
        """
        # Check for critical similarity matches
        critical_matches = [
            inc
            for inc in incidents
            if inc["similarity"] > self.similarity_threshold
            and inc["financial_impact"] > self.financial_impact_threshold
        ]

        if critical_matches:
            top_match = critical_matches[0]
            recommendation = (
                f"⛔ TRADE BLOCKED: High similarity ({top_match['similarity']:.2f}) "
                f"to past incident '{top_match['title']}' with "
                f"${top_match['financial_impact']:.0f} impact. "
                f"Prevention: {top_match['prevention']}"
            )
            return False, recommendation

        # Check for high risk score
        if risk_score > 0.7:
            recommendation = (
                f"⚠️ HIGH RISK (score: {risk_score:.2f}): "
                f"Trade similar to {len(incidents)} past incidents. "
                f"Review prevention steps before proceeding."
            )
            return False, recommendation

        # Medium risk - warn but allow
        if risk_score > 0.4:
            top_incident = incidents[0] if incidents else None
            if top_incident:
                recommendation = (
                    f"⚠️ MEDIUM RISK (score: {risk_score:.2f}): "
                    f"Some similarity to '{top_incident['title']}'. "
                    f"Ensure prevention steps are followed."
                )
            else:
                recommendation = f"⚠️ MEDIUM RISK (score: {risk_score:.2f})"
            return True, recommendation

        # Low risk - proceed
        if incidents:
            recommendation = (
                f"✅ LOW RISK (score: {risk_score:.2f}): "
                f"No significant similarity to past failures. Proceed with standard checks."
            )
        else:
            recommendation = "✅ SAFE: No similar past incidents found."

        return True, recommendation

    def _fallback_check(self, context: TradeContext, start_time: float) -> dict[str, Any]:
        """
        Fallback check when RAG unavailable.

        Uses simple heuristics:
        - Block very large amounts (>$2000)
        - Block very small amounts (<$1)
        """
        safe = True
        risk_score = 0.0
        recommendation = "✅ SAFE (fallback mode - RAG unavailable)"

        # Simple heuristic checks
        if context.amount > 2000:
            safe = False
            risk_score = 0.8
            recommendation = (
                f"⛔ BLOCKED: Amount ${context.amount:.2f} exceeds safety limit "
                f"(fallback mode - RAG unavailable)"
            )
        elif context.amount < 1:
            safe = False
            risk_score = 0.3
            recommendation = (
                f"⚠️ WARNING: Amount ${context.amount:.2f} below minimum "
                f"(fallback mode - RAG unavailable)"
            )

        latency_ms = (time.time() - start_time) * 1000

        return {
            "safe": safe,
            "risk_score": risk_score,
            "similar_incidents": [],
            "recommendation": recommendation,
            "latency_ms": latency_ms,
            "rag_available": False,
        }

    def _error_result(self, error_msg: str, start_time: float) -> dict[str, Any]:
        """Return error result (safe by default to avoid false blocks)."""
        latency_ms = (time.time() - start_time) * 1000
        return {
            "safe": True,  # Fail open - don't block on errors
            "risk_score": 0.0,
            "similar_incidents": [],
            "recommendation": f"⚠️ ERROR: {error_msg} (allowing trade)",
            "latency_ms": latency_ms,
            "rag_available": self.rag_available,
        }

    def get_stats(self) -> dict[str, Any]:
        """Get detector statistics."""
        stats = {
            "rag_available": self.rag_available,
            "similarity_threshold": self.similarity_threshold,
            "financial_impact_threshold": self.financial_impact_threshold,
            "top_k": self.top_k,
        }

        if self.rag_available and self.rag:
            stats["total_lessons"] = len(self.rag.lessons)
            stats["embeddings_available"] = self.rag.encoder is not None

        return stats


if __name__ == "__main__":
    """Demo the semantic trade anomaly detector."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("=" * 80)
    print("SEMANTIC TRADE ANOMALY DETECTOR DEMO")
    print("=" * 80)

    # Initialize detector
    detector = SemanticTradeAnomalyDetector(
        similarity_threshold=0.7,
        financial_impact_threshold=100,
    )

    print(f"\nDetector Stats: {detector.get_stats()}")

    # Test Case 1: Large position (similar to 200x bug)
    print("\n" + "=" * 80)
    print("TEST 1: Large Position ($1600 - similar to 200x bug)")
    print("=" * 80)

    result = detector.check_trade(
        {
            "symbol": "SPY",
            "side": "buy",
            "amount": 1600.0,
            "strategy": "momentum",
        }
    )

    print(f"\nSafe: {result['safe']}")
    print(f"Risk Score: {result['risk_score']:.2f}")
    print(f"Latency: {result['latency_ms']:.2f}ms")
    print(f"Recommendation: {result['recommendation']}")
    print(f"\nSimilar Incidents ({len(result['similar_incidents'])}):")
    for inc in result["similar_incidents"][:3]:
        print(f"  [{inc['similarity']:.2f}] {inc['title']}")
        print(f"    Impact: ${inc['financial_impact']:.2f}")
        print(f"    Prevention: {inc['prevention'][:100]}...")

    # Test Case 2: Normal trade
    print("\n" + "=" * 80)
    print("TEST 2: Normal Trade ($10)")
    print("=" * 80)

    result = detector.check_trade(
        {
            "symbol": "AAPL",
            "side": "buy",
            "amount": 10.0,
            "strategy": "momentum",
        }
    )

    print(f"\nSafe: {result['safe']}")
    print(f"Risk Score: {result['risk_score']:.2f}")
    print(f"Latency: {result['latency_ms']:.2f}ms")
    print(f"Recommendation: {result['recommendation']}")

    # Test Case 3: Crypto trade
    print("\n" + "=" * 80)
    print("TEST 3: Crypto Trade with MACD context")
    print("=" * 80)

    result = detector.check_trade(
        {
            "symbol": "BTCUSD",
            "side": "buy",
            "amount": 0.5,
            "strategy": "momentum_crypto",
            "additional_context": {
                "macd": -5.0,
                "signal": "consolidation",
            },
        }
    )

    print(f"\nSafe: {result['safe']}")
    print(f"Risk Score: {result['risk_score']:.2f}")
    print(f"Latency: {result['latency_ms']:.2f}ms")
    print(f"Recommendation: {result['recommendation']}")
    if result["similar_incidents"]:
        print("\nSimilar Incidents:")
        for inc in result["similar_incidents"][:3]:
            print(f"  [{inc['similarity']:.2f}] {inc['title']}")

    print("\n" + "=" * 80)
    print("DEMO COMPLETE")
    print("=" * 80)
