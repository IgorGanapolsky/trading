"""Stub retriever module - original RAG deleted in cleanup.

Provides minimal interface to prevent ImportError crashes.
The trading system works without RAG - sentiment and context come from:
- VADER lexical analysis (src/utils/sentiment.py)
- LLM ensemble (mcp/servers/openrouter/sentiment.py)
- News aggregation (src/utils/news_sentiment.py)
- Lessons learned RAG (src/rag/lessons_learned_rag.py)
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class StubRetriever:
    """Minimal retriever that returns empty/neutral results.

    This prevents crashes while the full RAG system is not needed.
    Trading decisions use momentum signals + sentiment from other sources.
    """

    def __init__(self):
        logger.debug("StubRetriever initialized (full RAG not available)")

    def get_market_sentiment(self, ticker: str, days_back: int = 7, **kwargs) -> dict[str, Any]:
        """Return neutral market sentiment.

        Real sentiment comes from unified_sentiment.py which aggregates:
        - News (40% weight)
        - Social media (35% weight)
        - YouTube analysis (25% weight)
        """
        return {
            "ticker": ticker,
            "sentiment_score": 0.5,  # Neutral - let other systems provide signal
            "article_count": 0,
            "confidence": 0.0,
            "source": "stub_retriever",
            "message": "Use unified_sentiment.py for real sentiment",
        }

    def get_ticker_context(
        self, ticker: str, n_results: int = 5, days_back: int = 30, **kwargs
    ) -> list[dict[str, Any]]:
        """Return empty context list.

        Real context comes from:
        - Market data provider (src/utils/market_data.py)
        - Lessons learned RAG (src/rag/lessons_learned_rag.py)
        """
        return []

    def query_rag(
        self, query: str, n_results: int = 5, ticker: Optional[str] = None, **kwargs
    ) -> list[dict[str, Any]]:
        """Return empty query results.

        For lesson queries, use LessonsLearnedRAG directly.
        """
        return []

    def search(self, query: str, top_k: int = 5, **kwargs) -> list:
        """Generic search - returns empty results."""
        return []


# Module-level retriever instance
_retriever_instance: Optional[StubRetriever] = None


def get_retriever() -> StubRetriever:
    """Get or create the singleton retriever instance.

    Returns:
        StubRetriever that provides neutral/empty results.
        The trading system works fine with this stub because:
        - Momentum signals (90%) drive decisions
        - VADER + LLM sentiment is separate from RAG
        - Lessons learned RAG works independently
    """
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = StubRetriever()
        logger.info("Initialized stub RAG retriever (full RAG not available)")
    return _retriever_instance
