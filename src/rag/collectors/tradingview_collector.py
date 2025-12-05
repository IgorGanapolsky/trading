"""
TradingView Ideas Collector for RAG System

Collects trading ideas, technical analysis, and signals from TradingView.
Uses public RSS feeds and web scraping for community insights.
"""

from __future__ import annotations
import logging
import re
from datetime import datetime
from typing import Any

import feedparser
import requests
from bs4 import BeautifulSoup

from src.rag.collectors.base_collector import BaseNewsCollector

logger = logging.getLogger(__name__)


class TradingViewCollector(BaseNewsCollector):
    """
    Collector for TradingView trading ideas and signals.

    Collects:
    - Community trading ideas (long/short calls)
    - Technical analysis from popular authors
    - Chart patterns and setups
    - Price targets and stop losses
    """

    BASE_URL = "https://www.tradingview.com"
    IDEAS_URL = "https://www.tradingview.com/symbols/{symbol}/ideas/"
    RSS_FEED_URL = "https://www.tradingview.com/feed/?sort=popular"

    # Popular symbol-specific RSS feeds
    SYMBOL_FEEDS = {
        "SPY": "https://www.tradingview.com/symbols/AMEX-SPY/ideas/rss",
        "QQQ": "https://www.tradingview.com/symbols/NASDAQ-QQQ/ideas/rss",
        "NVDA": "https://www.tradingview.com/symbols/NASDAQ-NVDA/ideas/rss",
        "AAPL": "https://www.tradingview.com/symbols/NASDAQ-AAPL/ideas/rss",
        "GOOGL": "https://www.tradingview.com/symbols/NASDAQ-GOOGL/ideas/rss",
        "AMZN": "https://www.tradingview.com/symbols/NASDAQ-AMZN/ideas/rss",
        "MSFT": "https://www.tradingview.com/symbols/NASDAQ-MSFT/ideas/rss",
        "TSLA": "https://www.tradingview.com/symbols/NASDAQ-TSLA/ideas/rss",
    }

    def __init__(self):
        super().__init__(source_name="tradingview")
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    def collect_ticker_news(self, ticker: str, days_back: int = 7) -> list[dict[str, Any]]:
        """
        Collect TradingView ideas for a specific ticker.

        Args:
            ticker: Stock symbol (e.g., "NVDA")
            days_back: Not directly used (TradingView shows recent ideas)

        Returns:
            List of trading ideas and analysis
        """
        results = []

        # Try RSS feed first (cleaner data)
        if ticker.upper() in self.SYMBOL_FEEDS:
            rss_data = self._collect_from_rss(ticker)
            results.extend(rss_data)

        # Scrape ideas page for additional data
        web_data = self._scrape_ideas_page(ticker)
        results.extend(web_data)

        logger.info(f"Collected {len(results)} TradingView ideas for {ticker}")
        return results

    def collect_market_news(self, days_back: int = 1) -> list[dict[str, Any]]:
        """
        Collect popular market-wide trading ideas.

        Returns:
            List of trending trading ideas across all markets
        """
        results = []

        try:
            # Parse popular ideas RSS feed
            feed = feedparser.parse(self.RSS_FEED_URL)

            for entry in feed.entries[:20]:  # Top 20 popular ideas
                # Extract ticker from title or link
                ticker = self._extract_ticker(entry.title, entry.link)

                # Analyze idea direction
                direction, sentiment = self._analyze_idea_direction(
                    entry.title, entry.get("summary", "")
                )

                idea = self.normalize_article(
                    title=entry.title,
                    content=entry.get("summary", entry.title),
                    url=entry.link,
                    published_date=entry.get("published", datetime.now().isoformat()),
                    ticker=ticker,
                    sentiment=sentiment,
                )
                idea["author"] = entry.get("author", "unknown")
                idea["direction"] = direction
                idea["signal_type"] = "trading_idea"
                idea["popularity"] = "high"  # From popular feed

                results.append(idea)

        except Exception as e:
            logger.error(f"Error collecting TradingView market ideas: {e}")

        logger.info(f"Collected {len(results)} market-wide TradingView ideas")
        return results

    def _collect_from_rss(self, ticker: str) -> list[dict[str, Any]]:
        """
        Collect ideas from ticker-specific RSS feed.

        Args:
            ticker: Stock symbol

        Returns:
            List of trading ideas
        """
        results = []
        feed_url = self.SYMBOL_FEEDS.get(ticker.upper())

        if not feed_url:
            return []

        try:
            feed = feedparser.parse(feed_url)

            for entry in feed.entries[:15]:  # Top 15 ideas
                direction, sentiment = self._analyze_idea_direction(
                    entry.title, entry.get("summary", "")
                )

                idea = self.normalize_article(
                    title=entry.title,
                    content=entry.get("summary", entry.title),
                    url=entry.link,
                    published_date=entry.get("published", datetime.now().isoformat()),
                    ticker=ticker,
                    sentiment=sentiment,
                )
                idea["author"] = entry.get("author", "unknown")
                idea["direction"] = direction
                idea["signal_type"] = "trading_idea"
                idea["source_type"] = "rss"

                results.append(idea)

        except Exception as e:
            logger.error(f"Error collecting TradingView RSS for {ticker}: {e}")

        return results

    def _scrape_ideas_page(self, ticker: str) -> list[dict[str, Any]]:
        """
        Scrape trading ideas from TradingView ideas page.

        Args:
            ticker: Stock symbol

        Returns:
            List of trading ideas
        """
        results = []
        url = self.IDEAS_URL.format(symbol=ticker.upper())

        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            if response.status_code != 200:
                logger.warning(f"TradingView ideas page fetch failed for {ticker}")
                return []

            soup = BeautifulSoup(response.text, "html.parser")

            # Find idea cards
            idea_cards = soup.find_all("div", class_=re.compile(r"idea-card|tv-widget-idea"))

            for card in idea_cards[:10]:  # Top 10 ideas
                try:
                    # Extract title
                    title_elem = card.find(["h2", "h3", "a"], class_=re.compile(r"title|heading"))
                    title = title_elem.text.strip() if title_elem else "Trading Idea"

                    # Extract link
                    link_elem = card.find("a", href=True)
                    idea_url = link_elem["href"] if link_elem else url
                    if not idea_url.startswith("http"):
                        idea_url = self.BASE_URL + idea_url

                    # Extract author
                    author_elem = card.find(class_=re.compile(r"author|username"))
                    author = author_elem.text.strip() if author_elem else "unknown"

                    # Extract description/summary
                    desc_elem = card.find(class_=re.compile(r"description|summary|body"))
                    description = desc_elem.text.strip()[:500] if desc_elem else title

                    # Analyze direction and sentiment
                    direction, sentiment = self._analyze_idea_direction(title, description)

                    # Look for explicit long/short badges
                    badge = card.find(class_=re.compile(r"badge|label|type"))
                    if badge:
                        badge_text = badge.text.strip().lower()
                        if "long" in badge_text:
                            direction = "LONG"
                            sentiment = 0.75
                        elif "short" in badge_text:
                            direction = "SHORT"
                            sentiment = 0.25

                    idea = self.normalize_article(
                        title=title,
                        content=description,
                        url=idea_url,
                        published_date=datetime.now().isoformat(),
                        ticker=ticker,
                        sentiment=sentiment,
                    )
                    idea["author"] = author
                    idea["direction"] = direction
                    idea["signal_type"] = "trading_idea"
                    idea["source_type"] = "web"

                    results.append(idea)

                except Exception:
                    continue

        except Exception as e:
            logger.error(f"Error scraping TradingView ideas for {ticker}: {e}")

        return results

    def _analyze_idea_direction(self, title: str, content: str) -> tuple[str, float]:
        """
        Analyze trading idea to determine direction and sentiment.

        Args:
            title: Idea title
            content: Idea description

        Returns:
            Tuple of (direction, sentiment_score)
        """
        text = (title + " " + content).lower()

        # Bullish indicators
        bullish_keywords = [
            "long",
            "buy",
            "bullish",
            "upside",
            "breakout",
            "support",
            "bounce",
            "rally",
            "accumulate",
            "targets",
            "moon",
            "going up",
            "bottom",
            "reversal up",
            "higher",
            "ascending",
        ]

        # Bearish indicators
        bearish_keywords = [
            "short",
            "sell",
            "bearish",
            "downside",
            "breakdown",
            "resistance",
            "dump",
            "crash",
            "distribute",
            "top",
            "reversal down",
            "lower",
            "descending",
            "head and shoulders",
            "double top",
        ]

        bullish_count = sum(1 for kw in bullish_keywords if kw in text)
        bearish_count = sum(1 for kw in bearish_keywords if kw in text)

        if bullish_count > bearish_count:
            direction = "LONG"
            sentiment = 0.6 + min(0.3, bullish_count * 0.05)
        elif bearish_count > bullish_count:
            direction = "SHORT"
            sentiment = 0.4 - min(0.3, bearish_count * 0.05)
        else:
            direction = "NEUTRAL"
            sentiment = 0.5

        return direction, sentiment

    def _extract_ticker(self, title: str, link: str) -> str:
        """
        Extract ticker symbol from idea title or link.

        Args:
            title: Idea title
            link: Idea URL

        Returns:
            Ticker symbol or "MARKET"
        """
        # Try to extract from URL (e.g., /symbols/NASDAQ-AAPL/)
        match = re.search(r"/symbols/[\w-]+[-:](\w+)/", link)
        if match:
            return match.group(1).upper()

        # Try to extract ticker pattern from title
        match = re.search(r"\b([A-Z]{2,5})\b", title)
        if match:
            potential_ticker = match.group(1)
            # Filter out common words
            if potential_ticker not in ["THE", "AND", "FOR", "WITH", "THIS"]:
                return potential_ticker

        return "MARKET"

    def collect_daily_snapshot(self, tickers: list[str] | None = None) -> list[dict[str, Any]]:
        """
        Collect daily TradingView snapshot.

        Args:
            tickers: Optional list of tickers to focus on

        Returns:
            Combined trading ideas
        """
        results = []

        # Popular market-wide ideas
        market_ideas = self.collect_market_news()
        results.extend(market_ideas)

        # Ticker-specific ideas
        if tickers:
            for ticker in tickers:
                ticker_ideas = self.collect_ticker_news(ticker)
                results.extend(ticker_ideas)

        logger.info(f"Daily TradingView snapshot: {len(results)} ideas")
        return results
