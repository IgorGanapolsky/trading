"""Lessons Learned Knowledge Graph Query.

Before executing ANY trade, query what went wrong with similar trades before.
Uses multi-query semantic search to find relevant historical context.

Architecture:
--------------
1. Multi-Query Generation: Creates 4 types of queries from trade context
   - Direct: Symbol + side + strategy (e.g., "SPY buy momentum")
   - Category: Trading logic category (e.g., "trading_logic momentum")
   - Risk: Position size + regime (e.g., "large position volatile_market")
   - Historical: Recent trades for same symbol (e.g., "SPY trades last 30 days")

2. Semantic Search: Uses sentence-transformers to find similar past failures
   - Query embedding: all-MiniLM-L6-v2 (fast, 384 dims)
   - Cosine similarity matching
   - Relevance threshold: >0.3 (configurable)

3. Result Aggregation: Combines multi-query results
   - Deduplicates by lesson ID
   - Weights by relevance score
   - Prioritizes by severity (critical > high > medium > low)

4. Prevention Synthesis: Builds actionable checklist
   - Extracts prevention steps from matched lessons
   - Orders by severity and relevance
   - Generates risk narrative summary

Integration:
--------------
Called from:
- src/risk/trade_gateway.py (pre-trade validation)
- src/verification/pre_merge_verifier.py (code change safety)
- src/strategies/*.py (strategy-specific validation)

Performance:
--------------
- Query latency: <100ms (target)
- Cache TTL: 5 minutes per symbol
- Max queries per trade: 4 (direct + category + risk + historical)

Author: Trading System
Created: 2025-12-11
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TradeContext:
    """Context for a proposed trade."""

    symbol: str
    side: str  # "buy" or "sell"
    amount: float  # Dollar amount
    strategy: str  # "momentum", "mean_reversion", etc.
    position_size_pct: float = 0.0  # % of portfolio
    regime: str = "normal"  # "volatile", "trending", "consolidating", "normal"
    signals: dict = field(default_factory=dict)  # Strategy-specific signals

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "side": self.side,
            "amount": self.amount,
            "strategy": self.strategy,
            "position_size_pct": self.position_size_pct,
            "regime": self.regime,
            "signals": self.signals,
        }


@dataclass
class MatchedLesson:
    """A lesson matched to a trade context."""

    lesson_id: str
    title: str
    description: str
    prevention: str
    severity: str
    category: str
    relevance: float  # 0-1 similarity score
    financial_impact: Optional[float] = None
    tags: list = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "lesson_id": self.lesson_id,
            "title": self.title,
            "description": self.description,
            "prevention": self.prevention,
            "severity": self.severity,
            "category": self.category,
            "relevance": self.relevance,
            "financial_impact": self.financial_impact,
            "tags": self.tags,
        }


class LessonsKnowledgeGraphQuery:
    """
    Query lessons learned knowledge graph before executing trades.

    Usage:
        query = LessonsKnowledgeGraphQuery()

        context = TradeContext(
            symbol="SPY",
            side="buy",
            amount=100.0,
            strategy="momentum",
            position_size_pct=5.0,
            regime="volatile"
        )

        result = query.query_for_trade(context)

        if result["matched_lessons"]:
            print(f"⚠️  {len(result['matched_lessons'])} past lessons found!")
            for lesson in result["matched_lessons"]:
                print(f"  - {lesson['title']} (relevance: {lesson['relevance']:.2f})")

            print("\\nPrevention Checklist:")
            for step in result["prevention_checklist"]:
                print(f"  ☐ {step}")
    """

    def __init__(self):
        """Initialize the knowledge graph query system."""
        self.rag = None
        self._cache = {}  # symbol -> (result, timestamp)
        self.cache_ttl_seconds = 300  # 5 minutes
        self.relevance_threshold = 0.3

        # Lazy load RAG to avoid import errors
        self._initialize_rag()

    def _initialize_rag(self) -> None:
        """Initialize the RAG system."""
        try:
            from src.rag.lessons_learned_rag import LessonsLearnedRAG

            self.rag = LessonsLearnedRAG()
            logger.info("Initialized lessons learned RAG system")
        except Exception as e:
            logger.warning(f"Could not initialize RAG system: {e}")
            self.rag = None

    def query_for_trade(self, trade_context: dict | TradeContext) -> dict:
        """
        Query lessons learned for a proposed trade.

        Args:
            trade_context: Trade context dict or TradeContext object

        Returns:
            Dict with:
                - matched_lessons: List of MatchedLesson dicts
                - prevention_checklist: List of prevention steps
                - risk_narrative: Summary of risks
                - query_time_ms: Query latency
                - cache_hit: Whether result was cached
        """
        start_time = time.time()

        # Convert dict to TradeContext if needed
        if isinstance(trade_context, dict):
            trade_context = TradeContext(**trade_context)

        # Check cache
        cache_key = f"{trade_context.symbol}_{trade_context.side}_{trade_context.strategy}"
        cached_result = self._check_cache(cache_key)
        if cached_result:
            cached_result["cache_hit"] = True
            cached_result["query_time_ms"] = (time.time() - start_time) * 1000
            return cached_result

        # Build search queries
        queries = self.build_search_queries(trade_context)

        # Execute queries if RAG available
        all_results = []
        if self.rag:
            for query in queries:
                try:
                    results = self.rag.search(
                        query=query["text"],
                        category=query.get("category"),
                        symbol=query.get("symbol"),
                        top_k=5,
                    )
                    all_results.extend(results)
                except Exception as e:
                    logger.warning(f"Query failed: {e}")

        # Aggregate lessons
        aggregated = self.aggregate_lessons(all_results, trade_context)

        # Build result
        result = {
            "matched_lessons": [lesson.to_dict() for lesson in aggregated["lessons"]],
            "prevention_checklist": aggregated["prevention_checklist"],
            "risk_narrative": aggregated["risk_narrative"],
            "query_time_ms": (time.time() - start_time) * 1000,
            "cache_hit": False,
            "queries_executed": len(queries),
        }

        # Cache result
        self._cache[cache_key] = (result, datetime.now())

        return result

    def build_search_queries(self, context: TradeContext) -> list[dict]:
        """
        Build multi-query search from trade context.

        Generates 4 types of queries:
        1. Direct: Symbol + side + strategy
        2. Category: Trading logic category
        3. Risk: Position size descriptor + regime
        4. Historical: Recent trades for same symbol

        Args:
            context: Trade context

        Returns:
            List of query dicts with:
                - text: Query text
                - category: Optional category filter
                - symbol: Optional symbol filter
                - weight: Query weight (0-1)
        """
        queries = []

        # Query 1: Direct match (highest weight)
        queries.append(
            {
                "text": f"{context.symbol} {context.side} {context.strategy}",
                "category": None,
                "symbol": context.symbol,
                "weight": 1.0,
            }
        )

        # Query 2: Category match (trading logic)
        queries.append(
            {
                "text": f"trading_logic {context.strategy} {context.side} decision",
                "category": "trading_logic",
                "symbol": None,
                "weight": 0.8,
            }
        )

        # Query 3: Risk-based (position size + regime)
        position_descriptor = self._get_position_size_descriptor(context.position_size_pct)
        queries.append(
            {
                "text": f"{position_descriptor} position {context.regime} market risk",
                "category": "risk_management",
                "symbol": None,
                "weight": 0.7,
            }
        )

        # Query 4: Historical (symbol-specific)
        queries.append(
            {
                "text": f"{context.symbol} trades recent history",
                "category": None,
                "symbol": context.symbol,
                "weight": 0.6,
            }
        )

        return queries

    def aggregate_lessons(self, results: list[tuple], context: TradeContext) -> dict:
        """
        Aggregate lessons from multi-query results.

        Args:
            results: List of (Lesson, score) tuples from RAG queries
            context: Trade context for risk narrative

        Returns:
            Dict with:
                - lessons: List of MatchedLesson objects
                - prevention_checklist: List of prevention steps
                - risk_narrative: Summary text
        """
        # Deduplicate by lesson ID, keeping highest score
        lesson_map = {}
        for lesson, score in results:
            if score >= self.relevance_threshold:
                if lesson.id not in lesson_map or score > lesson_map[lesson.id][1]:
                    lesson_map[lesson.id] = (lesson, score)

        # Convert to MatchedLesson objects
        matched_lessons = []
        for lesson, score in lesson_map.values():
            matched_lessons.append(
                MatchedLesson(
                    lesson_id=lesson.id,
                    title=lesson.title,
                    description=lesson.description,
                    prevention=lesson.prevention,
                    severity=lesson.severity,
                    category=lesson.category,
                    relevance=score,
                    financial_impact=lesson.financial_impact,
                    tags=lesson.tags,
                )
            )

        # Sort by severity (critical first) then relevance
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        matched_lessons.sort(key=lambda lesson: (severity_order.get(lesson.severity, 4), -lesson.relevance))

        # Build prevention checklist
        prevention_checklist = []
        seen_prevention = set()
        for lesson in matched_lessons:
            if lesson.prevention not in seen_prevention:
                prevention_checklist.append(lesson.prevention)
                seen_prevention.add(lesson.prevention)

        # Build risk narrative
        risk_narrative = self._build_risk_narrative(matched_lessons, context)

        return {
            "lessons": matched_lessons,
            "prevention_checklist": prevention_checklist,
            "risk_narrative": risk_narrative,
        }

    def _get_position_size_descriptor(self, pct: float) -> str:
        """Convert position size % to descriptor."""
        if pct >= 20:
            return "very_large"
        elif pct >= 10:
            return "large"
        elif pct >= 5:
            return "medium"
        elif pct >= 2:
            return "small"
        else:
            return "tiny"

    def _build_risk_narrative(self, lessons: list[MatchedLesson], context: TradeContext) -> str:
        """
        Build human-readable risk narrative.

        Args:
            lessons: Matched lessons
            context: Trade context

        Returns:
            Risk narrative text
        """
        if not lessons:
            return f"No past lessons found for {context.symbol} {context.side} {context.strategy}."

        # Count by severity
        critical_count = sum(1 for lesson in lessons if lesson.severity == "critical")
        high_count = sum(1 for lesson in lessons if lesson.severity == "high")

        # Calculate total financial impact
        total_impact = sum(lesson.financial_impact for lesson in lessons if lesson.financial_impact is not None)

        # Build narrative
        narrative_parts = []

        # Severity summary
        if critical_count > 0:
            narrative_parts.append(f"⚠️  CRITICAL: {critical_count} critical past failure(s) found.")
        if high_count > 0:
            narrative_parts.append(f"⚠️  {high_count} high-severity issue(s) found.")

        # Financial impact
        if total_impact > 0:
            narrative_parts.append(f"💰 Past similar trades had ${total_impact:,.2f} in losses.")

        # Top lessons
        narrative_parts.append(f"📚 {len(lessons)} relevant lesson(s) from past trading:")

        for i, lesson in enumerate(lessons[:3], 1):  # Top 3
            narrative_parts.append(
                f"  {i}. [{lesson.severity.upper()}] {lesson.title} "
                f"(relevance: {lesson.relevance:.1%})"
            )

        # Recommendation
        if critical_count > 0:
            narrative_parts.append(
                "\n🛑 RECOMMENDATION: Review prevention checklist before proceeding."
            )
        elif high_count > 0:
            narrative_parts.append("\n⚠️  RECOMMENDATION: Verify prevention steps are satisfied.")
        else:
            narrative_parts.append("\n✅ RECOMMENDATION: Proceed with caution, monitor closely.")

        return "\n".join(narrative_parts)

    def _check_cache(self, cache_key: str) -> Optional[dict]:
        """Check if cached result is still valid."""
        if cache_key not in self._cache:
            return None

        result, timestamp = self._cache[cache_key]

        # Check if expired
        age_seconds = (datetime.now() - timestamp).total_seconds()
        if age_seconds > self.cache_ttl_seconds:
            del self._cache[cache_key]
            return None

        return result

    def clear_cache(self) -> None:
        """Clear the cache."""
        self._cache.clear()
        logger.info("Cache cleared")

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        return {
            "entries": len(self._cache),
            "ttl_seconds": self.cache_ttl_seconds,
            "oldest_entry_age": self._get_oldest_cache_age(),
        }

    def _get_oldest_cache_age(self) -> Optional[float]:
        """Get age of oldest cache entry in seconds."""
        if not self._cache:
            return None

        oldest_timestamp = min(ts for _, ts in self._cache.values())
        return (datetime.now() - oldest_timestamp).total_seconds()


# Convenience function for quick queries
def query_lessons_for_trade(
    symbol: str, side: str, amount: float, strategy: str = "momentum", **kwargs
) -> dict:
    """
    Quick query for lessons learned.

    Args:
        symbol: Trading symbol
        side: "buy" or "sell"
        amount: Dollar amount
        strategy: Strategy name
        **kwargs: Additional context (position_size_pct, regime, etc.)

    Returns:
        Query result dict

    Example:
        result = query_lessons_for_trade(
            symbol="SPY",
            side="buy",
            amount=100.0,
            strategy="momentum",
            position_size_pct=5.0,
            regime="volatile"
        )

        if result["matched_lessons"]:
            print(f"Found {len(result['matched_lessons'])} warnings!")
    """
    query = LessonsKnowledgeGraphQuery()

    context = TradeContext(symbol=symbol, side=side, amount=amount, strategy=strategy, **kwargs)

    return query.query_for_trade(context)


if __name__ == "__main__":
    """Demo the knowledge graph query system."""

    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("LESSONS LEARNED KNOWLEDGE GRAPH QUERY DEMO")
    print("=" * 80)

    # Initialize
    query = LessonsKnowledgeGraphQuery()

    # Test context
    context = TradeContext(
        symbol="SPY",
        side="buy",
        amount=1500.0,
        strategy="momentum",
        position_size_pct=15.0,
        regime="volatile",
    )

    print("\nQuerying for trade:")
    print(f"  Symbol: {context.symbol}")
    print(f"  Side: {context.side}")
    print(f"  Amount: ${context.amount:,.2f}")
    print(f"  Strategy: {context.strategy}")
    print(f"  Position Size: {context.position_size_pct}%")
    print(f"  Regime: {context.regime}")

    # Execute query
    result = query.query_for_trade(context)

    print(f"\n{'=' * 80}")
    print(f"QUERY RESULTS ({result['query_time_ms']:.1f}ms)")
    print(f"{'=' * 80}")

    print(f"\nMatched Lessons: {len(result['matched_lessons'])}")
    print(f"Queries Executed: {result['queries_executed']}")
    print(f"Cache Hit: {result['cache_hit']}")

    if result["matched_lessons"]:
        print(f"\n{'=' * 80}")
        print("MATCHED LESSONS")
        print(f"{'=' * 80}")

        for lesson in result["matched_lessons"]:
            print(f"\n[{lesson['severity'].upper()}] {lesson['title']}")
            print(f"  Category: {lesson['category']}")
            print(f"  Relevance: {lesson['relevance']:.1%}")
            if lesson["financial_impact"]:
                print(f"  Financial Impact: ${lesson['financial_impact']:,.2f}")
            print(f"  Prevention: {lesson['prevention']}")

    if result["prevention_checklist"]:
        print(f"\n{'=' * 80}")
        print("PREVENTION CHECKLIST")
        print(f"{'=' * 80}")

        for i, step in enumerate(result["prevention_checklist"], 1):
            print(f"  {i}. {step}")

    print(f"\n{'=' * 80}")
    print("RISK NARRATIVE")
    print(f"{'=' * 80}")
    print(result["risk_narrative"])

    # Test caching
    print(f"\n{'=' * 80}")
    print("CACHE TEST")
    print(f"{'=' * 80}")

    result2 = query.query_for_trade(context)
    print(f"Second query: {result2['query_time_ms']:.1f}ms (cache hit: {result2['cache_hit']})")

    cache_stats = query.get_cache_stats()
    print(f"Cache entries: {cache_stats['entries']}")
    print(f"Cache TTL: {cache_stats['ttl_seconds']}s")
