"""
Demo script for News Sentiment Aggregator

Shows functionality with example data and real API calls where available.
"""

import json
from datetime import datetime

from src.utils.news_sentiment import NewsSentimentAggregator


def create_mock_report():
    """Create a mock sentiment report to demonstrate output format."""
    print("\n" + "=" * 80)
    print("MOCK SENTIMENT REPORT (Example Output Format)")
    print("=" * 80)

    mock_data = {
        "meta": {
            "date": "2025-11-09",
            "timestamp": datetime.now().isoformat(),
            "sources": ["yahoo", "stocktwits", "alphavantage"],
            "tickers_analyzed": 6,
        },
        "sentiment_by_ticker": {
            "SPY": {
                "ticker": "SPY",
                "score": 65.0,
                "confidence": "high",
                "sources": {
                    "yahoo": {"score": 70, "articles": 12},
                    "stocktwits": {
                        "score": 55,
                        "messages": 234,
                        "bullish": 150,
                        "bearish": 84,
                    },
                    "alphavantage": {"score": 75, "relevance": 0.9, "articles": 15},
                },
                "timestamp": datetime.now().isoformat(),
            },
            "NVDA": {
                "ticker": "NVDA",
                "score": 82.5,
                "confidence": "high",
                "sources": {
                    "yahoo": {"score": 85, "articles": 18},
                    "stocktwits": {
                        "score": 78,
                        "messages": 456,
                        "bullish": 320,
                        "bearish": 136,
                    },
                    "alphavantage": {"score": 85, "relevance": 0.95, "articles": 22},
                },
                "timestamp": datetime.now().isoformat(),
            },
            "GOOGL": {
                "ticker": "GOOGL",
                "score": 45.0,
                "confidence": "medium",
                "sources": {
                    "yahoo": {"score": 50, "articles": 8},
                    "stocktwits": {
                        "score": 35,
                        "messages": 123,
                        "bullish": 65,
                        "bearish": 58,
                    },
                    "alphavantage": {"score": 52, "relevance": 0.75, "articles": 10},
                },
                "timestamp": datetime.now().isoformat(),
            },
            "AMZN": {
                "ticker": "AMZN",
                "score": -15.0,
                "confidence": "medium",
                "sources": {
                    "yahoo": {"score": -10, "articles": 7},
                    "stocktwits": {
                        "score": -25,
                        "messages": 89,
                        "bullish": 30,
                        "bearish": 59,
                    },
                    "alphavantage": {"score": -12, "relevance": 0.68, "articles": 9},
                },
                "timestamp": datetime.now().isoformat(),
            },
            "QQQ": {
                "ticker": "QQQ",
                "score": 58.0,
                "confidence": "high",
                "sources": {
                    "yahoo": {"score": 60, "articles": 14},
                    "stocktwits": {
                        "score": 52,
                        "messages": 198,
                        "bullish": 125,
                        "bearish": 73,
                    },
                    "alphavantage": {"score": 65, "relevance": 0.88, "articles": 16},
                },
                "timestamp": datetime.now().isoformat(),
            },
            "VOO": {
                "ticker": "VOO",
                "score": 55.0,
                "confidence": "medium",
                "sources": {
                    "yahoo": {"score": 55, "articles": 6},
                    "stocktwits": {
                        "score": 48,
                        "messages": 67,
                        "bullish": 42,
                        "bearish": 25,
                    },
                    "alphavantage": {"score": 62, "relevance": 0.72, "articles": 8},
                },
                "timestamp": datetime.now().isoformat(),
            },
        },
    }

    print(json.dumps(mock_data, indent=2))
    print("\n" + "-" * 80)
    print("SENTIMENT SUMMARY")
    print("-" * 80)

    for ticker, data in mock_data["sentiment_by_ticker"].items():
        score = data["score"]
        confidence = data["confidence"]

        if score > 20:
            label = "BULLISH"
        elif score < -20:
            label = "BEARISH"
        else:
            label = "NEUTRAL"

        print(f"\n{ticker}: {label} ({score:+.1f}) - Confidence: {confidence.upper()}")

        for source_name, source_data in data["sources"].items():
            source_score = source_data.get("score", 0)
            articles = source_data.get("articles", 0)
            messages = source_data.get("messages", 0)

            if articles > 0:
                print(f"  - {source_name.capitalize()}: {source_score:+.1f} ({articles} articles)")
            elif messages > 0:
                bullish = source_data.get("bullish", 0)
                bearish = source_data.get("bearish", 0)
                print(
                    f"  - {source_name.capitalize()}: {source_score:+.1f} ({messages} messages: {bullish}B/{bearish}B)"
                )
            else:
                print(f"  - {source_name.capitalize()}: {source_score:+.1f}")

    print("\n" + "=" * 80)


