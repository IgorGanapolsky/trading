#!/usr/bin/env python3
"""
Unified Sentiment Synthesizer - Usage Examples

This file demonstrates how to use the UnifiedSentiment class
to aggregate sentiment from multiple sources and make trading decisions.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.unified_sentiment import UnifiedSentiment


def example_1_basic_usage():
    """Example 1: Basic sentiment analysis for a single ticker"""
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Basic Sentiment Analysis")
    print("=" * 80)

    # Initialize analyzer
    analyzer = UnifiedSentiment()

    # Get sentiment for SPY
    result = analyzer.get_ticker_sentiment("SPY")

    print(f"\nTicker: {result['symbol']}")
    print(f"Overall Score: {result['overall_score']:+.2f} (-1.0 to +1.0)")
    print(f"Confidence: {result['confidence']:.1%}")
    print(f"Signal: {result['signal']}")
    print(f"Recommendation: {result['recommendation']}")

    # Show which sources contributed
    active_sources = [name for name, data in result["sources"].items() if data["available"]]
    print(f"Active Sources: {', '.join(active_sources) if active_sources else 'None'}")


def example_2_batch_analysis():
    """Example 2: Analyze multiple tickers in batch"""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Batch Sentiment Analysis")
    print("=" * 80)

    analyzer = UnifiedSentiment()

    # Analyze watchlist
    watchlist = ["SPY", "QQQ", "NVDA", "GOOGL", "AMZN"]
    results = analyzer.get_batch_sentiment(watchlist)

    print(f"\nAnalyzing {len(watchlist)} tickers...\n")

    # Display results in table format
    print(f"{'Ticker':<8} {'Score':<8} {'Signal':<10} {'Recommendation':<15} {'Confidence':<12}")
    print("-" * 80)

    for symbol, data in results.items():
        score = data["overall_score"]
        signal = data["signal"]
        recommendation = data["recommendation"]
        confidence = data["confidence"]

        print(f"{symbol:<8} {score:+.2f}     {signal:<10} {recommendation:<15} {confidence:.1%}")


def example_3_trading_decision():
    """Example 3: Use sentiment to make trading decisions"""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Trading Decision Logic")
    print("=" * 80)

    analyzer = UnifiedSentiment()

    # Check sentiment before entering trade
    symbol = "NVDA"
    result = analyzer.get_ticker_sentiment(symbol)

    print(f"\nEvaluating trade entry for {symbol}...")
    print(f"Sentiment Score: {result['overall_score']:+.2f}")
    print(f"Confidence: {result['confidence']:.1%}")
    print(f"Recommendation: {result['recommendation']}")

    # Decision logic
    if result["recommendation"] == "BUY_SIGNAL":
        print("\n✅ ENTER POSITION: Strong bullish sentiment detected")
        print(f"   - Score > 0.40: {result['overall_score'] > 0.40}")
        print(f"   - Confidence > 60%: {result['confidence'] > 0.60}")

    elif result["recommendation"] == "SELL_SIGNAL":
        print("\n❌ AVOID/EXIT: Strong bearish sentiment detected")
        print(f"   - Score < -0.40: {result['overall_score'] < -0.40}")
        print(f"   - Confidence > 60%: {result['confidence'] > 0.60}")

    else:
        print("\n⚠️  HOLD: Neutral or uncertain sentiment")
        print("   Action: Wait for clearer signal or use other indicators")


def example_4_position_sizing():
    """Example 4: Use sentiment to adjust position size"""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Sentiment-Based Position Sizing")
    print("=" * 80)

    analyzer = UnifiedSentiment()

    symbol = "NVDA"
    base_amount = 100.00  # Base position size

    result = analyzer.get_ticker_sentiment(symbol)

    print(f"\nBase Position Size: ${base_amount:.2f}")
    print(f"Sentiment Score: {result['overall_score']:+.2f}")
    print(f"Confidence: {result['confidence']:.1%}")

    # Apply sentiment boost
    if result["overall_score"] > 0.60 and result["confidence"] > 0.70:
        # Strong bullish sentiment - boost by up to 50%
        boost_multiplier = 1.0 + (result["overall_score"] * 0.5)
        adjusted_amount = base_amount * boost_multiplier

        print("\n🚀 SENTIMENT BOOST APPLIED")
        print(f"   Multiplier: {boost_multiplier:.2f}x")
        print(f"   Adjusted Position: ${adjusted_amount:.2f}")
        print(
            f"   Boost: +${adjusted_amount - base_amount:.2f} (+{((boost_multiplier - 1) * 100):.0f}%)"
        )

    elif result["overall_score"] < -0.40:
        # Bearish sentiment - reduce position
        print("\n⚠️  REDUCE POSITION: Bearish sentiment detected")
        print("   Consider reducing exposure or exiting position")

    else:
        print(f"\n✓ Standard Position: ${base_amount:.2f}")
        print("   No sentiment adjustment needed")


def example_5_source_breakdown():
    """Example 5: Examine individual source contributions"""
    print("\n" + "=" * 80)
    print("EXAMPLE 5: Source Contribution Breakdown")
    print("=" * 80)

    analyzer = UnifiedSentiment()

    # Use the built-in summary method
    analyzer.print_sentiment_summary("SPY")


def example_6_custom_weights():
    """Example 6: Initialize with custom source configuration"""
    print("\n" + "=" * 80)
    print("EXAMPLE 6: Custom Source Configuration")
    print("=" * 80)

    # Disable Reddit if you don't have credentials
    analyzer = UnifiedSentiment(
        enable_news=True,
        enable_reddit=False,  # Disable Reddit
        enable_youtube=True,
    )

    print("\nAnalyzer Configuration:")
    print(f"Active Sources: {analyzer._get_active_sources()}")
    print(f"Normalized Weights: {analyzer.normalized_weights}")

    # Analyze with custom configuration
    result = analyzer.get_ticker_sentiment("SPY")
    print("\nSPY Sentiment (News + YouTube only):")
    print(f"Score: {result['overall_score']:+.2f}")
    print(f"Confidence: {result['confidence']:.1%}")


def example_7_cache_usage():
    """Example 7: Understanding and using the cache"""
    print("\n" + "=" * 80)
    print("EXAMPLE 7: Cache Usage")
    print("=" * 80)

    analyzer = UnifiedSentiment()

    # First call - fetch fresh data
    print("\n1. First call (fresh data)...")
    result1 = analyzer.get_ticker_sentiment("SPY", use_cache=False)
    print(f"   Cache Hit: {result1.get('cache_hit', False)}")
    print(f"   Timestamp: {result1['timestamp']}")

    # Second call - use cache
    print("\n2. Second call (from cache)...")
    result2 = analyzer.get_ticker_sentiment("SPY", use_cache=True)
    print(f"   Cache Hit: {result2.get('cache_hit', False)}")
    print(f"   Timestamp: {result2['timestamp']}")

    # Verify they're the same
    if result1["overall_score"] == result2["overall_score"]:
        print("\n✓ Cache working correctly - scores match")
    else:
        print("\n⚠️  Warning: Cache mismatch")


def main():
    """Run all examples"""
    print("\n" + "=" * 80)
    print("UNIFIED SENTIMENT SYNTHESIZER - USAGE EXAMPLES")
    print("=" * 80)

    try:
        example_1_basic_usage()
        example_2_batch_analysis()
        example_3_trading_decision()
        example_4_position_sizing()
        example_5_source_breakdown()
        example_6_custom_weights()
        example_7_cache_usage()

        print("\n" + "=" * 80)
        print("ALL EXAMPLES COMPLETED")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
