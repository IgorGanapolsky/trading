"""Sentiment Scraper - Dynamic web scraping for trading sentiment analysis.

Uses Playwright MCP for full JavaScript rendering to scrape:
- Reddit (r/wallstreetbets, r/stocks, r/investing)
- YouTube (financial channels, video metadata, comments)
- Bogleheads (forum threads, investment discussions)

This provides more robust scraping than HTTP requests for JS-heavy sites.
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from urllib.parse import urlparse

from src.integrations.playwright_mcp.client import (
    AccessibilitySnapshot,
    PlaywrightMCPClient,
    get_playwright_client,
)

logger = logging.getLogger(__name__)


class SentimentSignal(Enum):
    """Sentiment signal classification."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class DataSource(Enum):
    """Supported data sources for scraping."""

    REDDIT = "reddit"
    YOUTUBE = "youtube"
    BOGLEHEADS = "bogleheads"


@dataclass
class MentionData:
    """Data about a ticker mention from a source."""

    ticker: str
    source: DataSource
    url: str
    title: str
    content: str
    sentiment: SentimentSignal
    confidence: float
    timestamp: datetime
    upvotes: int = 0
    comments: int = 0
    author: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class ScrapeResult:
    """Result of a scraping operation."""

    source: DataSource
    mentions: list[MentionData]
    total_posts_scanned: int
    scrape_time: datetime
    duration_seconds: float
    errors: list[str] = field(default_factory=list)


@dataclass
class AggregatedSentiment:
    """Aggregated sentiment for a ticker across sources."""

    ticker: str
    total_mentions: int
    bullish_count: int
    bearish_count: int
    neutral_count: int
    avg_confidence: float
    weighted_score: float  # -1 to 1
    sources: list[DataSource]
    top_mentions: list[MentionData]


