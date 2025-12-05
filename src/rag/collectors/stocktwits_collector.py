"""
StockTwits Collector for RAG System

Collects sentiment and messages from StockTwits API.
"""

import logging
from datetime import datetime
from typing import Any

import requests

from src.rag.collectors.base_collector import BaseNewsCollector

logger = logging.getLogger(__name__)


class StockTwitsCollector(BaseNewsCollector):
    """
    Collector for StockTwits data.

    Uses the public API to fetch messages for specific symbols.
    """

    BASE_URL = "https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json"

    def __init__(self):
        super().__init__(source_name="stocktwits")

    def collect_ticker_news(self, ticker: str, days_back: int = 7) -> list[dict[str, Any]]:
        """
        Collect messages for a specific ticker.

        Args:
            ticker: Stock symbol (e.g., "AAPL")
            days_back: Not used directly by API limit, but good for interface consistency

        Returns:
            List of dictionaries containing message data
        """
        url = self.BASE_URL.format(symbol=ticker)
        limit = 30  # Default limit

        try:
            response = requests.get(url)

            if response.status_code == 429:
                logger.warning(f"Rate limit exceeded for StockTwits ({ticker})")
                return []

            if response.status_code != 200:
                logger.error(
                    f"Failed to fetch StockTwits data for {ticker}: {response.status_code}"
                )
                return []

            data = response.json()
            messages = data.get("messages", [])

            results = []
            for msg in messages[:limit]:
                # Extract sentiment if available
                sentiment_label = "Neutral"
                if msg.get("entities") and msg["entities"].get("sentiment"):
                    sentiment_label = msg["entities"]["sentiment"]["basic"]

                # Normalize using base class method
                entry = self.normalize_article(
                    title=f"StockTwits: {ticker}",
                    content=msg.get("body", ""),
                    url=f"https://stocktwits.com/message/{msg.get('id')}",
                    published_date=msg.get("created_at", datetime.now().isoformat()),
                    ticker=ticker,
                    sentiment=0.0,  # Placeholder
                )
                # Add extra metadata
                entry["author"] = msg.get("user", {}).get("username", "unknown")
                entry["sentiment_label"] = sentiment_label

                results.append(entry)

            logger.info(f"Collected {len(results)} messages from StockTwits for {ticker}")
            return results

        except Exception as e:
            logger.error(f"Error collecting from StockTwits for {ticker}: {e}")
            return []

    def collect_market_news(self, days_back: int = 1) -> list[dict[str, Any]]:
        """StockTwits is ticker-centric, no general market news."""
        return []

    def collect_daily_snapshot(self, tickers: list[str]) -> list[dict[str, Any]]:
        """Collect latest messages for all tracked tickers."""
        all_messages = []
        for ticker in tickers:
            messages = self.collect_ticker_news(ticker)
            all_messages.extend(messages)
        return all_messages
