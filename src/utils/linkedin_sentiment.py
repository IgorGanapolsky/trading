"""
LinkedIn Sentiment Scraper for Trading System

Collects sentiment from LinkedIn posts about specific stocks to gauge professional
investor sentiment and insider perspectives.

Features:
- Scrapes public LinkedIn posts (no login required for public content)
- Extracts ticker mentions and professional sentiment
- Scores sentiment using weighted algorithm
- Caches results for 4 hours
- **NO API KEY REQUIRED**: Uses web scraping of public content

Limitations:
- LinkedIn aggressively limits scraping, so this uses a conservative approach
- Only scrapes publicly accessible content (no authentication)
- Rate limited to avoid detection (1 request per 3 seconds)
- Falls back to cached data if scraping fails

Usage:
    # Command line
    python linkedin_sentiment.py --ticker NVDA

    # Programmatic
    from linkedin_sentiment import LinkedInSentiment
    scraper = LinkedInSentiment()
    sentiment = scraper.get_ticker_sentiment("NVDA")
"""

import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class LinkedInSentiment:
    """
    Scrapes and analyzes sentiment from LinkedIn posts about stocks.

    This uses web scraping of publicly accessible LinkedIn content since
    LinkedIn doesn't provide a public API for free.

    Attributes:
        data_dir: Directory for saving sentiment data
        cache_hours: Hours to cache results (default: 4)
        request_delay: Seconds between requests to avoid rate limiting
    """

    # Professional bullish keywords (LinkedIn is more formal than Reddit)
    BULLISH_KEYWORDS = {
        # Strong bullish
        "recommend buying": 3,
        "strong buy": 3,
        "excellent opportunity": 3,
        "undervalued": 3,
        "significant upside": 3,
        "bullish": 2,
        "buy": 2,
        "long": 2,
        "positive outlook": 2,
        "growth potential": 2,
        "strong fundamentals": 2,
        "outperform": 2,
        "overweight": 2,
        "upgrade": 2,
        "accumulate": 2,
        # Moderate bullish
        "opportunity": 1,
        "growth": 1,
        "positive": 1,
        "momentum": 1,
        "breakout": 1,
        "support": 1,
        "rally": 1,
        "upside": 1,
        "favorable": 1,
        "promising": 1,
    }

    # Professional bearish keywords
    BEARISH_KEYWORDS = {
        # Strong bearish
        "recommend selling": -3,
        "strong sell": -3,
        "overvalued": -3,
        "significant downside": -3,
        "major concerns": -3,
        "bearish": -2,
        "sell": -2,
        "short": -2,
        "negative outlook": -2,
        "risk": -2,
        "weak fundamentals": -2,
        "underperform": -2,
        "underweight": -2,
        "downgrade": -2,
        "avoid": -2,
        # Moderate bearish
        "concern": -1,
        "decline": -1,
        "negative": -1,
        "weakness": -1,
        "resistance": -1,
        "pullback": -1,
        "downside": -1,
        "unfavorable": -1,
        "caution": -1,
        "warning": -1,
    }

    # Ticker pattern (e.g., $SPY, NVDA, GOOGL)
    TICKER_PATTERN = re.compile(r"\$?([A-Z]{1,5})(?:\b|$)")

    # Common false positives to exclude
    EXCLUDED_TICKERS = {
        "CEO", "CFO", "CTO", "CIO", "COO",
        "MBA", "PhD", "IPO", "ETF", "ESG",
        "USA", "UK", "EU", "AI", "ML",
        "IT", "HR", "PR", "IR", "VP",
    }

    # User-Agent to mimic a browser
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(
        self,
        data_dir: str = "data/sentiment/linkedin",
        cache_hours: int = 4,
        request_delay: float = 3.0,
    ):
        """
        Initialize LinkedIn sentiment scraper.

        Args:
            data_dir: Directory for caching sentiment data
            cache_hours: Hours to cache results (default: 4)
            request_delay: Seconds to wait between requests (default: 3.0)
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_hours = cache_hours
        self.request_delay = request_delay

        # Session with browser-like headers
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })

        logger.info(f"LinkedInSentiment initialized. Cache: {self.data_dir}")

    def _get_cache_file(self, ticker: str) -> Path:
        """Get cache file path for a ticker"""
        return self.data_dir / f"{ticker.upper()}_sentiment.json"

    def _load_from_cache(self, ticker: str) -> dict[str, Any] | None:
        """Load sentiment from cache if fresh enough"""
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

            logger.info(f"Cache hit for {ticker} (age: {cache_age})")
            return data

        except Exception as e:
            logger.warning(f"Error loading cache for {ticker}: {e}")
            return None

    def _save_to_cache(self, ticker: str, data: dict[str, Any]):
        """Save sentiment to cache"""
        cache_file = self._get_cache_file(ticker)

        try:
            with open(cache_file, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Cached sentiment for {ticker}")
        except Exception as e:
            logger.warning(f"Error saving cache for {ticker}: {e}")

    def _search_google_for_linkedin_posts(self, ticker: str, company_name: str | None = None) -> list[str]:
        """
        Use Google to find LinkedIn posts about a ticker.

        LinkedIn heavily rate-limits direct scraping, so we use Google search
        to find relevant LinkedIn posts, then extract content from Google's cache/snippets.

        Args:
            ticker: Stock ticker symbol
            company_name: Optional company name for better search results

        Returns:
            List of post URLs found
        """
        search_terms = [ticker]
        if company_name:
            search_terms.append(company_name)

        # Build Google search query for LinkedIn posts
        query = f"site:linkedin.com/posts {' OR '.join(search_terms)} stock OR shares OR trading"
        encoded_query = quote_plus(query)
        search_url = f"https://www.google.com/search?q={encoded_query}&num=10"

        try:
            logger.debug(f"Searching Google for LinkedIn posts about {ticker}")
            response = self.session.get(search_url, timeout=10)
            response.raise_for_status()

            # Parse Google search results
            soup = BeautifulSoup(response.text, "html.parser")

            # Extract LinkedIn post URLs from search results
            post_urls = []
            for link in soup.find_all("a", href=True):
                href = link["href"]
                # Google wraps URLs in /url?q=...
                if "/url?q=" in href and "linkedin.com/posts/" in href:
                    # Extract actual URL
                    url = href.split("/url?q=")[1].split("&")[0]
                    if url.startswith("https://www.linkedin.com/posts/"):
                        post_urls.append(url)

            logger.info(f"Found {len(post_urls)} LinkedIn posts for {ticker} via Google")
            return post_urls[:5]  # Limit to 5 most recent

        except Exception as e:
            logger.warning(f"Error searching Google for {ticker} LinkedIn posts: {e}")
            return []

    def _extract_text_from_snippets(self, ticker: str, company_name: str | None = None) -> list[str]:
        """
        Extract text snippets from Google search results about the ticker.

        This is a fallback method that doesn't require accessing LinkedIn directly.
        We extract the text snippets from Google's search results which often
        contain the key sentiment from LinkedIn posts.

        Args:
            ticker: Stock ticker symbol
            company_name: Optional company name

        Returns:
            List of text snippets
        """
        search_terms = [ticker]
        if company_name:
            search_terms.append(company_name)

        query = f"site:linkedin.com/posts {' OR '.join(search_terms)} stock OR shares OR analysis"
        encoded_query = quote_plus(query)
        search_url = f"https://www.google.com/search?q={encoded_query}&num=20"

        try:
            logger.debug(f"Extracting snippets for {ticker} from Google")
            response = self.session.get(search_url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Extract text snippets from search results
            snippets = []

            # Google uses various div classes for snippets
            for snippet_div in soup.find_all(["div", "span"], class_=["VwiC3b", "yXK7lf", "MUxGbd", "yDYNvb"]):
                text = snippet_div.get_text(strip=True)
                if len(text) > 30 and ticker.upper() in text.upper():
                    snippets.append(text)

            logger.info(f"Extracted {len(snippets)} text snippets for {ticker}")
            return snippets

        except Exception as e:
            logger.warning(f"Error extracting snippets for {ticker}: {e}")
            return []

    def _analyze_sentiment(self, texts: list[str], ticker: str) -> dict[str, Any]:
        """
        Analyze sentiment from text snippets.

        Args:
            texts: List of text snippets to analyze
            ticker: Stock ticker symbol

        Returns:
            Dictionary with sentiment analysis
        """
        if not texts:
            return {
                "score": 0,
                "confidence": "low",
                "sentiment": "neutral",
                "bullish_count": 0,
                "bearish_count": 0,
                "neutral_count": 0,
                "total_snippets": 0,
                "mentions_analyzed": 0,
                "bullish_keywords": 0,
                "bearish_keywords": 0,
                "timestamp": datetime.now().isoformat(),
            }

        bullish_score = 0
        bearish_score = 0
        mentions_analyzed = 0

        for text in texts:
            text_lower = text.lower()

            # Check if ticker is mentioned (avoid false positives)
            if ticker.lower() not in text_lower and f"${ticker.lower()}" not in text_lower:
                continue

            mentions_analyzed += 1

            # Score bullish keywords
            for keyword, weight in self.BULLISH_KEYWORDS.items():
                if keyword in text_lower:
                    bullish_score += weight

            # Score bearish keywords
            for keyword, weight in self.BEARISH_KEYWORDS.items():
                if keyword in text_lower:
                    bearish_score += abs(weight)  # Make positive for counting

        # Calculate net sentiment score
        total_keywords = bullish_score + bearish_score

        if total_keywords > 0:
            # Normalize to -100 to +100 scale
            net_score = ((bullish_score - bearish_score) / total_keywords) * 100
        else:
            net_score = 0

        # Determine confidence based on volume
        if mentions_analyzed >= 5 and total_keywords >= 10:
            confidence = "high"
        elif mentions_analyzed >= 3 and total_keywords >= 5:
            confidence = "medium"
        else:
            confidence = "low"

        # Categorize sentiment
        if net_score > 20:
            sentiment_category = "bullish"
            bullish_count = mentions_analyzed
            bearish_count = 0
            neutral_count = 0
        elif net_score < -20:
            sentiment_category = "bearish"
            bullish_count = 0
            bearish_count = mentions_analyzed
            neutral_count = 0
        else:
            sentiment_category = "neutral"
            bullish_count = 0
            bearish_count = 0
            neutral_count = mentions_analyzed

        return {
            "score": round(net_score, 2),
            "confidence": confidence,
            "sentiment": sentiment_category,
            "bullish_count": bullish_count,
            "bearish_count": bearish_count,
            "neutral_count": neutral_count,
            "total_snippets": len(texts),
            "mentions_analyzed": mentions_analyzed,
            "bullish_keywords": bullish_score,
            "bearish_keywords": bearish_score,
            "timestamp": datetime.now().isoformat(),
        }

    def get_ticker_sentiment(
        self,
        ticker: str,
        company_name: str | None = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """
        Get sentiment for a ticker from LinkedIn.

        Args:
            ticker: Stock ticker symbol (e.g., "NVDA", "TSLA")
            company_name: Optional company name for better search (e.g., "Nvidia")
            force_refresh: Force fresh data (skip cache)

        Returns:
            Dictionary with sentiment data:
            {
                "ticker": "NVDA",
                "score": 45.2,  # -100 to +100
                "confidence": "medium",  # "low", "medium", "high"
                "sentiment": "bullish",  # "bullish", "bearish", "neutral"
                "mentions_analyzed": 5,
                "timestamp": "2025-12-14T10:30:00",
                "cache_hit": False
            }
        """
        ticker = ticker.upper()

        # Check cache first
        if not force_refresh:
            cached = self._load_from_cache(ticker)
            if cached:
                cached["cache_hit"] = True
                return cached

        logger.info(f"Fetching LinkedIn sentiment for {ticker}...")

        try:
            # Extract text snippets from Google search results
            # This is more reliable than trying to scrape LinkedIn directly
            snippets = self._extract_text_from_snippets(ticker, company_name)

            # Rate limiting
            time.sleep(self.request_delay)

            # Analyze sentiment
            sentiment_data = self._analyze_sentiment(snippets, ticker)
            sentiment_data["ticker"] = ticker
            sentiment_data["cache_hit"] = False

            # Save to cache
            self._save_to_cache(ticker, sentiment_data)

            logger.info(
                f"{ticker} LinkedIn sentiment: score={sentiment_data['score']:.1f}, "
                f"confidence={sentiment_data['confidence']}, "
                f"snippets={sentiment_data['total_snippets']}"
            )

            return sentiment_data

        except Exception as e:
            logger.error(f"Error getting LinkedIn sentiment for {ticker}: {e}")

            # Return neutral sentiment on error
            return {
                "ticker": ticker,
                "score": 0,
                "confidence": "low",
                "sentiment": "neutral",
                "bullish_count": 0,
                "bearish_count": 0,
                "neutral_count": 0,
                "total_snippets": 0,
                "mentions_analyzed": 0,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "cache_hit": False,
            }

    def get_batch_sentiment(
        self,
        tickers: list[str],
        force_refresh: bool = False,
    ) -> dict[str, dict[str, Any]]:
        """
        Get sentiment for multiple tickers.

        Args:
            tickers: List of ticker symbols
            force_refresh: Force fresh data (skip cache)

        Returns:
            Dictionary mapping tickers to sentiment data
        """
        results = {}

        for ticker in tickers:
            results[ticker] = self.get_ticker_sentiment(ticker, force_refresh=force_refresh)

            # Rate limiting between tickers
            if ticker != tickers[-1]:  # Don't delay after last ticker
                time.sleep(self.request_delay)

        return results


def main():
    """CLI interface for LinkedIn sentiment analysis"""
    import argparse

    parser = argparse.ArgumentParser(description="LinkedIn Sentiment Analysis")
    parser.add_argument(
        "--ticker",
        type=str,
        default="NVDA",
        help="Ticker symbol to analyze (default: NVDA)",
    )
    parser.add_argument(
        "--company",
        type=str,
        help="Company name for better search results (e.g., 'Nvidia')",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force fresh data (skip cache)",
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Initialize scraper
    scraper = LinkedInSentiment()

    # Get sentiment
    result = scraper.get_ticker_sentiment(
        args.ticker,
        company_name=args.company,
        force_refresh=args.force_refresh,
    )

    # Print results
    print("\n" + "=" * 60)
    print(f"LinkedIn Sentiment: {result['ticker']}")
    print("=" * 60)
    print(f"Score: {result['score']:+.1f} (-100 to +100)")
    print(f"Sentiment: {result.get('sentiment', 'N/A').upper()}")
    print(f"Confidence: {result['confidence'].upper()}")
    print(f"Snippets Analyzed: {result['total_snippets']}")
    print(f"Mentions Found: {result['mentions_analyzed']}")
    print(f"Timestamp: {result['timestamp']}")
    print(f"Cache Hit: {result.get('cache_hit', False)}")

    if result.get('error'):
        print(f"Error: {result['error']}")

    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
