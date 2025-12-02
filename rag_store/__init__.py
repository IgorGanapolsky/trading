"""
Utilities for the sentiment Retrieval-Augmented Generation (RAG) store.

This package coordinates the SQLite metadata database and the Chroma vector
store used to persist and retrieve sentiment intelligence collected from
Reddit, financial news, and other data sources.
"""

from .config import SQLITE_PATH, VECTOR_PATH  # noqa: F401
from .ingest import ingest_news_snapshot, ingest_reddit_snapshot  # noqa: F401
from .sqlite_store import SentimentSQLiteStore  # noqa: F401
from .vector_store import SentimentVectorStore  # noqa: F401

__all__ = [
    "ingest_news_snapshot",
    "ingest_reddit_snapshot",
    "SentimentSQLiteStore",
    "SentimentVectorStore",
    "SQLITE_PATH",
    "VECTOR_PATH",
]
