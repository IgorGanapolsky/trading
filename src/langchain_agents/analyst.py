"""Stub module - original langchain_agents deleted in cleanup."""

import logging

logger = logging.getLogger(__name__)


class LangChainSentimentAgent:
    """Stub for deleted LangChain sentiment agent."""

    def __init__(self, *args, **kwargs):
        logger.debug("LangChainSentimentAgent stub initialized (module was deleted)")

    def analyze(self, *args, **kwargs) -> dict:
        """Return neutral sentiment."""
        return {"sentiment": "neutral", "confidence": 0.5, "stub": True}

    def get_sentiment(self, *args, **kwargs) -> str:
        """Return neutral."""
        return "neutral"
