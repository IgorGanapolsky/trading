"""
Sentiment Loader Utility

Loads sentiment scores from cached data files (Reddit + News) and provides
a unified interface for strategies to query sentiment by ticker.

This module acts as the integration layer between sentiment collection
(reddit_sentiment.py, news_sentiment.py) and strategy execution
(core_strategy.py, growth_strategy.py).

Usage:
    from src.utils.sentiment_loader import load_latest_sentiment, get_ticker_sentiment

    # Load all sentiment data
    sentiment_data = load_latest_sentiment()

    # Get score for specific ticker
    score, confidence = get_ticker_sentiment("SPY", sentiment_data)

    # Check if data is fresh
    if is_sentiment_fresh(sentiment_data):
        use_sentiment_in_strategy()
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    from rag_store.sqlite_store import SentimentSQLiteStore
except Exception:  # noqa: BLE001
    _SQLITE_STORE: Optional["SentimentSQLiteStore"] = None
else:
    _SQLITE_STORE = SentimentSQLiteStore()

logger = logging.getLogger(__name__)


# Sentiment data directory
SENTIMENT_DIR = Path("data/sentiment")

# Sentiment score thresholds (0-100 scale)
VERY_BEARISH_THRESHOLD = 30  # Below 30 = very bearish
BEARISH_THRESHOLD = 40  # 30-40 = bearish
NEUTRAL_LOW = 40  # 40-60 = neutral
NEUTRAL_HIGH = 60
BULLISH_THRESHOLD = 70  # 60-70 = bullish
VERY_BULLISH_THRESHOLD = 70  # Above 70 = very bullish

# Data freshness threshold (hours)
MAX_AGE_HOURS = 24


def _load_source_from_sqlite(source: str, date_str: str) -> Optional[dict]:
    """
    Load sentiment snapshot from SQLite store when JSON cache is missing.

    Args:
        source: Data source identifier ("reddit" or "news")
        date_str: Date string (YYYY-MM-DD)

    Returns:
        Sentiment dict matching cached JSON structure, or None if unavailable.
    """
    if _SQLITE_STORE is None:
        return None

    rows = list(_SQLITE_STORE.fetch_by_source_date(source=source, snapshot_date=date_str))
    if not rows:
        return None

    sentiment_by_ticker = {}
    for row in rows:
        metadata = json.loads(row["metadata"])
        sentiment_by_ticker[row["ticker"]] = metadata

    meta = {
        "date": date_str,
        "timestamp": rows[0]["created_at"],
        "sources": [source],
        "tickers_analyzed": len(sentiment_by_ticker),
        "store_backfill": True,
    }

    if source == "reddit":
        meta.update(
            {
                "subreddits": [],
                "total_tickers": len(sentiment_by_ticker),
            }
        )
    return {"meta": meta, "sentiment_by_ticker": sentiment_by_ticker}


def normalize_sentiment_score(score: float, source: str) -> float:
    """
    Normalize sentiment score from various sources to 0-100 scale.

    Different sources use different scales:
    - Reddit: Raw scores (can be large positive/negative integers)
    - News: -100 to +100 scale
    - Alpha Vantage: -1 to +1 scale

    We normalize everything to 0-100 where:
    - 0 = maximally bearish
    - 50 = neutral
    - 100 = maximally bullish

    Args:
        score: Raw sentiment score from source
        source: Source identifier ("reddit", "news", "alphavantage")

    Returns:
        Normalized score on 0-100 scale
    """
    if source == "reddit":
        # Reddit scores are raw weighted counts (can be -500 to +500)
        # Clamp to reasonable range and normalize
        clamped = max(-100, min(100, score))
        normalized = (clamped + 100) / 2  # Map -100..+100 to 0..100
        return normalized

    elif source == "news":
        # News scores are already -100 to +100
        normalized = (score + 100) / 2  # Map -100..+100 to 0..100
        return normalized

    elif source == "alphavantage":
        # Alpha Vantage is -1 to +1
        normalized = (score + 1) * 50  # Map -1..+1 to 0..100
        return normalized

    else:
        # Unknown source, assume 0-100 scale already
        return max(0, min(100, score))


def load_latest_sentiment(date: Optional[str] = None, fallback_days: int = 7) -> dict:
    """
    Load the most recent sentiment data from cache files.

    Combines data from:
    - Reddit sentiment (data/sentiment/reddit_YYYY-MM-DD.json)
    - News sentiment (data/sentiment/news_YYYY-MM-DD.json)

    Args:
        date: Specific date to load (YYYY-MM-DD), or None for today
        fallback_days: Days to look back if today's data not found (default: 7)

    Returns:
        Dict with combined sentiment data:
        {
            "meta": {
                "date": "2025-11-09",
                "timestamp": "2025-11-09T08:00:00",
                "sources": ["reddit", "news"],
                "freshness": "fresh|stale|missing"
            },
            "sentiment_by_ticker": {
                "SPY": {
                    "score": 65.5,  # 0-100 normalized scale
                    "confidence": "high|medium|low",
                    "sources": {
                        "reddit": {"score": 120, "mentions": 45, ...},
                        "news": {"score": 35, "articles": 12, ...}
                    },
                    "market_regime": "risk_on|risk_off|neutral"
                },
                ...
            }
        }
    """
    target_date = datetime.now() if date is None else datetime.strptime(date, "%Y-%m-%d")

    logger.info(f"Loading sentiment data for {target_date.strftime('%Y-%m-%d')}")

    reddit_data = None
    news_data = None
    days_searched = 0

    # Try to find sentiment files (fallback to recent days if not found)
    for days_back in range(fallback_days + 1):
        search_date = target_date - timedelta(days=days_back)
        date_str = search_date.strftime("%Y-%m-%d")
        days_searched = days_back

        # Try Reddit data
        if reddit_data is None:
            reddit_file = SENTIMENT_DIR / f"reddit_{date_str}.json"
            if reddit_file.exists():
                try:
                    with open(reddit_file) as f:
                        reddit_data = json.load(f)
                        logger.info(f"Loaded Reddit sentiment from {reddit_file}")
                except Exception as e:
                    logger.error(f"Failed to load Reddit sentiment: {e}")
            elif _SQLITE_STORE:
                reddit_data = _load_source_from_sqlite("reddit", date_str)
                if reddit_data:
                    logger.info("Loaded Reddit sentiment from SQLite fallback")

        # Try News data
        if news_data is None:
            news_file = SENTIMENT_DIR / f"news_{date_str}.json"
            if news_file.exists():
                try:
                    with open(news_file) as f:
                        news_data = json.load(f)
                        logger.info(f"Loaded news sentiment from {news_file}")
                except Exception as e:
                    logger.error(f"Failed to load news sentiment: {e}")
            elif _SQLITE_STORE:
                news_data = _load_source_from_sqlite("news", date_str)
                if news_data:
                    logger.info("Loaded news sentiment from SQLite fallback")

        # If we found both, stop searching
        if reddit_data and news_data:
            break

    # Determine freshness
    if days_searched == 0:
        freshness = "fresh"
    elif days_searched <= 3:
        freshness = "stale"
    else:
        freshness = "old"

    if not reddit_data and not news_data:
        logger.warning("No sentiment data found!")
        return {
            "meta": {
                "date": target_date.strftime("%Y-%m-%d"),
                "timestamp": datetime.now().isoformat(),
                "sources": [],
                "freshness": "missing",
            },
            "sentiment_by_ticker": {},
        }

    # Combine sentiment from both sources
    combined_sentiment = {}
    sources_used = []

    # Process Reddit data
    if reddit_data:
        sources_used.append("reddit")
        reddit_tickers = reddit_data.get("sentiment_by_ticker", {})

        for ticker, data in reddit_tickers.items():
            if ticker not in combined_sentiment:
                combined_sentiment[ticker] = {
                    "sources": {},
                    "scores": [],
                    "confidences": [],
                }

            # Normalize Reddit score
            reddit_score = data.get("score", 0)
            normalized_score = normalize_sentiment_score(reddit_score, "reddit")

            combined_sentiment[ticker]["sources"]["reddit"] = {
                "raw_score": reddit_score,
                "normalized_score": normalized_score,
                "mentions": data.get("mentions", 0),
                "confidence": data.get("confidence", "low"),
                "bullish_keywords": data.get("bullish_keywords", 0),
                "bearish_keywords": data.get("bearish_keywords", 0),
            }

            combined_sentiment[ticker]["scores"].append(normalized_score)
            combined_sentiment[ticker]["confidences"].append(data.get("confidence", "low"))

    # Process News data
    if news_data:
        sources_used.append("news")
        news_tickers = news_data.get("sentiment_by_ticker", {})

        for ticker, ticker_obj in news_tickers.items():
            if ticker not in combined_sentiment:
                combined_sentiment[ticker] = {
                    "sources": {},
                    "scores": [],
                    "confidences": [],
                }

            # News data is wrapped in TickerSentiment object
            news_score = ticker_obj.get("score", 0)
            normalized_score = normalize_sentiment_score(news_score, "news")

            combined_sentiment[ticker]["sources"]["news"] = {
                "raw_score": news_score,
                "normalized_score": normalized_score,
                "confidence": ticker_obj.get("confidence", "low"),
                "yahoo": ticker_obj.get("sources", {}).get("yahoo", {}),
                "stocktwits": ticker_obj.get("sources", {}).get("stocktwits", {}),
                "alphavantage": ticker_obj.get("sources", {}).get("alphavantage", {}),
            }

            combined_sentiment[ticker]["scores"].append(normalized_score)
            combined_sentiment[ticker]["confidences"].append(ticker_obj.get("confidence", "low"))

    # Calculate final scores and confidence
    final_sentiment = {}

    for ticker, data in combined_sentiment.items():
        scores = data["scores"]
        confidences = data["confidences"]

        # Average of all source scores
        final_score = sum(scores) / len(scores) if scores else 50.0

        # Overall confidence (highest confidence from any source)
        confidence_map = {"low": 0, "medium": 1, "high": 2}
        max_confidence = max(confidence_map.get(c, 0) for c in confidences)
        confidence_reverse = {0: "low", 1: "medium", 2: "high"}
        final_confidence = confidence_reverse[max_confidence]

        # Determine market regime based on score
        if final_score < VERY_BEARISH_THRESHOLD:
            market_regime = "risk_off"
        elif final_score > VERY_BULLISH_THRESHOLD:
            market_regime = "risk_on"
        else:
            market_regime = "neutral"

        final_sentiment[ticker] = {
            "score": round(final_score, 2),
            "confidence": final_confidence,
            "sources": data["sources"],
            "market_regime": market_regime,
        }

    return {
        "meta": {
            "date": target_date.strftime("%Y-%m-%d"),
            "timestamp": datetime.now().isoformat(),
            "sources": sources_used,
            "freshness": freshness,
            "days_old": days_searched,
        },
        "sentiment_by_ticker": final_sentiment,
    }


def get_ticker_sentiment(
    ticker: str,
    sentiment_data: Optional[dict] = None,
    default_score: float = 50.0,
    default_confidence: str = "low",
) -> tuple[float, str, str]:
    """
    Get sentiment score for a specific ticker.

    Args:
        ticker: Stock ticker symbol (e.g., "SPY", "NVDA")
        sentiment_data: Pre-loaded sentiment data (optional - will load if None)
        default_score: Default score if ticker not found (default: 50.0 = neutral)
        default_confidence: Default confidence if ticker not found (default: "low")

    Returns:
        Tuple of (score, confidence, market_regime)
        - score: Sentiment score on 0-100 scale
        - confidence: "low", "medium", or "high"
        - market_regime: "risk_on", "risk_off", or "neutral"
    """
    # Load data if not provided
    if sentiment_data is None:
        sentiment_data = load_latest_sentiment()

    # Check if ticker exists
    ticker_data = sentiment_data.get("sentiment_by_ticker", {}).get(ticker)

    if not ticker_data:
        logger.debug(f"No sentiment data for {ticker}, using default {default_score}")
        # Determine default market regime
        if default_score < VERY_BEARISH_THRESHOLD:
            default_regime = "risk_off"
        elif default_score > VERY_BULLISH_THRESHOLD:
            default_regime = "risk_on"
        else:
            default_regime = "neutral"

        return default_score, default_confidence, default_regime

    score = ticker_data.get("score", default_score)
    confidence = ticker_data.get("confidence", default_confidence)
    market_regime = ticker_data.get("market_regime", "neutral")

    logger.debug(
        f"{ticker} sentiment: score={score}, confidence={confidence}, regime={market_regime}"
    )

    return score, confidence, market_regime


def is_sentiment_fresh(sentiment_data: dict, max_age_hours: int = MAX_AGE_HOURS) -> bool:
    """
    Check if sentiment data is fresh (recent enough to use).

    Args:
        sentiment_data: Sentiment data dict
        max_age_hours: Maximum age in hours (default: 24)

    Returns:
        True if data is fresh, False if stale
    """
    freshness = sentiment_data.get("meta", {}).get("freshness", "missing")
    days_old = sentiment_data.get("meta", {}).get("days_old", 999)

    if freshness == "missing":
        return False

    hours_old = days_old * 24
    return hours_old <= max_age_hours


def get_market_regime(sentiment_data: Optional[dict] = None) -> str:
    """
    Get overall market regime based on SPY sentiment.

    Market regimes:
    - "risk_on": Bullish market, favorable for growth stocks
    - "risk_off": Bearish market, defensive positioning needed
    - "neutral": No clear trend, normal operation

    Args:
        sentiment_data: Pre-loaded sentiment data (optional)

    Returns:
        Market regime string
    """
    # Use SPY as proxy for overall market sentiment
    spy_score, spy_confidence, spy_regime = get_ticker_sentiment("SPY", sentiment_data)

    logger.info(
        f"Market regime: {spy_regime} (SPY sentiment: {spy_score}, confidence: {spy_confidence})"
    )

    return spy_regime


def get_sentiment_summary(sentiment_data: Optional[dict] = None) -> dict:
    """
    Get a human-readable summary of sentiment data.

    Args:
        sentiment_data: Pre-loaded sentiment data (optional)

    Returns:
        Dict with summary statistics
    """
    if sentiment_data is None:
        sentiment_data = load_latest_sentiment()

    meta = sentiment_data.get("meta", {})
    tickers = sentiment_data.get("sentiment_by_ticker", {})

    # Count tickers by sentiment
    bullish = sum(1 for t in tickers.values() if t.get("score", 50) >= BULLISH_THRESHOLD)
    bearish = sum(1 for t in tickers.values() if t.get("score", 50) <= BEARISH_THRESHOLD)
    neutral = len(tickers) - bullish - bearish

    # Count by confidence
    high_conf = sum(1 for t in tickers.values() if t.get("confidence") == "high")
    med_conf = sum(1 for t in tickers.values() if t.get("confidence") == "medium")
    low_conf = sum(1 for t in tickers.values() if t.get("confidence") == "low")

    return {
        "date": meta.get("date"),
        "freshness": meta.get("freshness"),
        "days_old": meta.get("days_old", 0),
        "sources": meta.get("sources", []),
        "total_tickers": len(tickers),
        "bullish": bullish,
        "bearish": bearish,
        "neutral": neutral,
        "high_confidence": high_conf,
        "medium_confidence": med_conf,
        "low_confidence": low_conf,
        "market_regime": get_market_regime(sentiment_data),
    }


def print_sentiment_summary(sentiment_data: Optional[dict] = None):
    """
    Print a formatted summary of sentiment data.

    Args:
        sentiment_data: Pre-loaded sentiment data (optional)
    """
    summary = get_sentiment_summary(sentiment_data)

    print("\n" + "=" * 80)
    print("SENTIMENT SUMMARY")
    print("=" * 80)
    print(f"Date: {summary['date']}")
    print(f"Freshness: {summary['freshness'].upper()} ({summary['days_old']} days old)")
    print(f"Sources: {', '.join(summary['sources'])}")
    print(f"Market Regime: {summary['market_regime'].upper()}")
    print()
    print(f"Total Tickers: {summary['total_tickers']}")
    print(
        f"  Bullish:  {summary['bullish']} ({summary['bullish'] / summary['total_tickers'] * 100:.0f}%)"
    )
    print(
        f"  Neutral:  {summary['neutral']} ({summary['neutral'] / summary['total_tickers'] * 100:.0f}%)"
    )
    print(
        f"  Bearish:  {summary['bearish']} ({summary['bearish'] / summary['total_tickers'] * 100:.0f}%)"
    )
    print()
    print("Confidence Levels:")
    print(f"  High:   {summary['high_confidence']}")
    print(f"  Medium: {summary['medium_confidence']}")
    print(f"  Low:    {summary['low_confidence']}")
    print("=" * 80 + "\n")


def query_sentiment_rag(
    query: str,
    ticker: Optional[str] = None,
    top_k: int = 5,
) -> list[dict]:
    """
    Retrieve historical sentiment snapshots using the vector store.

    Args:
        query: Natural language query
        ticker: Optional ticker symbol to filter results
        top_k: Number of results to return
    """
    from src.rag.sentiment_store import SentimentRAGStore  # Lazy import to avoid

    # heavy dependencies when only using JSON loader

    store = SentimentRAGStore()
    return store.query(query=query, ticker=ticker, top_k=top_k)


def get_sentiment_history(
    ticker: str,
    limit: int = 10,
) -> list[dict]:
    """
    Fetch the most recent sentiment snapshots for a ticker from the RAG store.

    Args:
        ticker: Stock ticker symbol
        limit: Maximum number of snapshots to return
    """
    from src.rag.sentiment_store import SentimentRAGStore  # Lazy import

    store = SentimentRAGStore()
    return store.get_ticker_history(ticker=ticker, limit=limit)


if __name__ == "__main__":
    """CLI interface for testing sentiment loader."""
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Load and display sentiment summary
    print("Loading sentiment data...")
    sentiment_data = load_latest_sentiment()

    print_sentiment_summary(sentiment_data)

    # Test specific tickers if provided
    if len(sys.argv) > 1:
        tickers = sys.argv[1].split(",")
        print(f"Checking sentiment for: {', '.join(tickers)}")
        print("-" * 80)

        for ticker in tickers:
            score, confidence, regime = get_ticker_sentiment(ticker.strip(), sentiment_data)
            print(f"{ticker}: score={score:.1f}, confidence={confidence}, regime={regime}")
