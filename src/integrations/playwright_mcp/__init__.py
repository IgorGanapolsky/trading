"""Playwright MCP integration stub (original deleted in cleanup)."""


class SentimentScraper:
    """Stub for SentimentScraper - not used in Phil Town strategy."""

    def __init__(self, *args, **kwargs):
        pass

    def scrape(self, *args, **kwargs) -> dict:
        return {"sentiment": "neutral", "confidence": 0.0}


class TradeVerifier:
    """Stub for TradeVerifier - not used in Phil Town strategy."""

    def __init__(self, *args, **kwargs):
        pass

    def verify(self, *args, **kwargs) -> bool:
        return True
