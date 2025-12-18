"""Stub module - original RAG deleted in cleanup."""

import logging

logger = logging.getLogger(__name__)


class SentimentRAGStore:
    """Stub for deleted RAG sentiment store."""

    def __init__(self, *args, **kwargs):
        logger.debug("SentimentRAGStore stub initialized (module was deleted)")

    def query(self, *args, **kwargs) -> list:
        """Return empty results."""
        return []

    def add(self, *args, **kwargs) -> None:
        """No-op."""
        pass

    def search(self, *args, **kwargs) -> list:
        """Return empty results."""
        return []
