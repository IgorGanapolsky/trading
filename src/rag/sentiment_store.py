"""Stub module - original RAG deleted in cleanup.

Provides minimal interface to prevent crashes while real RAG is not needed.
The trading system uses VADER + LLM ensemble for sentiment (see unified_sentiment.py).
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SentimentRAGStore:
    """Stub for deleted RAG sentiment store.

    The trading system works without RAG - sentiment comes from:
    - VADER lexical analysis (src/utils/sentiment.py)
    - LLM ensemble (mcp/servers/openrouter/sentiment.py)
    - News aggregation (src/utils/news_sentiment.py)
    """

    def __init__(self, *args, **kwargs):
        logger.debug("SentimentRAGStore stub initialized (using VADER + LLM instead)")

    def query(self, query: str = "", ticker: str = "", top_k: int = 5, **kwargs) -> list:
        """Return empty results - sentiment comes from unified_sentiment.py."""
        return []

    def add(self, *args, **kwargs) -> None:
        """No-op - not storing RAG data."""
        pass

    def search(self, *args, **kwargs) -> list:
        """Return empty results."""
        return []

    def get_ticker_history(self, ticker: str, limit: int = 10, **kwargs) -> list:
        """Return empty history - called by sentiment_loader.py.

        Real sentiment history comes from:
        - data/sentiment/ticker_*.json (cached files)
        - SQLite database (data/sentiment.db)
        """
        return []

    def get_market_sentiment(self, ticker: str, days_back: int = 7, **kwargs) -> dict:
        """Return neutral sentiment score."""
        return {
            "ticker": ticker,
            "sentiment_score": 0.5,  # Neutral
            "article_count": 0,
            "source": "stub",
        }
