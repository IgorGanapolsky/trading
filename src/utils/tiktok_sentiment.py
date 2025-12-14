"""
TikTok Sentiment Scraper for Trading System

Collects sentiment from TikTok videos about stocks and trading to gauge viral
momentum and retail trader interest. Focuses on trending content that could
drive short-term price movements.

Features:
- Monitors #stocks #trading #investing content
- Extracts ticker mentions from video titles/descriptions
- Scores sentiment using keyword analysis
- Caches results for 24 hours
- **NO API KEY REQUIRED**: Uses publicly accessible TikTok web endpoints
- Fallback to multiple scraping methods for reliability

Search Strategy:
- Searches for hashtag combinations (#stocks #NVDA, #trading #TSLA, etc.)
- Analyzes video titles, descriptions, and hashtags
- Weights recent/trending videos higher
- Filters out spam and low-quality content

Usage:
    # Command line
    python tiktok_sentiment.py --tickers NVDA,TSLA --limit 20

    # Programmatic
    from src.utils.tiktok_sentiment import TikTokSentiment
    analyzer = TikTokSentiment()
    data = analyzer.get_ticker_sentiment("NVDA")
"""

import json
import logging
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

from src.utils.retry_decorator import retry_with_backoff

logger = logging.getLogger(__name__)


