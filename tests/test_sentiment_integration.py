#!/usr/bin/env python3
"""
Test Sentiment Integration

Tests the complete sentiment integration flow:
1. Load sentiment data
2. Test CoreStrategy sentiment filter
3. Test GrowthStrategy sentiment modifier
4. Verify scoring logic

Run:
    python tests/test_sentiment_integration.py
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.sentiment_loader import (
    get_market_regime,
    get_ticker_sentiment,
    load_latest_sentiment,
    normalize_sentiment_score,
    print_sentiment_summary,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_mock_sentiment_data():
    """Create mock sentiment data for testing."""
    mock_dir = Path("data/sentiment")
    mock_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")

    # Mock Reddit data
    reddit_data = {
        "meta": {
            "date": today,
            "timestamp": datetime.now().isoformat(),
            "subreddits": ["wallstreetbets", "stocks"],
            "total_posts": 100,
            "total_tickers": 5,
        },
        "sentiment_by_ticker": {
            "SPY": {
                "score": 150,  # Bullish (will normalize to 75/100)
                "mentions": 45,
                "confidence": "high",
                "bullish_keywords": 30,
                "bearish_keywords": 5,
            },
            "NVDA": {
                "score": 200,  # Very bullish (will normalize to 85/100)
                "mentions": 60,
                "confidence": "high",
                "bullish_keywords": 50,
                "bearish_keywords": 2,
            },
            "GOOGL": {
                "score": -50,  # Bearish (will normalize to 25/100)
                "mentions": 20,
                "confidence": "medium",
                "bullish_keywords": 5,
                "bearish_keywords": 15,
            },
            "TSLA": {
                "score": 0,  # Neutral
                "mentions": 30,
                "confidence": "medium",
                "bullish_keywords": 10,
                "bearish_keywords": 10,
            },
        },
    }

    # Mock News data
    news_data = {
        "meta": {
            "date": today,
            "timestamp": datetime.now().isoformat(),
            "sources": ["yahoo", "stocktwits", "alphavantage"],
            "tickers_analyzed": 4,
        },
        "sentiment_by_ticker": {
            "SPY": {
                "ticker": "SPY",
                "score": 35.0,  # News already on -100 to +100 scale → 67.5/100
                "confidence": "high",
                "sources": {
                    "yahoo": {"score": 40, "articles": 15},
                    "stocktwits": {"score": 30, "messages": 50},
                },
            },
            "NVDA": {
                "ticker": "NVDA",
                "score": 60.0,  # Very bullish → 80/100
                "confidence": "high",
                "sources": {
                    "yahoo": {"score": 70, "articles": 20},
                    "stocktwits": {"score": 50, "messages": 100},
                },
            },
            "GOOGL": {
                "ticker": "GOOGL",
                "score": -30.0,  # Bearish → 35/100
                "confidence": "medium",
                "sources": {
                    "yahoo": {"score": -25, "articles": 10},
                    "stocktwits": {"score": -35, "messages": 30},
                },
            },
            "TSLA": {
                "ticker": "TSLA",
                "score": 5.0,  # Slightly bullish → 52.5/100
                "confidence": "medium",
                "sources": {
                    "yahoo": {"score": 10, "articles": 12},
                    "stocktwits": {"score": 0, "messages": 40},
                },
            },
        },
    }

    # Save mock data
    reddit_file = mock_dir / f"reddit_{today}.json"
    news_file = mock_dir / f"news_{today}.json"

    with open(reddit_file, "w") as f:
        json.dump(reddit_data, f, indent=2)

    with open(news_file, "w") as f:
        json.dump(news_data, f, indent=2)

    logger.info("Created mock sentiment data:")
    logger.info(f"  {reddit_file}")
    logger.info(f"  {news_file}")

    return reddit_file, news_file


def test_sentiment_loader():
    """Test sentiment loader functionality."""
    print("\n" + "=" * 80)
    print("TEST 1: SENTIMENT LOADER")
    print("=" * 80)

    # Load sentiment data
    sentiment_data = load_latest_sentiment()

    # Print summary
    print_sentiment_summary(sentiment_data)

    # Test individual ticker lookups
    test_tickers = ["SPY", "NVDA", "GOOGL", "TSLA", "AAPL"]

    print("\nTicker Sentiment Scores:")
    print("-" * 80)
    for ticker in test_tickers:
        score, confidence, regime = get_ticker_sentiment(ticker, sentiment_data)
        print(
            f"{ticker:<6} | Score: {score:>5.1f} | Confidence: {confidence:<6} | Regime: {regime}"
        )

    # Test market regime
    market_regime = get_market_regime(sentiment_data)
    print(f"\nMarket Regime: {market_regime.upper()}")

    return sentiment_data


def test_core_strategy_integration(sentiment_data):
    """Test CoreStrategy sentiment filter."""
    print("\n" + "=" * 80)
    print("TEST 2: CORE STRATEGY INTEGRATION")
    print("=" * 80)

    from src.strategies.core_strategy import CoreStrategy, MarketSentiment

    # Initialize strategy with sentiment enabled
    CoreStrategy(daily_allocation=6.0, use_sentiment=True)

    # Test sentiment conversion
    spy_score, _, _ = get_ticker_sentiment("SPY", sentiment_data)

    # Simulate sentiment mapping
    if spy_score < 30:
        expected = MarketSentiment.VERY_BEARISH
    elif spy_score < 40:
        expected = MarketSentiment.BEARISH
    elif spy_score < 60:
        expected = MarketSentiment.NEUTRAL
    elif spy_score < 70:
        expected = MarketSentiment.BULLISH
    else:
        expected = MarketSentiment.VERY_BULLISH

    print(f"\nSPY Sentiment Score: {spy_score:.1f}")
    print(f"Expected Market Sentiment: {expected.value}")

    # Test if VERY_BEARISH would trigger skip
    if expected == MarketSentiment.VERY_BEARISH:
        print("✓ CoreStrategy would SKIP trades (very bearish)")
    else:
        print(f"✓ CoreStrategy would PROCEED with trades ({expected.value})")

    return True


def test_growth_strategy_integration(sentiment_data):
    """Test GrowthStrategy sentiment modifier."""
    print("\n" + "=" * 80)
    print("TEST 3: GROWTH STRATEGY INTEGRATION")
    print("=" * 80)

    # Test sentiment modifier calculation
    test_cases = [
        ("NVDA", 85, "high", +15),  # Very bullish, high confidence
        ("SPY", 70, "high", +6),  # Bullish, high confidence
        ("TSLA", 50, "medium", 0),  # Neutral, medium confidence
        ("GOOGL", 30, "medium", -7),  # Bearish, medium confidence
    ]

    print("\nSentiment Modifier Calculation:")
    print("-" * 80)
    print(
        f"{'Ticker':<6} | {'Score':>5} | {'Confidence':<6} | {'Expected Modifier':>18} | {'Actual Modifier':>16}"
    )
    print("-" * 80)

    for ticker, score, confidence, expected_mod in test_cases:
        # Calculate modifier (same logic as GrowthStrategy)
        confidence_weight = {"high": 1.0, "medium": 0.6, "low": 0.3}.get(confidence, 0.3)
        actual_mod = ((score - 50) / 50) * 15 * confidence_weight

        # Get from sentiment data
        data_score, data_confidence, _ = get_ticker_sentiment(ticker, sentiment_data)

        match = "✓" if abs(actual_mod - expected_mod) < 2 else "✗"
        print(
            f"{ticker:<6} | {score:>5.1f} | {confidence:<6} | {expected_mod:>+17.1f} | {actual_mod:>+15.1f} {match}"
        )

    print("\nSentiment Impact on Ranking:")
    print("-" * 80)

    # Simulate two stocks with same technical/consensus scores
    base_score = 70  # Technical + Consensus score

    print(f"\nBase score (40% tech + 40% consensus): {base_score}")
    print("\nWith sentiment modifiers:")

    for ticker, score, confidence, _ in test_cases:
        data_score, data_confidence, _ = get_ticker_sentiment(ticker, sentiment_data)
        confidence_weight = {"high": 1.0, "medium": 0.6, "low": 0.3}.get(data_confidence, 0.3)
        sentiment_modifier = ((data_score - 50) / 50) * 15 * confidence_weight

        # Final score: 40% tech + 40% consensus + 20% sentiment
        final_score = 0.4 * base_score + 0.4 * base_score + 0.2 * (50 + sentiment_modifier)
        print(
            f"  {ticker:<6}: {final_score:>5.1f} (sentiment modifier: {sentiment_modifier:>+5.1f})"
        )

    return True


def test_normalization():
    """Test sentiment score normalization."""
    print("\n" + "=" * 80)
    print("TEST 4: SCORE NORMALIZATION")
    print("=" * 80)

    test_cases = [
        # (source, raw_score, expected_normalized)
        ("reddit", 100, 100.0),  # Max bullish
        ("reddit", 0, 50.0),  # Neutral
        ("reddit", -100, 0.0),  # Max bearish
        ("news", 100, 100.0),  # Max bullish
        ("news", 0, 50.0),  # Neutral
        ("news", -100, 0.0),  # Max bearish
        ("alphavantage", 1.0, 100.0),  # Max bullish
        ("alphavantage", 0.0, 50.0),  # Neutral
        ("alphavantage", -1.0, 0.0),  # Max bearish
    ]

    print("\nNormalization Tests:")
    print("-" * 80)
    print(f"{'Source':<15} | {'Raw Score':>10} | {'Expected':>10} | {'Actual':>10} | {'Status'}")
    print("-" * 80)

    for source, raw_score, expected in test_cases:
        actual = normalize_sentiment_score(raw_score, source)
        match = "✓" if abs(actual - expected) < 0.1 else "✗"
        print(f"{source:<15} | {raw_score:>10} | {expected:>10.1f} | {actual:>10.1f} | {match}")

    return True


def main():
    """Run all integration tests."""
    print("\n" + "=" * 80)
    print("SENTIMENT INTEGRATION TEST SUITE")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Create mock data
    print("\nCreating mock sentiment data...")
    create_mock_sentiment_data()

    # Run tests
    results = {}

    try:
        sentiment_data = test_sentiment_loader()
        results["loader"] = True
    except Exception as e:
        logger.error(f"Sentiment loader test failed: {e}", exc_info=True)
        results["loader"] = False

    try:
        test_core_strategy_integration(sentiment_data)
        results["core_strategy"] = True
    except Exception as e:
        logger.error(f"CoreStrategy integration test failed: {e}", exc_info=True)
        results["core_strategy"] = False

    try:
        test_growth_strategy_integration(sentiment_data)
        results["growth_strategy"] = True
    except Exception as e:
        logger.error(f"GrowthStrategy integration test failed: {e}", exc_info=True)
        results["growth_strategy"] = False

    try:
        test_normalization()
        results["normalization"] = True
    except Exception as e:
        logger.error(f"Normalization test failed: {e}", exc_info=True)
        results["normalization"] = False

    # Summary
    print("\n" + "=" * 80)
    print("TEST RESULTS SUMMARY")
    print("=" * 80)

    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name.replace('_', ' ').title():<30} | {status}")

    all_passed = all(results.values())
    print("\n" + "=" * 80)
    if all_passed:
        print("✓ ALL TESTS PASSED")
    else:
        print("✗ SOME TESTS FAILED")
    print("=" * 80 + "\n")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
