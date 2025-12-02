"""
RAG Ingestion Pipeline

Orchestrates:
1. News collection from multiple sources
2. Embedding generation
3. Storage in ChromaDB vector database
"""

import logging
from datetime import datetime
from typing import Any

from src.rag.collectors.orchestrator import get_orchestrator
from src.rag.knowledge_graph import get_knowledge_graph
from src.rag.vector_db.chroma_client import get_rag_db
from src.rag.vector_db.embedder import get_embedder

logger = logging.getLogger(__name__)


class RAGIngestionPipeline:
    """
    Complete RAG ingestion pipeline.

    Usage:
        pipeline = RAGIngestionPipeline()

        # Option 1: Ingest ticker news
        pipeline.ingest_ticker_news("NVDA", days_back=7)

        # Option 2: Ingest watchlist news
        pipeline.ingest_watchlist_news(["NVDA", "GOOGL", "SPY"])

        # Option 3: Ingest general market news
        pipeline.ingest_market_news(days_back=1)
    """

    def __init__(self):
        """Initialize pipeline components."""
        self.orchestrator = get_orchestrator()
        self.db = get_rag_db()
        self.embedder = get_embedder()
        self.kg = get_knowledge_graph()

        logger.info("RAG Ingestion Pipeline initialized")

    def ingest_ticker_news(
        self, ticker: str, days_back: int = 7, save_normalized: bool = True
    ) -> dict[str, Any]:
        """
        Collect, embed, and store news for a single ticker.

        Args:
            ticker: Stock ticker symbol
            days_back: How many days back to collect
            save_normalized: Save normalized JSON to disk

        Returns:
            Dict with status, count, and stats
        """
        logger.info(f"\n{'=' * 60}")
        logger.info(f"🚀 Starting RAG ingestion for {ticker}")
        logger.info(f"{'=' * 60}")

        # Step 1: Collect news from all sources
        logger.info("\n📰 Step 1: Collecting news...")
        articles = self.orchestrator.collect_all_ticker_news(ticker, days_back=days_back)

        if not articles:
            logger.warning(f"No articles collected for {ticker}")
            return {"status": "no_articles", "count": 0}

        logger.info(f"✅ Collected {len(articles)} articles")

        # Save normalized articles if requested
        if save_normalized:
            self.orchestrator.save_collected_news(articles, ticker=ticker)

        # Step 2: Prepare for embedding
        logger.info("\n🧠 Step 2: Generating embeddings...")

        documents = []
        metadatas = []
        ids = []

        for i, article in enumerate(articles):
            # Combine title and content for better embeddings
            title = article.get("title", "")
            content = article.get("content", "")
            combined_text = f"{title}\n\n{content}" if title and content else (title or content)

            documents.append(combined_text)

            # Build metadata
            metadata = {
                "ticker": ticker,
                "source": article.get("source", "unknown"),
                "date": article.get("published_date", datetime.now().strftime("%Y-%m-%d")),
                "url": article.get("url", ""),
                "sentiment": article.get("sentiment", 0.5),
            }
            metadatas.append(metadata)

            # Generate unique ID
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            source = article.get("source", "unknown")
            ids.append(f"{ticker}_{source}_{timestamp}_{i}")

            # Update Knowledge Graph
            self.kg.add_document(combined_text, source_ticker=ticker)

        # Save KG changes
        self.kg.save_graph()

        # Step 3: Add to vector database (ChromaDB will auto-embed)
        logger.info("\n💾 Step 3: Storing in ChromaDB...")

        result = self.db.add_documents(documents=documents, metadatas=metadatas, ids=ids)

        if result["status"] == "success":
            logger.info(f"✅ Successfully stored {result['count']} articles in RAG database")

            # Get updated stats
            stats = self.db.get_stats()
            logger.info("\n📊 Database Stats:")
            logger.info(f"   Total documents: {stats.get('total_documents', 0)}")
            logger.info(f"   Unique tickers: {stats.get('unique_tickers', 0)}")
            logger.info(f"   Sources: {', '.join(stats.get('sources', []))}")

            return {"status": "success", "count": result["count"], "stats": stats}

        else:
            logger.error(f"❌ Failed to store articles: {result.get('message')}")
            return {"status": "error", "message": result.get("message")}

    def ingest_watchlist_news(self, tickers: list[str], days_back: int = 7) -> dict[str, Any]:
        """
        Collect, embed, and store news for multiple tickers.

        Args:
            tickers: List of stock ticker symbols
            days_back: How many days back to collect

        Returns:
            Dict with per-ticker results
        """
        results = {}

        for ticker in tickers:
            result = self.ingest_ticker_news(ticker, days_back=days_back)
            results[ticker] = result

        total_ingested = sum(r.get("count", 0) for r in results.values())
        logger.info(f"\n✅ Total ingested: {total_ingested} articles across {len(tickers)} tickers")

        return results

    def ingest_market_news(self, days_back: int = 1) -> dict[str, Any]:
        """
        Collect, embed, and store general market news.

        Args:
            days_back: How many days back to collect

        Returns:
            Dict with status and count
        """
        logger.info(f"\n{'=' * 60}")
        logger.info("🚀 Starting market news ingestion")
        logger.info(f"{'=' * 60}")

        # Collect market news
        articles = self.orchestrator.collect_market_news(days_back=days_back)

        if not articles:
            logger.warning("No market news collected")
            return {"status": "no_articles", "count": 0}

        # Save normalized articles
        self.orchestrator.save_collected_news(articles)

        # Prepare documents
        documents = []
        metadatas = []
        ids = []

        for i, article in enumerate(articles):
            title = article.get("title", "")
            content = article.get("content", "")
            combined_text = f"{title}\n\n{content}" if title and content else (title or content)

            documents.append(combined_text)

            metadata = {
                "ticker": "MARKET",
                "source": article.get("source", "unknown"),
                "date": article.get("published_date", datetime.now().strftime("%Y-%m-%d")),
                "url": article.get("url", ""),
                "sentiment": article.get("sentiment", 0.5),
            }
            metadatas.append(metadata)

            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            source = article.get("source", "unknown")
            ids.append(f"MARKET_{source}_{timestamp}_{i}")

            # Update Knowledge Graph
            self.kg.add_document(combined_text, source_ticker="MARKET")

        # Save KG changes
        self.kg.save_graph()

        # Store in database
        result = self.db.add_documents(documents=documents, metadatas=metadatas, ids=ids)

        if result["status"] == "success":
            logger.info(f"✅ Successfully stored {result['count']} market articles")
            return {"status": "success", "count": result["count"]}
        else:
            logger.error(f"❌ Failed to store market articles: {result.get('message')}")
            return {"status": "error", "message": result.get("message")}


# Convenience function
def get_pipeline() -> RAGIngestionPipeline:
    """
    Get or create RAGIngestionPipeline instance.

    Returns:
        RAGIngestionPipeline instance
    """
    return RAGIngestionPipeline()
