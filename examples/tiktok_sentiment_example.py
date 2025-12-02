#!/usr/bin/env python3
"""
TikTok Sentiment Collector - Usage Example

Demonstrates how to use the TikTok collector for financial sentiment analysis.

Prerequisites:
- TikTok API credentials configured in .env
- TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET set

Usage:
    python3 examples/tiktok_sentiment_example.py
"""

import logging
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.rag.collectors.tiktok_collector import TikTokCollector

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def example_1_ticker_sentiment():
    """Example 1: Get sentiment summary for a single ticker."""
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Ticker Sentiment Summary")
    print("=" * 80)

    collector = TikTokCollector()

    ticker = "NVDA"
    days_back = 7

    print(f"\nAnalyzing TikTok sentiment for ${ticker} (last {days_back} days)...")

    summary = collector.get_ticker_sentiment_summary(ticker=ticker, days_back=days_back)

    print(f"\n📊 Sentiment Summary for ${ticker}:")
    print(f"   Symbol: {summary['symbol']}")
    print(f"   Sentiment Score: {summary['sentiment_score']:.3f} (0=bearish, 1=bullish)")
    print(f"   Video Count: {summary['video_count']}")
    print(f"   Avg Engagement: {summary['engagement_score']:.2f}/100")
    print(f"   Source: {summary['source']}")
    print(f"   Timestamp: {summary['timestamp']}")

    # Interpret sentiment
    score = summary["sentiment_score"]
    if score > 0.7:
        interpretation = "🚀 STRONG BULLISH"
    elif score > 0.55:
        interpretation = "📈 Bullish"
    elif score >= 0.45:
        interpretation = "➡️  Neutral"
    elif score >= 0.3:
        interpretation = "📉 Bearish"
    else:
        interpretation = "💥 STRONG BEARISH"

    print(f"\n   Interpretation: {interpretation}")


def example_2_individual_videos():
    """Example 2: Collect and display individual videos."""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Individual Video Analysis")
    print("=" * 80)

    collector = TikTokCollector()

    ticker = "SPY"
    days_back = 3

    print(f"\nCollecting TikTok videos for ${ticker} (last {days_back} days)...")

    videos = collector.collect_ticker_news(ticker=ticker, days_back=days_back)

    print(f"\n📹 Found {len(videos)} videos mentioning ${ticker}")

    # Display top 5 by engagement
    for i, video in enumerate(videos[:5], 1):
        print(f"\n{i}. {video['title']}")
        print(f"   Sentiment: {video['sentiment']:.2f} (0=bearish, 1=bullish)")
        print(f"   Engagement: {video['engagement_score']:.2f}/100")
        print(f"   Views: {video.get('view_count', 0):,}")
        print(f"   Likes: {video.get('like_count', 0):,}")
        print(f"   Comments: {video.get('comment_count', 0):,}")
        print(f"   Shares: {video.get('share_count', 0):,}")
        print(f"   Date: {video['published_date']}")
        print(f"   URL: {video['url']}")


def example_3_market_overview():
    """Example 3: Get general market sentiment from TikTok."""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Market Overview")
    print("=" * 80)

    collector = TikTokCollector()

    days_back = 1

    print(f"\nCollecting general market videos (last {days_back} day)...")

    videos = collector.collect_market_news(days_back=days_back)

    print(f"\n📊 Found {len(videos)} market-related videos")

    # Calculate overall market sentiment
    if videos:
        avg_sentiment = sum(v["sentiment"] for v in videos) / len(videos)
        avg_engagement = sum(v["engagement_score"] for v in videos) / len(videos)

        print(f"\n   Average Sentiment: {avg_sentiment:.3f}")
        print(f"   Average Engagement: {avg_engagement:.2f}/100")

        # Top hashtags
        all_hashtags = []
        for video in videos:
            all_hashtags.extend(video.get("hashtags", []))

        from collections import Counter

        top_hashtags = Counter(all_hashtags).most_common(5)

        print("\n   Top Hashtags:")
        for hashtag, count in top_hashtags:
            print(f"      #{hashtag}: {count} videos")


