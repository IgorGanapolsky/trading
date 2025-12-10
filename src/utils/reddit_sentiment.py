"""
Reddit Sentiment Scraper for Trading System

Collects daily sentiment from key investing subreddits to gauge retail investor
sentiment and detect meme stock activity. Runs BEFORE market open (9:35 AM ET).

Features:
- Monitors r/wallstreetbets, r/stocks, r/investing, r/options
- Extracts ticker mentions and sentiment indicators
- Scores sentiment using weighted algorithm
- Caches results for 24 hours
- FREE tier: 100 requests/minute (no API key needed for read-only)

Usage:
    # Command line
    python reddit_sentiment.py --subreddits wallstreetbets,stocks --limit 25

    # Programmatic
    from reddit_sentiment import RedditSentiment
    scraper = RedditSentiment()
    data = scraper.collect_daily_sentiment()
"""

import argparse
import json
import logging
import os
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import praw
from praw.exceptions import PRAWException
from src.utils.retry_decorator import retry_with_backoff

logger = logging.getLogger(__name__)


class RedditSentiment:
    """
    Scrapes and analyzes sentiment from investing subreddits.

    Attributes:
        reddit: PRAW Reddit instance
        data_dir: Directory for saving sentiment data
        cache_hours: Hours to cache results
    """

    # Subreddits to monitor
    SUBREDDITS = [
        "wallstreetbets",  # Meme stocks, YOLO plays, loss/gain porn
        "stocks",  # General market discussion
        "investing",  # Long-term investment talk
        "options",  # Derivatives sentiment
    ]

    # Bullish keywords and their weights
    BULLISH_KEYWORDS = {
        # Strong bullish
        "moon": 3,
        "rocket": 3,
        "calls": 2,
        "buy": 2,
        "long": 2,
        "bullish": 2,
        "gains": 2,
        "profit": 2,
        "up": 1,
        "green": 1,
        "bull": 2,
        "rally": 2,
        "surge": 2,
        "breakout": 2,
        # Moderate bullish
        "hold": 1,
        "hodl": 1,
        "diamond hands": 3,
        "to the moon": 3,
        "tendies": 2,
        "yolo": 2,
        "ath": 1,
        "bounce": 1,
    }

    # Bearish keywords and their weights
    BEARISH_KEYWORDS = {
        # Strong bearish
        "dump": -3,
        "crash": -3,
        "puts": -2,
        "sell": -2,
        "short": -2,
        "bearish": -2,
        "loss": -2,
        "down": -1,
        "red": -1,
        "bear": -2,
        "tank": -3,
        "plunge": -3,
        "collapse": -3,
        # Moderate bearish
        "drop": -2,
        "fall": -2,
        "bag holder": -3,
        "rip": -1,
        "rug pull": -3,
        "dead cat bounce": -2,
    }

    # Ticker pattern (e.g., $SPY, NVDA, GOOGL)
    TICKER_PATTERN = re.compile(r"\$?([A-Z]{1,5})(?:\b|$)")

    # Common false positives to exclude
    EXCLUDED_TICKERS = {
        "CEO",
        "CFO",
        "CTO",
        "DD",
        "ER",
        "IPO",
        "ETF",
        "IMO",
        "YOLO",
        "RIP",
        "ATH",
        "USA",
        "SEC",
        "IRS",
        "FBI",
        "CIA",
        "FDA",
        "NEWS",
        "EDIT",
        "LINK",
        "POST",
        "FOMO",
        "ATM",
        "GDP",
        "CPI",
        "I",
        "A",
        "AM",
        "PM",
        "IT",
        "IS",
        "OR",
        "AND",
        "THE",
        "FOR",
        "API",
        "AI",
        "ML",
        "RL",
        "WSB",
        "TLDR",
        "TL",
        "DR",
    }

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        user_agent: str | None = None,
        data_dir: str = "data/sentiment",
        cache_hours: int = 24,
    ):
        """
        Initialize Reddit sentiment scraper.

        Args:
            client_id: Reddit API client ID (optional - can use read-only mode)
            client_secret: Reddit API client secret (optional)
            user_agent: Reddit API user agent (optional)
            data_dir: Directory to save sentiment data
            cache_hours: Hours to cache results (default: 24)
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_hours = cache_hours

        # Initialize Reddit API
        # For read-only access, we need to create a Reddit app at:
        # https://www.reddit.com/prefs/apps
        # Click "create app" -> select "script" -> fill in details
        # This gives us client_id and client_secret for read-only access

        try:
            # Check environment variables first
            if not client_id:
                client_id = os.getenv("REDDIT_CLIENT_ID")
            if not client_secret:
                client_secret = os.getenv("REDDIT_CLIENT_SECRET")
            if not user_agent:
                user_agent = os.getenv("REDDIT_USER_AGENT", "TradingBot/1.0 by AutomatedTrader")

            if client_id and client_secret:
                self.reddit = praw.Reddit(
                    client_id=client_id,
                    client_secret=client_secret,
                    user_agent=user_agent,
                )
                logger.info("Initialized Reddit API with credentials")
            else:
                # Use dummy credentials for demonstration
                # In production, you MUST provide real credentials
                logger.warning("No Reddit API credentials provided!")
                logger.warning("To use this scraper, create a Reddit app at:")
                logger.warning("https://www.reddit.com/prefs/apps")
                logger.warning("Then set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in .env")

                # This will fail but provides clear error message
                raise ValueError(
                    "Reddit API credentials required. "
                    "Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in .env file. "
                    "Create app at: https://www.reddit.com/prefs/apps"
                )

        except Exception as e:
            logger.error(f"Failed to initialize Reddit API: {e}")
            raise

    @retry_with_backoff(max_retries=3, initial_delay=2.0)
    def scrape_subreddit(
        self, subreddit_name: str, limit: int = 25, time_filter: str = "day"
    ) -> list[dict]:
        """
        Scrape posts from a subreddit.

        Args:
            subreddit_name: Name of subreddit (without r/)
            limit: Number of posts to fetch (default: 25)
            time_filter: Time filter - 'day', 'week', 'month' (default: 'day')

        Returns:
            List of post dictionaries with metadata
        """
        logger.info(f"Scraping r/{subreddit_name} (limit={limit}, filter={time_filter})")

        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            posts = []

            # Get hot posts
            for post in subreddit.hot(limit=limit):
                # Skip if older than time filter
                post_age_hours = (
                    datetime.utcnow() - datetime.utcfromtimestamp(post.created_utc)
                ).total_seconds() / 3600

                if (
                    time_filter == "day"
                    and post_age_hours > 24
                    or time_filter == "week"
                    and post_age_hours > 168
                ):
                    continue

                posts.append(
                    {
                        "id": post.id,
                        "title": post.title,
                        "text": post.selftext,
                        "author": str(post.author),
                        "created_utc": post.created_utc,
                        "score": post.score,
                        "upvote_ratio": post.upvote_ratio,
                        "num_comments": post.num_comments,
                        "flair": post.link_flair_text or "",
                        "url": post.url,
                        "permalink": f"https://reddit.com{post.permalink}",
                    }
                )

            logger.info(f"Scraped {len(posts)} posts from r/{subreddit_name}")
            return posts

        except PRAWException as e:
            logger.error(f"Error scraping r/{subreddit_name}: {e}")
            raise

    def extract_tickers(self, text: str) -> list[str]:
        """
        Extract stock tickers from text.

        Args:
            text: Text to search for tickers

        Returns:
            List of unique ticker symbols
        """
        # Find all potential tickers
        matches = self.TICKER_PATTERN.findall(text.upper())

        # Filter out false positives
        tickers = [
            ticker
            for ticker in matches
            if ticker not in self.EXCLUDED_TICKERS and len(ticker) >= 1 and len(ticker) <= 5
        ]

        # Return unique tickers
        return list(set(tickers))

    def calculate_sentiment_score(
        self, text: str, upvotes: int = 0, comments: int = 0
    ) -> tuple[int, dict[str, int]]:
        """
        Calculate sentiment score for text.

        Algorithm:
        - Bullish keywords: +1 to +3 points
        - Bearish keywords: -1 to -3 points
        - Weight by upvotes (high upvotes = higher impact)
        - Weight by comments (high engagement = more reliable)

        Args:
            text: Text to analyze
            upvotes: Number of upvotes
            comments: Number of comments

        Returns:
            Tuple of (total_score, keyword_counts)
        """
        text_lower = text.lower()

        # Count keyword occurrences
        bullish_count = 0
        bearish_count = 0
        keyword_details = {"bullish": 0, "bearish": 0}

        # Check bullish keywords
        for keyword, weight in self.BULLISH_KEYWORDS.items():
            if keyword in text_lower:
                count = text_lower.count(keyword)
                bullish_count += count * weight
                keyword_details["bullish"] += count

        # Check bearish keywords
        for keyword, weight in self.BEARISH_KEYWORDS.items():
            if keyword in text_lower:
                count = text_lower.count(keyword)
                bearish_count += count * abs(weight)
                keyword_details["bearish"] += count

        # Base sentiment score
        base_score = bullish_count + bearish_count

        # Weight by engagement (logarithmic scaling to prevent outliers)
        import math

        upvote_weight = math.log(max(upvotes, 1) + 1)
        comment_weight = math.log(max(comments, 1) + 1)

        # Combined weight (average of upvotes and comments)
        engagement_weight = (upvote_weight + comment_weight) / 2

        # Final weighted score
        weighted_score = int(base_score * engagement_weight)

        return weighted_score, keyword_details

    def analyze_posts(self, posts: list[dict]) -> dict[str, dict]:
        """
        Analyze posts and aggregate sentiment by ticker.

        Args:
            posts: List of post dictionaries

        Returns:
            Dictionary mapping tickers to sentiment data
        """
        ticker_data = defaultdict(
            lambda: {
                "mentions": 0,
                "total_score": 0,
                "bullish_keywords": 0,
                "bearish_keywords": 0,
                "total_upvotes": 0,
                "total_comments": 0,
                "posts": [],
            }
        )

        for post in posts:
            # Combine title and text for analysis
            full_text = f"{post['title']} {post['text']}"

            # Extract tickers
            tickers = self.extract_tickers(full_text)

            # Calculate sentiment
            sentiment_score, keyword_counts = self.calculate_sentiment_score(
                full_text, upvotes=post["score"], comments=post["num_comments"]
            )

            # Update ticker data
            for ticker in tickers:
                ticker_data[ticker]["mentions"] += 1
                ticker_data[ticker]["total_score"] += sentiment_score
                ticker_data[ticker]["bullish_keywords"] += keyword_counts["bullish"]
                ticker_data[ticker]["bearish_keywords"] += keyword_counts["bearish"]
                ticker_data[ticker]["total_upvotes"] += post["score"]
                ticker_data[ticker]["total_comments"] += post["num_comments"]
                ticker_data[ticker]["posts"].append(
                    {
                        "title": post["title"],
                        "score": post["score"],
                        "comments": post["num_comments"],
                        "flair": post["flair"],
                        "permalink": post["permalink"],
                        "sentiment_score": sentiment_score,
                    }
                )

        # Calculate confidence levels
        for ticker, data in ticker_data.items():
            # Confidence based on mentions and engagement
            if data["mentions"] >= 10 and data["total_upvotes"] >= 100:
                confidence = "high"
            elif data["mentions"] >= 5 and data["total_upvotes"] >= 50:
                confidence = "medium"
            else:
                confidence = "low"

            data["confidence"] = confidence

        return dict(ticker_data)

    def collect_daily_sentiment(
        self,
        subreddits: list[str] | None = None,
        limit_per_sub: int = 25,
        force_refresh: bool = False,
    ) -> dict:
        """
        Collect daily sentiment from all subreddits.

        Args:
            subreddits: List of subreddit names (default: self.SUBREDDITS)
            limit_per_sub: Posts to fetch per subreddit (default: 25)
            force_refresh: Ignore cache and fetch fresh data (default: False)

        Returns:
            Dictionary with sentiment data
        """
        today = datetime.now().strftime("%Y-%m-%d")
        cache_file = self.data_dir / f"reddit_{today}.json"

        # Check cache
        if not force_refresh and cache_file.exists():
            cache_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
            if cache_age.total_seconds() < self.cache_hours * 3600:
                logger.info(f"Loading cached sentiment data from {cache_file}")
                with open(cache_file) as f:
                    return json.load(f)

        # Use default subreddits if none provided
        subreddits = subreddits or self.SUBREDDITS

        logger.info(f"Collecting sentiment from {len(subreddits)} subreddits")

        # Collect posts from all subreddits
        all_posts = []
        subreddit_stats = {}

        for subreddit_name in subreddits:
            try:
                posts = self.scrape_subreddit(
                    subreddit_name, limit=limit_per_sub, time_filter="day"
                )
                all_posts.extend(posts)
                subreddit_stats[subreddit_name] = {
                    "posts_collected": len(posts),
                    "status": "success",
                }
            except Exception as e:
                logger.error(f"Failed to scrape r/{subreddit_name}: {e}")
                subreddit_stats[subreddit_name] = {
                    "posts_collected": 0,
                    "status": "failed",
                    "error": str(e),
                }

        # Analyze posts
        ticker_sentiment = self.analyze_posts(all_posts)

        # Sort tickers by total score (descending)
        sorted_tickers = sorted(
            ticker_sentiment.items(), key=lambda x: x[1]["total_score"], reverse=True
        )

        # Build output
        output = {
            "meta": {
                "date": today,
                "timestamp": datetime.now().isoformat(),
                "subreddits": subreddits,
                "total_posts": len(all_posts),
                "total_tickers": len(ticker_sentiment),
                "subreddit_stats": subreddit_stats,
            },
            "sentiment_by_ticker": {
                ticker: {
                    "score": data["total_score"],
                    "mentions": data["mentions"],
                    "confidence": data["confidence"],
                    "bullish_keywords": data["bullish_keywords"],
                    "bearish_keywords": data["bearish_keywords"],
                    "total_upvotes": data["total_upvotes"],
                    "total_comments": data["total_comments"],
                    "avg_score_per_mention": (
                        round(data["total_score"] / data["mentions"], 2)
                        if data["mentions"] > 0
                        else 0
                    ),
                    "top_posts": sorted(
                        data["posts"], key=lambda x: x["sentiment_score"], reverse=True
                    )[:3],
                }
                for ticker, data in sorted_tickers
            },
        }

        # Save to file
        with open(cache_file, "w") as f:
            json.dump(output, f, indent=2)

        logger.info(f"Saved sentiment data to {cache_file}")
        logger.info(f"Analyzed {len(all_posts)} posts, found {len(ticker_sentiment)} tickers")

        return output

    def get_top_tickers(
        self,
        sentiment_data: dict | None = None,
        min_mentions: int = 5,
        min_confidence: str = "medium",
        limit: int = 10,
    ) -> list[tuple[str, dict]]:
        """
        Get top tickers by sentiment score.

        Args:
            sentiment_data: Sentiment data (default: load from today's cache)
            min_mentions: Minimum mentions to include (default: 5)
            min_confidence: Minimum confidence level (default: 'medium')
            limit: Maximum tickers to return (default: 10)

        Returns:
            List of (ticker, data) tuples sorted by score
        """
        # Load from cache if not provided
        if sentiment_data is None:
            today = datetime.now().strftime("%Y-%m-%d")
            cache_file = self.data_dir / f"reddit_{today}.json"

            if cache_file.exists():
                with open(cache_file) as f:
                    sentiment_data = json.load(f)
            else:
                logger.warning("No cached sentiment data found")
                return []

        # Filter and sort
        confidence_levels = {"low": 0, "medium": 1, "high": 2}
        min_conf_level = confidence_levels.get(min_confidence, 1)

        filtered = [
            (ticker, data)
            for ticker, data in sentiment_data["sentiment_by_ticker"].items()
            if data["mentions"] >= min_mentions
            and confidence_levels.get(data["confidence"], 0) >= min_conf_level
        ]

        # Sort by score
        sorted_tickers = sorted(filtered, key=lambda x: x[1]["score"], reverse=True)

        return sorted_tickers[:limit]


def get_reddit_sentiment(
    subreddits: list[str] | None = None,
    limit_per_sub: int = 25,
    force_refresh: bool = False,
) -> dict:
    """
    Lightweight helper to fetch sentiment data with graceful degradation.
    """
    try:
        scraper = RedditSentiment()
        return scraper.collect_daily_sentiment(
            subreddits=subreddits,
            limit_per_sub=limit_per_sub,
            force_refresh=force_refresh,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Reddit sentiment unavailable: %s", exc)
        return {
            "sentiment_by_ticker": {},
            "error": str(exc),
            "subreddits": subreddits or RedditSentiment.SUBREDDITS,
        }


def main():
    """CLI interface for Reddit sentiment scraping."""
    parser = argparse.ArgumentParser(description="Scrape Reddit sentiment for trading system")
    parser.add_argument(
        "--subreddits",
        type=str,
        default="wallstreetbets,stocks,investing,options",
        help="Comma-separated list of subreddits (default: wallstreetbets,stocks,investing,options)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Posts to fetch per subreddit (default: 25)",
    )
    parser.add_argument(
        "--force-refresh", action="store_true", help="Ignore cache and fetch fresh data"
    )
    parser.add_argument("--top", type=int, default=10, help="Show top N tickers (default: 10)")
    parser.add_argument(
        "--min-mentions",
        type=int,
        default=5,
        help="Minimum mentions to include in top tickers (default: 5)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path (default: data/sentiment/reddit_YYYY-MM-DD.json)",
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Initialize scraper
    scraper = RedditSentiment()

    # Parse subreddits
    subreddits = [s.strip() for s in args.subreddits.split(",")]

    # Collect sentiment
    logger.info("Starting Reddit sentiment collection...")
    sentiment_data = scraper.collect_daily_sentiment(
        subreddits=subreddits,
        limit_per_sub=args.limit,
        force_refresh=args.force_refresh,
    )

    # Print summary
    print("\n" + "=" * 80)
    print("REDDIT SENTIMENT ANALYSIS")
    print("=" * 80)
    print(f"Date: {sentiment_data['meta']['date']}")
    print(f"Subreddits: {', '.join(['r/' + s for s in subreddits])}")
    print(f"Total Posts: {sentiment_data['meta']['total_posts']}")
    print(f"Total Tickers: {sentiment_data['meta']['total_tickers']}")

    # Print top tickers
    print(f"\nTop {args.top} Tickers by Sentiment Score:")
    print("-" * 80)

    top_tickers = scraper.get_top_tickers(
        sentiment_data=sentiment_data, min_mentions=args.min_mentions, limit=args.top
    )

    for i, (ticker, data) in enumerate(top_tickers, 1):
        sentiment = (
            "BULLISH" if data["score"] > 0 else "BEARISH" if data["score"] < 0 else "NEUTRAL"
        )
        print(
            f"{i}. {ticker:<6} | Score: {data['score']:>6} | Mentions: {data['mentions']:>3} | "
            f"Confidence: {data['confidence'].upper():<6} | {sentiment}"
        )
        print(
            f"   Bullish Keywords: {data['bullish_keywords']}, "
            f"Bearish Keywords: {data['bearish_keywords']}"
        )
        print(f"   Engagement: {data['total_upvotes']} upvotes, {data['total_comments']} comments")

        if data["top_posts"]:
            print(f"   Top Post: {data['top_posts'][0]['title'][:60]}...")
        print()

    # Print subreddit stats
    print("\nSubreddit Statistics:")
    print("-" * 80)
    for sub, stats in sentiment_data["meta"]["subreddit_stats"].items():
        status_icon = "✓" if stats["status"] == "success" else "✗"
        print(
            f"{status_icon} r/{sub:<20} | Posts: {stats['posts_collected']:>3} | Status: {stats['status']}"
        )

    print("\n" + "=" * 80)
    print(f"Data saved to: {scraper.data_dir}/reddit_{sentiment_data['meta']['date']}.json")
    print("=" * 80)


if __name__ == "__main__":
    main()
