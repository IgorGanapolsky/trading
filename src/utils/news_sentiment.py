"""
Financial News Sentiment Aggregator

Aggregates sentiment from multiple sources:
- Yahoo Finance (via yfinance)
- Stocktwits API
- Alpha Vantage News Sentiment API

Combines professional analyst sentiment and social trading sentiment
for pre-market analysis.
"""

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

# Optional imports - make dependencies optional
try:
    from src.utils import yfinance_wrapper as yf

    YFINANCE_AVAILABLE = True
except ImportError:
    yf = None
    YFINANCE_AVAILABLE = False

try:
    from alpha_vantage.timeseries import TimeSeries

    ALPHA_VANTAGE_AVAILABLE = True
except ImportError:
    TimeSeries = None
    ALPHA_VANTAGE_AVAILABLE = False

try:
    from bs4 import BeautifulSoup

    BEAUTIFULSOUP_AVAILABLE = True
except ImportError:
    BeautifulSoup = None
    BEAUTIFULSOUP_AVAILABLE = False

from .retry_decorator import retry_with_backoff

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class TickerSentiment:
    """Sentiment data for a single ticker."""

    ticker: str
    score: float  # -100 to +100
    confidence: str  # low, medium, high
    sources: dict[str, dict]
    timestamp: str


@dataclass
class SentimentReport:
    """Aggregated sentiment report."""

    meta: dict
    sentiment_by_ticker: dict[str, TickerSentiment]


