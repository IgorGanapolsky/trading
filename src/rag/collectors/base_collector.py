"""
Base class for news collectors.
"""

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class BaseNewsCollector(ABC):
    """
    Abstract base class for news collectors.

    All collectors must implement:
    - collect_ticker_news(ticker) -> List[Dict]
    - collect_market_news() -> List[Dict]
    """

    def __init__(self, source_name: str):
        """
        Initialize collector.

        Args:
            source_name: Name of the source (e.g., "yahoo", "bloomberg")
        """
        self.source_name = source_name
        logger.info(f"Initialized {source_name} collector")

    @abstractmethod
    def collect_ticker_news(self, ticker: str, days_back: int = 7) -> list[dict[str, Any]]:
        """
        Collect news for a specific ticker.

        Args:
            ticker: Stock ticker symbol
            days_back: How many days back to collect

        Returns:
            List of normalized article dicts:
            [
                {
                    "title": "...",
                    "content": "...",
                    "url": "...",
                    "published_date": "YYYY-MM-DD",
                    "source": "yahoo",
                    "ticker": "NVDA",
                    "sentiment": 0.75  # optional
                }
            ]
        """
        pass

    @abstractmethod
    def collect_market_news(self, days_back: int = 1) -> list[dict[str, Any]]:
        """
        Collect general market news.

        Args:
            days_back: How many days back to collect

        Returns:
            List of normalized article dicts
        """
        pass

    def normalize_article(
        self,
        title: str,
        content: str,
        url: str,
        published_date: str,
        ticker: str = None,
        sentiment: float = None,
    ) -> dict[str, Any]:
        """
        Normalize article to standard format.

        Args:
            title: Article title
            content: Article content
            url: Article URL
            published_date: Publication date (YYYY-MM-DD)
            ticker: Optional ticker symbol
            sentiment: Optional sentiment score (0-1)

        Returns:
            Normalized article dict
        """
        return {
            "title": title,
            "content": content,
            "url": url,
            "published_date": published_date,
            "source": self.source_name,
            "ticker": ticker,
            "sentiment": sentiment,
            "collected_at": datetime.now().isoformat(),
        }

    def save_raw(self, articles: list[dict[str, Any]], ticker: str = None):
        """
        Save raw collected articles to data/rag/raw/.

        Args:
            articles: List of articles
            ticker: Optional ticker (for filename)
        """
        if not articles:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ticker_suffix = f"_{ticker}" if ticker else ""
        filename = f"data/rag/raw/{self.source_name}{ticker_suffix}_{timestamp}.json"

        try:
            with open(filename, "w") as f:
                json.dump(articles, f, indent=2)

            logger.info(f"Saved {len(articles)} raw articles to {filename}")

        except Exception as e:
            logger.error(f"Error saving raw articles: {e}")