class SentimentScraper:
    """Scrapes sentiment data from multiple web sources using Playwright MCP.

    Provides dynamic scraping with full JavaScript rendering for sites
    that don't work well with traditional HTTP requests.
    """

    # Sentiment keywords for basic classification
    BULLISH_KEYWORDS = [
        "buy",
        "bullish",
        "moon",
        "rocket",
        "long",
        "calls",
        "breakout",
        "undervalued",
        "accumulate",
        "green",
        "pump",
        "squeeze",
        "tendies",
        "gains",
        "lambo",
        "diamond hands",
        "hodl",
        "to the moon",
        "🚀",
        "💎",
        "🐂",
    ]

    BEARISH_KEYWORDS = [
        "sell",
        "bearish",
        "short",
        "puts",
        "crash",
        "overvalued",
        "dump",
        "red",
        "loss",
        "bagholder",
        "paper hands",
        "dead cat",
        "ponzi",
        "scam",
        "bankrupt",
        "recession",
        "🐻",
        "📉",
    ]

    # Reddit configuration
    REDDIT_SUBREDDITS = {
        "wallstreetbets": {"weight": 1.0, "category": "meme_stocks"},
        "stocks": {"weight": 0.8, "category": "general"},
        "investing": {"weight": 0.7, "category": "conservative"},
        "options": {"weight": 0.9, "category": "derivatives"},
        "stockmarket": {"weight": 0.6, "category": "general"},
    }

    # YouTube financial channels
    YOUTUBE_CHANNELS = {
        "meet_kevin": "UCUALwC8dChLpkWHl_JtGnMw",
        "graham_stephan": "UCV6KDgJskWaEckne5aPA0aQ",
        "andrei_jikh": "UCGy7SkBjcIAgTiwkXEtPnYg",
        "financial_education": "UCnMn36GT_H0X-w5_ckLtlgQ",
    }

    def __init__(
        self,
        client: PlaywrightMCPClient | None = None,
        max_posts_per_source: int = 50,
        scroll_depth: int = 3,
    ):
        """Initialize the sentiment scraper.

        Args:
            client: Playwright MCP client (creates new if None)
            max_posts_per_source: Maximum posts to scrape per source
            scroll_depth: Number of times to scroll for more content
        """
        self.client = client or get_playwright_client()
        self.max_posts_per_source = max_posts_per_source
        self.scroll_depth = scroll_depth
        self._ticker_pattern = re.compile(r"\$([A-Z]{1,5})\b|\b([A-Z]{2,5})\b")

    async def scrape_all(
        self,
        tickers: list[str],
        sources: list[DataSource] | None = None,
    ) -> dict[str, AggregatedSentiment]:
        """Scrape sentiment from all configured sources.

        Args:
            tickers: List of ticker symbols to search for
            sources: Sources to scrape (default: all)

        Returns:
            Dictionary of ticker -> AggregatedSentiment
        """
        sources = sources or list(DataSource)
        all_mentions: list[MentionData] = []

        # Initialize client
        if not self.client.is_initialized:
            await self.client.initialize()

        # Scrape each source
        tasks = []
        for source in sources:
            if source == DataSource.REDDIT:
                tasks.append(self.scrape_reddit(tickers))
            elif source == DataSource.YOUTUBE:
                tasks.append(self.scrape_youtube(tickers))
            elif source == DataSource.BOGLEHEADS:
                tasks.append(self.scrape_bogleheads(tickers))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect all mentions
        for result in results:
            if isinstance(result, ScrapeResult):
                all_mentions.extend(result.mentions)
            elif isinstance(result, Exception):
                logger.error("Scraping error: %s", result)

        # Aggregate by ticker
        return self._aggregate_sentiment(tickers, all_mentions)

    async def scrape_reddit(
        self,
        tickers: list[str],
        subreddits: list[str] | None = None,
    ) -> ScrapeResult:
        """Scrape Reddit for ticker mentions and sentiment.

        Args:
            tickers: Ticker symbols to search for
            subreddits: Subreddits to scrape (default: configured list)

        Returns:
            ScrapeResult with mentions found
        """
        start_time = datetime.now()
        mentions: list[MentionData] = []
        errors: list[str] = []
        total_posts = 0

        subreddits = subreddits or list(self.REDDIT_SUBREDDITS.keys())

        for subreddit in subreddits:
            try:
                url = f"https://old.reddit.com/r/{subreddit}/hot/"
                snapshot = await self.client.navigate(url)

                if not snapshot:
                    errors.append(f"Failed to load r/{subreddit}")
                    continue

                # Scroll to load more content
                for _ in range(self.scroll_depth):
                    await self.client.scroll("down", 1000)
                    await asyncio.sleep(0.5)

                # Get updated snapshot after scrolling
                snapshot = await self.client.get_snapshot()
                if not snapshot:
                    continue

                # Extract posts
                posts = self._extract_reddit_posts(snapshot, subreddit)
                total_posts += len(posts)

                # Filter for ticker mentions
                for post in posts[: self.max_posts_per_source]:
                    mentioned_tickers = self._find_tickers(
                        post["title"] + " " + post.get("selftext", ""),
                        tickers,
                    )

                    for ticker in mentioned_tickers:
                        sentiment, confidence = self._analyze_sentiment(
                            post["title"] + " " + post.get("selftext", "")
                        )

                        mentions.append(
                            MentionData(
                                ticker=ticker,
                                source=DataSource.REDDIT,
                                url=post.get("url", f"https://reddit.com/r/{subreddit}"),
                                title=post["title"],
                                content=post.get("selftext", "")[:500],
                                sentiment=sentiment,
                                confidence=confidence,
                                timestamp=datetime.now(),
                                upvotes=post.get("score", 0),
                                comments=post.get("num_comments", 0),
                                author=post.get("author", ""),
                                metadata={
                                    "subreddit": subreddit,
                                    "weight": self.REDDIT_SUBREDDITS.get(subreddit, {}).get(
                                        "weight", 0.5
                                    ),
                                },
                            )
                        )

            except Exception as e:
                errors.append(f"Error scraping r/{subreddit}: {e}")
                logger.error("Reddit scraping error for r/%s: %s", subreddit, e)

        duration = (datetime.now() - start_time).total_seconds()

        return ScrapeResult(
            source=DataSource.REDDIT,
            mentions=mentions,
            total_posts_scanned=total_posts,
            scrape_time=start_time,
            duration_seconds=duration,
            errors=errors,
        )

    async def scrape_youtube(
        self,
        tickers: list[str],
        search_query: str | None = None,
    ) -> ScrapeResult:
        """Scrape YouTube for financial video mentions.

        Args:
            tickers: Ticker symbols to search for
            search_query: Custom search query (default: ticker-based)

        Returns:
            ScrapeResult with mentions found
        """
        start_time = datetime.now()
        mentions: list[MentionData] = []
        errors: list[str] = []
        total_videos = 0

        # Search for each ticker
        for ticker in tickers:
            try:
                query = search_query or f"{ticker} stock analysis"
                url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"

                snapshot = await self.client.navigate(url)
                if not snapshot:
                    errors.append(f"Failed to load YouTube search for {ticker}")
                    continue

                # Wait for video results to load
                await asyncio.sleep(2)

                # Scroll for more results
                for _ in range(self.scroll_depth):
                    await self.client.scroll("down", 800)
                    await asyncio.sleep(0.5)

                snapshot = await self.client.get_snapshot()
                if not snapshot:
                    continue

                # Extract video data
                videos = self._extract_youtube_videos(snapshot)
                total_videos += len(videos)

                for video in videos[: self.max_posts_per_source // len(tickers)]:
                    # Check if video mentions the ticker
                    text = video.get("title", "") + " " + video.get("description", "")
                    if not self._ticker_mentioned(ticker, text):
                        continue

                    sentiment, confidence = self._analyze_sentiment(text)

                    mentions.append(
                        MentionData(
                            ticker=ticker,
                            source=DataSource.YOUTUBE,
                            url=video.get("url", ""),
                            title=video.get("title", ""),
                            content=video.get("description", "")[:500],
                            sentiment=sentiment,
                            confidence=confidence,
                            timestamp=datetime.now(),
                            upvotes=video.get("views", 0),
                            comments=0,
                            author=video.get("channel", ""),
                            metadata={
                                "duration": video.get("duration", ""),
                                "published": video.get("published", ""),
                            },
                        )
                    )

            except Exception as e:
                errors.append(f"Error scraping YouTube for {ticker}: {e}")
                logger.error("YouTube scraping error for %s: %s", ticker, e)

        duration = (datetime.now() - start_time).total_seconds()

        return ScrapeResult(
            source=DataSource.YOUTUBE,
            mentions=mentions,
            total_posts_scanned=total_videos,
            scrape_time=start_time,
            duration_seconds=duration,
            errors=errors,
        )

    async def scrape_bogleheads(
        self,
        tickers: list[str],
        forum_ids: list[str] | None = None,
    ) -> ScrapeResult:
        """Scrape Bogleheads forum for investment discussions.

        Args:
            tickers: Ticker symbols to search for
            forum_ids: Forum IDs to scrape (default: main investing forum)

        Returns:
            ScrapeResult with mentions found
        """
        start_time = datetime.now()
        mentions: list[MentionData] = []
        errors: list[str] = []
        total_posts = 0

        # Default to main investing forum and help with personal investments
        forum_urls = [
            "https://www.bogleheads.org/forum/viewforum.php?f=1",  # Investing
            "https://www.bogleheads.org/forum/viewforum.php?f=2",  # Help
        ]

        for url in forum_urls:
            try:
                snapshot = await self.client.navigate(url)
                if not snapshot:
                    errors.append(f"Failed to load Bogleheads forum: {url}")
                    continue

                # Scroll to load more threads
                for _ in range(self.scroll_depth):
                    await self.client.scroll("down", 600)
                    await asyncio.sleep(0.5)

                snapshot = await self.client.get_snapshot()
                if not snapshot:
                    continue

                # Extract forum threads
                threads = self._extract_bogleheads_threads(snapshot)
                total_posts += len(threads)

                for thread in threads[: self.max_posts_per_source]:
                    mentioned_tickers = self._find_tickers(
                        thread.get("title", ""),
                        tickers,
                    )

                    for ticker in mentioned_tickers:
                        sentiment, confidence = self._analyze_sentiment(thread.get("title", ""))

                        mentions.append(
                            MentionData(
                                ticker=ticker,
                                source=DataSource.BOGLEHEADS,
                                url=thread.get("url", url),
                                title=thread.get("title", ""),
                                content="",  # Would need to navigate to thread
                                sentiment=sentiment,
                                confidence=confidence,
                                timestamp=datetime.now(),
                                upvotes=0,
                                comments=thread.get("replies", 0),
                                author=thread.get("author", ""),
                                metadata={
                                    "forum": "bogleheads",
                                    "views": thread.get("views", 0),
                                },
                            )
                        )

            except Exception as e:
                errors.append(f"Error scraping Bogleheads: {e}")
                logger.error("Bogleheads scraping error: %s", e)

        duration = (datetime.now() - start_time).total_seconds()

        return ScrapeResult(
            source=DataSource.BOGLEHEADS,
            mentions=mentions,
            total_posts_scanned=total_posts,
            scrape_time=start_time,
            duration_seconds=duration,
            errors=errors,
        )

    def _extract_reddit_posts(
        self,
        snapshot: AccessibilitySnapshot,
        subreddit: str,
    ) -> list[dict]:
        """Extract post data from Reddit accessibility snapshot."""
        posts = []

        # Find post elements (old.reddit.com structure)
        post_elements = snapshot.find_elements(role="article")
        if not post_elements:
            # Try alternative selectors
            post_elements = snapshot.find_elements(role="listitem")

        for element in post_elements:
            try:
                post = {
                    "title": "",
                    "selftext": "",
                    "score": 0,
                    "num_comments": 0,
                    "author": "",
                    "url": f"https://reddit.com/r/{subreddit}",
                }

                # Extract title from heading
                headings: list[dict] = []
                self._find_by_role(element, "heading", headings)
                if headings:
                    post["title"] = headings[0].get("name", "")

                # Extract link
                links: list[dict] = []
                self._find_by_role(element, "link", links)
                for link in links:
                    href = link.get("href", "")

                    # Security fix: Verify domain matches reddit.com to prevent open redirects/phishing
                    is_safe_domain = False
                    if href.startswith("/"):
                        is_safe_domain = True
                    else:
                        try:
                            parsed = urlparse(href)
                            # Ensure scheme is http or https
                            if parsed.scheme not in ("http", "https"):
                                is_safe_domain = False
                            else:
                                domain = parsed.netloc.lower()
                                # Prepare domain for strict validation (remove valid port if present)
                                if ":" in domain:
                                    domain = domain.split(":")[0]

                                # Strict allowlist for reddit domains
                                is_safe_domain = (
                                    domain == "reddit.com"
                                    or domain == "www.reddit.com"
                                    or domain == "old.reddit.com"
                                )
                        except Exception:
                            is_safe_domain = False

                    if is_safe_domain and ("comments" in href or "reddit.com" in href):
                        post["url"] = href
                        break

                # Extract score/votes
                score_text = element.get("name", "")
                score_match = re.search(r"(\d+)\s*(?:points?|upvotes?)", score_text)
                if score_match:
                    post["score"] = int(score_match.group(1))

                if post["title"]:
                    posts.append(post)

            except Exception as e:
                logger.debug("Error extracting Reddit post: %s", e)

        return posts

    def _extract_youtube_videos(self, snapshot: AccessibilitySnapshot) -> list[dict]:
        """Extract video data from YouTube search results."""
        videos = []

        # Find video renderers
        video_elements = snapshot.find_elements(role="link")

        for element in video_elements:
            try:
                name = element.get("name", "")
                # Filter for actual video links
                if not name or len(name) < 10:
                    continue

                # Extract video ID from various link patterns
                href = element.get("href", "")
                if "/watch?v=" in href or "youtu.be/" in href:
                    video = {
                        "title": name,
                        "url": href if href.startswith("http") else f"https://youtube.com{href}",
                        "description": "",
                        "channel": "",
                        "views": 0,
                        "duration": "",
                    }

                    # Try to extract view count
                    views_match = re.search(
                        r"([\d,.]+[KMB]?)\s*views?",
                        name,
                        re.IGNORECASE,
                    )
                    if views_match:
                        video["views"] = self._parse_count(views_match.group(1))

                    videos.append(video)

            except Exception as e:
                logger.debug("Error extracting YouTube video: %s", e)

        return videos

    def _extract_bogleheads_threads(
        self,
        snapshot: AccessibilitySnapshot,
    ) -> list[dict]:
        """Extract thread data from Bogleheads forum."""
        threads = []

        # Find topic links
        link_elements = snapshot.find_elements(role="link")

        for element in link_elements:
            try:
                name = element.get("name", "")
                href = element.get("href", "")

                # Filter for topic links
                if "viewtopic.php" in href and name:
                    thread = {
                        "title": name,
                        "url": href
                        if href.startswith("http")
                        else f"https://www.bogleheads.org{href}",
                        "author": "",
                        "replies": 0,
                        "views": 0,
                    }
                    threads.append(thread)

            except Exception as e:
                logger.debug("Error extracting Bogleheads thread: %s", e)

        return threads

    def _find_by_role(self, node: dict, role: str, results: list) -> None:
        """Find all descendants with a specific role."""
        if node.get("role") == role:
            results.append(node)
        for child in node.get("children", []):
            self._find_by_role(child, role, results)

    def _find_tickers(self, text: str, target_tickers: list[str]) -> list[str]:
        """Find mentioned tickers in text."""
        text_upper = text.upper()
        found = []

        for ticker in target_tickers:
            ticker_upper = ticker.upper()
            # Check for $TICKER pattern or standalone ticker
            if f"${ticker_upper}" in text_upper or f" {ticker_upper} " in f" {text_upper} ":
                found.append(ticker_upper)

        return found

    def _ticker_mentioned(self, ticker: str, text: str) -> bool:
        """Check if a ticker is mentioned in text."""
        return bool(self._find_tickers(text, [ticker]))

    def _analyze_sentiment(self, text: str) -> tuple[SentimentSignal, float]:
        """Analyze sentiment of text using keyword matching.

        Args:
            text: Text to analyze

        Returns:
            Tuple of (SentimentSignal, confidence)
        """
        text_lower = text.lower()

        bullish_count = sum(1 for keyword in self.BULLISH_KEYWORDS if keyword.lower() in text_lower)
        bearish_count = sum(1 for keyword in self.BEARISH_KEYWORDS if keyword.lower() in text_lower)

        total = bullish_count + bearish_count
        if total == 0:
            return SentimentSignal.NEUTRAL, 0.5

        bullish_ratio = bullish_count / total
        bearish_ratio = bearish_count / total

        confidence = max(bullish_ratio, bearish_ratio)

        if bullish_ratio > 0.6:
            return SentimentSignal.BULLISH, confidence
        elif bearish_ratio > 0.6:
            return SentimentSignal.BEARISH, confidence
        else:
            return SentimentSignal.NEUTRAL, confidence

    def _parse_count(self, count_str: str) -> int:
        """Parse view/like counts like '1.2K', '3M'."""
        count_str = count_str.replace(",", "").strip()

        multipliers = {"K": 1000, "M": 1000000, "B": 1000000000}

        for suffix, mult in multipliers.items():
            if count_str.upper().endswith(suffix):
                try:
                    return int(float(count_str[:-1]) * mult)
                except ValueError:
                    return 0

        try:
            return int(float(count_str))
        except ValueError:
            return 0

    def _aggregate_sentiment(
        self,
        tickers: list[str],
        mentions: list[MentionData],
    ) -> dict[str, AggregatedSentiment]:
        """Aggregate mentions into per-ticker sentiment."""
        results = {}

        for ticker in tickers:
            ticker_mentions = [m for m in mentions if m.ticker.upper() == ticker.upper()]

            if not ticker_mentions:
                results[ticker] = AggregatedSentiment(
                    ticker=ticker,
                    total_mentions=0,
                    bullish_count=0,
                    bearish_count=0,
                    neutral_count=0,
                    avg_confidence=0.0,
                    weighted_score=0.0,
                    sources=[],
                    top_mentions=[],
                )
                continue

            bullish = [m for m in ticker_mentions if m.sentiment == SentimentSignal.BULLISH]
            bearish = [m for m in ticker_mentions if m.sentiment == SentimentSignal.BEARISH]
            neutral = [m for m in ticker_mentions if m.sentiment == SentimentSignal.NEUTRAL]

            avg_confidence = sum(m.confidence for m in ticker_mentions) / len(ticker_mentions)

            # Calculate weighted score (-1 to 1)
            total = len(ticker_mentions)
            weighted_score = (len(bullish) - len(bearish)) / total if total > 0 else 0

            # Get unique sources
            sources = list({m.source for m in ticker_mentions})

            # Get top mentions by engagement (upvotes + comments)
            sorted_mentions = sorted(
                ticker_mentions,
                key=lambda m: m.upvotes + m.comments * 2,
                reverse=True,
            )

            results[ticker] = AggregatedSentiment(
                ticker=ticker,
                total_mentions=len(ticker_mentions),
                bullish_count=len(bullish),
                bearish_count=len(bearish),
                neutral_count=len(neutral),
                avg_confidence=avg_confidence,
                weighted_score=weighted_score,
                sources=sources,
                top_mentions=sorted_mentions[:5],
            )

        return results


# Convenience function for quick scraping
async def scrape_sentiment(
    tickers: list[str],
    sources: list[DataSource] | None = None,
) -> dict[str, AggregatedSentiment]:
    """Convenience function to scrape sentiment for tickers.

    Args:
        tickers: List of ticker symbols
        sources: Sources to scrape (default: all)

    Returns:
        Dictionary of ticker -> AggregatedSentiment
    """
    scraper = SentimentScraper()
    return await scraper.scrape_all(tickers, sources)
