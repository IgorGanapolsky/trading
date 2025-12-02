"""
Reddit news collector using existing reddit_sentiment infrastructure.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from src.rag.collectors.base_collector import BaseNewsCollector
from src.utils.reddit_sentiment import get_reddit_sentiment

logger = logging.getLogger(__name__)


class RedditCollector(BaseNewsCollector):
    """
    Collect posts from r/wallstreetbets, r/stocks, r/investing.
    """

    def __init__(self):
        super().__init__(source_name="reddit")

    def collect_ticker_news(self, ticker: str, days_back: int = 7) -> list[dict[str, Any]]:
        """
        Collect Reddit posts mentioning a ticker.

        Args:
            ticker: Stock ticker symbol
            days_back: How many days back to collect

        Returns:
            List of normalized articles (Reddit posts)
        """
        try:
            # Use existing reddit_sentiment.py
            sentiment_data = get_reddit_sentiment(ticker)

            # Convert to normalized format
            articles = []

            for post in sentiment_data.get("posts", [])[:20]:  # Top 20 posts
                # Parse date
                created_timestamp = post.get("created_utc", 0)
                created_date = datetime.fromtimestamp(created_timestamp)

                # Filter by date
                cutoff_date = datetime.now() - timedelta(days=days_back)
                if created_date < cutoff_date:
                    continue

                # Combine title and body
                title = post.get("title", "")
                body = post.get("body", "")
                content = f"{title}\n\n{body}" if body else title

                article = self.normalize_article(
                    title=title,
                    content=content,
                    url=post.get("url", ""),
                    published_date=created_date.strftime("%Y-%m-%d"),
                    ticker=ticker,
                    sentiment=sentiment_data.get("overall_sentiment", 0.5),
                )

                articles.append(article)

            logger.info(f"Collected {len(articles)} Reddit posts for {ticker}")
            return articles

        except Exception as e:
            logger.error(f"Error collecting Reddit posts for {ticker}: {e}")
            return []

    def collect_market_news(self, days_back: int = 1) -> list[dict[str, Any]]:
        """
        Collect general market posts from Reddit.

        Uses SPY as proxy for market sentiment.

        Args:
            days_back: How many days back to collect

        Returns:
            List of normalized articles
        """
        return self.collect_ticker_news("SPY", days_back=days_back)
