"""

This module provides a hybrid approach to consuming CoinSnacks newsletter:
1. Primary: Read from MCP-populated JSON files (data/newsletter_signals_YYYY-MM-DD.json)
2. Fallback: Direct RSS parsing from CoinSnacks Medium feed

Extracts actionable trading signals for and including:
- Bullish/Bearish sentiment
- Entry points and price targets
- Technical analysis signals
- Risk/reward recommendations
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import feedparser

    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False
    logging.warning("feedparser not available - RSS fallback disabled")

logger = logging.getLogger(__name__)

# Directory for MCP-populated newsletter signals
NEWSLETTER_DATA_DIR = Path("data/newsletter_signals")
NEWSLETTER_DATA_DIR.mkdir(parents=True, exist_ok=True)

# CoinSnacks Medium RSS feed
COINSNACKS_RSS_URL = "https://medium.com/feed/coinsnacks"


@dataclass
class NewsletterSignal:
    """Represents a trading signal extracted from newsletter."""

    ticker: str
    sentiment: str  # bullish, bearish, neutral
    confidence: float  # 0.0 - 1.0
    entry_price: float | None = None
    target_price: float | None = None
    stop_loss: float | None = None
    timeframe: str | None = None  # short-term, medium-term, long-term
    reasoning: str | None = None
    source_date: datetime | None = None

    def to_dict(self) -> dict:
        """Convert signal to dictionary for JSON serialization"""
        return {
            "ticker": self.ticker,
            "sentiment": self.sentiment,
            "confidence": self.confidence,
            "entry_price": self.entry_price,
            "target_price": self.target_price,
            "stop_loss": self.stop_loss,
            "timeframe": self.timeframe,
            "reasoning": self.reasoning,
            "source_date": self.source_date.isoformat() if self.source_date else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> NewsletterSignal:
        """Create signal from dictionary"""
        return cls(
            ticker=data["ticker"],
            sentiment=data["sentiment"],
            confidence=float(data["confidence"]),
            entry_price=float(data["entry_price"]) if data.get("entry_price") else None,
            target_price=(float(data["target_price"]) if data.get("target_price") else None),
            stop_loss=float(data["stop_loss"]) if data.get("stop_loss") else None,
            timeframe=data.get("timeframe"),
            reasoning=data.get("reasoning"),
            source_date=(
                datetime.fromisoformat(data["source_date"]) if data.get("source_date") else None
            ),
        )


class NewsletterAnalyzer:
    """
    Analyzes CoinSnacks newsletter for /trading signals.

    Uses hybrid approach:
    1. Reads MCP-populated JSON files (preferred)
    2. Falls back to direct RSS parsing if available
    """

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or NEWSLETTER_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Bullish/bearish keywords for sentiment analysis
        self.bullish_keywords = [
            "bullish",
            "buy",
            "long",
            "breakout",
            "rally",
            "uptrend",
            "accumulate",
            "support",
            "bottom",
            "undervalued",
            "pump",
            "moon",
            "calls",
            "strong",
            "momentum",
            "reversal up",
        ]

        self.bearish_keywords = [
            "bearish",
            "sell",
            "short",
            "breakdown",
            "dump",
            "downtrend",
            "distribute",
            "resistance",
            "top",
            "overvalued",
            "crash",
            "puts",
            "weak",
            "consolidation",
            "reversal down",
        ]

        # Technical indicator keywords
        self.technical_keywords = [
            "rsi",
            "macd",
            "moving average",
            "ma",
            "ema",
            "sma",
            "volume",
            "fibonacci",
            "golden cross",
            "death cross",
            "bollinger",
            "support",
            "resistance",
            "trendline",
        ]

        # Ticker name mappings for article parsing
        self.ticker_names = {
            "BTC": ["btc", "bitcoin"],
            "ETH": ["eth", "ethereum"],
        }

    def get_latest_signals(self, max_age_days: int = 7) -> dict[str, NewsletterSignal]:
        """
        Get latest signals from newsletter.

        Args:
            max_age_days: Maximum age of signals to consider (default: 7 days)

        Returns:
            Dictionary of signals by ticker
        """
        # Try reading from MCP-populated JSON first
        signals = self._read_mcp_signals(max_age_days)

        if signals:
            logger.info(f"Loaded {len(signals)} signals from MCP-populated files")
            return signals

        # Fallback to RSS parsing if feedparser available
        if FEEDPARSER_AVAILABLE:
            logger.info("No MCP signals found, falling back to RSS parsing")
            signals = self._parse_rss_feed(max_age_days)

            if signals:
                logger.info(f"Extracted {len(signals)} signals from RSS feed")
                return signals

        logger.warning("No newsletter signals available from any source")
        return {}

    def _read_mcp_signals(self, max_age_days: int) -> dict[str, NewsletterSignal]:
        """
        Read newsletter signals from MCP-populated JSON files.

        Files are expected in format: data/newsletter_signals/newsletter_signals_YYYY-MM-DD.json
        """
        signals = {}
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=max_age_days)

        # Find all newsletter signal files
        signal_files = sorted(
            self.data_dir.glob("newsletter_signals_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        for signal_file in signal_files:
            try:
                # Extract date from filename
                date_str = signal_file.stem.replace("newsletter_signals_", "")
                file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)

                # Skip if too old
                if file_date < cutoff_date:
                    continue

                # Load signals from file
                with signal_file.open("r") as f:
                    data = json.load(f)

                # Parse signals for each ticker
                for ticker in self.ticker_names:
                    if ticker in data:
                        signal_data = data[ticker]
                        signal_data["source_date"] = file_date.isoformat()
                        signals[ticker] = NewsletterSignal.from_dict(signal_data)
                        logger.info(f"Loaded {ticker} signal from {signal_file.name}")

            except Exception as e:
                logger.error(f"Error reading signal file {signal_file}: {e}")
                continue

        return signals

    def _parse_rss_feed(self, max_age_days: int) -> dict[str, NewsletterSignal]:
        """
        Parse CoinSnacks RSS feed directly for trading signals.

        This is a fallback when MCP-populated files are not available.
        """
        if not FEEDPARSER_AVAILABLE:
            logger.warning("feedparser not installed - cannot parse RSS feed")
            return {}

        try:
            feed = feedparser.parse(COINSNACKS_RSS_URL)

            if not feed.entries:
                logger.warning("No entries found in CoinSnacks RSS feed")
                return {}

            cutoff_date = datetime.now(timezone.utc) - timedelta(days=max_age_days)
            signals = {}

            for entry in feed.entries:
                try:
                    # Parse entry date
                    if hasattr(entry, "published_parsed"):
                        entry_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    else:
                        entry_date = datetime.now(timezone.utc)

                    # Skip if too old
                    if entry_date < cutoff_date:
                        continue

                    # Extract article content
                    content = entry.get("summary", "") or entry.get("description", "")
                    title = entry.get("title", "")

                    # Parse article for and signals
                    article_signals = self.parse_article(title + "\n\n" + content, entry_date)

                    # Update signals dictionary (newer signals override older ones)
                    for ticker, signal in article_signals.items():
                        if (
                            ticker not in signals
                            or signal.source_date > signals[ticker].source_date
                        ):
                            signals[ticker] = signal

                except Exception as e:
                    logger.error(f"Error parsing RSS entry: {e}")
                    continue

            return signals

        except Exception as e:
            logger.error(f"Error fetching RSS feed: {e}")
            return {}

    def parse_article(
        self, article_text: str, source_date: datetime | None = None
    ) -> dict:
        """Parse article text and extract trading signals.

        Args:
            article_text: Full article text (title + content)
            source_date: Date of article publication

        Returns:
            Dictionary of signals by ticker
        """
        signals = {}
        article_lower = article_text.lower()

        # Analyze each ticker
        for ticker in self.ticker_names:
            ticker_lower = ticker.lower()

            # Check if ticker is mentioned
            if (
                ticker_lower not in article_lower
                and "ethereum" not in article_lower
            ):
                continue

            # Extract sentiment
            sentiment, confidence = self._extract_sentiment(article_text, ticker)

            # Extract price targets
            entry_price, target_price, stop_loss = self._extract_price_targets(article_text, ticker)

            # Extract timeframe
            timeframe = self._extract_timeframe(article_text)

            # Extract reasoning (first paragraph mentioning the ticker)
            reasoning = self._extract_reasoning(article_text, ticker)

            # Create signal
            signals[ticker] = NewsletterSignal(
                ticker=ticker,
                sentiment=sentiment,
                confidence=confidence,
                entry_price=entry_price,
                target_price=target_price,
                stop_loss=stop_loss,
                timeframe=timeframe,
                reasoning=reasoning,
                source_date=source_date or datetime.now(timezone.utc),
            )

            signals[ticker] = signal
            logger.info(f"Extracted {ticker} signal: {sentiment} (confidence: {confidence:.2f})")

        return signals

    def _extract_sentiment(self, text: str, ticker: str) -> tuple[str, float]:
        """
        Extract bullish/bearish sentiment and confidence score.

        Returns:
            Tuple of (sentiment, confidence) where sentiment is "bullish", "bearish", or "neutral"
            and confidence is 0.0-1.0
        """
        text_lower = text.lower()

        # Count bullish and bearish keywords
        bullish_count = sum(1 for keyword in self.bullish_keywords if keyword in text_lower)
        bearish_count = sum(1 for keyword in self.bearish_keywords if keyword in text_lower)

        # Check for technical indicators (increases confidence)
        technical_count = sum(1 for keyword in self.technical_keywords if keyword in text_lower)

        # Determine sentiment
        if bullish_count > bearish_count:
            sentiment = "bullish"
            confidence = min(0.5 + (bullish_count * 0.1) + (technical_count * 0.05), 1.0)
        elif bearish_count > bullish_count:
            sentiment = "bearish"
            confidence = min(0.5 + (bearish_count * 0.1) + (technical_count * 0.05), 1.0)
        else:
            sentiment = "neutral"
            confidence = 0.3

        return sentiment, confidence

    def _extract_price_targets(
        self, text: str, ticker: str
    ) -> tuple[float | None, float | None, float | None]:
        """
        Extract entry price, target price, and stop loss from article.

        Returns:
            Tuple of (entry_price, target_price, stop_loss)
        """
        entry_price = None
        target_price = None
        stop_loss = None

        # Look for price patterns like "$45,000", "$45k", "45000"
        # Match prices with at least 2 digits to avoid matching random numbers
        price_patterns = [
            r"\$(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*k\b",  # $45k or $45.5k
            r"\$(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\b",  # $45,000 or $45000.50
            r"(\d{4,}(?:\.\d+)?)\s*k\b",  # 45k (at least 4 digits before k)
        ]

        # Search for entry/target/stop keywords near prices
        entry_keywords = ["entry", "buy at", "enter at", "support at"]
        target_keywords = ["target", "take profit", "tp", "resistance at"]
        stop_keywords = ["stop loss", "sl", "stop at"]

        for pattern in price_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                price_str = match.group(1).replace(",", "").strip()

                # Skip empty or invalid strings
                if not price_str or price_str == ".":
                    continue

                try:
                    # Handle 'k' suffix (thousands)
                    if "k" in match.group(0).lower():
                        price = float(price_str) * 1000
                    else:
                        price = float(price_str)
                except ValueError:
                    continue

                # Get context around the price
                context_start = max(0, match.start() - 50)
                context_end = min(len(text), match.end() + 50)
                context = text[context_start:context_end].lower()

                # Classify the price based on context
                if any(keyword in context for keyword in entry_keywords):
                    entry_price = price
                elif any(keyword in context for keyword in target_keywords):
                    target_price = price
                elif any(keyword in context for keyword in stop_keywords):
                    stop_loss = price

        return entry_price, target_price, stop_loss

    def _extract_timeframe(self, text: str) -> str | None:
        """
        Extract trading timeframe from article.

        Returns:
            "short-term", "medium-term", "long-term", or None
        """
        text_lower = text.lower()

        short_keywords = [
            "short-term",
            "day trade",
            "swing",
            "days",
            "hours",
            "intraday",
        ]
        medium_keywords = ["medium-term", "weeks", "months", "intermediate"]
        long_keywords = ["long-term", "hold", "hodl", "year", "years", "accumulation"]

        if any(keyword in text_lower for keyword in long_keywords):
            return "long-term"
        elif any(keyword in text_lower for keyword in medium_keywords):
            return "medium-term"
        elif any(keyword in text_lower for keyword in short_keywords):
            return "short-term"

        return None

    def _extract_reasoning(self, text: str, ticker: str) -> str | None:
        """
        Extract reasoning/justification for the signal.

        Returns first paragraph mentioning the ticker (max 500 chars).
        """
        # Split text into paragraphs
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        ticker_lower = ticker.lower()

        # Find first paragraph mentioning the ticker
        for paragraph in paragraphs:
            paragraph_lower = paragraph.lower()
            if any(name in paragraph_lower for name in self.ticker_names.get(ticker, [ticker_lower])):
                # Truncate to 500 chars
                if len(paragraph) > 500:
                    return paragraph[:497] + "..."
                return paragraph

        return None

    def save_signals(
        self, signals: dict[str, NewsletterSignal], date: datetime | None = None
    ) -> Path:
        """
        Save extracted signals to JSON file (for MCP to populate or manual caching).

        Args:
            signals: Dictionary of signals to save
            date: Date for the signals (default: today)

        Returns:
            Path to saved file
        """
        if not signals:
            raise ValueError("Cannot save empty signals dictionary")

        date = date or datetime.now(timezone.utc)
        date_str = date.strftime("%Y-%m-%d")
        file_path = self.data_dir / f"newsletter_signals_{date_str}.json"

        # Convert signals to JSON-serializable format
        data = {ticker: signal.to_dict() for ticker, signal in signals.items()}

        with file_path.open("w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved {len(signals)} newsletter signals to {file_path}")
        return file_path

    def get_signal_for_ticker(
        self, ticker: str, max_age_days: int = 7
    ) -> NewsletterSignal | None:
        """
        Get signal for specific ticker.

        Args:
            ticker: Ticker symbol (e.g., "BTC", "ETH")
            max_age_days: Maximum age of signal to consider

        Returns:
            NewsletterSignal if found, None otherwise
        """
        signals = self.get_latest_signals(max_age_days)
        return signals.get(ticker.upper())


# Convenience functions for quick access


def get_btc_signal(max_age_days: int = 7) -> NewsletterSignal | None:
    """Get latest BTC trading signal from newsletter"""
    analyzer = NewsletterAnalyzer()
    return analyzer.get_signal_for_ticker("BTC", max_age_days)


def get_eth_signal(max_age_days: int = 7) -> NewsletterSignal | None:
    """Get latest ETH trading signal from newsletter"""
    analyzer = NewsletterAnalyzer()
    return analyzer.get_signal_for_ticker("ETH", max_age_days)


def get_all_signals(max_age_days: int = 7) -> dict[str, NewsletterSignal]:
    """Get all latest trading signals from newsletter"""
    analyzer = NewsletterAnalyzer()
    return analyzer.get_latest_signals(max_age_days)


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    analyzer = NewsletterAnalyzer()

    # Test with sample article
    sample_article = """

    is showing strong momentum above $45,000 support level.
    RSI indicates oversold conditions and MACD is crossing bullish.

    Entry: $45,500
    Target: $52,000
    Stop Loss: $43,000

    This is a medium-term trade with high confidence based on multiple
    technical indicators converging.
    """

    signals = analyzer.parse_article(sample_article)

    for ticker, signal in signals.items():
        print(f"\n{ticker} Signal:")
        print(f"  Sentiment: {signal.sentiment} ({signal.confidence:.2f} confidence)")
        print(f"  Entry: ${signal.entry_price:,.0f}" if signal.entry_price else "  Entry: N/A")
        print(f"  Target: ${signal.target_price:,.0f}" if signal.target_price else "  Target: N/A")
        print(f"  Stop Loss: ${signal.stop_loss:,.0f}" if signal.stop_loss else "  Stop Loss: N/A")
        print(f"  Timeframe: {signal.timeframe or 'N/A'}")
        print(f"  Reasoning: {signal.reasoning[:100] if signal.reasoning else 'N/A'}...")
