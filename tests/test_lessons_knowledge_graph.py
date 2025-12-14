"""Tests for Lessons Learned Knowledge Graph Query.

Tests the multi-query semantic search system that queries lessons learned
before executing trades.

Test Coverage:
- Multi-query generation (direct, category, risk, historical)
- Lesson aggregation and deduplication
- Risk narrative generation
- Caching behavior
- Performance (latency <100ms target)
- Integration with RAG system

Author: Trading System
Created: 2025-12-11
"""

import time

import pytest
from src.verification.lessons_knowledge_graph_query import (
    LessonsKnowledgeGraphQuery,
    MatchedLesson,
    TradeContext,
    query_lessons_for_trade,
)


class TestTradeContext:
    """Test TradeContext dataclass."""

    def test_create_context(self):
        """Test creating a trade context."""
        context = TradeContext(
            symbol="SPY",
            side="buy",
            amount=100.0,
            strategy="momentum",
            position_size_pct=5.0,
            regime="volatile",
        )

        assert context.symbol == "SPY"
        assert context.side == "buy"
        assert context.amount == 100.0
        assert context.strategy == "momentum"
        assert context.position_size_pct == 5.0
        assert context.regime == "volatile"

    def test_context_to_dict(self):
        """Test converting context to dict."""
        context = TradeContext(
            symbol="AAPL",
            side="sell",
            amount=200.0,
            strategy="mean_reversion",
        )

        d = context.to_dict()

        assert d["symbol"] == "AAPL"
        assert d["side"] == "sell"
        assert d["amount"] == 200.0
        assert d["strategy"] == "mean_reversion"
        assert "signals" in d


class TestMatchedLesson:
    """Test MatchedLesson dataclass."""

    def test_create_lesson(self):
        """Test creating a matched lesson."""
        lesson = MatchedLesson(
            lesson_id="test-001",
            title="Test Lesson",
            description="Test description",
            prevention="Test prevention",
            severity="high",
            category="trading_logic",
            relevance=0.85,
            financial_impact=100.0,
            tags=["test", "demo"],
        )

        assert lesson.lesson_id == "test-001"
        assert lesson.title == "Test Lesson"
        assert lesson.relevance == 0.85
        assert lesson.financial_impact == 100.0

    def test_lesson_to_dict(self):
        """Test converting lesson to dict."""
        lesson = MatchedLesson(
            lesson_id="test-002",
            title="Another Test",
            description="Description",
            prevention="Prevention",
            severity="critical",
            category="risk_management",
            relevance=0.95,
        )

        d = lesson.to_dict()

        assert d["lesson_id"] == "test-002"
        assert d["severity"] == "critical"
        assert d["relevance"] == 0.95


class TestBuildSearchQueries:
    """Test multi-query generation."""

    def test_generates_four_queries(self):
        """Test that 4 queries are generated."""
        query_system = LessonsKnowledgeGraphQuery()

        context = TradeContext(
            symbol="SPY",
            side="buy",
            amount=100.0,
            strategy="momentum",
            position_size_pct=5.0,
            regime="volatile",
        )

        queries = query_system.build_search_queries(context)

        assert len(queries) == 4
        assert all("text" in q for q in queries)
        assert all("weight" in q for q in queries)

    def test_direct_query(self):
        """Test direct query (symbol + side + strategy)."""
        query_system = LessonsKnowledgeGraphQuery()

        context = TradeContext(
            symbol="AAPL",
            side="sell",
            amount=150.0,
            strategy="mean_reversion",
        )

        queries = query_system.build_search_queries(context)

        # First query should be direct match
        direct_query = queries[0]
        assert "AAPL" in direct_query["text"]
        assert "sell" in direct_query["text"]
        assert "mean_reversion" in direct_query["text"]
        assert direct_query["symbol"] == "AAPL"
        assert direct_query["weight"] == 1.0

    def test_category_query(self):
        """Test category query (trading logic)."""
        query_system = LessonsKnowledgeGraphQuery()

        context = TradeContext(
            symbol="BTC",
            side="buy",
            amount=50.0,
            strategy="momentum",
        )

        queries = query_system.build_search_queries(context)

        # Second query should be category-based
        category_query = queries[1]
        assert "trading_logic" in category_query["text"]
        assert "momentum" in category_query["text"]
        assert category_query["category"] == "trading_logic"
        assert category_query["weight"] == 0.8

    def test_risk_query(self):
        """Test risk-based query (position size + regime)."""
        query_system = LessonsKnowledgeGraphQuery()

        context = TradeContext(
            symbol="SPY",
            side="buy",
            amount=500.0,
            strategy="momentum",
            position_size_pct=15.0,  # Large position
            regime="volatile",
        )

        queries = query_system.build_search_queries(context)

        # Third query should be risk-based
        risk_query = queries[2]
        assert "large" in risk_query["text"]
        assert "volatile" in risk_query["text"]
        assert "risk" in risk_query["text"]
        assert risk_query["category"] == "risk_management"
        assert risk_query["weight"] == 0.7

    def test_historical_query(self):
        """Test historical query (symbol-specific)."""
        query_system = LessonsKnowledgeGraphQuery()

        context = TradeContext(
            symbol="ETH",
            side="sell",
            amount=75.0,
            strategy="momentum",
        )

        queries = query_system.build_search_queries(context)

        # Fourth query should be historical
        historical_query = queries[3]
        assert "ETH" in historical_query["text"]
        assert "recent history" in historical_query["text"]
        assert historical_query["symbol"] == "ETH"
        assert historical_query["weight"] == 0.6

    def test_position_size_descriptors(self):
        """Test position size percentage descriptors."""
        query_system = LessonsKnowledgeGraphQuery()

        # Test all size ranges
        test_cases = [
            (25.0, "very_large"),
            (15.0, "large"),
            (7.0, "medium"),
            (3.0, "small"),
            (0.5, "tiny"),
        ]

        for pct, expected_descriptor in test_cases:
            descriptor = query_system._get_position_size_descriptor(pct)
            assert descriptor == expected_descriptor, f"Failed for {pct}%"


