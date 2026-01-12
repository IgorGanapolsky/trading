"""Playwright MCP integration stub (original deleted in cleanup)."""

from typing import Any


class SentimentScraper:
    """Stub for SentimentScraper - not used in Phil Town strategy."""

    def __init__(self, *args, **kwargs):
        pass

    def scrape(self, *args, **kwargs) -> dict:
        return {"sentiment": "neutral", "confidence": 0.0}

    async def scrape_all(self, tickers: list[str], *args, **kwargs) -> dict[str, Any]:
        """Stub for scrape_all - returns neutral sentiment for all tickers."""
        return {ticker: {"sentiment": "neutral", "confidence": 0.0} for ticker in tickers}


class TradeVerifier:
    """Stub for TradeVerifier - not used in Phil Town strategy."""

    def __init__(self, *args, **kwargs):
        pass

    def verify(self, *args, **kwargs) -> bool:
        return True

    async def verify_order_execution(
        self,
        order_id: str = "",
        expected_symbol: str = "",
        expected_qty: float = 0,
        expected_side: str = "",
        api_response: dict = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Stub for verify_order_execution - always returns success."""
        return {"verified": True, "order_id": order_id}
