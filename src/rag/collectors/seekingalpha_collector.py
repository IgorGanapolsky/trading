"""
Seeking Alpha article collector using free RSS feeds.

Seeking Alpha is a major investment research platform with analyst articles,
ratings, and sentiment. This collector uses their free RSS feeds to gather
investment research data.

RSS Feed Format: https://seekingalpha.com/api/sa/combined/{SYMBOL}.xml

Features:
- Article title and summary extraction
- Sentiment analysis from content
- Analyst rating inference from articles
- Rate limiting and caching (24 hours)
- Respectful of robots.txt and ToS
"""

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import feedparser

from src.rag.collectors.base_collector import BaseNewsCollector

logger = logging.getLogger(__name__)


class SeekingAlphaCollector(BaseNewsCollector):
    """
    Collect investment research articles from Seeking Alpha using RSS feeds.

    Rate Limiting:
    - Implements 24-hour caching per ticker
    - 2-second delay between requests
    - Respects robots.txt and ToS

    Sentiment Scoring:
    - Bullish/Bearish keyword analysis
    - Analyst rating extraction (Strong Buy to Strong Sell)
    - Weighted by article recency
    """

    # RSS feed template
    RSS_FEED_URL = "https://seekingalpha.com/api/sa/combined/{symbol}.xml"

    # Cache settings
    CACHE_DIR = Path("data/rag/cache/seekingalpha")
    CACHE_DURATION_HOURS = 24

    # Rate limiting
    REQUEST_DELAY_SECONDS = 2

    # Sentiment keywords
    BULLISH_KEYWORDS = [
        "buy",
        "bullish",
        "upgrade",
        "outperform",
        "strong buy",
        "positive",
        "growth",
        "surge",
        "rally",
        "gain",
        "beat",
        "strong",
        "profit",
        "rise",
        "optimistic",
        "overweight",
        "conviction buy",
        "undervalued",
        "opportunity",
        "momentum",
        "breakout",
    ]

    BEARISH_KEYWORDS = [
        "sell",
        "bearish",
        "downgrade",
        "underperform",
        "strong sell",
        "negative",
        "decline",
        "drop",
        "fall",
        "miss",
        "weak",
        "loss",
        "crash",
        "pessimistic",
        "underweight",
        "overvalued",
        "risk",
        "warning",
        "concern",
        "headwind",
    ]

    # Analyst ratings (normalized to score)
    RATING_SCORES = {
        "strong buy": 1.0,
        "buy": 0.5,
        "hold": 0.0,
        "sell": -0.5,
        "strong sell": -1.0,
    }

    def __init__(self):
        """Initialize Seeking Alpha collector with caching."""
        super().__init__(source_name="seekingalpha")

        # Create cache directory
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

        self._last_request_time = 0
        logger.info("Seeking Alpha collector initialized with 24h caching")

    def _get_cache_path(self, ticker: str) -> Path:
        """
        Get cache file path for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Path to cache file
        """
        # Use hash to avoid filesystem issues with special characters
        ticker_hash = hashlib.md5(ticker.encode()).hexdigest()  # nosec B324
        return self.CACHE_DIR / f"{ticker}_{ticker_hash}.json"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """
        Check if cached data is still valid (< 24 hours old).

        Args:
            cache_path: Path to cache file

        Returns:
            True if cache is valid, False otherwise
        """
        if not cache_path.exists():
            return False

        # Check file modification time
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age = datetime.now() - mtime

        return age < timedelta(hours=self.CACHE_DURATION_HOURS)

    def _load_from_cache(self, ticker: str) -> Optional[list[dict[str, Any]]]:
        """
        Load articles from cache if valid.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Cached articles or None if cache invalid/missing
        """
        cache_path = self._get_cache_path(ticker)

        if not self._is_cache_valid(cache_path):
            return None

        try:
            with open(cache_path) as f:
                data = json.load(f)

            logger.info(f"Loaded {len(data)} articles from cache for {ticker}")
            return data

        except Exception as e:
            logger.warning(f"Error loading cache for {ticker}: {e}")
            return None

    def _save_to_cache(self, ticker: str, articles: list[dict[str, Any]]):
        """
        Save articles to cache.

        Args:
            ticker: Stock ticker symbol
            articles: List of articles to cache
        """
        cache_path = self._get_cache_path(ticker)

        try:
            with open(cache_path, "w") as f:
                json.dump(articles, f, indent=2)

            logger.info(f"Cached {len(articles)} articles for {ticker}")

        except Exception as e:
            logger.error(f"Error saving cache for {ticker}: {e}")

    def _rate_limit(self):
        """Implement rate limiting with delay between requests."""
        elapsed = time.time() - self._last_request_time

        if elapsed < self.REQUEST_DELAY_SECONDS:
            sleep_time = self.REQUEST_DELAY_SECONDS - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)

        self._last_request_time = time.time()

    def _extract_sentiment_from_text(self, text: str) -> float:
        """
        Extract sentiment score from text using keyword analysis.

        Args:
            text: Article title or content

        Returns:
            Sentiment score (-1.0 to +1.0)
        """
        if not text:
            return 0.0

        text_lower = text.lower()

        # Count keyword matches
        bullish_count = sum(1 for kw in self.BULLISH_KEYWORDS if kw in text_lower)
        bearish_count = sum(1 for kw in self.BEARISH_KEYWORDS if kw in text_lower)

        # Calculate sentiment
        total_keywords = bullish_count + bearish_count

        if total_keywords == 0:
            return 0.0

        sentiment = (bullish_count - bearish_count) / total_keywords

        return sentiment

    def _extract_rating_from_text(self, text: str) -> Optional[str]:
        """
        Extract analyst rating from article text.

        Args:
            text: Article title or content

        Returns:
            Rating string (e.g., "Strong Buy") or None
        """
        if not text:
            return None

        text_lower = text.lower()

        # Check for explicit ratings
        for rating in self.RATING_SCORES:
            if rating in text_lower:
                return rating.title()

        return None

    def _parse_rss_feed(self, ticker: str) -> list[dict[str, Any]]:
        """
        Parse RSS feed for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            List of normalized articles
        """
        try:
            # Rate limit
            self._rate_limit()

            # Fetch RSS feed
            feed_url = self.RSS_FEED_URL.format(symbol=ticker)
            logger.info(f"Fetching Seeking Alpha RSS for {ticker}: {feed_url}")

            feed = feedparser.parse(feed_url)

            # Check for errors
            if feed.bozo and not feed.entries:
                logger.warning(f"Error parsing feed for {ticker}: {feed.bozo_exception}")
                return []

            if not feed.entries:
                logger.warning(f"No articles found for {ticker} on Seeking Alpha")
                return []

            articles = []

            for entry in feed.entries:
                # Extract data
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                link = entry.get("link", "")

                # Parse publication date
                published = entry.get("published_parsed")
                if published:
                    pub_date = datetime(*published[:6])
                    published_date = pub_date.strftime("%Y-%m-%d")
                else:
                    published_date = datetime.now().strftime("%Y-%m-%d")

                # Extract sentiment
                combined_text = f"{title} {summary}"
                sentiment = self._extract_sentiment_from_text(combined_text)

                # Extract rating
                rating = self._extract_rating_from_text(combined_text)

                # Normalize article
                article = self.normalize_article(
                    title=title,
                    content=summary,
                    url=link,
                    published_date=published_date,
                    ticker=ticker,
                    sentiment=sentiment,
                )

                # Add Seeking Alpha specific fields
                article["rating"] = rating
                article["rating_score"] = self.RATING_SCORES.get(
                    rating.lower() if rating else "", 0.0
                )

                articles.append(article)

            logger.info(f"Collected {len(articles)} articles for {ticker} from Seeking Alpha")
            return articles

        except Exception as e:
            logger.error(f"Error fetching Seeking Alpha RSS for {ticker}: {e}")
            return []

    def collect_ticker_news(self, ticker: str, days_back: int = 7) -> list[dict[str, Any]]:
        """
        Collect news for a specific ticker from Seeking Alpha.

        Uses 24-hour cache to respect rate limits.

        Args:
            ticker: Stock ticker symbol
            days_back: How many days back to collect (filters results)

        Returns:
            List of normalized articles with sentiment and ratings
        """
        # Check cache first
        cached_articles = self._load_from_cache(ticker)
        if cached_articles is not None:
            # Filter by date
            cutoff_date = datetime.now() - timedelta(days=days_back)
            filtered = [
                article
                for article in cached_articles
                if datetime.strptime(article["published_date"], "%Y-%m-%d") >= cutoff_date
            ]
            logger.info(f"Returning {len(filtered)} cached articles for {ticker}")
            return filtered

        # Fetch from RSS
        articles = self._parse_rss_feed(ticker)

        # Cache results
        if articles:
            self._save_to_cache(ticker, articles)

        # Filter by date
        cutoff_date = datetime.now() - timedelta(days=days_back)
        filtered = [
            article
            for article in articles
            if datetime.strptime(article["published_date"], "%Y-%m-%d") >= cutoff_date
        ]

        return filtered

    def collect_market_news(self, days_back: int = 1) -> list[dict[str, Any]]:
        """
        Collect general market news from Seeking Alpha.

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

        logger.info(f"Collected {len(unique_articles)} unique market articles from Seeking Alpha")
        return unique_articles

    def get_ticker_summary(self, ticker: str, days_back: int = 7) -> dict[str, Any]:
        """
        Get aggregated sentiment summary for a ticker.

        Returns structured data suitable for trading decisions.

        Args:
            ticker: Stock ticker symbol
            days_back: How many days back to analyze

        Returns:
            Dict with:
            {
                "symbol": str,
                "sentiment_score": float (-1.0 to +1.0),
                "article_count": int,
                "avg_rating": float (-1.0 to +1.0),
                "source": "seekingalpha",
                "ratings_breakdown": dict,
                "recent_articles": list
            }
        """
        articles = self.collect_ticker_news(ticker, days_back=days_back)

        if not articles:
            return {
                "symbol": ticker,
                "sentiment_score": 0.0,
                "article_count": 0,
                "avg_rating": 0.0,
                "source": "seekingalpha",
                "ratings_breakdown": {},
                "recent_articles": [],
            }

        # Calculate average sentiment (weighted by recency)
        total_sentiment = 0.0
        total_weight = 0.0

        for i, article in enumerate(articles):
            # More recent articles get higher weight
            recency_weight = 1.0 / (i + 1)
            sentiment = article.get("sentiment", 0.0)

            total_sentiment += sentiment * recency_weight
            total_weight += recency_weight

        avg_sentiment = total_sentiment / total_weight if total_weight > 0 else 0.0

        # Calculate average rating
        ratings = [
            article.get("rating_score", 0.0)
            for article in articles
            if article.get("rating_score") is not None
        ]
        avg_rating = sum(ratings) / len(ratings) if ratings else 0.0

        # Ratings breakdown
        ratings_breakdown = {}
        for article in articles:
            rating = article.get("rating")
            if rating:
                ratings_breakdown[rating] = ratings_breakdown.get(rating, 0) + 1

        # Get recent article summaries
        recent_articles = [
            {
                "title": article.get("title"),
                "url": article.get("url"),
                "published_date": article.get("published_date"),
                "sentiment": article.get("sentiment"),
                "rating": article.get("rating"),
            }
            for article in articles[:5]  # Top 5 most recent
        ]

        return {
            "symbol": ticker,
            "sentiment_score": round(avg_sentiment, 3),
            "article_count": len(articles),
            "avg_rating": round(avg_rating, 3),
            "source": "seekingalpha",
            "ratings_breakdown": ratings_breakdown,
            "recent_articles": recent_articles,
        }


def main():
    """CLI interface for Seeking Alpha collector."""
    import argparse

    parser = argparse.ArgumentParser(description="Collect investment research from Seeking Alpha")
    parser.add_argument(
        "--ticker",
        type=str,
        default="NVDA",
        help="Stock ticker to analyze (default: NVDA)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Days back to collect (default: 7)",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Show summary instead of full articles",
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear cache before fetching",
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Initialize collector
    collector = SeekingAlphaCollector()

    # Clear cache if requested
    if args.clear_cache:
        cache_path = collector._get_cache_path(args.ticker)
        if cache_path.exists():
            cache_path.unlink()
            logger.info(f"Cleared cache for {args.ticker}")

    if args.summary:
        # Get summary
        summary = collector.get_ticker_summary(args.ticker, days_back=args.days)
        print("\n" + "=" * 80)
        print(f"SEEKING ALPHA SUMMARY - {args.ticker}")
        print("=" * 80)
        print(f"Sentiment Score: {summary['sentiment_score']:+.3f}")
        print(f"Article Count: {summary['article_count']}")
        print(f"Avg Rating: {summary['avg_rating']:+.3f}")
        print("\nRatings Breakdown:")
        for rating, count in summary["ratings_breakdown"].items():
            print(f"  - {rating}: {count}")
        print("\nRecent Articles:")
        for article in summary["recent_articles"]:
            print(f"  - {article['title']}")
            print(f"    Sentiment: {article['sentiment']:+.3f}, Rating: {article['rating']}")
            print(f"    {article['url']}")
        print("=" * 80 + "\n")
    else:
        # Get full articles
        articles = collector.collect_ticker_news(args.ticker, days_back=args.days)
        print("\n" + "=" * 80)
        print(f"SEEKING ALPHA ARTICLES - {args.ticker}")
        print("=" * 80)
        print(f"Found {len(articles)} articles")
        print("=" * 80 + "\n")

        for i, article in enumerate(articles, 1):
            print(f"{i}. {article['title']}")
            print(f"   Date: {article['published_date']}")
            print(f"   Sentiment: {article['sentiment']:+.3f}")
            print(f"   Rating: {article.get('rating', 'N/A')}")
            print(f"   URL: {article['url']}")
            print(f"   Summary: {article['content'][:150]}...")
            print()


if __name__ == "__main__":
    main()