class TestAggregateLesson:
    """Test lesson aggregation."""

    def test_deduplication(self):
        """Test that duplicate lessons are deduplicated."""
        query_system = LessonsKnowledgeGraphQuery()

        # Mock lessons
        from src.rag.lessons_learned_rag import Lesson

        lesson1 = Lesson(
            id="lesson-001",
            timestamp="2025-12-11T10:00:00",
            category="trading_logic",
            title="Test Lesson",
            description="Description",
            root_cause="Cause",
            prevention="Prevention",
            tags=["test"],
            severity="high",
        )

        # Same lesson appears twice with different scores
        results = [
            (lesson1, 0.85),
            (lesson1, 0.75),  # Duplicate, lower score
        ]

        context = TradeContext(
            symbol="SPY",
            side="buy",
            amount=100.0,
            strategy="momentum",
        )

        aggregated = query_system.aggregate_lessons(results, context)

        # Should only have one lesson (highest score)
        assert len(aggregated["lessons"]) == 1
        assert aggregated["lessons"][0].relevance == 0.85

    def test_relevance_threshold(self):
        """Test that low-relevance lessons are filtered."""
        query_system = LessonsKnowledgeGraphQuery()
        query_system.relevance_threshold = 0.5

        from src.rag.lessons_learned_rag import Lesson

        lesson1 = Lesson(
            id="lesson-001",
            timestamp="2025-12-11T10:00:00",
            category="trading_logic",
            title="High Relevance",
            description="Description",
            root_cause="Cause",
            prevention="Prevention",
            tags=["test"],
            severity="high",
        )

        lesson2 = Lesson(
            id="lesson-002",
            timestamp="2025-12-11T11:00:00",
            category="trading_logic",
            title="Low Relevance",
            description="Description",
            root_cause="Cause",
            prevention="Prevention",
            tags=["test"],
            severity="medium",
        )

        results = [
            (lesson1, 0.75),  # Above threshold
            (lesson2, 0.25),  # Below threshold
        ]

        context = TradeContext(
            symbol="SPY",
            side="buy",
            amount=100.0,
            strategy="momentum",
        )

        aggregated = query_system.aggregate_lessons(results, context)

        # Should only have high-relevance lesson
        assert len(aggregated["lessons"]) == 1
        assert aggregated["lessons"][0].title == "High Relevance"

    def test_severity_sorting(self):
        """Test that lessons are sorted by severity."""
        query_system = LessonsKnowledgeGraphQuery()

        from src.rag.lessons_learned_rag import Lesson

        # Create lessons with different severities
        critical_lesson = Lesson(
            id="lesson-001",
            timestamp="2025-12-11T10:00:00",
            category="trading_logic",
            title="Critical Issue",
            description="Description",
            root_cause="Cause",
            prevention="Prevention",
            tags=["test"],
            severity="critical",
        )

        medium_lesson = Lesson(
            id="lesson-002",
            timestamp="2025-12-11T11:00:00",
            category="trading_logic",
            title="Medium Issue",
            description="Description",
            root_cause="Cause",
            prevention="Prevention",
            tags=["test"],
            severity="medium",
        )

        high_lesson = Lesson(
            id="lesson-003",
            timestamp="2025-12-11T12:00:00",
            category="trading_logic",
            title="High Issue",
            description="Description",
            root_cause="Cause",
            prevention="Prevention",
            tags=["test"],
            severity="high",
        )

        results = [
            (medium_lesson, 0.8),
            (critical_lesson, 0.7),
            (high_lesson, 0.75),
        ]

        context = TradeContext(
            symbol="SPY",
            side="buy",
            amount=100.0,
            strategy="momentum",
        )

        aggregated = query_system.aggregate_lessons(results, context)

        # Should be sorted: critical, high, medium
        assert aggregated["lessons"][0].severity == "critical"
        assert aggregated["lessons"][1].severity == "high"
        assert aggregated["lessons"][2].severity == "medium"

    def test_prevention_checklist(self):
        """Test prevention checklist generation."""
        query_system = LessonsKnowledgeGraphQuery()

        from src.rag.lessons_learned_rag import Lesson

        lesson1 = Lesson(
            id="lesson-001",
            timestamp="2025-12-11T10:00:00",
            category="trading_logic",
            title="Lesson 1",
            description="Description",
            root_cause="Cause",
            prevention="Check data freshness",
            tags=["test"],
            severity="high",
        )

        lesson2 = Lesson(
            id="lesson-002",
            timestamp="2025-12-11T11:00:00",
            category="trading_logic",
            title="Lesson 2",
            description="Description",
            root_cause="Cause",
            prevention="Validate position size",
            tags=["test"],
            severity="critical",
        )

        results = [
            (lesson1, 0.8),
            (lesson2, 0.9),
        ]

        context = TradeContext(
            symbol="SPY",
            side="buy",
            amount=100.0,
            strategy="momentum",
        )

        aggregated = query_system.aggregate_lessons(results, context)

        # Should have both prevention steps
        assert len(aggregated["prevention_checklist"]) == 2
        assert "Check data freshness" in aggregated["prevention_checklist"]
        assert "Validate position size" in aggregated["prevention_checklist"]


