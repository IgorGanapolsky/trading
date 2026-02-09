"""LanceDB-backed retriever for historical context."""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    from src.memory.document_aware_rag import get_document_aware_rag

    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False
    logger.warning("DocumentAwareRAG not available")


class LanceDBRetriever:
    """Retriever that uses LanceDB for context (with safe fallbacks)."""

    def __init__(self):
        self._rag = None
        if LANCEDB_AVAILABLE:
            try:
                self._rag = get_document_aware_rag()
                # Ensure index exists; non-fatal if it fails
                self._rag.ensure_index()
                logger.info("LanceDB Retriever initialized")
            except Exception as e:
                logger.warning(f"LanceDB Retriever init failed: {e}")
                self._rag = None
        else:
            logger.warning("LanceDB Retriever disabled (DocumentAwareRAG missing)")

    def get_market_sentiment(self, ticker: str, days_back: int = 7, **kwargs) -> dict[str, Any]:
        """Return neutral market sentiment (context only)."""
        return {
            "ticker": ticker,
            "sentiment_score": 0.5,  # Neutral - let other systems provide signal
            "article_count": 0,
            "confidence": 0.0,
            "source": "lancedb_retriever",
            "message": "Use unified_sentiment.py for sentiment",
        }

    def get_ticker_context(
        self, ticker: str, n_results: int = 5, days_back: int = 30, **kwargs
    ) -> list[dict[str, Any]]:
        """Return context snippets from LanceDB."""
        if not self._rag:
            return []
        query = f"{ticker} trading lesson risk mistake"
        results = self._rag.search(query, limit=n_results)
        return [
            {
                "title": r.title,
                "section": r.section_title,
                "content": r.content,
                "score": r.score,
                "source": r.metadata.get("source") if r.metadata else "",
            }
            for r in results
        ]

    def query_rag(
        self, query: str, n_results: int = 5, ticker: Optional[str] = None, **kwargs
    ) -> list[dict[str, Any]]:
        """Return query results from LanceDB."""
        if not self._rag:
            return []
        if ticker:
            query = f"{query} {ticker}"
        results = self._rag.search(query, limit=n_results)
        return [
            {
                "title": r.title,
                "section": r.section_title,
                "content": r.content,
                "score": r.score,
                "source": r.metadata.get("source") if r.metadata else "",
            }
            for r in results
        ]

    def search(self, query: str, top_k: int = 5, **kwargs) -> list:
        """Generic search - returns SearchResult objects from LanceDB."""
        if not self._rag:
            return []
        return self._rag.search(query, limit=top_k)


# Module-level retriever instance
_retriever_instance: Optional[LanceDBRetriever] = None


def get_retriever() -> LanceDBRetriever:
    """Get or create the singleton retriever instance.

    Returns:
        LanceDBRetriever that provides context snippets.
    """
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = LanceDBRetriever()
    return _retriever_instance