def test_real_apis():
    """Test real API calls with available services."""
    print("\n" + "=" * 80)
    print("TESTING REAL API CALLS")
    print("=" * 80)

    aggregator = NewsSentimentAggregator()

    # Test single ticker
    ticker = "AAPL"
    print("\n=== Running Sentiment Analysis Demo ===")

    try:
        sentiment = aggregator.aggregate_sentiment(ticker)
        print(f"Results for {ticker}:")
        print(f"  Combined Score: {sentiment.score:+.1f}")
        print(f"  Confidence: {sentiment.confidence}")
        print("\n  Source Breakdown:")

        for source_name, source_data in sentiment.sources.items():
            score = source_data.get("score", 0)
            articles = source_data.get("articles", 0)
            messages = source_data.get("messages", 0)
            error = source_data.get("error")

            if error:
                print(f"    {source_name.capitalize()}: ERROR - {error}")
            elif articles > 0:
                print(f"    {source_name.capitalize()}: {score:+.1f} ({articles} articles)")
            elif messages > 0:
                print(f"    {source_name.capitalize()}: {score:+.1f} ({messages} messages)")
            else:
                print(f"    {source_name.capitalize()}: {score:+.1f} (no data)")

    except Exception as e:
        print(f"  Error during test: {e}")

    print("\n" + "=" * 80)


def show_integration_guide():
    """Show how to integrate with trading system."""
    print("\n" + "=" * 80)
    print("INTEGRATION GUIDE")
    print("=" * 80)

    integration_code = """
# Integration with Trading System

from src.utils.news_sentiment import NewsSentimentAnalyzer

# Initialize aggregator (add API key to .env first)
aggregator = NewsSentimentAggregator()

# Get sentiment for watchlist tickers
watchlist = ["SPY", "QQQ", "VOO", "NVDA", "GOOGL", "AMZN"]
report = aggregator.analyze_tickers(watchlist)

# Use in pre-market analysis
for ticker, sentiment in report.sentiment_by_ticker.items():
    if sentiment.score > 60 and sentiment.confidence == "high":
        print(f"STRONG BUY signal for {ticker}")
    elif sentiment.score < -60 and sentiment.confidence == "high":
        print(f"STRONG SELL signal for {ticker}")
    elif abs(sentiment.score) < 20:
        print(f"NEUTRAL - Hold {ticker}")

# Save daily report
filepath = aggregator.save_report(report)
print(f"Report saved to: {filepath}")

# Example output format:
# {
#   "meta": {
#     "date": "2025-11-09",
#     "sources": ["yahoo", "stocktwits", "alphavantage"],
#     "tickers_analyzed": 6
#   },
#   "sentiment_by_ticker": {
#     "SPY": {
#       "ticker": "SPY",
#       "score": 65.0,
#       "confidence": "high",
#       "sources": {...}
#     }
#   }
# }
"""

    print(integration_code)
    print("=" * 80)


def show_api_setup():
    """Show API setup instructions."""
    print("\n" + "=" * 80)
    print("API SETUP INSTRUCTIONS")
    print("=" * 80)

    setup_instructions = """
1. ALPHA VANTAGE (REQUIRED for best results)
   - Get free API key: https://www.alphavantage.co/support/#api-key
   - Free tier: 25 requests/day (enough for pre-market analysis)
   - Add to .env:
     ALPHA_VANTAGE_API_KEY=your_key_here

2. YAHOO FINANCE (Built-in via yfinance)
   - No API key needed
   - Uses yfinance library
   - Free unlimited access
   - Provides: News headlines, basic sentiment

3. STOCKTWITS (Public API)
   - No API key needed for public data
   - Free tier: 200 requests/hour
   - Provides: Social trading sentiment
   - Note: May rate limit during high usage

RECOMMENDED WORKFLOW:
- Run sentiment analysis once per day BEFORE market open
- Use Alpha Vantage for your core holdings (SPY, QQQ, VOO, etc.)
- Yahoo + Stocktwits for growth stocks (NVDA, GOOGL, AMZN)
- Save reports to data/sentiment/ directory
- Review sentiment trends over time

COST: $0/month (all free tiers)
"""

    print(setup_instructions)
    print("=" * 80)


def main():
    """Run complete demo."""
    print("\n" + "=" * 80)
    print("NEWS SENTIMENT AGGREGATOR - COMPREHENSIVE DEMO")
    print("=" * 80)

    # Show example output format
    create_mock_report()

    # Test real APIs if available
    test_real_apis()

    # Show integration guide
    show_integration_guide()

    # Show API setup
    show_api_setup()

    print("\n" + "=" * 80)
    print("DEMO COMPLETE")
    print("=" * 80)
    print("\nNext Steps:")
    print("1. Add ALPHA_VANTAGE_API_KEY to .env file")
    print("2. Run: python3 -m src.utils.news_sentiment --test")
    print("3. Integrate with CoreStrategy for pre-market analysis")
    print("4. Monitor sentiment trends in data/sentiment/ directory")
    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