class TestRiskNarrative:
    """Test risk narrative generation."""

    def test_no_lessons_narrative(self):
        """Test narrative when no lessons found."""
        query_system = LessonsKnowledgeGraphQuery()

        context = TradeContext(
            symbol="SPY",
            side="buy",
            amount=100.0,
            strategy="momentum",
        )

        narrative = query_system._build_risk_narrative([], context)

        assert "No past lessons found" in narrative
        assert "SPY" in narrative
        assert "momentum" in narrative

    def test_critical_lesson_narrative(self):
        """Test narrative with critical lessons."""
        query_system = LessonsKnowledgeGraphQuery()

        lessons = [
            MatchedLesson(
                lesson_id="test-001",
                title="Critical Error",
                description="Description",
                prevention="Prevention",
                severity="critical",
                category="trading_logic",
                relevance=0.9,
                financial_impact=500.0,
            )
        ]

        context = TradeContext(
            symbol="SPY",
            side="buy",
            amount=100.0,
            strategy="momentum",
        )

        narrative = query_system._build_risk_narrative(lessons, context)

        assert "CRITICAL" in narrative
        assert "1 critical" in narrative
        assert "Review prevention checklist" in narrative
        assert "$500.00" in narrative

    def test_financial_impact_narrative(self):
        """Test narrative includes financial impact."""
        query_system = LessonsKnowledgeGraphQuery()

        lessons = [
            MatchedLesson(
                lesson_id="test-001",
                title="Loss 1",
                description="Description",
                prevention="Prevention",
                severity="high",
                category="trading_logic",
                relevance=0.8,
                financial_impact=300.0,
            ),
            MatchedLesson(
                lesson_id="test-002",
                title="Loss 2",
                description="Description",
                prevention="Prevention",
                severity="medium",
                category="trading_logic",
                relevance=0.7,
                financial_impact=200.0,
            ),
        ]

        context = TradeContext(
            symbol="SPY",
            side="buy",
            amount=100.0,
            strategy="momentum",
        )

        narrative = query_system._build_risk_narrative(lessons, context)

        # Should show total impact
        assert "$500.00" in narrative


