"""
TikTok sentiment collector for financial/trading content.

Uses TikTok Research API to search for financial content and extract
ticker mentions and sentiment from video captions/descriptions.

API Documentation: https://developers.tiktok.com/doc/research-api-overview
"""

import logging
import os
import re
import time
from datetime import datetime, timedelta
from typing import Any

import requests
from dotenv import load_dotenv

from src.rag.collectors.base_collector import BaseNewsCollector

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class TikTokCollector(BaseNewsCollector):
    """
    Collect financial content from TikTok using Research API.

    Searches hashtags: #stocks, #investing, #stocktok, #trading, #wallstreetbets
    Extracts ticker mentions and sentiment from video captions/descriptions.
    """

    # TikTok API Configuration
    API_BASE_URL = "https://open.tiktokapis.com/v2"
    AUTH_URL = "https://open.tiktokapis.com/v2/oauth/token/"

    # Financial hashtags to monitor
    FINANCIAL_HASHTAGS = [
        "stocks",
        "investing",
        "stocktok",
        "trading",
        "wallstreetbets",
        "daytrading",
        "stockmarket",
        "finance",
        "investing101",
        "tradingview",
    ]

    # Sentiment keywords
    BULLISH_KEYWORDS = [
        "buy",
        "bullish",
        "moon",
        "rocket",
        "gains",
        "calls",
        "long",
        "hold",
        "breakout",
        "rally",
        "surge",
        "pump",
        "strong",
        "beating",
        "upgrade",
        "winning",
        "profits",
        "growth",
        "boom",
        "success",
        "soaring",
        "skyrocket",
    ]

    BEARISH_KEYWORDS = [
        "sell",
        "bearish",
        "crash",
        "dump",
        "puts",
        "short",
        "drop",
        "fall",
        "decline",
        "downgrade",
        "losing",
        "losses",
        "weak",
        "tank",
        "plunge",
        "recession",
        "bubble",
        "overvalued",
        "failing",
        "bankruptcy",
        "collapse",
        "bear market",
    ]

    # Ticker pattern (e.g., $NVDA, $SPY)
    TICKER_PATTERN = re.compile(r"\$([A-Z]{1,5})\b")

    # Rate limiting
    MAX_REQUESTS_PER_DAY = 1000  # TikTok Research API daily limit
    REQUEST_DELAY = 1.0  # Seconds between requests

    def __init__(self):
        """Initialize TikTok collector with API credentials."""
        super().__init__(source_name="tiktok")

        # Load credentials from environment
        self.client_key = os.getenv("TIKTOK_CLIENT_KEY")
        self.client_secret = os.getenv("TIKTOK_CLIENT_SECRET")

        if not self.client_key or not self.client_secret:
            logger.warning(
                "TikTok API credentials not found in environment. "
                "Set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET to enable TikTok sentiment."
            )

        # OAuth2 access token (cached)
        self.access_token = None
        self.token_expires_at = None

        # Rate limiting tracking
        self.request_count = 0
        self.last_request_time = None

        logger.info("TikTok collector initialized")

    def _get_access_token(self) -> str | None:
        """
        Get OAuth2 access token using client credentials flow.

        Returns:
            Access token string, or None if authentication fails
        """
        # Check if we have a valid cached token
        if self.access_token and self.token_expires_at:
            expires_at = self.token_expires_at
            if isinstance(expires_at, (int, float)):
                expires_at = datetime.fromtimestamp(expires_at)
            if datetime.now() < expires_at:
                return self.access_token

        if not self.client_key or not self.client_secret:
            logger.error("TikTok API credentials not configured")
            return None

        try:
            logger.info("Requesting TikTok OAuth2 access token...")

            response = requests.post(
                self.AUTH_URL,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "client_key": self.client_key,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                },
                timeout=10,
            )

            response.raise_for_status()
            data = response.json()

            self.access_token = data.get("access_token")
            expires_in = data.get("expires_in", 7200)  # Default 2 hours

            # Cache token with 5-minute buffer before expiry
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 300)

            logger.info(f"TikTok access token obtained, expires in {expires_in}s")
            return self.access_token

        except requests.exceptions.HTTPError as e:
            logger.error(f"TikTok OAuth2 authentication failed: {e}")
            if e.response:
                logger.error(f"Response: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Error getting TikTok access token: {e}")
            return None

    def _rate_limit_wait(self):
        """Implement rate limiting between API requests."""
        if self.last_request_time:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.REQUEST_DELAY:
                time.sleep(self.REQUEST_DELAY - elapsed)

        self.last_request_time = time.time()
        self.request_count += 1

        if self.request_count >= self.MAX_REQUESTS_PER_DAY:
            logger.warning(
                f"Approaching TikTok API daily limit ({self.MAX_REQUESTS_PER_DAY} requests)"
            )

    def _search_videos(
        self, query: str, max_results: int = 20, days_back: int = 7
    ) -> list[dict[str, Any]]:
        """
        Search TikTok videos using Research API.

        Args:
            query: Search query (hashtag or keyword)
            max_results: Maximum number of videos to return
            days_back: How many days back to search

        Returns:
            List of video data dictionaries
        """
        token = self._get_access_token()
        if not token:
            logger.error("Cannot search TikTok videos without access token")
            return []

        try:
            self._rate_limit_wait()

            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)

            # TikTok Research API search endpoint
            url = f"{self.API_BASE_URL}/research/video/query/"

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            payload = {
                "query": {
                    "and": [
                        {
                            "field_name": "hashtag_name",
                            "operation": "IN",
                            "field_values": [query],
                        },
                    ]
                },
                "start_date": start_date.strftime("%Y%m%d"),
                "end_date": end_date.strftime("%Y%m%d"),
                "max_count": max_results,
            }

            response = requests.post(url, headers=headers, json=payload, timeout=15)

            response.raise_for_status()
            data = response.json()

            videos = data.get("data", {}).get("videos", [])
            logger.info(f"Found {len(videos)} TikTok videos for query '{query}'")

            return videos

        except requests.exceptions.HTTPError as e:
            logger.error(f"TikTok API search failed for '{query}': {e}")
            if e.response:
                logger.error(f"Response: {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"Error searching TikTok videos for '{query}': {e}")
            return []

    def _extract_tickers(self, text: str) -> set[str]:
        """
        Extract stock ticker symbols from text.

        Args:
            text: Video caption/description

        Returns:
            Set of ticker symbols (without $)
        """
        if not text:
            return set()

        # Find all ticker mentions ($TICKER format)
        matches = self.TICKER_PATTERN.findall(text.upper())

        # Filter out common false positives
        common_words = {
            "THE",
            "FOR",
            "AND",
            "YOU",
            "ARE",
            "NOT",
            "BUT",
            "GET",
            "ALL",
            "OUT",
        }
        tickers = {t for t in matches if t not in common_words}

        return tickers

    def _analyze_sentiment(self, text: str) -> float:
        """
        Analyze sentiment of text using keyword matching.

        Args:
            text: Video caption/description

        Returns:
            Sentiment score (-1.0 to +1.0)
        """
        if not text:
            return 0.0

        text_lower = text.lower()

        # Count keyword matches
        bullish_count = sum(1 for kw in self.BULLISH_KEYWORDS if kw in text_lower)
        bearish_count = sum(1 for kw in self.BEARISH_KEYWORDS if kw in text_lower)

        total_keywords = bullish_count + bearish_count

        if total_keywords == 0:
            return 0.0  # Neutral

        # Calculate sentiment (-1 to +1)
        sentiment = (bullish_count - bearish_count) / total_keywords

        return round(sentiment, 3)

    def _calculate_engagement_score(self, video: dict[str, Any]) -> float:
        """
        Calculate engagement score from video metrics.

        Args:
            video: Video data dictionary

        Returns:
            Normalized engagement score (0-100)
        """
        # Extract engagement metrics
        like_count = video.get("like_count", 0)
        comment_count = video.get("comment_count", 0)
        share_count = video.get("share_count", 0)
        view_count = video.get("view_count", 1)  # Avoid division by zero

        # Weighted engagement rate
        # Higher weight on shares (most valuable) > comments > likes
        engagement = (share_count * 10 + comment_count * 5 + like_count * 1) / view_count

        # Normalize to 0-100 scale (cap at 0.1 engagement rate = 100 score)
        engagement_score = min(engagement * 1000, 100)

        return round(engagement_score, 2)

    def collect_ticker_news(self, ticker: str, days_back: int = 7) -> list[dict[str, Any]]:
        """
        Collect TikTok videos mentioning a specific ticker.

        Args:
            ticker: Stock ticker symbol
            days_back: How many days back to collect

        Returns:
            List of normalized articles (TikTok videos)
        """
        try:
            articles = []

            seen_ids = set()
            # Search financial hashtags for ticker mentions
            for hashtag in self.FINANCIAL_HASHTAGS[:3]:  # Limit to top 3 hashtags
                videos = self._search_videos(query=hashtag, max_results=20, days_back=days_back)

                for video in videos:
                    # Extract video metadata
                    video_id = video.get("id", "")
                    if video_id in seen_ids:
                        continue
                    caption = video.get("video_description", "")
                    create_time = video.get("create_time", 0)

                    # Check if ticker is mentioned
                    tickers = self._extract_tickers(caption)
                    if ticker.upper() not in tickers:
                        continue

                    # Calculate sentiment and engagement
                    sentiment = self._analyze_sentiment(caption)
                    engagement = self._calculate_engagement_score(video)

                    # Convert timestamp to date
                    create_date = datetime.fromtimestamp(create_time)
                    published_date = create_date.strftime("%Y-%m-%d")

                    # Create video URL
                    video_url = f"https://www.tiktok.com/@{video.get('username', 'unknown')}/video/{video_id}"

                    # Normalize to article format
                    article = self.normalize_article(
                        title=caption[:100] + "..." if len(caption) > 100 else caption,
                        content=caption,
                        url=video_url,
                        published_date=published_date,
                        ticker=ticker,
                        sentiment=(sentiment + 1) / 2,  # Convert -1 to +1 range to 0-1
                    )

                    # Add TikTok-specific metadata
                    article["engagement_score"] = engagement
                    article["video_id"] = video_id
                    article["like_count"] = video.get("like_count", 0)
                    article["comment_count"] = video.get("comment_count", 0)
                    article["share_count"] = video.get("share_count", 0)
                    article["view_count"] = video.get("view_count", 0)
                    article["hashtags"] = video.get("hashtag_names", [])

                    articles.append(article)
                    seen_ids.add(video_id)

                # If we already gathered videos for this ticker, stop after first hashtag batch
                if articles:
                    break

            # Sort by engagement score (most engaging first)
            articles.sort(key=lambda x: x.get("engagement_score", 0), reverse=True)

            logger.info(f"Collected {len(articles)} TikTok videos for {ticker}")
            return articles[:20]  # Return top 20 by engagement

        except Exception as e:
            logger.error(f"Error collecting TikTok videos for {ticker}: {e}")
            return []

    def collect_market_news(self, days_back: int = 1) -> list[dict[str, Any]]:
        """
        Collect general market videos from TikTok.

        Aggregates content from financial hashtags without ticker filtering.

        Args:
            days_back: How many days back to collect

        Returns:
            List of normalized articles (TikTok videos)
        """
        try:
            articles = []

            # Search top financial hashtags
            for hashtag in self.FINANCIAL_HASHTAGS[:5]:  # Top 5 hashtags
                videos = self._search_videos(query=hashtag, max_results=10, days_back=days_back)

                for video in videos:
                    video_id = video.get("id", "")
                    caption = video.get("video_description", "")
                    create_time = video.get("create_time", 0)

                    # Calculate sentiment and engagement
                    sentiment = self._analyze_sentiment(caption)
                    engagement = self._calculate_engagement_score(video)

                    # Extract any ticker mentions
                    tickers = self._extract_tickers(caption)
                    ticker = list(tickers)[0] if tickers else None

                    # Convert timestamp to date
                    create_date = datetime.fromtimestamp(create_time)
                    published_date = create_date.strftime("%Y-%m-%d")

                    # Create video URL
                    video_url = f"https://www.tiktok.com/@{video.get('username', 'unknown')}/video/{video_id}"

                    # Normalize to article format
                    article = self.normalize_article(
                        title=caption[:100] + "..." if len(caption) > 100 else caption,
                        content=caption,
                        url=video_url,
                        published_date=published_date,
                        ticker=ticker,
                        sentiment=(sentiment + 1) / 2,  # Convert -1 to +1 range to 0-1
                    )

                    # Add TikTok-specific metadata
                    article["engagement_score"] = engagement
                    article["video_id"] = video_id
                    article["hashtags"] = video.get("hashtag_names", [])

                    articles.append(article)

            # Sort by engagement score
            articles.sort(key=lambda x: x.get("engagement_score", 0), reverse=True)

            logger.info(f"Collected {len(articles)} general market TikTok videos")
            return articles[:30]  # Return top 30 by engagement

        except Exception as e:
            logger.error(f"Error collecting market TikTok videos: {e}")
            return []

    def get_ticker_sentiment_summary(self, ticker: str, days_back: int = 7) -> dict[str, Any]:
        """
        Get aggregated sentiment summary for a ticker.

        Args:
            ticker: Stock ticker symbol
            days_back: How many days back to analyze

        Returns:
            Structured sentiment data:
            {
                "symbol": "NVDA",
                "sentiment_score": 0.65,
                "video_count": 15,
                "engagement_score": 75.2,
                "source": "tiktok"
            }
        """
        try:
            videos = self.collect_ticker_news(ticker, days_back=days_back)

            if not videos:
                return {
                    "symbol": ticker,
                    "sentiment_score": 0.5,  # Neutral
                    "video_count": 0,
                    "engagement_score": 0.0,
                    "source": "tiktok",
                }

            # Calculate weighted average sentiment (weighted by engagement)
            total_weighted_sentiment = 0
            total_engagement = 0

            for video in videos:
                sentiment = video.get("sentiment", 0.5)
                engagement = video.get("engagement_score", 1.0)

                total_weighted_sentiment += sentiment * engagement
                total_engagement += engagement

            avg_sentiment = (
                total_weighted_sentiment / total_engagement if total_engagement > 0 else 0.5
            )

            # Calculate average engagement score
            avg_engagement = (
                sum(v.get("engagement_score", 0) for v in videos) / len(videos) if videos else 0.0
            )

            return {
                "symbol": ticker,
                "sentiment_score": round(avg_sentiment, 3),
                "video_count": len(videos),
                "engagement_score": round(avg_engagement, 2),
                "source": "tiktok",
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting TikTok sentiment summary for {ticker}: {e}")
            return {
                "symbol": ticker,
                "sentiment_score": 0.5,
                "video_count": 0,
                "engagement_score": 0.0,
                "source": "tiktok",
                "error": str(e),
            }


def main():
    """CLI interface for TikTok sentiment collector."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Collect TikTok financial sentiment")
    parser.add_argument("--ticker", type=str, help="Stock ticker to analyze (e.g., NVDA)")
    parser.add_argument("--days", type=int, default=7, help="Days back to search (default: 7)")
    parser.add_argument("--market", action="store_true", help="Collect general market videos")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Initialize collector
    collector = TikTokCollector()

    if args.market:
        # Collect general market videos
        print("\nCollecting general market TikTok videos...")
        videos = collector.collect_market_news(days_back=args.days)
        print(f"\nFound {len(videos)} videos")
        print(json.dumps(videos, indent=2))

    elif args.ticker:
        # Get ticker sentiment summary
        print(f"\nAnalyzing TikTok sentiment for {args.ticker}...")
        summary = collector.get_ticker_sentiment_summary(args.ticker.upper(), days_back=args.days)
        print("\nSentiment Summary:")
        print(json.dumps(summary, indent=2))

        # Also show individual videos
        videos = collector.collect_ticker_news(args.ticker.upper(), days_back=args.days)
        if videos:
            print(f"\n\nTop {len(videos)} videos:")
            for i, video in enumerate(videos[:5], 1):
                print(f"\n{i}. {video['title']}")
                print(f"   Sentiment: {video.get('sentiment', 0):.2f}")
                print(f"   Engagement: {video.get('engagement_score', 0):.2f}")
                print(f"   Views: {video.get('view_count', 0):,}")
                print(f"   URL: {video['url']}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
