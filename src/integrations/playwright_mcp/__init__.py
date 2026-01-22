"""Playwright MCP integration stub (original deleted in cleanup)."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SentimentResult:
    """Stub sentiment result."""

    weighted_score: float = 0.0
    total_mentions: int = 0
    bullish_count: int = 0
    bearish_count: int = 0
    sources: list = field(default_factory=list)


class SentimentScraper:
    """Stub for SentimentScraper - not used in Phil Town strategy."""

    def __init__(self, *args, **kwargs):
        pass

    def scrape(self, *args, **kwargs) -> dict:
        return {"sentiment": "neutral", "confidence": 0.0}

    async def scrape_all(self, tickers: list[str], *args, **kwargs) -> dict[str, SentimentResult]:
        """Stub for scrape_all - returns empty results for all tickers."""
        return {ticker: SentimentResult() for ticker in tickers}


class TradeVerifier:
    """Stub for TradeVerifier - not used in Phil Town strategy."""

    def __init__(self, *args, **kwargs):
        pass

    def verify(self, *args, **kwargs) -> bool:
        return True

    async def verify_order_execution(
        self,
        order_id: str = "",
        _expected_symbol: str = "",
        _expected_qty: float = 0,
        _expected_side: str = "",
        _api_response: dict = None,
        **_kwargs,
    ) -> dict[str, Any]:
        """Stub for verify_order_execution - always returns success."""
        return {"verified": True, "order_id": order_id, "status": "stub_verified"}
