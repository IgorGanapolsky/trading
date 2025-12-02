"""
Alpha Vantage news and sentiment collector.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Any

import requests
from src.rag.collectors.base_collector import BaseNewsCollector

logger = logging.getLogger(__name__)


class AlphaVantageCollector(BaseNewsCollector):
    """
    Collect news and sentiment from Alpha Vantage API.

    Free tier: 25 API calls/day
    Features: AI-powered sentiment scores, news articles, relevance scoring
    """

    def __init__(self):
        super().__init__(source_name="alphavantage")

        # Get API key from environment
        self.api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        if not self.api_key:
            logger.warning("ALPHA_VANTAGE_API_KEY not found - collector will be disabled")

        self.base_url = "https://www.alphavantage.co/query"

    def collect_ticker_news(self, ticker: str, days_back: int = 7) -> list[dict[str, Any]]:
        """
        Collect news and sentiment for a ticker from Alpha Vantage.

        Args:
            ticker: Stock ticker symbol
            days_back: How many days back to collect (max 1000 articles)

        Returns:
            List of normalized articles with AI sentiment scores
        """
        if not self.api_key:
            logger.warning("Alpha Vantage API key not configured")
            return []

        try:
            # Call NEWS_SENTIMENT function
            params = {
                "function": "NEWS_SENTIMENT",
                "tickers": ticker,
                "apikey": self.api_key,
                "limit": 50,  # Max 50 articles per call
            }

            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if "feed" not in data:
                logger.warning(f"No news feed found for {ticker} from Alpha Vantage")
                return []

            # Filter by date
            cutoff_date = datetime.now() - timedelta(days=days_back)
            articles = []

            for item in data["feed"]:
                # Parse publication date
                pub_date_str = item.get("time_published", "")
                try:
                    pub_date = datetime.strptime(pub_date_str, "%Y%m%dT%H%M%S")
                except ValueError:
                    continue  # Skip if date parsing fails

                if pub_date < cutoff_date:
                    continue

                # Extract sentiment score
                ticker_sentiments = item.get("ticker_sentiment", [])
                ticker_score = 0.5  # Default neutral

                for ts in ticker_sentiments:
                    if ts.get("ticker") == ticker:
                        # Alpha Vantage sentiment: -1 to 1, convert to 0-1
                        raw_score = float(ts.get("ticker_sentiment_score", 0))
                        ticker_score = (raw_score + 1) / 2  # Map -1..1 to 0..1
                        break

                # Normalize article
                article = self.normalize_article(
                    title=item.get("title", ""),
                    content=item.get("summary", ""),
                    url=item.get("url", ""),
                    published_date=pub_date.strftime("%Y-%m-%d"),
                    ticker=ticker,
                    sentiment=ticker_score,
                )

                # Add additional metadata
                article["overall_sentiment_score"] = item.get("overall_sentiment_score", 0)
                article["relevance_score"] = item.get("relevance_score", 0)

                articles.append(article)

            logger.info(f"Collected {len(articles)} articles for {ticker} from Alpha Vantage")
            return articles

        except Exception as e:
            logger.error(f"Error collecting Alpha Vantage news for {ticker}: {e}")
            return []

    def collect_market_news(self, days_back: int = 1) -> list[dict[str, Any]]:
        """
        Collect general market news from Alpha Vantage.

        Args:
            days_back: How many days back to collect

        Returns:
            List of normalized articles
        """
        if not self.api_key:
            logger.warning("Alpha Vantage API key not configured")
            return []

        try:
            # Call NEWS_SENTIMENT without ticker filter
            params = {"function": "NEWS_SENTIMENT", "apikey": self.api_key, "limit": 50}

            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if "feed" not in data:
                logger.warning("No market news feed found from Alpha Vantage")
                return []

            # Filter by date
            cutoff_date = datetime.now() - timedelta(days=days_back)
            articles = []

            for item in data["feed"]:
                # Parse publication date
                pub_date_str = item.get("time_published", "")
                try:
                    pub_date = datetime.strptime(pub_date_str, "%Y%m%dT%H%M%S")
                except ValueError:
                    continue

                if pub_date < cutoff_date:
                    continue

                # Extract overall sentiment
                overall_score = item.get("overall_sentiment_score", 0)
                # Map -1..1 to 0..1
                sentiment = (float(overall_score) + 1) / 2

                article = self.normalize_article(
                    title=item.get("title", ""),
                    content=item.get("summary", ""),
                    url=item.get("url", ""),
                    published_date=pub_date.strftime("%Y-%m-%d"),
                    sentiment=sentiment,
                )

                articles.append(article)

            logger.info(f"Collected {len(articles)} market articles from Alpha Vantage")
            return articles

        except Exception as e:
            logger.error(f"Error collecting Alpha Vantage market news: {e}")
            return []