class NewsSentimentAggregator:
    """Aggregates financial news sentiment from multiple sources."""

    # API Configuration
    STOCKTWITS_BASE_URL = "https://api.stocktwits.com/api/2"
    ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"

    # Sentiment weights (must sum to 1.0)
    ALPHA_VANTAGE_WEIGHT = 0.30  # Reduced from 0.40
    STOCKTWITS_WEIGHT = 0.25  # Reduced from 0.30
    YAHOO_WEIGHT = 0.25  # Reduced from 0.30
    GROK_TWITTER_WEIGHT = 0.20  # NEW: Real-time Twitter/X sentiment

    def __init__(
        self,
        alpha_vantage_key: str | None = None,
        grok_api_key: str | None = None,
        output_dir: str = "data/sentiment",
    ):
        """
        Initialize the sentiment aggregator.

        Args:
            alpha_vantage_key: Alpha Vantage API key (optional, reads from env)
            grok_api_key: Grok/X.ai API key for Twitter sentiment (optional, reads from env)
            output_dir: Directory to save sentiment reports
        """
        self.alpha_vantage_key = alpha_vantage_key or os.getenv("ALPHA_VANTAGE_API_KEY")
        self.grok_api_key = grok_api_key or os.getenv("GROK_API_KEY")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize Alpha Vantage client if key available
        self.av_client = None
        if self.alpha_vantage_key and ALPHA_VANTAGE_AVAILABLE:
            try:
                self.av_client = TimeSeries(key=self.alpha_vantage_key, output_format="json")
                logger.info("Alpha Vantage client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Alpha Vantage: {e}")
        elif not ALPHA_VANTAGE_AVAILABLE:
            logger.info("Alpha Vantage library not installed - using free sources only")
        else:
            logger.info("No Alpha Vantage API key - using free sources only")

        # Initialize Grok client for Twitter/X sentiment if key available
        self.grok_client = None
        if self.grok_api_key:
            try:
                from openai import OpenAI

                self.grok_client = OpenAI(api_key=self.grok_api_key, base_url="https://api.x.ai/v1")
                logger.info("Grok/X.ai API client initialized for Twitter sentiment")
            except Exception as e:
                logger.warning(f"Failed to initialize Grok client: {e}")
        else:
            logger.debug("No Grok API key found - Twitter sentiment will be skipped")

        logger.info(f"NewsSentimentAggregator initialized: {self.output_dir}")

    def _scrape_yahoo_news(self, ticker: str) -> list[dict]:
        """
        Scrape Yahoo Finance news as fallback when yfinance is unavailable.

        Args:
            ticker: Stock ticker symbol

        Returns:
            List of news articles with titles
        """
        if not BEAUTIFULSOUP_AVAILABLE:
            logger.warning("BeautifulSoup not available - cannot scrape news")
            return []

        try:
            url = f"https://finance.yahoo.com/quote/{ticker}/news"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

            # Disable proxy if it's causing issues
            proxies = {"http": None, "https": None}

            response = requests.get(url, headers=headers, timeout=10, proxies=proxies)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")

            # Find news articles - Yahoo Finance uses various div structures
            news_items = []

            # Try multiple selectors (Yahoo's HTML structure changes frequently)
            selectors = [
                "h3",  # Common headline tag
                "[data-test-locator='mega']",  # Yahoo's test locator
                ".js-stream-content h3",  # Stream content
            ]

            for selector in selectors:
                elements = soup.select(selector)
                if elements:
                    for elem in elements[:20]:  # Limit to 20 articles
                        text = elem.get_text(strip=True)
                        if text and len(text) > 10:  # Filter out junk
                            news_items.append({"title": text})
                    if news_items:
                        break

            logger.info(f"Scraped {len(news_items)} news items for {ticker}")
            return news_items

        except requests.exceptions.ProxyError as e:
            logger.warning(f"Proxy error scraping Yahoo news for {ticker}: {e}")
            return []
        except requests.exceptions.RequestException as e:
            logger.warning(f"Network error scraping Yahoo news for {ticker}: {e}")
            return []
        except Exception as e:
            logger.warning(f"Failed to scrape Yahoo news for {ticker}: {e}")
            return []

    @retry_with_backoff(max_retries=3, initial_delay=1.0)
    def get_yahoo_sentiment(self, ticker: str) -> dict:
        """
        Get news sentiment from Yahoo Finance.
        Uses yfinance API if available, falls back to web scraping.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dict with score, articles count, and details
        """
        news = []

        # Try yfinance API first
        if YFINANCE_AVAILABLE:
            try:
                stock = yf.Ticker(ticker)

                # Try to get news - handle potential API changes
                try:
                    news = stock.news
                except (AttributeError, TypeError):
                    # Fallback: try alternative method
                    try:
                        news = stock.get_news()
                    except Exception:
                        logger.info(f"yfinance API unavailable for {ticker}, trying web scraping")
                        news = []
            except Exception as e:
                logger.warning(f"yfinance failed for {ticker}: {e}, trying web scraping")
                news = []

        # Fallback to web scraping if yfinance didn't work
        if not news:
            news = self._scrape_yahoo_news(ticker)

        if not news or len(news) == 0:
            logger.warning(f"No Yahoo news found for {ticker}")
            return {"score": 0, "articles": 0, "confidence": "low", "method": "none"}

        try:
            # Simple keyword-based sentiment analysis
            bullish_keywords = [
                "surge",
                "rally",
                "gain",
                "bull",
                "upgrade",
                "beat",
                "strong",
                "growth",
                "positive",
                "profit",
                "rise",
                "outperform",
                "buy",
                "soar",
                "jump",
            ]
            bearish_keywords = [
                "drop",
                "fall",
                "bear",
                "downgrade",
                "miss",
                "weak",
                "decline",
                "negative",
                "loss",
                "crash",
                "underperform",
                "sell",
                "plunge",
                "tumble",
            ]

            sentiment_score = 0
            articles_analyzed = 0

            for article in news[:20]:  # Analyze up to 20 recent articles
                title = article.get("title", "").lower()

                # Count keyword matches
                bullish_count = sum(1 for kw in bullish_keywords if kw in title)
                bearish_count = sum(1 for kw in bearish_keywords if kw in title)

                # Calculate article sentiment (-1 to +1)
                if bullish_count > bearish_count:
                    sentiment_score += 1
                elif bearish_count > bullish_count:
                    sentiment_score -= 1

                articles_analyzed += 1

            # Normalize to -100 to +100 scale
            if articles_analyzed > 0:
                normalized_score = (sentiment_score / articles_analyzed) * 100
            else:
                normalized_score = 0

            confidence = (
                "high" if articles_analyzed >= 10 else "medium" if articles_analyzed >= 5 else "low"
            )

            method = "yfinance" if YFINANCE_AVAILABLE and news else "scraping"

            return {
                "score": round(normalized_score, 2),
                "articles": articles_analyzed,
                "confidence": confidence,
                "raw_sentiment": sentiment_score,
                "method": method,
            }

        except Exception as e:
            logger.error(f"Error analyzing Yahoo sentiment for {ticker}: {e}")
            return {"score": 0, "articles": 0, "confidence": "low", "error": str(e)}

    @retry_with_backoff(max_retries=3, initial_delay=1.0)
    def get_stocktwits_sentiment(self, ticker: str) -> dict:
        """
        Get sentiment from Stocktwits social trading platform.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dict with score, messages count, and details
        """
        try:
            url = f"{self.STOCKTWITS_BASE_URL}/streams/symbol/{ticker}.json"
            # Disable proxy if it's causing issues
            proxies = {"http": None, "https": None}
            response = requests.get(url, timeout=10, proxies=proxies)
            response.raise_for_status()

            data = response.json()
            messages = data.get("messages", [])

            if not messages:
                logger.warning(f"No Stocktwits messages found for {ticker}")
                return {"score": 0, "messages": 0, "confidence": "low"}

            # Aggregate sentiment from messages
            bullish_count = 0
            bearish_count = 0
            neutral_count = 0

            for msg in messages:
                entities = msg.get("entities", {})
                sentiment = entities.get("sentiment")

                if sentiment:
                    if sentiment.get("basic") == "Bullish":
                        bullish_count += 1
                    elif sentiment.get("basic") == "Bearish":
                        bearish_count += 1
                    else:
                        neutral_count += 1

            total_with_sentiment = bullish_count + bearish_count + neutral_count

            if total_with_sentiment == 0:
                return {"score": 0, "messages": len(messages), "confidence": "low"}

            # Calculate sentiment score (-100 to +100)
            sentiment_score = ((bullish_count - bearish_count) / total_with_sentiment) * 100

            confidence = (
                "high"
                if total_with_sentiment >= 20
                else "medium"
                if total_with_sentiment >= 10
                else "low"
            )

            return {
                "score": round(sentiment_score, 2),
                "messages": len(messages),
                "bullish": bullish_count,
                "bearish": bearish_count,
                "neutral": neutral_count,
                "confidence": confidence,
            }

        except requests.exceptions.ProxyError:
            logger.warning(f"Proxy error getting Stocktwits sentiment for {ticker}")
            return {
                "score": 0,
                "messages": 0,
                "confidence": "low",
                "error": "proxy_error",
            }
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"Ticker {ticker} not found on Stocktwits")
                return {
                    "score": 0,
                    "messages": 0,
                    "confidence": "low",
                    "error": "not_found",
                }
            else:
                logger.error(f"HTTP error getting Stocktwits sentiment for {ticker}: {e}")
                return {"score": 0, "messages": 0, "confidence": "low", "error": str(e)}
        except requests.exceptions.RequestException:
            logger.warning(f"Network error getting Stocktwits sentiment for {ticker}")
            return {
                "score": 0,
                "messages": 0,
                "confidence": "low",
                "error": "network_error",
            }
        except Exception as e:
            logger.error(f"Error getting Stocktwits sentiment for {ticker}: {e}")
            return {"score": 0, "messages": 0, "confidence": "low", "error": str(e)}

    @retry_with_backoff(max_retries=2, initial_delay=2.0)
    def get_alpha_vantage_sentiment(self, ticker: str) -> dict:
        """
        Get AI-powered sentiment from Alpha Vantage.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dict with score, relevance, and article count
        """
        if not self.alpha_vantage_key:
            logger.warning("Alpha Vantage API key not configured")
            return {
                "score": 0,
                "articles": 0,
                "confidence": "low",
                "error": "no_api_key",
            }

        try:
            # Use News Sentiment API
            url = f"{self.ALPHA_VANTAGE_BASE_URL}"
            params = {
                "function": "NEWS_SENTIMENT",
                "tickers": ticker,
                "apikey": self.alpha_vantage_key,
                "limit": 50,  # Analyze up to 50 articles
            }

            # Disable proxy if it's causing issues
            proxies = {"http": None, "https": None}
            response = requests.get(url, params=params, timeout=15, proxies=proxies)
            response.raise_for_status()

            data = response.json()

            # Check for API errors
            if "Error Message" in data:
                logger.error(f"Alpha Vantage API error: {data['Error Message']}")
                return {
                    "score": 0,
                    "articles": 0,
                    "confidence": "low",
                    "error": data["Error Message"],
                }

            if "Note" in data:
                logger.warning(f"Alpha Vantage rate limit: {data['Note']}")
                return {
                    "score": 0,
                    "articles": 0,
                    "confidence": "low",
                    "error": "rate_limit",
                }

            feed = data.get("feed", [])

            if not feed:
                logger.warning(f"No Alpha Vantage news found for {ticker}")
                return {"score": 0, "articles": 0, "confidence": "low"}

            # Aggregate sentiment scores weighted by relevance
            total_sentiment = 0
            total_relevance = 0
            articles_count = 0

            for article in feed:
                ticker_sentiments = article.get("ticker_sentiment", [])

                for ts in ticker_sentiments:
                    if ts.get("ticker") == ticker:
                        sentiment_score = float(ts.get("ticker_sentiment_score", 0))
                        relevance_score = float(ts.get("relevance_score", 0))

                        # Weight sentiment by relevance
                        total_sentiment += sentiment_score * relevance_score
                        total_relevance += relevance_score
                        articles_count += 1

            if total_relevance == 0:
                return {"score": 0, "articles": articles_count, "confidence": "low"}

            # Alpha Vantage sentiment is -1 to +1, convert to -100 to +100
            weighted_sentiment = (total_sentiment / total_relevance) * 100

            confidence = (
                "high" if articles_count >= 10 else "medium" if articles_count >= 5 else "low"
            )

            return {
                "score": round(weighted_sentiment, 2),
                "articles": articles_count,
                "relevance": (
                    round(total_relevance / articles_count, 3) if articles_count > 0 else 0
                ),
                "confidence": confidence,
            }

        except Exception as e:
            logger.error(f"Error getting Alpha Vantage sentiment for {ticker}: {e}")
            return {"score": 0, "articles": 0, "confidence": "low", "error": str(e)}

    @retry_with_backoff(max_retries=2, initial_delay=1.0)
    def get_grok_twitter_sentiment(self, ticker: str) -> dict:
        """
        Get real-time Twitter/X sentiment via Grok API.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dict with score, tweets analyzed, and confidence
        """
        if not self.grok_client:
            return {"score": 0, "tweets": 0, "confidence": "low", "error": "no_api_key"}

        try:
            # Query Grok for Twitter/X sentiment about ticker
            query = (
                f"Analyze Twitter/X sentiment for ${ticker} stock. "
                f"Look for recent tweets mentioning {ticker} and provide: "
                f"1. Overall sentiment score (-100 to +100), "
                f"2. Number of tweets analyzed, "
                f"3. Key bullish/bearish themes, "
                f"4. Confidence level (high/medium/low). "
                f'Respond in JSON format: {{"score": <number>, "tweets": <count>, "confidence": "<level>", "themes": ["<theme1>", "<theme2>"]}}'
            )

            response = self.grok_client.chat.completions.create(
                model="grok-2-1212",  # Latest Grok model
                messages=[
                    {
                        "role": "system",
                        "content": "You are a financial sentiment analyst. Analyze Twitter/X sentiment for stocks. Always respond with valid JSON only.",
                    },
                    {"role": "user", "content": query},
                ],
                temperature=0.3,
                max_tokens=500,
            )

            # Parse Grok response
            content = response.choices[0].message.content.strip()

            # Try to extract JSON from response (might have markdown code blocks)
            import re

            # Remove markdown code blocks if present
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                content = json_match.group(0)

            result = json.loads(content)

            score = result.get("score", 0)
            tweets = result.get("tweets", 0)
            confidence = result.get("confidence", "low")
            themes = result.get("themes", [])

            logger.info(
                f"Grok Twitter sentiment for {ticker}: score={score}, tweets={tweets}, confidence={confidence}"
            )

            return {
                "score": float(score),
                "tweets": int(tweets),
                "confidence": confidence,
                "themes": themes,
                "source": "grok_twitter",
            }

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Grok response for {ticker}: {e}")
            return {
                "score": 0,
                "tweets": 0,
                "confidence": "low",
                "error": "parse_error",
            }
        except Exception as e:
            logger.warning(f"Grok Twitter sentiment failed for {ticker}: {e}")
            return {"score": 0, "tweets": 0, "confidence": "low", "error": str(e)}

    def aggregate_sentiment(self, ticker: str) -> TickerSentiment:
        """
        Aggregate sentiment from all sources for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            TickerSentiment object with combined data
        """
        logger.info(f"Aggregating sentiment for {ticker}...")

        # Fetch from all sources
        yahoo_data = self.get_yahoo_sentiment(ticker)
        stocktwits_data = self.get_stocktwits_sentiment(ticker)
        alpha_vantage_data = self.get_alpha_vantage_sentiment(ticker)
        grok_twitter_data = self.get_grok_twitter_sentiment(
            ticker
        )  # NEW: Real-time Twitter sentiment

        # Calculate weighted average
        sources = {
            "yahoo": yahoo_data,
            "stocktwits": stocktwits_data,
            "alphavantage": alpha_vantage_data,
            "grok_twitter": grok_twitter_data,  # NEW
        }

        # Calculate combined score
        yahoo_score = yahoo_data.get("score", 0)
        stocktwits_score = stocktwits_data.get("score", 0)
        alpha_vantage_score = alpha_vantage_data.get("score", 0)
        grok_twitter_score = grok_twitter_data.get("score", 0)  # NEW

        # Adjust weights if Grok is unavailable (normalize remaining weights)
        weights_sum = self.YAHOO_WEIGHT + self.STOCKTWITS_WEIGHT + self.ALPHA_VANTAGE_WEIGHT
        if grok_twitter_data.get("error") == "no_api_key":
            # Grok unavailable - redistribute its weight proportionally
            grok_weight = 0
            yahoo_weight = self.YAHOO_WEIGHT / weights_sum
            stocktwits_weight = self.STOCKTWITS_WEIGHT / weights_sum
            alpha_vantage_weight = self.ALPHA_VANTAGE_WEIGHT / weights_sum
        else:
            # All sources available
            grok_weight = self.GROK_TWITTER_WEIGHT
            yahoo_weight = self.YAHOO_WEIGHT
            stocktwits_weight = self.STOCKTWITS_WEIGHT
            alpha_vantage_weight = self.ALPHA_VANTAGE_WEIGHT

        combined_score = (
            yahoo_score * yahoo_weight
            + stocktwits_score * stocktwits_weight
            + alpha_vantage_score * alpha_vantage_weight
            + grok_twitter_score * grok_weight  # NEW
        )

        # Determine overall confidence
        confidences = [
            yahoo_data.get("confidence", "low"),
            stocktwits_data.get("confidence", "low"),
            alpha_vantage_data.get("confidence", "low"),
            grok_twitter_data.get("confidence", "low"),  # NEW
        ]

        high_count = confidences.count("high")
        medium_count = confidences.count("medium")

        if high_count >= 2:
            overall_confidence = "high"
        elif high_count >= 1 or medium_count >= 2:
            overall_confidence = "medium"
        else:
            overall_confidence = "low"

        return TickerSentiment(
            ticker=ticker,
            score=round(combined_score, 2),
            confidence=overall_confidence,
            sources=sources,
            timestamp=datetime.now().isoformat(),
        )

    def analyze_tickers(self, tickers: list[str]) -> SentimentReport:
        """
        Analyze sentiment for multiple tickers.

        Args:
            tickers: List of ticker symbols

        Returns:
            SentimentReport with all ticker data
        """
        logger.info(f"Analyzing sentiment for {len(tickers)} tickers...")

        sentiment_data = {}
        sources_used = set()

        for ticker in tickers:
            try:
                sentiment = self.aggregate_sentiment(ticker)
                sentiment_data[ticker] = sentiment

                # Track which sources returned data
                for source_name, source_data in sentiment.sources.items():
                    if (
                        source_data.get("score", 0) != 0
                        or source_data.get("articles", 0) > 0
                        or source_data.get("messages", 0) > 0
                    ):
                        sources_used.add(source_name)

            except Exception as e:
                logger.error(f"Error analyzing {ticker}: {e}")
                continue

        report = SentimentReport(
            meta={
                "date": datetime.now().strftime("%Y-%m-%d"),
                "timestamp": datetime.now().isoformat(),
                "sources": sorted(list(sources_used)),
                "tickers_analyzed": len(sentiment_data),
            },
            sentiment_by_ticker=sentiment_data,
        )

        return report

    def save_report(self, report: SentimentReport, filename: str | None = None) -> str:
        """
        Save sentiment report to JSON file.

        Args:
            report: SentimentReport to save
            filename: Optional custom filename (default: news_YYYY-MM-DD.json)

        Returns:
            Path to saved file
        """
        if filename is None:
            today = datetime.now().strftime("%Y-%m-%d")
            filename = f"news_{today}.json"

        filepath = self.output_dir / filename

        # Convert dataclasses to dict
        report_dict = {
            "meta": report.meta,
            "sentiment_by_ticker": {
                ticker: asdict(sentiment)
                for ticker, sentiment in report.sentiment_by_ticker.items()
            },
        }

        with open(filepath, "w") as f:
            json.dump(report_dict, f, indent=2)

        logger.info(f"Sentiment report saved to {filepath}")
        return str(filepath)

    def load_report(self, filename: str) -> dict | None:
        """
        Load a sentiment report from file.

        Args:
            filename: Name of the file to load

        Returns:
            Report data as dict, or None if file not found
        """
        filepath = self.output_dir / filename

        if not filepath.exists():
            logger.error(f"Report file not found: {filepath}")
            return None

        with open(filepath) as f:
            data = json.load(f)

        logger.info(f"Loaded sentiment report from {filepath}")
        return data

    def print_summary(self, report: SentimentReport):
        """
        Print a formatted summary of the sentiment report.

        Args:
            report: SentimentReport to summarize
        """
        print("\n" + "=" * 80)
        print(f"SENTIMENT REPORT - {report.meta['date']}")
        print("=" * 80)
        print(f"Sources: {', '.join(report.meta['sources'])}")
        print(f"Tickers Analyzed: {report.meta['tickers_analyzed']}")
        print("-" * 80)

        for ticker, sentiment in report.sentiment_by_ticker.items():
            score = sentiment.score
            confidence = sentiment.confidence

            # Determine sentiment label
            if score > 20:
                label = "BULLISH"
            elif score < -20:
                label = "BEARISH"
            else:
                label = "NEUTRAL"

            print(f"\n{ticker}: {label} ({score:+.1f}) - Confidence: {confidence.upper()}")

            # Print source breakdown
            for source_name, source_data in sentiment.sources.items():
                source_score = source_data.get("score", 0)
                articles = source_data.get("articles", 0)
                messages = source_data.get("messages", 0)

                if articles > 0:
                    print(
                        f"  - {source_name.capitalize()}: {source_score:+.1f} ({articles} articles)"
                    )
                elif messages > 0:
                    print(
                        f"  - {source_name.capitalize()}: {source_score:+.1f} ({messages} messages)"
                    )
                elif source_score != 0:
                    print(f"  - {source_name.capitalize()}: {source_score:+.1f}")

        print("\n" + "=" * 80 + "\n")


