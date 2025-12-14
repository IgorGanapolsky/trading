#!/usr/bin/env python3
"""
Example: Using the Lightweight RAG Module

This script demonstrates how to use the new lightweight RAG implementation
with FastEmbed + LanceDB for trading knowledge management.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rag.lightweight_rag import LightweightRAG


def main():
    print("=" * 60)
    print("Lightweight RAG Example - FastEmbed + LanceDB")
    print("=" * 60)

    # Initialize lightweight RAG
    print("\n1. Initializing lightweight RAG...")
    db = LightweightRAG()
    print(f"   Status: {'✅ Active' if not db._fallback_mode else '⚠️  Fallback mode'}")

    # Add sample documents
    print("\n2. Adding sample documents...")
    documents = [
        "NVDA beats Q4 earnings expectations with $22.1B revenue, up 265% YoY",
        "GOOGL announces new Gemini AI model, competing with GPT-4",
        "AAPL reaches $3T market cap on strong iPhone 15 sales",
        "TSLA delivers record 1.8M vehicles in 2025, stock rallies 12%",
        "MSFT Azure revenue grows 30%, AI services driving growth",
    ]

    metadatas = [
        {"ticker": "NVDA", "date": "2025-12-12", "source": "yahoo"},
        {"ticker": "GOOGL", "date": "2025-12-11", "source": "bloomberg"},
        {"ticker": "AAPL", "date": "2025-12-10", "source": "reuters"},
        {"ticker": "TSLA", "date": "2025-12-09", "source": "yahoo"},
        {"ticker": "MSFT", "date": "2025-12-08", "source": "seekingalpha"},
    ]

    result = db.add_documents(documents=documents, metadatas=metadatas)
    print(f"   Added: {result['count']} documents")
    print(f"   Status: {result['status']}")

    # Query with semantic search
    print("\n3. Semantic search query...")
    query = "artificial intelligence earnings"
    results = db.query(query_text=query, n_results=3)

    print(f"   Query: '{query}'")
    print(f"   Found: {len(results['documents'])} results")
    print("\n   Top Results:")
    for i, (doc, meta, dist) in enumerate(
        zip(results["documents"], results["metadatas"], results["distances"], strict=False),
        1,
    ):
        print(f"   {i}. [{meta.get('ticker')}] {doc[:60]}...")
        print(f"      Distance: {dist:.4f} | Source: {meta.get('source')}")

    # Query with ticker filter
    print("\n4. Ticker-specific query...")
    results = db.query(query_text="latest news", n_results=5, where={"ticker": "NVDA"})
    print("   Ticker: NVDA")
    print(f"   Found: {len(results['documents'])} documents")
    if results["documents"]:
        print(f"   Content: {results['documents'][0][:80]}...")

    # Get database statistics
    print("\n5. Database statistics...")
    stats = db.get_stats()
    print(f"   Total documents: {stats['total_documents']}")
    print(f"   Unique tickers: {stats['unique_tickers']}")
    print(f"   Tickers: {', '.join(stats['tickers'][:5])}")
    print(f"   Sources: {', '.join(stats['sources'])}")
    if stats.get("date_range"):
        print(f"   Date range: {stats['date_range']['start']} to {stats['date_range']['end']}")
    print(f"   Mode: {stats.get('mode', 'unknown')}")

    # Get latest insights (new feature!)
    print("\n6. Get latest insights (NEW FEATURE)...")
    insights = db.get_latest_insights(n=3)
    print(f"   Retrieved: {len(insights)} latest insights")
    for i, insight in enumerate(insights, 1):
        print(
            f"\n   {i}. [{insight['metadata'].get('ticker')}] - {insight['metadata'].get('date')}"
        )
        print(f"      {insight['content'][:70]}...")

    # Get ticker-specific insights
    print("\n7. Get NVDA-specific insights...")
    nvda_insights = db.get_latest_insights(ticker="NVDA", n=5)
    print(f"   Retrieved: {len(nvda_insights)} NVDA insights")
    for insight in nvda_insights:
        print(f"   - {insight['content'][:60]}...")

    # Document count
    print("\n8. Document count...")
    count = db.count()
    print(f"   Total: {count} documents")

    print("\n" + "=" * 60)
    print("✅ Example complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