def example_4_multi_ticker_comparison():
    """Example 4: Compare sentiment across multiple tickers."""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Multi-Ticker Comparison")
    print("=" * 80)

    collector = TikTokCollector()

    tickers = ["SPY", "QQQ", "NVDA", "GOOGL", "AMZN"]
    days_back = 7

    print(f"\nComparing sentiment for {len(tickers)} tickers (last {days_back} days)...")

    results = []
    for ticker in tickers:
        summary = collector.get_ticker_sentiment_summary(ticker, days_back=days_back)
        results.append(summary)

    # Sort by sentiment score (most bullish first)
    results.sort(key=lambda x: x["sentiment_score"], reverse=True)

    print("\n📊 Sentiment Rankings (Most Bullish → Most Bearish):\n")
    print(f"{'Rank':<6} {'Ticker':<8} {'Sentiment':<12} {'Videos':<10} {'Engagement':<12}")
    print("-" * 60)

    for i, result in enumerate(results, 1):
        ticker = result["symbol"]
        sentiment = result["sentiment_score"]
        videos = result["video_count"]
        engagement = result["engagement_score"]

        # Sentiment indicator
        if sentiment > 0.7:
            indicator = "🚀"
        elif sentiment > 0.55:
            indicator = "📈"
        elif sentiment >= 0.45:
            indicator = "➡️"
        elif sentiment >= 0.3:
            indicator = "📉"
        else:
            indicator = "💥"

        print(
            f"{i:<6} {ticker:<8} {indicator} {sentiment:.3f}      {videos:<10} {engagement:.2f}/100"
        )


def example_5_integrated_with_orchestrator():
    """Example 5: Use TikTok collector via News Orchestrator."""
    print("\n" + "=" * 80)
    print("EXAMPLE 5: Integrated Multi-Source Analysis")
    print("=" * 80)

    from src.rag.collectors import get_orchestrator

    orchestrator = get_orchestrator()

    ticker = "NVDA"
    days_back = 7

    print(f"\nCollecting news for ${ticker} from ALL sources (including TikTok)...")

    all_news = orchestrator.collect_all_ticker_news(ticker=ticker, days_back=days_back)

    # Separate by source
    tiktok_news = [n for n in all_news if n["source"] == "tiktok"]
    reddit_news = [n for n in all_news if n["source"] == "reddit"]
    yahoo_news = [n for n in all_news if n["source"] == "yahoo"]
    alphavantage_news = [n for n in all_news if n["source"] == "alphavantage"]

    print("\n📰 News collected from all sources:")
    print(f"   TikTok: {len(tiktok_news)} videos")
    print(f"   Reddit: {len(reddit_news)} posts")
    print(f"   Yahoo Finance: {len(yahoo_news)} articles")
    print(f"   Alpha Vantage: {len(alphavantage_news)} articles")
    print(f"   TOTAL: {len(all_news)} items")

    # Calculate average sentiment by source
    if tiktok_news:
        tiktok_sentiment = sum(v["sentiment"] for v in tiktok_news if v.get("sentiment")) / len(
            tiktok_news
        )
        print(f"\n   TikTok Sentiment: {tiktok_sentiment:.3f}")

    if reddit_news:
        reddit_sentiment = sum(v["sentiment"] for v in reddit_news if v.get("sentiment")) / len(
            reddit_news
        )
        print(f"   Reddit Sentiment: {reddit_sentiment:.3f}")

    # Show highest engagement TikTok video
    if tiktok_news:
        top_video = max(tiktok_news, key=lambda x: x.get("engagement_score", 0))
        print("\n   🏆 Top TikTok Video:")
        print(f"      Title: {top_video['title']}")
        print(f"      Engagement: {top_video['engagement_score']:.2f}/100")
        print(f"      Sentiment: {top_video['sentiment']:.2f}")


def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("TIKTOK SENTIMENT COLLECTOR - USAGE EXAMPLES")
    print("=" * 80)
    print(f"\nDate: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Check if credentials are configured
    if not os.getenv("TIKTOK_CLIENT_KEY") or not os.getenv("TIKTOK_CLIENT_SECRET"):
        print("\n⚠️  WARNING: TikTok API credentials not found!")
        print("   Set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET in .env file")
        print("   Examples will run but return empty results.\n")

    try:
        # Run examples
        example_1_ticker_sentiment()
        example_2_individual_videos()
        example_3_market_overview()
        example_4_multi_ticker_comparison()
        example_5_integrated_with_orchestrator()

        print("\n" + "=" * 80)
        print("✅ All examples completed successfully!")
        print("=" * 80 + "\n")

    except Exception as e:
        logger.error(f"Error running examples: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