def main():
    """CLI interface for news sentiment aggregator."""
    import argparse

    parser = argparse.ArgumentParser(description="Aggregate financial news sentiment")
    parser.add_argument(
        "--tickers",
        type=str,
        default="SPY,QQQ,VOO,NVDA,GOOGL,AMZN",
        help="Comma-separated list of tickers (default: SPY,QQQ,VOO,NVDA,GOOGL,AMZN)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/sentiment",
        help="Directory to save reports (default: data/sentiment)",
    )
    parser.add_argument("--load", type=str, help="Load and display an existing report (filename)")
    parser.add_argument("--test", action="store_true", help="Test with SPY only")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Initialize aggregator
    aggregator = NewsSentimentAggregator(output_dir=args.output_dir)

    if args.load:
        # Load and display existing report
        report_data = aggregator.load_report(args.load)
        if report_data:
            print("\n" + "=" * 80)
            print(f"LOADED REPORT - {report_data['meta']['date']}")
            print("=" * 80)
            print(json.dumps(report_data, indent=2))

    elif args.test:
        # Test with single ticker
        print("\nTesting with SPY ticker...")
        tickers = ["SPY"]
        report = aggregator.analyze_tickers(tickers)
        aggregator.print_summary(report)
        filepath = aggregator.save_report(report)
        print(f"Report saved to: {filepath}")

    else:
        # Analyze tickers
        tickers = [t.strip() for t in args.tickers.split(",")]
        report = aggregator.analyze_tickers(tickers)
        aggregator.print_summary(report)
        filepath = aggregator.save_report(report)
        print(f"Report saved to: {filepath}")


if __name__ == "__main__":
    main()
