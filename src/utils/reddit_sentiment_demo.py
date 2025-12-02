"""
Reddit Sentiment Scraper - Demo Mode

Demonstrates the scraper functionality using mock data.
No Reddit API credentials required.

This shows what the output looks like when properly configured.
"""

import json
from datetime import datetime
from pathlib import Path


def generate_demo_data() -> dict:
    """Generate realistic demo sentiment data."""

    return {
        "meta": {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.now().isoformat(),
            "subreddits": ["wallstreetbets", "stocks", "investing", "options"],
            "total_posts": 87,
            "total_tickers": 24,
            "subreddit_stats": {
                "wallstreetbets": {"posts_collected": 25, "status": "success"},
                "stocks": {"posts_collected": 23, "status": "success"},
                "investing": {"posts_collected": 20, "status": "success"},
                "options": {"posts_collected": 19, "status": "success"},
            },
            "demo_mode": True,
            "note": "This is DEMO data - not real Reddit sentiment",
        },
        "sentiment_by_ticker": {
            "SPY": {
                "score": 127,
                "mentions": 45,
                "confidence": "high",
                "bullish_keywords": 67,
                "bearish_keywords": 12,
                "total_upvotes": 2340,
                "total_comments": 890,
                "avg_score_per_mention": 2.82,
                "top_posts": [
                    {
                        "title": "SPY breakout incoming - MACD bullish crossover confirmed",
                        "score": 567,
                        "comments": 234,
                        "flair": "DD",
                        "permalink": "https://reddit.com/r/wallstreetbets/xyz",
                        "sentiment_score": 45,
                    },
                    {
                        "title": "Loading up on SPY calls for next week 🚀",
                        "score": 432,
                        "comments": 156,
                        "flair": "YOLO",
                        "permalink": "https://reddit.com/r/wallstreetbets/abc",
                        "sentiment_score": 38,
                    },
                ],
            },
            "NVDA": {
                "score": 95,
                "mentions": 38,
                "confidence": "high",
                "bullish_keywords": 54,
                "bearish_keywords": 8,
                "total_upvotes": 1890,
                "total_comments": 670,
                "avg_score_per_mention": 2.5,
                "top_posts": [
                    {
                        "title": "NVDA AI dominance continues - analyst PT $200",
                        "score": 489,
                        "comments": 203,
                        "flair": "DD",
                        "permalink": "https://reddit.com/r/stocks/xyz",
                        "sentiment_score": 42,
                    }
                ],
            },
            "TSLA": {
                "score": 82,
                "mentions": 52,
                "confidence": "high",
                "bullish_keywords": 71,
                "bearish_keywords": 23,
                "total_upvotes": 2100,
                "total_comments": 945,
                "avg_score_per_mention": 1.58,
                "top_posts": [
                    {
                        "title": "TSLA earnings beat expectations 📈",
                        "score": 678,
                        "comments": 342,
                        "flair": "News",
                        "permalink": "https://reddit.com/r/wallstreetbets/tsla",
                        "sentiment_score": 51,
                    }
                ],
            },
            "AMZN": {
                "score": 64,
                "mentions": 29,
                "confidence": "medium",
                "bullish_keywords": 42,
                "bearish_keywords": 11,
                "total_upvotes": 1450,
                "total_comments": 520,
                "avg_score_per_mention": 2.21,
                "top_posts": [
                    {
                        "title": "AMZN OpenAI partnership is huge - $295 PT",
                        "score": 523,
                        "comments": 198,
                        "flair": "DD",
                        "permalink": "https://reddit.com/r/stocks/amzn",
                        "sentiment_score": 39,
                    }
                ],
            },
            "GOOGL": {
                "score": 47,
                "mentions": 23,
                "confidence": "medium",
                "bullish_keywords": 31,
                "bearish_keywords": 9,
                "total_upvotes": 980,
                "total_comments": 410,
                "avg_score_per_mention": 2.04,
                "top_posts": [
                    {
                        "title": "GOOGL undervalued - AI catching up to MSFT",
                        "score": 412,
                        "comments": 167,
                        "flair": "Discussion",
                        "permalink": "https://reddit.com/r/investing/googl",
                        "sentiment_score": 28,
                    }
                ],
            },
            "QQQ": {
                "score": 41,
                "mentions": 18,
                "confidence": "medium",
                "bullish_keywords": 26,
                "bearish_keywords": 7,
                "total_upvotes": 720,
                "total_comments": 290,
                "avg_score_per_mention": 2.28,
                "top_posts": [
                    {
                        "title": "QQQ looking strong - tech rally continues",
                        "score": 345,
                        "comments": 123,
                        "flair": "Discussion",
                        "permalink": "https://reddit.com/r/stocks/qqq",
                        "sentiment_score": 24,
                    }
                ],
            },
            "AAPL": {
                "score": 35,
                "mentions": 31,
                "confidence": "medium",
                "bullish_keywords": 38,
                "bearish_keywords": 19,
                "total_upvotes": 1250,
                "total_comments": 580,
                "avg_score_per_mention": 1.13,
                "top_posts": [
                    {
                        "title": "AAPL Vision Pro sales disappointing",
                        "score": 456,
                        "comments": 234,
                        "flair": "News",
                        "permalink": "https://reddit.com/r/stocks/aapl",
                        "sentiment_score": 18,
                    }
                ],
            },
            "PLTR": {
                "score": -34,
                "mentions": 27,
                "confidence": "medium",
                "bullish_keywords": 12,
                "bearish_keywords": 41,
                "total_upvotes": 890,
                "total_comments": 450,
                "avg_score_per_mention": -1.26,
                "top_posts": [
                    {
                        "title": "PLTR bag holders unite - when will this dump end?",
                        "score": 567,
                        "comments": 289,
                        "flair": "Loss",
                        "permalink": "https://reddit.com/r/wallstreetbets/pltr",
                        "sentiment_score": -28,
                    }
                ],
            },
            "GME": {
                "score": 28,
                "mentions": 19,
                "confidence": "low",
                "bullish_keywords": 34,
                "bearish_keywords": 15,
                "total_upvotes": 620,
                "total_comments": 340,
                "avg_score_per_mention": 1.47,
                "top_posts": [
                    {
                        "title": "GME still has potential - diamond hands 💎🙌",
                        "score": 234,
                        "comments": 156,
                        "flair": "YOLO",
                        "permalink": "https://reddit.com/r/wallstreetbets/gme",
                        "sentiment_score": 21,
                    }
                ],
            },
            "AMD": {
                "score": 23,
                "mentions": 15,
                "confidence": "low",
                "bullish_keywords": 19,
                "bearish_keywords": 8,
                "total_upvotes": 450,
                "total_comments": 180,
                "avg_score_per_mention": 1.53,
                "top_posts": [
                    {
                        "title": "AMD gaining market share from Intel",
                        "score": 289,
                        "comments": 98,
                        "flair": "DD",
                        "permalink": "https://reddit.com/r/stocks/amd",
                        "sentiment_score": 15,
                    }
                ],
            },
        },
    }


