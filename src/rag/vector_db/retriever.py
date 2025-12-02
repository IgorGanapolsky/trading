"""
RAG Retrieval Interface for Trading System

High-level API for querying the vector database.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from src.rag.vector_db.chroma_client import get_rag_db
from src.rag.vector_db.embedder import get_embedder

logger = logging.getLogger(__name__)


class RAGRetriever:
    """
    High-level interface for querying trading RAG database.

    Provides:
    - Semantic search (natural language queries)
    - Ticker-specific news retrieval
    - Date range filtering
    - Multi-source aggregation
    """

    def __init__(self):
        """Initialize retriever with database and embedder."""
        self.db = get_rag_db()
        self.embedder = get_embedder()
        logger.info("RAG Retriever initialized")

    def query_rag(
        self,
        query: str,
        n_results: int = 5,
        ticker: Optional[str] = None,
        source: Optional[str] = None,
        days_back: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """
        Query RAG database with natural language.

        Args:
            query: Natural language query
            n_results: Number of results to return
            ticker: Optional ticker filter
            source: Optional source filter (yahoo, bloomberg, etc.)
            days_back: Optional date filter (last N days)

        Returns:
            List of relevant articles with metadata and scores

        Example:
            retriever = RAGRetriever()
            articles = retriever.query_rag(
                query="NVIDIA earnings beat expectations",
                n_results=10,
                ticker="NVDA",
                days_back=7
            )
        """
        # Build metadata filter
        where = {}
        if ticker:
            where["ticker"] = ticker
        if source:
            where["source"] = source

        # Query database
        results = self.db.query(
            query_text=query, n_results=n_results, where=where if where else None
        )

        if results["status"] != "success":
            logger.error(f"Query failed: {results.get('message')}")
            return []

        # Format results
        articles = []
        for i in range(len(results["documents"])):
            metadata = results["metadatas"][i]

            # Apply date filter if specified
            if days_back is not None:
                article_date = metadata.get("date")
                if article_date:
                    cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
                    if article_date < cutoff_date:
                        continue  # Skip old articles

            articles.append(
                {
                    "content": results["documents"][i],
                    "metadata": metadata,
                    "relevance_score": 1
                    - results["distances"][i],  # Convert distance to similarity
                    "id": results["ids"][i],
                }
            )

        logger.info(f"Retrieved {len(articles)} articles for query: {query[:50]}...")
        return articles

    def get_ticker_context(self, ticker: str, n_results: int = 20, days_back: int = 7) -> str:
        """
        Get formatted context for a ticker (for LLM prompt).

        Args:
            ticker: Stock ticker
            n_results: Max results
            days_back: Last N days

        Returns:
            Formatted string with recent news and sentiment

        Example:
            context = retriever.get_ticker_context("NVDA", n_results=10, days_back=3)
            # Returns:
            # "Recent news for NVDA (last 3 days):
            # 1. [Yahoo Finance] NVIDIA reports record revenue...
            # 2. [Bloomberg] Jensen Huang announces..."
        """
        articles = self.query_rag(
            query=f"Latest news and analysis for {ticker}",
            n_results=n_results,
            ticker=ticker,
            days_back=days_back,
        )

        if not articles:
            return f"No recent news found for {ticker} in last {days_back} days."

        # Format as numbered list
        context_lines = [f"Recent news for {ticker} (last {days_back} days):"]

        for i, article in enumerate(articles, 1):
            source = article["metadata"].get("source", "Unknown")
            date = article["metadata"].get("date", "Unknown")
            content = article["content"][:200]  # First 200 chars

            context_lines.append(f"{i}. [{source.title()}] ({date}) {content}...")

        return "\n".join(context_lines)

    def get_market_sentiment(self, ticker: str, days_back: int = 7) -> dict[str, Any]:
        """
        Aggregate sentiment for a ticker from RAG database.

        Args:
            ticker: Stock ticker
            days_back: Last N days

        Returns:
            Dict with sentiment score, article count, sources

        Example:
            sentiment = retriever.get_market_sentiment("NVDA", days_back=7)
            # Returns: {
            #     "ticker": "NVDA",
            #     "sentiment_score": 0.75,  # 0-1 scale
            #     "article_count": 15,
            #     "sources": ["yahoo", "bloomberg", "reddit"],
            #     "summary": "Strongly positive (15 articles)"
            # }
        """
        articles = self.query_rag(
            query=f"Sentiment and market analysis for {ticker}",
            n_results=50,  # Get more for aggregation
            ticker=ticker,
            days_back=days_back,
        )

        if not articles:
            return {
                "ticker": ticker,
                "sentiment_score": 0.5,  # Neutral
                "article_count": 0,
                "sources": [],
                "summary": "No recent news",
            }

        # Aggregate sentiment from relevance scores
        avg_sentiment = sum(a["relevance_score"] for a in articles) / len(articles)

        # Extract unique sources
        sources = list(
            set(a["metadata"].get("source") for a in articles if a["metadata"].get("source"))
        )

        # Classify sentiment
        if avg_sentiment > 0.7:
            summary = f"Strongly positive ({len(articles)} articles)"
        elif avg_sentiment > 0.6:
            summary = f"Positive ({len(articles)} articles)"
        elif avg_sentiment > 0.4:
            summary = f"Neutral ({len(articles)} articles)"
        elif avg_sentiment > 0.3:
            summary = f"Negative ({len(articles)} articles)"
        else:
            summary = f"Strongly negative ({len(articles)} articles)"

        return {
            "ticker": ticker,
            "sentiment_score": avg_sentiment,
            "article_count": len(articles),
            "sources": sources,
            "summary": summary,
        }

    def semantic_search(self, query: str, n_results: int = 10) -> list[str]:
        """
        Simple semantic search (returns just content).

        Args:
            query: Natural language query
            n_results: Number of results

        Returns:
            List of article content strings
        """
        articles = self.query_rag(query, n_results=n_results)
        return [a["content"] for a in articles]

    def get_stats(self) -> dict[str, Any]:
        """Get RAG database statistics."""
        return self.db.get_stats()


# Singleton instance
_retriever_instance = None


def get_retriever() -> RAGRetriever:
    """
    Get or create RAGRetriever instance (singleton).

    Returns:
        RAGRetriever instance
    """
    global _retriever_instance

    if _retriever_instance is None:
        _retriever_instance = RAGRetriever()

    return _retriever_instance
