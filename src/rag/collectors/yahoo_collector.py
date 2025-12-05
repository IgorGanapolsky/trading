"""
Yahoo Finance news collector using yfinance.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

import yfinance as yf

from src.rag.collectors.base_collector import BaseNewsCollector

logger = logging.getLogger(__name__)


class YahooFinanceCollector(BaseNewsCollector):
    """
    Collect news from Yahoo Finance using yfinance library.
    """

    def __init__(self):
        super().__init__(source_name="yahoo")

    def collect_ticker_news(self, ticker: str, days_back: int = 7) -> list[dict[str, Any]]:
        """
        Collect news for a specific ticker from Yahoo Finance.

        Args:
            ticker: Stock ticker symbol
            days_back: How many days back to collect

        Returns:
            List of normalized articles
        """
        try:
            stock = yf.Ticker(ticker)
            news = stock.news

            if not news:
                logger.warning(f"No news found for {ticker} on Yahoo Finance")
                return []

            # Filter by date
            cutoff_date = datetime.now() - timedelta(days=days_back)
            articles = []

            for item in news:
                # Parse publication date
                pub_timestamp = item.get("providerPublishTime", 0)
                pub_date = datetime.fromtimestamp(pub_timestamp)

                if pub_date < cutoff_date:
                    continue  # Skip old articles

                # Normalize article
                article = self.normalize_article(
                    title=item.get("title", ""),
                    content=item.get("summary", ""),  # Yahoo provides summary
                    url=item.get("link", ""),
                    published_date=pub_date.strftime("%Y-%m-%d"),
                    ticker=ticker,
                )

                articles.append(article)

            logger.info(f"Collected {len(articles)} articles for {ticker} from Yahoo Finance")
            return articles

        except Exception as e:
            logger.error(f"Error collecting Yahoo Finance news for {ticker}: {e}")
            return []

    def collect_market_news(self, days_back: int = 1) -> list[dict[str, Any]]:
        """
        Collect general market news from Yahoo Finance.

        Uses major market tickers: SPY, QQQ, DIA

        Args:
            days_back: How many days back to collect

        Returns:
            List of normalized articles
        """
        market_tickers = ["SPY", "QQQ", "DIA"]
        all_articles = []

        for ticker in market_tickers:
            articles = self.collect_ticker_news(ticker, days_back=days_back)
            all_articles.extend(articles)

        # Deduplicate by URL
        seen_urls = set()
        unique_articles = []

        for article in all_articles:
            url = article.get("url")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_articles.append(article)

        logger.info(f"Collected {len(unique_articles)} unique market articles from Yahoo Finance")
        return unique_articles
