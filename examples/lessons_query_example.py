#!/usr/bin/env python3
"""
Example: Using Lessons Knowledge Graph Query

This example demonstrates how to query lessons learned before executing a trade.

Author: Trading System
Date: 2025-12-11
"""

import logging

from src.verification.lessons_knowledge_graph_query import (
    LessonsKnowledgeGraphQuery,
    TradeContext,
    query_lessons_for_trade,
)

logging.basicConfig(level=logging.INFO)


def example_1_basic_query():
    """Example 1: Basic query using TradeContext."""
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Basic Query")
    print("=" * 80)

    # Create query system
    query = LessonsKnowledgeGraphQuery()

    # Define trade context
    context = TradeContext(
        symbol="SPY",
        side="buy",
        amount=1500.0,  # Large trade
        strategy="momentum",
        position_size_pct=15.0,  # 15% of portfolio
        regime="volatile",
    )

    # Query lessons
    result = query.query_for_trade(context)

    # Display results
    print(f"\n✅ Query completed in {result['query_time_ms']:.1f}ms")
    print(f"   Found {len(result['matched_lessons'])} relevant lessons")

    if result["matched_lessons"]:
        print("\n⚠️  Past Lessons:")
        for lesson in result["matched_lessons"]:
            print(f"   [{lesson['severity'].upper()}] {lesson['title']}")
            print(f"   Relevance: {lesson['relevance']:.1%}")
            print(f"   Prevention: {lesson['prevention']}")
            print()

    if result["prevention_checklist"]:
        print("📋 Prevention Checklist:")
        for i, step in enumerate(result["prevention_checklist"], 1):
            print(f"   {i}. {step}")

    print(f"\n{result['risk_narrative']}")


def example_2_convenience_function():
    """Example 2: Using convenience function."""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Convenience Function")
    print("=" * 80)

    # Quick query without creating objects
    result = query_lessons_for_trade(
        symbol="AAPL",
        side="sell",
        amount=200.0,
        strategy="mean_reversion",
        position_size_pct=5.0,
        regime="normal",
    )

    print(f"\n✅ Query completed in {result['query_time_ms']:.1f}ms")
    print(f"   Matched lessons: {len(result['matched_lessons'])}")
    print(f"   Cache hit: {result['cache_hit']}")


def example_3_multi_query():
    """Example 3: Multiple queries to demonstrate caching."""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Caching Demonstration")
    print("=" * 80)

    query = LessonsKnowledgeGraphQuery()

    context = TradeContext(
        symbol="AAPL",
        side="buy",
        amount=500.0,
        strategy="momentum",
    )

    # First query - cache miss
    result1 = query.query_for_trade(context)
    print(f"\n1st query: {result1['query_time_ms']:.1f}ms (cache hit: {result1['cache_hit']})")

    # Second query - cache hit
    result2 = query.query_for_trade(context)
    print(f"2nd query: {result2['query_time_ms']:.1f}ms (cache hit: {result2['cache_hit']})")

    # Different context - cache miss
    context2 = TradeContext(
        symbol="NVDA",  # Different symbol
        side="buy",
        amount=500.0,
        strategy="momentum",
    )

    result3 = query.query_for_trade(context2)
    print(f"3rd query: {result3['query_time_ms']:.1f}ms (cache hit: {result3['cache_hit']})")

    # Cache stats
    stats = query.get_cache_stats()
    print("\n📊 Cache Stats:")
    print(f"   Entries: {stats['entries']}")
    print(f"   TTL: {stats['ttl_seconds']}s")
    print(f"   Oldest entry age: {stats['oldest_entry_age']:.1f}s")


def example_4_risk_assessment():
    """Example 4: Risk assessment for different trade sizes."""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Risk Assessment by Trade Size")
    print("=" * 80)

    query = LessonsKnowledgeGraphQuery()

    # Test different position sizes
    position_sizes = [
        (0.5, "Tiny"),
        (3.0, "Small"),
        (7.0, "Medium"),
        (15.0, "Large"),
        (25.0, "Very Large"),
    ]

    for pct, descriptor in position_sizes:
        context = TradeContext(
            symbol="SPY",
            side="buy",
            amount=pct * 100,  # Approximate dollar amount
            strategy="momentum",
            position_size_pct=pct,
            regime="volatile",
        )

        result = query.query_for_trade(context)

        print(f"\n{descriptor} Position ({pct}%):")
        print(f"  Lessons found: {len(result['matched_lessons'])}")

        if result["matched_lessons"]:
            # Show highest severity
            highest_severity = max(
                result["matched_lessons"],
                key=lambda l: {"critical": 3, "high": 2, "medium": 1, "low": 0}[l["severity"]],
            )
            print(f"  Highest severity: {highest_severity['severity'].upper()}")


def example_5_dict_context():
    """Example 5: Using dictionary context."""
    print("\n" + "=" * 80)
    print("EXAMPLE 5: Dictionary Context")
    print("=" * 80)

    query = LessonsKnowledgeGraphQuery()

    # Pass context as dictionary
    context_dict = {
        "symbol": "TSLA",
        "side": "buy",
        "amount": 300.0,
        "strategy": "momentum",
        "position_size_pct": 10.0,
        "regime": "trending",
    }

    result = query.query_for_trade(context_dict)

    print("\n✅ Query with dict context successful")
    print(f"   Query time: {result['query_time_ms']:.1f}ms")
    print(f"   Matched lessons: {len(result['matched_lessons'])}")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("LESSONS KNOWLEDGE GRAPH QUERY - USAGE EXAMPLES")
    print("=" * 80)

    # Run all examples
    example_1_basic_query()
    example_2_convenience_function()
    example_3_multi_query()
    example_4_risk_assessment()
    example_5_dict_context()

    print("\n" + "=" * 80)
    print("EXAMPLES COMPLETE")
    print("=" * 80)
    print("\nSee docs/lessons_knowledge_graph_integration.md for more details.\n")