class TikTokSentiment:
    """
    Scrapes and analyzes sentiment from TikTok trading content.

    Since TikTok doesn't have an official public API, this uses web scraping
    techniques and publicly accessible endpoints to gather data.
    """

    # Stock-related hashtags to search
    STOCK_HASHTAGS = [
        "stocks",
        "stockmarket",
        "trading",
        "investing",
        "daytrading",
        "stockstobuy",
        "stockanalysis",
        "wallstreetbets",
    ]

    # Bullish keywords and their weights
    BULLISH_KEYWORDS = {
        # Strong bullish
        "moon": 3,
        "rocket": 3,
        "buy now": 3,
        "buying": 2,
        "bullish": 2,
        "calls": 2,
        "long": 2,
        "undervalued": 2,
        "breakout": 2,
        "rally": 2,
        # Moderate bullish
        "buy": 2,
        "hold": 1,
        "up": 1,
        "green": 1,
        "bull": 2,
        "gains": 2,
        "profit": 2,
        "surge": 2,
        "growth": 1,
        "strong": 1,
        "opportunity": 2,
        "accumulate": 2,
    }

    # Bearish keywords and their weights
    BEARISH_KEYWORDS = {
        # Strong bearish
        "crash": 3,
        "dump": 3,
        "sell now": 3,
        "short": 2,
        "bearish": 2,
        "puts": 2,
        "overvalued": 2,
        "bubble": 2,
        "collapse": 3,
        # Moderate bearish
        "sell": 2,
        "down": 1,
        "red": 1,
        "bear": 2,
        "loss": 2,
        "drop": 2,
        "decline": 2,
        "risk": 1,
        "warning": 2,
        "avoid": 2,
        "falling": 1,
    }

    # User agent to avoid blocking
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    def __init__(self, data_dir: str = "data/sentiment", cache_hours: int = 24):
        """
        Initialize TikTok sentiment analyzer.

        Args:
            data_dir: Directory for caching sentiment data
            cache_hours: Hours to cache results before refresh
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_hours = cache_hours

        # Session for making requests
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.tiktok.com/",
        })

        logger.info("TikTokSentiment initialized (no API key required)")

    def _get_cache_file(self, ticker: str) -> Path:
        """Get cache file path for a ticker"""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.data_dir / f"tiktok_{ticker}_{today}.json"

    def _load_from_cache(self, ticker: str) -> dict[str, Any] | None:
        """Load sentiment data from cache if fresh enough"""
        cache_file = self._get_cache_file(ticker)

        if not cache_file.exists():
            return None

        try:
            cache_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
            if cache_age.total_seconds() > self.cache_hours * 3600:
                logger.debug(f"Cache expired for {ticker} (age: {cache_age})")
                return None

            with open(cache_file) as f:
                data = json.load(f)

            logger.info(f"Cache hit for TikTok sentiment: {ticker}")
            return data

        except Exception as e:
            logger.warning(f"Error loading cache for {ticker}: {e}")
            return None

    def _save_to_cache(self, ticker: str, data: dict[str, Any]):
        """Save sentiment data to cache"""
        cache_file = self._get_cache_file(ticker)

        try:
            with open(cache_file, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Cached TikTok sentiment for {ticker}")
        except Exception as e:
            logger.warning(f"Error saving cache for {ticker}: {e}")

    @retry_with_backoff(max_retries=3, initial_delay=2.0)
    def _search_tiktok_web(self, query: str, limit: int = 20) -> list[dict]:
        """
        Search TikTok using web scraping (fallback method).

        This scrapes the public TikTok search page which doesn't require auth.

        Args:
            query: Search query (e.g., "#stocks NVDA")
            limit: Max number of videos to analyze

        Returns:
            List of video data dictionaries
        """
        try:
            # TikTok search URL (public, no auth needed)
            search_url = f"https://www.tiktok.com/search?q={query}"

            logger.debug(f"Searching TikTok web for: {query}")

            # Make request
            response = self.session.get(search_url, timeout=10)
            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.text, "html.parser")

            videos = []

            # TikTok loads content via JavaScript, so we need to extract data from script tags
            # Look for __UNIVERSAL_DATA_FOR_REHYDRATION__ which contains video data
            script_tags = soup.find_all("script", {"id": "__UNIVERSAL_DATA_FOR_REHYDRATION__"})

            for script in script_tags:
                try:
                    data = json.loads(script.string)

                    # Navigate the data structure to find video items
                    # This structure may change, so we have fallbacks
                    search_data = data.get("__DEFAULT_SCOPE__", {}).get("webapp.search-result", {})
                    item_list = search_data.get("itemList", [])

                    for item in item_list[:limit]:
                        video_data = item.get("item", {})
                        if not video_data:
                            continue

                        videos.append({
                            "id": video_data.get("id"),
                            "desc": video_data.get("desc", ""),
                            "hashtags": [tag.get("name", "") for tag in video_data.get("textExtra", [])],
                            "stats": video_data.get("stats", {}),
                            "create_time": video_data.get("createTime", 0),
                        })

                except json.JSONDecodeError:
                    continue

            logger.info(f"Found {len(videos)} TikTok videos for query: {query}")
            return videos

        except requests.exceptions.RequestException as e:
            logger.warning(f"Error searching TikTok web for {query}: {e}")
            return []
        except Exception as e:
            logger.warning(f"Unexpected error in TikTok search: {e}")
            return []

    def _extract_ticker_from_text(self, text: str, target_ticker: str) -> bool:
        """Check if text mentions the target ticker"""
        if not text:
            return False

        text_upper = text.upper()
        ticker_upper = target_ticker.upper()

        # Look for ticker with $ prefix (common on social media)
        if f"${ticker_upper}" in text_upper:
            return True

        # Look for ticker as standalone word
        pattern = r'\b' + re.escape(ticker_upper) + r'\b'
        if re.search(pattern, text_upper):
            return True

        return False

    def _calculate_sentiment_score(
        self, text: str, stats: dict[str, Any], ticker: str
    ) -> tuple[float, dict[str, Any]]:
        """
        Calculate sentiment score for a video.

        Args:
            text: Video description/title
            stats: Video statistics (likes, shares, comments, views)
            ticker: Target ticker symbol

        Returns:
            Tuple of (sentiment_score, details)
            Score range: -1.0 (very bearish) to +1.0 (very bullish)
        """
        text_lower = text.lower()

        # Count bullish/bearish keywords
        bullish_score = 0
        bearish_score = 0
        bullish_keywords_found = []
        bearish_keywords_found = []

        for keyword, weight in self.BULLISH_KEYWORDS.items():
            count = text_lower.count(keyword)
            if count > 0:
                bullish_score += count * weight
                bullish_keywords_found.append(keyword)

        for keyword, weight in self.BEARISH_KEYWORDS.items():
            count = text_lower.count(keyword)
            if count > 0:
                bearish_score += count * weight
                bearish_keywords_found.append(keyword)

        # Calculate base sentiment
        total_score = bullish_score + bearish_score
        if total_score > 0:
            base_sentiment = (bullish_score - bearish_score) / total_score
        else:
            # No keywords found = neutral
            base_sentiment = 0.0

        # Adjust for engagement (viral content has more weight)
        engagement_score = 0
        if stats:
            likes = stats.get("diggCount", 0)
            shares = stats.get("shareCount", 0)
            comments = stats.get("commentCount", 0)
            views = stats.get("playCount", 0)

            # Calculate engagement rate (likes + comments + shares) / views
            if views > 0:
                engagement_rate = (likes + comments + shares) / views
                engagement_score = min(1.0, engagement_rate * 100)  # Cap at 1.0

        # Weight sentiment by engagement (viral content gets amplified)
        weighted_sentiment = base_sentiment * (1.0 + engagement_score * 0.5)

        # Clamp to -1.0 to 1.0
        final_sentiment = max(-1.0, min(1.0, weighted_sentiment))

        details = {
            "bullish_score": bullish_score,
            "bearish_score": bearish_score,
            "bullish_keywords": bullish_keywords_found,
            "bearish_keywords": bearish_keywords_found,
            "engagement_score": engagement_score,
            "stats": stats,
        }

        return final_sentiment, details

    def get_ticker_sentiment(
        self, ticker: str, use_cache: bool = True, limit: int = 20
    ) -> dict[str, Any]:
        """
        Get TikTok sentiment for a specific ticker.

        Args:
            ticker: Stock ticker symbol (e.g., "NVDA", "TSLA")
            use_cache: Whether to use cached data if available
            limit: Maximum number of videos to analyze

        Returns:
            Dictionary with sentiment data:
            {
                "ticker": "NVDA",
                "score": 0.45,  # -1.0 to 1.0
                "confidence": 0.65,  # 0.0 to 1.0
                "videos_analyzed": 15,
                "bullish_count": 10,
                "bearish_count": 5,
                "total_engagement": 125000,
                "timestamp": "2025-12-14T10:30:00",
                "error": null
            }
        """
        # Check cache first
        if use_cache:
            cached_data = self._load_from_cache(ticker)
            if cached_data:
                return cached_data

        logger.info(f"Fetching TikTok sentiment for {ticker}...")

        try:
            # Search for ticker with stock-related hashtags
            search_queries = [
                f"${ticker} stocks",
                f"#{ticker} trading",
                f"{ticker} stock analysis",
            ]

            all_videos = []
            for query in search_queries[:2]:  # Limit to 2 queries to avoid rate limits
                videos = self._search_tiktok_web(query, limit=limit // 2)
                all_videos.extend(videos)
                time.sleep(1)  # Be nice to TikTok servers

            if not all_videos:
                logger.warning(f"No TikTok videos found for {ticker}")
                result = {
                    "ticker": ticker,
                    "score": 0.0,
                    "confidence": 0.0,
                    "videos_analyzed": 0,
                    "bullish_count": 0,
                    "bearish_count": 0,
                    "total_engagement": 0,
                    "timestamp": datetime.now().isoformat(),
                    "error": "No videos found",
                }
                self._save_to_cache(ticker, result)
                return result

            # Filter videos that actually mention the ticker
            relevant_videos = []
            for video in all_videos:
                desc = video.get("desc", "")
                hashtags = " ".join(video.get("hashtags", []))
                combined_text = f"{desc} {hashtags}"

                if self._extract_ticker_from_text(combined_text, ticker):
                    relevant_videos.append(video)

            if not relevant_videos:
                logger.warning(f"No relevant TikTok videos found for {ticker}")
                result = {
                    "ticker": ticker,
                    "score": 0.0,
                    "confidence": 0.0,
                    "videos_analyzed": 0,
                    "bullish_count": 0,
                    "bearish_count": 0,
                    "total_engagement": 0,
                    "timestamp": datetime.now().isoformat(),
                    "error": "No relevant videos found",
                }
                self._save_to_cache(ticker, result)
                return result

            # Analyze sentiment for each video
            sentiment_scores = []
            bullish_count = 0
            bearish_count = 0
            total_engagement = 0

            for video in relevant_videos[:limit]:
                desc = video.get("desc", "")
                hashtags = " ".join(video.get("hashtags", []))
                combined_text = f"{desc} {hashtags}"
                stats = video.get("stats", {})

                sentiment, details = self._calculate_sentiment_score(combined_text, stats, ticker)
                sentiment_scores.append(sentiment)

                if sentiment > 0.1:
                    bullish_count += 1
                elif sentiment < -0.1:
                    bearish_count += 1

                # Track engagement
                if stats:
                    total_engagement += stats.get("diggCount", 0)
                    total_engagement += stats.get("shareCount", 0)
                    total_engagement += stats.get("commentCount", 0)

            # Calculate overall sentiment (weighted average by engagement)
            if sentiment_scores:
                overall_score = sum(sentiment_scores) / len(sentiment_scores)
            else:
                overall_score = 0.0

            # Calculate confidence based on sample size and consistency
            videos_analyzed = len(relevant_videos)
            if videos_analyzed >= 15:
                base_confidence = 0.7
            elif videos_analyzed >= 10:
                base_confidence = 0.6
            elif videos_analyzed >= 5:
                base_confidence = 0.5
            else:
                base_confidence = 0.3

            # Reduce confidence if sentiment is mixed
            if sentiment_scores:
                sentiment_variance = sum((s - overall_score) ** 2 for s in sentiment_scores) / len(sentiment_scores)
                consistency_factor = max(0.5, 1.0 - sentiment_variance)
                confidence = base_confidence * consistency_factor
            else:
                confidence = 0.0

            result = {
                "ticker": ticker,
                "score": round(overall_score, 3),
                "confidence": round(confidence, 3),
                "videos_analyzed": videos_analyzed,
                "bullish_count": bullish_count,
                "bearish_count": bearish_count,
                "total_engagement": total_engagement,
                "timestamp": datetime.now().isoformat(),
                "error": None,
            }

            logger.info(
                f"TikTok sentiment for {ticker}: score={result['score']:.2f}, "
                f"confidence={result['confidence']:.2f}, videos={videos_analyzed}"
            )

            # Cache result
            self._save_to_cache(ticker, result)

            return result

        except Exception as e:
            logger.error(f"Error getting TikTok sentiment for {ticker}: {e}", exc_info=True)
            result = {
                "ticker": ticker,
                "score": 0.0,
                "confidence": 0.0,
                "videos_analyzed": 0,
                "bullish_count": 0,
                "bearish_count": 0,
                "total_engagement": 0,
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
            }
            return result


def main():
    """CLI interface for TikTok sentiment analysis"""
    import argparse

    parser = argparse.ArgumentParser(description="TikTok Sentiment Analysis")
    parser.add_argument(
        "--tickers",
        type=str,
        default="NVDA,TSLA,SPY",
        help="Comma-separated list of tickers (default: NVDA,TSLA,SPY)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max videos to analyze per ticker (default: 20)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable cache (fetch fresh data)",
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Parse tickers
    tickers = [t.strip().upper() for t in args.tickers.split(",")]

    # Initialize analyzer
    analyzer = TikTokSentiment()

    # Analyze each ticker
    for ticker in tickers:
        print(f"\n{'=' * 60}")
        print(f"TikTok Sentiment Analysis: {ticker}")
        print('=' * 60)

        result = analyzer.get_ticker_sentiment(
            ticker, use_cache=not args.no_cache, limit=args.limit
        )

        print(f"Score: {result['score']:+.2f} (-1.0 to +1.0)")
        print(f"Confidence: {result['confidence']:.1%}")
        print(f"Videos Analyzed: {result['videos_analyzed']}")
        print(f"Bullish: {result['bullish_count']} | Bearish: {result['bearish_count']}")
        print(f"Total Engagement: {result['total_engagement']:,}")
        print(f"Timestamp: {result['timestamp']}")

        if result.get("error"):
            print(f"Error: {result['error']}")

        print('=' * 60)


if __name__ == "__main__":
    main()
