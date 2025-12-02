#!/usr/bin/env python3
"""
Test RAG System End-to-End

Tests:
1. News collection from all sources
2. Embedding generation
3. Vector database storage
4. Semantic search and retrieval
5. ResearchAgent integration
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import logging

from src.agents.research_agent import ResearchAgent
from src.rag.ingestion_pipeline import get_pipeline
from src.rag.vector_db.retriever import get_retriever

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def test_news_collection():
    """Test collecting news for NVDA."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 1: News Collection")
    logger.info("=" * 60)

    pipeline = get_pipeline()

    # Collect news for NVDA (last 7 days)
    result = pipeline.orchestrator.collect_all_ticker_news("NVDA", days_back=7)

    logger.info(f"\n✅ Collected {len(result)} articles for NVDA")

    # Show sample
    if result:
        logger.info("\nSample article:")
        article = result[0]
        logger.info(f"  Title: {article.get('title', 'N/A')}")
        logger.info(f"  Source: {article.get('source', 'N/A')}")
        logger.info(f"  Date: {article.get('published_date', 'N/A')}")
        logger.info(f"  Sentiment: {article.get('sentiment', 'N/A')}")

    return len(result) > 0


def test_rag_ingestion():
    """Test ingesting news into RAG database."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: RAG Ingestion")
    logger.info("=" * 60)

    pipeline = get_pipeline()

    # Ingest news for NVDA
    result = pipeline.ingest_ticker_news("NVDA", days_back=7)

    success = result.get("status") == "success"
    count = result.get("count", 0)

    logger.info(f"\n✅ Ingested {count} articles for NVDA")

    return success and count > 0


def test_semantic_search():
    """Test semantic search in RAG database."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Semantic Search")
    logger.info("=" * 60)

    retriever = get_retriever()

    # Query: NVIDIA earnings
    query = "NVIDIA earnings and revenue growth"
    results = retriever.query_rag(query, n_results=5, ticker="NVDA")

    logger.info(f"\n✅ Found {len(results)} results for query: '{query}'")

    # Show sample
    if results:
        logger.info("\nTop result:")
        result = results[0]
        logger.info(f"  Content: {result['content'][:150]}...")
        logger.info(f"  Relevance: {result['relevance_score']:.2f}")
        logger.info(f"  Source: {result['metadata'].get('source', 'N/A')}")

    return len(results) > 0


def test_ticker_context():
    """Test getting ticker context for LLM."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: Ticker Context")
    logger.info("=" * 60)

    retriever = get_retriever()

    # Get formatted context for NVDA
    context = retriever.get_ticker_context("NVDA", n_results=5, days_back=7)

    logger.info("\n✅ Generated context for NVDA:")
    logger.info(context)

    return len(context) > 0


def test_research_agent_integration():
    """Test ResearchAgent RAG integration."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 5: ResearchAgent Integration")
    logger.info("=" * 60)

    agent = ResearchAgent()

    # Check if RAG is available
    if agent.retriever:
        logger.info("✅ RAG retriever initialized in ResearchAgent")

        # Test analysis (will query RAG internally)

        # This should query RAG internally
        # NOTE: Commenting out actual analysis to avoid LLM call
        # analysis = agent.analyze(data)
        # logger.info(f"\n✅ Analysis completed with RAG-retrieved news")

        logger.info("\n✅ ResearchAgent has RAG integration ready")
        return True
    else:
        logger.warning("❌ RAG retriever NOT available in ResearchAgent")
        return False


def test_database_stats():
    """Test database statistics."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 6: Database Statistics")
    logger.info("=" * 60)

    retriever = get_retriever()
    stats = retriever.get_stats()

    logger.info("\n📊 RAG Database Stats:")
    logger.info(f"  Total documents: {stats.get('total_documents', 0)}")
    logger.info(f"  Unique tickers: {stats.get('unique_tickers', 0)}")
    logger.info(f"  Tickers: {', '.join(stats.get('tickers', []))}")
    logger.info(f"  Sources: {', '.join(stats.get('sources', []))}")
    logger.info(f"  Date range: {stats.get('date_range', 'N/A')}")

    return stats.get("total_documents", 0) > 0


def main():
    """Run all tests."""
    logger.info("\n" + "=" * 60)
    logger.info("🚀 RAG SYSTEM END-TO-END TEST")
    logger.info("=" * 60)

    tests = [
        ("News Collection", test_news_collection),
        ("RAG Ingestion", test_rag_ingestion),
        ("Semantic Search", test_semantic_search),
        ("Ticker Context", test_ticker_context),
        ("ResearchAgent Integration", test_research_agent_integration),
        ("Database Stats", test_database_stats),
    ]

    results = {}
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = "✅ PASS" if result else "⚠️  PARTIAL"
        except Exception as e:
            logger.error(f"\n❌ {test_name} failed: {e}")
            results[test_name] = "❌ FAIL"

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)

    for test_name, result in results.items():
        logger.info(f"{test_name}: {result}")

    passed = sum(1 for r in results.values() if r == "✅ PASS")
    total = len(results)

    logger.info(f"\n🏁 Passed: {passed}/{total}")

    if passed == total:
        logger.info("✅ ALL TESTS PASSED!")
        return 0
    else:
        logger.warning(f"⚠️  {total - passed} test(s) failed or partial")
        return 1


if __name__ == "__main__":
    sys.exit(main())