class TestCaching:
    """Test caching behavior."""

    def test_cache_miss_then_hit(self):
        """Test cache miss followed by cache hit."""
        query_system = LessonsKnowledgeGraphQuery()

        # Mock RAG to avoid actual queries
        query_system.rag = None

        context = TradeContext(
            symbol="SPY",
            side="buy",
            amount=100.0,
            strategy="momentum",
        )

        # First query - cache miss
        result1 = query_system.query_for_trade(context)
        assert result1["cache_hit"] is False

        # Second query - cache hit
        result2 = query_system.query_for_trade(context)
        assert result2["cache_hit"] is True

    def test_cache_expiry(self):
        """Test cache expiry after TTL."""
        query_system = LessonsKnowledgeGraphQuery()
        query_system.cache_ttl_seconds = 1  # 1 second TTL
        query_system.rag = None

        context = TradeContext(
            symbol="SPY",
            side="buy",
            amount=100.0,
            strategy="momentum",
        )

        # First query
        result1 = query_system.query_for_trade(context)
        assert result1["cache_hit"] is False

        # Wait for cache to expire
        time.sleep(1.1)

        # Second query - should be cache miss
        result2 = query_system.query_for_trade(context)
        assert result2["cache_hit"] is False

    def test_cache_different_contexts(self):
        """Test that different contexts don't hit same cache."""
        query_system = LessonsKnowledgeGraphQuery()
        query_system.rag = None

        context1 = TradeContext(
            symbol="SPY",
            side="buy",
            amount=100.0,
            strategy="momentum",
        )

        context2 = TradeContext(
            symbol="AAPL",  # Different symbol
            side="buy",
            amount=100.0,
            strategy="momentum",
        )

        # Query both
        result1 = query_system.query_for_trade(context1)
        result2 = query_system.query_for_trade(context2)

        # Both should be cache misses
        assert result1["cache_hit"] is False
        assert result2["cache_hit"] is False

    def test_clear_cache(self):
        """Test cache clearing."""
        query_system = LessonsKnowledgeGraphQuery()
        query_system.rag = None

        context = TradeContext(
            symbol="SPY",
            side="buy",
            amount=100.0,
            strategy="momentum",
        )

        # Create cache entry
        query_system.query_for_trade(context)

        # Clear cache
        query_system.clear_cache()

        # Should be cache miss now
        result = query_system.query_for_trade(context)
        assert result["cache_hit"] is False

    def test_cache_stats(self):
        """Test cache statistics."""
        query_system = LessonsKnowledgeGraphQuery()
        query_system.rag = None

        context = TradeContext(
            symbol="SPY",
            side="buy",
            amount=100.0,
            strategy="momentum",
        )

        # Create cache entry
        query_system.query_for_trade(context)

        stats = query_system.get_cache_stats()

        assert stats["entries"] == 1
        assert stats["ttl_seconds"] == 300
        assert stats["oldest_entry_age"] is not None
        assert stats["oldest_entry_age"] < 1.0  # Should be fresh


class TestPerformance:
    """Test performance requirements."""

    def test_query_latency(self):
        """Test that queries complete in <100ms (when cached)."""
        query_system = LessonsKnowledgeGraphQuery()
        query_system.rag = None  # Avoid actual RAG queries

        context = TradeContext(
            symbol="SPY",
            side="buy",
            amount=100.0,
            strategy="momentum",
        )

        # Warm up cache
        query_system.query_for_trade(context)

        # Measure cached query
        result = query_system.query_for_trade(context)

        # Cached queries should be very fast
        assert result["query_time_ms"] < 10.0  # Much faster than 100ms


class TestConvenienceFunction:
    """Test convenience function."""

    def test_query_lessons_for_trade(self):
        """Test convenience function works."""
        result = query_lessons_for_trade(
            symbol="SPY",
            side="buy",
            amount=100.0,
            strategy="momentum",
            position_size_pct=5.0,
            regime="volatile",
        )

        assert "matched_lessons" in result
        assert "prevention_checklist" in result
        assert "risk_narrative" in result
        assert "query_time_ms" in result


class TestIntegration:
    """Integration tests with RAG system."""

    def test_with_real_rag_system(self):
        """Test with actual RAG system (if available)."""
        try:
            from src.rag.lessons_learned_rag import LessonsLearnedRAG

            query_system = LessonsKnowledgeGraphQuery()

            context = TradeContext(
                symbol="SPY",
                side="buy",
                amount=1500.0,  # Large amount
                strategy="momentum",
                position_size_pct=15.0,
                regime="volatile",
            )

            result = query_system.query_for_trade(context)

            # Should have results if RAG is seeded
            assert "matched_lessons" in result
            assert isinstance(result["matched_lessons"], list)
            assert "prevention_checklist" in result
            assert "risk_narrative" in result

        except ImportError:
            pytest.skip("RAG system not available")

    def test_dict_context_conversion(self):
        """Test that dict contexts are converted to TradeContext."""
        query_system = LessonsKnowledgeGraphQuery()
        query_system.rag = None

        context_dict = {
            "symbol": "AAPL",
            "side": "sell",
            "amount": 200.0,
            "strategy": "mean_reversion",
        }

        # Should accept dict
        result = query_system.query_for_trade(context_dict)

        assert "matched_lessons" in result
        assert result["cache_hit"] is False


if __name__ == "__main__":
    """Run tests with pytest."""
    pytest.main([__file__, "-v", "--tb=short"])