def main():
    """Run demo and display results."""

    print("\n" + "=" * 80)
    print("REDDIT SENTIMENT SCRAPER - DEMO MODE")
    print("=" * 80)
    print("\n⚠️  This is DEMO data - not real Reddit sentiment")
    print("To use real data, follow setup instructions in docs/reddit_sentiment_setup.md\n")

    # Generate demo data
    data = generate_demo_data()

    # Save to file
    output_dir = Path("data/sentiment")
    output_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    output_file = output_dir / f"reddit_demo_{today}.json"

    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)

    # Display summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Date: {data['meta']['date']}")
    print(f"Subreddits: {', '.join(['r/' + s for s in data['meta']['subreddits']])}")
    print(f"Total Posts: {data['meta']['total_posts']}")
    print(f"Total Tickers: {data['meta']['total_tickers']}")

    # Top tickers
    print("\nTop 10 Tickers by Sentiment Score:")
    print("-" * 80)

    sorted_tickers = sorted(
        data["sentiment_by_ticker"].items(), key=lambda x: x[1]["score"], reverse=True
    )

    for i, (ticker, ticker_data) in enumerate(sorted_tickers[:10], 1):
        sentiment = (
            "📈 BULLISH"
            if ticker_data["score"] > 0
            else "📉 BEARISH"
            if ticker_data["score"] < 0
            else "➡️ NEUTRAL"
        )
        print(
            f"{i:2}. {ticker:<6} | Score: {ticker_data['score']:>6} | Mentions: {ticker_data['mentions']:>3} | "
            f"Confidence: {ticker_data['confidence'].upper():<6} | {sentiment}"
        )
        print(
            f"    Bullish: {ticker_data['bullish_keywords']:>3} keywords | "
            f"Bearish: {ticker_data['bearish_keywords']:>3} keywords"
        )
        print(
            f"    Engagement: {ticker_data['total_upvotes']:>4} upvotes, {ticker_data['total_comments']:>4} comments"
        )

        if ticker_data["top_posts"]:
            print(f"    Top Post: {ticker_data['top_posts'][0]['title'][:60]}...")
        print()

    # Subreddit stats
    print("\nSubreddit Statistics:")
    print("-" * 80)
    for sub, stats in data["meta"]["subreddit_stats"].items():
        status_icon = "✓" if stats["status"] == "success" else "✗"
        print(
            f"{status_icon} r/{sub:<20} | Posts: {stats['posts_collected']:>3} | Status: {stats['status']}"
        )

    print("\n" + "=" * 80)
    print(f"Demo data saved to: {output_file}")
    print("=" * 80)

    # Trading insights
    print("\n" + "=" * 80)
    print("TRADING INSIGHTS (from demo data)")
    print("=" * 80)

    # Bullish tickers (high confidence)
    bullish = [
        (ticker, data)
        for ticker, data in sorted_tickers
        if data["score"] > 50 and data["confidence"] == "high"
    ]

    print("\n✅ High Confidence BULLISH (consider for Tier 2):")
    for ticker, data in bullish:
        print(f"   - {ticker}: Score {data['score']}, {data['mentions']} mentions")

    # Bearish tickers (avoid)
    bearish = [
        (ticker, data)
        for ticker, data in sorted_tickers
        if data["score"] < -20 and data["confidence"] in ["high", "medium"]
    ]

    print("\n❌ BEARISH (consider avoiding):")
    for ticker, data in bearish:
        print(f"   - {ticker}: Score {data['score']}, {data['mentions']} mentions")

    # Meme stocks (high volatility)
    meme_stocks = [
        (ticker, data)
        for ticker, data in sorted_tickers
        if data["mentions"] > 20
        and any(post["flair"] in ["YOLO", "Loss", "Gain"] for post in data["top_posts"])
    ]

    print("\n⚠️  Potential MEME STOCKS (high volatility risk):")
    for ticker, data in meme_stocks:
        print(f"   - {ticker}: Score {data['score']}, {data['mentions']} mentions")

    print("\n" + "=" * 80)
    print("To use real Reddit data:")
    print("1. Create Reddit app: https://www.reddit.com/prefs/apps")
    print("2. Add credentials to .env file (see docs/reddit_sentiment_setup.md)")
    print("3. Run: python3 src/utils/reddit_sentiment.py")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
