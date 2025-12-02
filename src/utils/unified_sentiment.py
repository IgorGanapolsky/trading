"""
Unified Sentiment Synthesizer

Aggregates sentiment from ALL sources (Reddit, YouTube, LinkedIn, TikTok, News)
with appropriate weighting and provides a single API for trading strategies.

Source Weights:
    - News: 0.30 (most reliable - professional analysts, financial news)
    - Reddit: 0.25 (high volume retail sentiment, meme stock detector)
    - YouTube: 0.20 (expert analysis from financial content creators)
    - LinkedIn: 0.15 (professional sentiment, insider perspectives)
    - TikTok: 0.10 (trending/momentum indicator, viral sentiment)

Usage:
    from src.utils.unified_sentiment import UnifiedSentiment

    analyzer = UnifiedSentiment()
    result = analyzer.get_ticker_sentiment("SPY")

    print(f"Signal: {result['signal']}")
    print(f"Overall Score: {result['overall_score']}")
    print(f"Recommendation: {result['recommendation']}")
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

# Import existing sentiment modules
try:
    from src.utils.news_sentiment import NewsSentimentAggregator
except ImportError:
    NewsSentimentAggregator = None

try:
    from src.utils.reddit_sentiment import RedditSentiment
except ImportError:
    RedditSentiment = None

try:
    from src.utils.sentiment_loader import (
        load_latest_sentiment,
        normalize_sentiment_score,
    )
except ImportError:
    load_latest_sentiment = None
    normalize_sentiment_score = None

logger = logging.getLogger(__name__)


@dataclass
class SourceSentiment:
    """Sentiment data from a single source"""

    source: str
    score: float  # Normalized -1.0 to 1.0
    confidence: float  # 0.0 to 1.0
    raw_data: dict[str, Any]
    timestamp: str
    available: bool = True
    error: Optional[str] = None


@dataclass
class UnifiedSentimentResult:
    """Aggregated sentiment result for a ticker"""

    symbol: str
    overall_score: float  # -1.0 to 1.0
    confidence: float  # 0.0 to 1.0
    signal: str  # "BULLISH", "BEARISH", "NEUTRAL"
    recommendation: str  # "BUY_SIGNAL", "SELL_SIGNAL", "HOLD"
    sources: dict[str, SourceSentiment]
    timestamp: str
    cache_hit: bool = False


class UnifiedSentiment:
    """
    Unified sentiment synthesizer aggregating all sentiment sources.

    Implements weighted aggregation with configurable source weights.
    Caches results to avoid redundant API calls (default: 1 hour).
    """

    # Source weights (must sum to 1.0)
    SOURCE_WEIGHTS = {
        "news": 0.30,  # Professional news and analyst sentiment
        "reddit": 0.25,  # Retail investor sentiment
        "youtube": 0.20,  # Expert content creator analysis
        "linkedin": 0.15,  # Professional network sentiment
        "tiktok": 0.10,  # Viral trends and momentum
    }

    # Signal thresholds
    BULLISH_THRESHOLD = 0.20  # > 0.20 = bullish
    BEARISH_THRESHOLD = -0.20  # < -0.20 = bearish

    # Recommendation thresholds (more conservative)
    BUY_THRESHOLD = 0.40  # > 0.40 + high confidence = BUY_SIGNAL
    SELL_THRESHOLD = -0.40  # < -0.40 + high confidence = SELL_SIGNAL
    MIN_CONFIDENCE_FOR_ACTION = 0.60  # Need 60%+ confidence for BUY/SELL

    # Cache settings
    CACHE_TTL_SECONDS = 3600  # 1 hour

    def __init__(
        self,
        cache_dir: str = "data/sentiment",
        enable_news: bool = True,
        enable_reddit: bool = True,
        enable_youtube: bool = True,
        enable_linkedin: bool = False,  # Not implemented yet
        enable_tiktok: bool = False,  # Not implemented yet
    ):
        """
        Initialize unified sentiment analyzer.

        Args:
            cache_dir: Directory for caching sentiment data
            enable_news: Enable news sentiment (Yahoo, Stocktwits, Alpha Vantage)
            enable_reddit: Enable Reddit sentiment
            enable_youtube: Enable YouTube sentiment
            enable_linkedin: Enable LinkedIn sentiment (placeholder)
            enable_tiktok: Enable TikTok sentiment (placeholder)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Source enablement flags
        self.enabled_sources = {
            "news": enable_news,
            "reddit": enable_reddit,
            "youtube": enable_youtube,
            "linkedin": enable_linkedin,
            "tiktok": enable_tiktok,
        }

        # Initialize source analyzers
        self.news_analyzer = None
        self.reddit_analyzer = None

        if enable_news and NewsSentimentAggregator:
            try:
                self.news_analyzer = NewsSentimentAggregator(output_dir=str(self.cache_dir))
                logger.info("News sentiment analyzer initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize news analyzer: {e}")
                self.enabled_sources["news"] = False

        if enable_reddit and RedditSentiment:
            try:
                self.reddit_analyzer = RedditSentiment(data_dir=str(self.cache_dir))
                logger.info("Reddit sentiment analyzer initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Reddit analyzer: {e}")
                self.enabled_sources["reddit"] = False

        # Calculate active source weights (normalize to 1.0)
        self._normalize_weights()

        logger.info(f"UnifiedSentiment initialized. Active sources: {self._get_active_sources()}")

    def _normalize_weights(self):
        """Normalize weights based on enabled sources to sum to 1.0"""
        active_weight_sum = sum(
            weight
            for source, weight in self.SOURCE_WEIGHTS.items()
            if self.enabled_sources.get(source, False)
        )

        if active_weight_sum == 0:
            logger.warning("No sentiment sources enabled!")
            self.normalized_weights = {}
            return

        self.normalized_weights = {
            source: weight / active_weight_sum
            for source, weight in self.SOURCE_WEIGHTS.items()
            if self.enabled_sources.get(source, False)
        }

        logger.debug(f"Normalized weights: {self.normalized_weights}")

    def _get_active_sources(self) -> list[str]:
        """Get list of active sentiment sources"""
        return [source for source, enabled in self.enabled_sources.items() if enabled]

    def _get_cache_key(self, symbol: str) -> str:
        """Generate cache key for a symbol"""
        return f"unified_{symbol}_{datetime.now().strftime('%Y%m%d_%H')}"

    def _load_from_cache(self, symbol: str) -> Optional[UnifiedSentimentResult]:
        """Load sentiment from cache if fresh enough"""
        cache_file = self.cache_dir / f"{self._get_cache_key(symbol)}.json"

        if not cache_file.exists():
            return None

        try:
            # Check if cache is still fresh
            cache_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
            if cache_age.total_seconds() > self.CACHE_TTL_SECONDS:
                logger.debug(f"Cache expired for {symbol} (age: {cache_age})")
                return None

            with open(cache_file) as f:
                data = json.load(f)

            logger.info(f"Cache hit for {symbol}")
            # Convert dict back to dataclass
            sources = {k: SourceSentiment(**v) for k, v in data.get("sources", {}).items()}
            result = UnifiedSentimentResult(
                symbol=data["symbol"],
                overall_score=data["overall_score"],
                confidence=data["confidence"],
                signal=data["signal"],
                recommendation=data["recommendation"],
                sources=sources,
                timestamp=data["timestamp"],
                cache_hit=True,
            )
            return result

        except Exception as e:
            logger.warning(f"Error loading cache for {symbol}: {e}")
            return None

    def _save_to_cache(self, result: UnifiedSentimentResult):
        """Save sentiment result to cache"""
        cache_file = self.cache_dir / f"{self._get_cache_key(result.symbol)}.json"

        try:
            # Convert dataclasses to dict
            data = {
                "symbol": result.symbol,
                "overall_score": result.overall_score,
                "confidence": result.confidence,
                "signal": result.signal,
                "recommendation": result.recommendation,
                "sources": {k: asdict(v) for k, v in result.sources.items()},
                "timestamp": result.timestamp,
                "cache_hit": False,
            }

            with open(cache_file, "w") as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Cached sentiment for {result.symbol}")

        except Exception as e:
            logger.warning(f"Error saving cache for {result.symbol}: {e}")

    def _get_news_sentiment(self, symbol: str) -> SourceSentiment:
        """Get sentiment from news sources"""
        if not self.enabled_sources.get("news") or not self.news_analyzer:
            return SourceSentiment(
                source="news",
                score=0.0,
                confidence=0.0,
                raw_data={},
                timestamp=datetime.now().isoformat(),
                available=False,
                error="News source disabled or unavailable",
            )

        try:
            # Get news sentiment
            ticker_sentiment = self.news_analyzer.aggregate_sentiment(symbol)

            # Normalize score from -100..100 to -1..1
            normalized_score = ticker_sentiment.score / 100.0

            # Map confidence to 0..1 scale
            confidence_map = {"low": 0.3, "medium": 0.6, "high": 0.9}
            confidence = confidence_map.get(ticker_sentiment.confidence, 0.5)

            return SourceSentiment(
                source="news",
                score=normalized_score,
                confidence=confidence,
                raw_data=ticker_sentiment.sources,
                timestamp=ticker_sentiment.timestamp,
                available=True,
            )

        except Exception as e:
            logger.error(f"Error getting news sentiment for {symbol}: {e}")
            return SourceSentiment(
                source="news",
                score=0.0,
                confidence=0.0,
                raw_data={},
                timestamp=datetime.now().isoformat(),
                available=False,
                error=str(e),
            )

    def _get_reddit_sentiment(self, symbol: str) -> SourceSentiment:
        """Get sentiment from Reddit"""
        if not self.enabled_sources.get("reddit") or not self.reddit_analyzer:
            return SourceSentiment(
                source="reddit",
                score=0.0,
                confidence=0.0,
                raw_data={},
                timestamp=datetime.now().isoformat(),
                available=False,
                error="Reddit source disabled or unavailable",
            )

        try:
            # Get Reddit sentiment data (from cache if available)
            sentiment_data = self.reddit_analyzer.collect_daily_sentiment(force_refresh=False)

            ticker_data = sentiment_data.get("sentiment_by_ticker", {}).get(symbol)

            if not ticker_data:
                logger.debug(f"No Reddit data for {symbol}")
                return SourceSentiment(
                    source="reddit",
                    score=0.0,
                    confidence=0.0,
                    raw_data={},
                    timestamp=datetime.now().isoformat(),
                    available=True,
                    error="Ticker not found in Reddit data",
                )

            # Normalize score (Reddit scores can be -500 to +500, clamp to -100..100)
            raw_score = ticker_data.get("score", 0)
            clamped_score = max(-100, min(100, raw_score))
            normalized_score = clamped_score / 100.0

            # Map confidence
            confidence_map = {"low": 0.3, "medium": 0.6, "high": 0.9}
            confidence = confidence_map.get(ticker_data.get("confidence", "low"), 0.5)

            return SourceSentiment(
                source="reddit",
                score=normalized_score,
                confidence=confidence,
                raw_data={
                    "mentions": ticker_data.get("mentions", 0),
                    "bullish_keywords": ticker_data.get("bullish_keywords", 0),
                    "bearish_keywords": ticker_data.get("bearish_keywords", 0),
                    "total_upvotes": ticker_data.get("total_upvotes", 0),
                },
                timestamp=sentiment_data.get("meta", {}).get(
                    "timestamp", datetime.now().isoformat()
                ),
                available=True,
            )

        except Exception as e:
            logger.error(f"Error getting Reddit sentiment for {symbol}: {e}")
            return SourceSentiment(
                source="reddit",
                score=0.0,
                confidence=0.0,
                raw_data={},
                timestamp=datetime.now().isoformat(),
                available=False,
                error=str(e),
            )

    def _get_youtube_sentiment(self, symbol: str) -> SourceSentiment:
        """Get sentiment from YouTube analysis"""
        if not self.enabled_sources.get("youtube"):
            return SourceSentiment(
                source="youtube",
                score=0.0,
                confidence=0.0,
                raw_data={},
                timestamp=datetime.now().isoformat(),
                available=False,
                error="YouTube source disabled",
            )

        # YouTube sentiment is file-based (from youtube_monitor.py)
        # Look for recent analysis files mentioning this ticker
        try:
            youtube_dir = Path("docs/youtube_analysis")
            if not youtube_dir.exists():
                return SourceSentiment(
                    source="youtube",
                    score=0.0,
                    confidence=0.0,
                    raw_data={},
                    timestamp=datetime.now().isoformat(),
                    available=False,
                    error="YouTube analysis directory not found",
                )

            # Find recent analysis files (last 7 days)
            cutoff_time = datetime.now() - timedelta(days=7)
            recent_analyses = []

            for analysis_file in youtube_dir.glob("*.md"):
                if analysis_file.stat().st_mtime < cutoff_time.timestamp():
                    continue

                # Read file and check if it mentions the ticker
                content = analysis_file.read_text()
                if symbol in content.upper():
                    recent_analyses.append(content)

            if not recent_analyses:
                return SourceSentiment(
                    source="youtube",
                    score=0.0,
                    confidence=0.0,
                    raw_data={},
                    timestamp=datetime.now().isoformat(),
                    available=True,
                    error="No recent YouTube analysis for ticker",
                )

            # Simple sentiment extraction (can be enhanced with LLM analysis)
            bullish_keywords = [
                "bullish",
                "buy",
                "long",
                "positive",
                "upgrade",
                "growth",
            ]
            bearish_keywords = [
                "bearish",
                "sell",
                "short",
                "negative",
                "downgrade",
                "decline",
            ]

            bullish_count = 0
            bearish_count = 0

            for content_lower in [c.lower() for c in recent_analyses]:
                bullish_count += sum(1 for kw in bullish_keywords if kw in content_lower)
                bearish_count += sum(1 for kw in bearish_keywords if kw in content_lower)

            # Normalize score
            total_keywords = bullish_count + bearish_count
            if total_keywords > 0:
                normalized_score = (bullish_count - bearish_count) / total_keywords
                confidence = min(
                    0.9, 0.3 + (total_keywords / 20.0)
                )  # More keywords = higher confidence
            else:
                normalized_score = 0.0
                confidence = 0.1

            return SourceSentiment(
                source="youtube",
                score=normalized_score,
                confidence=confidence,
                raw_data={
                    "analyses_found": len(recent_analyses),
                    "bullish_keywords": bullish_count,
                    "bearish_keywords": bearish_count,
                },
                timestamp=datetime.now().isoformat(),
                available=True,
            )

        except Exception as e:
            logger.error(f"Error getting YouTube sentiment for {symbol}: {e}")
            return SourceSentiment(
                source="youtube",
                score=0.0,
                confidence=0.0,
                raw_data={},
                timestamp=datetime.now().isoformat(),
                available=False,
                error=str(e),
            )

    def _get_linkedin_sentiment(self, symbol: str) -> SourceSentiment:
        """Get sentiment from LinkedIn (placeholder for future implementation)"""
        # TODO: Implement LinkedIn sentiment scraping
        # Potential approach: Use LinkedIn API or web scraping to analyze posts
        # about the ticker from finance professionals
        return SourceSentiment(
            source="linkedin",
            score=0.0,
            confidence=0.0,
            raw_data={},
            timestamp=datetime.now().isoformat(),
            available=False,
            error="LinkedIn sentiment not yet implemented",
        )

    def _get_tiktok_sentiment(self, symbol: str) -> SourceSentiment:
        """Get sentiment from TikTok (placeholder for future implementation)"""
        # TODO: Implement TikTok sentiment analysis
        # Potential approach: Use TikTok API to analyze hashtags and trending videos
        # mentioning the ticker
        return SourceSentiment(
            source="tiktok",
            score=0.0,
            confidence=0.0,
            raw_data={},
            timestamp=datetime.now().isoformat(),
            available=False,
            error="TikTok sentiment not yet implemented",
        )

    def get_ticker_sentiment(self, symbol: str, use_cache: bool = True) -> dict:
        """
        Get aggregated sentiment for a ticker from all sources.

        Args:
            symbol: Stock ticker symbol (e.g., "SPY", "NVDA")
            use_cache: Whether to use cached data if available (default: True)

        Returns:
            Dictionary with aggregated sentiment data:
            {
                "symbol": "SPY",
                "overall_score": 0.45,  # -1.0 to 1.0
                "confidence": 0.75,  # 0.0 to 1.0
                "signal": "BULLISH",  # "BULLISH", "BEARISH", "NEUTRAL"
                "recommendation": "BUY_SIGNAL",  # "BUY_SIGNAL", "SELL_SIGNAL", "HOLD"
                "sources": {
                    "news": {...},
                    "reddit": {...},
                    "youtube": {...},
                    "linkedin": {...},
                    "tiktok": {...}
                },
                "timestamp": "2025-11-29T10:30:00",
                "cache_hit": False
            }
        """
        # Check cache first
        if use_cache:
            cached_result = self._load_from_cache(symbol)
            if cached_result:
                return asdict(cached_result)

        logger.info(f"Fetching unified sentiment for {symbol}...")

        # Gather sentiment from all sources
        source_sentiments = {
            "news": self._get_news_sentiment(symbol),
            "reddit": self._get_reddit_sentiment(symbol),
            "youtube": self._get_youtube_sentiment(symbol),
            "linkedin": self._get_linkedin_sentiment(symbol),
            "tiktok": self._get_tiktok_sentiment(symbol),
        }

        # Calculate weighted average score
        weighted_score = 0.0
        total_weight = 0.0
        confidence_scores = []

        for source_name, sentiment in source_sentiments.items():
            if not sentiment.available:
                logger.debug(f"Skipping {source_name} for {symbol}: {sentiment.error}")
                continue

            weight = self.normalized_weights.get(source_name, 0.0)
            if weight > 0:
                weighted_score += sentiment.score * weight
                total_weight += weight
                confidence_scores.append(sentiment.confidence)

                logger.debug(
                    f"{source_name}: score={sentiment.score:.2f}, "
                    f"confidence={sentiment.confidence:.2f}, weight={weight:.2f}"
                )

        # Normalize if needed
        if total_weight > 0:
            overall_score = weighted_score / total_weight
        else:
            overall_score = 0.0
            logger.warning(f"No sentiment sources available for {symbol}")

        # Calculate overall confidence (average of available sources)
        overall_confidence = (
            sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        )

        # Determine signal
        if overall_score > self.BULLISH_THRESHOLD:
            signal = "BULLISH"
        elif overall_score < self.BEARISH_THRESHOLD:
            signal = "BEARISH"
        else:
            signal = "NEUTRAL"

        # Determine recommendation (more conservative)
        if (
            overall_score > self.BUY_THRESHOLD
            and overall_confidence >= self.MIN_CONFIDENCE_FOR_ACTION
        ):
            recommendation = "BUY_SIGNAL"
        elif (
            overall_score < self.SELL_THRESHOLD
            and overall_confidence >= self.MIN_CONFIDENCE_FOR_ACTION
        ):
            recommendation = "SELL_SIGNAL"
        else:
            recommendation = "HOLD"

        # Create result
        result = UnifiedSentimentResult(
            symbol=symbol,
            overall_score=overall_score,
            confidence=overall_confidence,
            signal=signal,
            recommendation=recommendation,
            sources=source_sentiments,
            timestamp=datetime.now().isoformat(),
            cache_hit=False,
        )

        # Log which sources contributed
        active_sources = [name for name, sent in source_sentiments.items() if sent.available]
        logger.info(
            f"{symbol}: score={overall_score:.2f}, confidence={overall_confidence:.2f}, "
            f"signal={signal}, recommendation={recommendation}, "
            f"sources={','.join(active_sources)}"
        )

        # Cache result
        self._save_to_cache(result)

        return asdict(result)

    def get_batch_sentiment(self, symbols: list[str], use_cache: bool = True) -> dict[str, dict]:
        """
        Get sentiment for multiple tickers in batch.

        Args:
            symbols: List of ticker symbols
            use_cache: Whether to use cached data if available

        Returns:
            Dictionary mapping symbols to sentiment results
        """
        results = {}

        for symbol in symbols:
            try:
                results[symbol] = self.get_ticker_sentiment(symbol, use_cache=use_cache)
            except Exception as e:
                logger.error(f"Error getting sentiment for {symbol}: {e}")
                results[symbol] = {
                    "symbol": symbol,
                    "overall_score": 0.0,
                    "confidence": 0.0,
                    "signal": "NEUTRAL",
                    "recommendation": "HOLD",
                    "sources": {},
                    "timestamp": datetime.now().isoformat(),
                    "error": str(e),
                }

        return results

    def print_sentiment_summary(self, symbol: str):
        """Print formatted sentiment summary for a ticker"""
        result = self.get_ticker_sentiment(symbol)

        print("\n" + "=" * 80)
        print(f"UNIFIED SENTIMENT ANALYSIS: {symbol}")
        print("=" * 80)
        print(f"Overall Score: {result['overall_score']:+.2f} (-1.0 to +1.0)")
        print(f"Confidence: {result['confidence']:.1%}")
        print(f"Signal: {result['signal']}")
        print(f"Recommendation: {result['recommendation']}")
        print(f"Timestamp: {result['timestamp']}")
        print(f"Cache Hit: {result.get('cache_hit', False)}")
        print("\n" + "-" * 80)
        print("SOURCE BREAKDOWN:")
        print("-" * 80)

        for source_name, source_data in result["sources"].items():
            if not source_data["available"]:
                print(f"\n{source_name.upper()}: UNAVAILABLE")
                print(f"  Error: {source_data.get('error', 'Unknown')}")
                continue

            weight = self.SOURCE_WEIGHTS.get(source_name, 0.0)
            print(f"\n{source_name.upper()} (weight: {weight:.0%}):")
            print(f"  Score: {source_data['score']:+.2f}")
            print(f"  Confidence: {source_data['confidence']:.1%}")

            # Print source-specific details
            raw_data = source_data.get("raw_data", {})
            if source_name == "reddit":
                mentions = raw_data.get("mentions", 0)
                bullish = raw_data.get("bullish_keywords", 0)
                bearish = raw_data.get("bearish_keywords", 0)
                print(
                    f"  Details: {mentions} mentions, {bullish} bullish keywords, {bearish} bearish keywords"
                )
            elif source_name == "youtube":
                analyses = raw_data.get("analyses_found", 0)
                print(f"  Details: {analyses} recent video analyses")
            elif source_name == "news":
                sources_used = list(raw_data.keys())
                print(f"  Details: {', '.join(sources_used)}")

        print("\n" + "=" * 80 + "\n")


def main():
    """CLI interface for unified sentiment analysis"""
    import argparse

    parser = argparse.ArgumentParser(description="Unified Sentiment Analysis")
    parser.add_argument(
        "symbols",
        type=str,
        nargs="?",
        default="SPY,QQQ,NVDA",
        help="Comma-separated list of tickers (default: SPY,QQQ,NVDA)",
    )
    parser.add_argument("--no-cache", action="store_true", help="Disable cache (fetch fresh data)")
    parser.add_argument("--disable-news", action="store_true", help="Disable news sentiment")
    parser.add_argument("--disable-reddit", action="store_true", help="Disable Reddit sentiment")
    parser.add_argument("--disable-youtube", action="store_true", help="Disable YouTube sentiment")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Parse symbols
    symbols = [s.strip().upper() for s in args.symbols.split(",")]

    # Initialize analyzer
    analyzer = UnifiedSentiment(
        enable_news=not args.disable_news,
        enable_reddit=not args.disable_reddit,
        enable_youtube=not args.disable_youtube,
    )

    # Analyze each symbol
    for symbol in symbols:
        analyzer.print_sentiment_summary(symbol)


if __name__ == "__main__":
    main()
