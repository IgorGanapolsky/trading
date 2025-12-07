#!/usr/bin/env python3
"""
Sentiment Analyzer Skill - Implementation
Multi-source sentiment analysis for trading signals
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any, Optional

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from dotenv import load_dotenv

load_dotenv()

# Import existing sentiment modules
try:
    from src.utils.news_sentiment import NewsSentimentAggregator
    from src.utils.reddit_sentiment import RedditSentiment
    from src.utils.sentiment_loader import get_ticker_sentiment, load_latest_sentiment

    SENTIMENT_AVAILABLE = True
except ImportError:
    SENTIMENT_AVAILABLE = False
    print("Warning: Sentiment modules not available")


def error_response(error_msg: str, error_code: str = "ERROR") -> dict[str, Any]:
    """Standard error response format"""
    return {"success": False, "error": error_msg, "error_code": error_code}


def success_response(data: Any) -> dict[str, Any]:
    """Standard success response format"""
    return {"success": True, **data}


class SentimentAnalyzer:
    """Multi-source sentiment analysis for trading"""

    def __init__(self):
        """Initialize sentiment analyzers"""
        if SENTIMENT_AVAILABLE:
            self.news_aggregator = NewsSentimentAggregator()
            self.reddit_sentiment = RedditSentiment()
        else:
            self.news_aggregator = None
            self.reddit_sentiment = None

    def analyze_news_sentiment(
        self,
        symbols: list[str],
        time_window_hours: int = 24,
        sources: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Analyze sentiment from financial news

        Args:
            symbols: List of ticker symbols
            time_window_hours: Analysis window in hours
            sources: Specific news sources (optional)

        Returns:
            Dict with sentiment analysis
        """
        try:
            if not self.news_aggregator:
                return error_response("News aggregator not available", "NO_AGGREGATOR")

            sentiment_results = {}
            for symbol in symbols:
                try:
                    ticker_sentiment = self.news_aggregator.aggregate_sentiment(symbol)

                    # Convert to standard format
                    score = (
                        ticker_sentiment.score / 100.0
                        if ticker_sentiment.score > 1.0
                        else ticker_sentiment.score
                    )
                    score = (score - 0.5) * 2  # Convert 0-100 to -1 to +1 scale

                    sentiment_results[symbol] = {
                        "overall_score": score,
                        "label": (
                            "positive" if score > 0.3 else "negative" if score < -0.3 else "neutral"
                        ),
                        "confidence": (
                            0.8
                            if ticker_sentiment.confidence == "high"
                            else 0.6
                            if ticker_sentiment.confidence == "medium"
                            else 0.4
                        ),
                        "article_count": ticker_sentiment.news_count or 0,
                        "breakdown": {
                            "positive": ticker_sentiment.positive_count or 0,
                            "neutral": ticker_sentiment.neutral_count or 0,
                            "negative": ticker_sentiment.negative_count or 0,
                        },
                        "sources": {
                            "yahoo": (
                                ticker_sentiment.yahoo_score / 100.0
                                if ticker_sentiment.yahoo_score
                                else 0.5
                            ),
                            "stocktwits": (
                                ticker_sentiment.stocktwits_score / 100.0
                                if ticker_sentiment.stocktwits_score
                                else 0.5
                            ),
                            "alphavantage": (
                                ticker_sentiment.alpha_vantage_score / 100.0
                                if ticker_sentiment.alpha_vantage_score
                                else 0.5
                            ),
                        },
                        "trends": {
                            "direction": "improving" if score > 0.5 else "declining",
                            "momentum": abs(score) * 0.2,
                        },
                    }
                except Exception as e:
                    sentiment_results[symbol] = {
                        "error": str(e),
                        "overall_score": 0.0,
                        "label": "neutral",
                    }

            return success_response(
                {
                    "sentiment": sentiment_results,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        except Exception as e:
            return error_response(f"Error analyzing news sentiment: {str(e)}", "ANALYSIS_ERROR")

    def analyze_social_sentiment(
        self,
        symbols: list[str],
        platforms: list[str] | None = None,
        time_window_hours: int = 6,
        min_mentions: int = 10,
    ) -> dict[str, Any]:
        """
        Aggregate sentiment from social media platforms

        Args:
            symbols: List of ticker symbols
            platforms: Platforms to analyze (optional)
            time_window_hours: Analysis window
            min_mentions: Minimum mention threshold

        Returns:
            Dict with social sentiment analysis
        """
        try:
            if not self.reddit_sentiment:
                return error_response("Social sentiment not available", "NO_SOCIAL")

            sentiment_results = {}
            for symbol in symbols:
                try:
                    # Get Reddit sentiment
                    reddit_data = self.reddit_sentiment.get_sentiment(symbol)

                    sentiment_results[symbol] = {
                        "overall_score": (
                            reddit_data.get("score", 0.5) / 100.0
                            if reddit_data.get("score", 0) > 1.0
                            else reddit_data.get("score", 0.5)
                        ),
                        "label": (
                            "positive"
                            if reddit_data.get("score", 50) > 60
                            else ("negative" if reddit_data.get("score", 50) < 40 else "neutral")
                        ),
                        "confidence": 0.7,
                        "total_mentions": reddit_data.get("mentions", 0),
                        "platforms": {
                            "reddit": {
                                "score": reddit_data.get("score", 50) / 100.0,
                                "mentions": reddit_data.get("mentions", 0),
                                "trending": reddit_data.get("mentions", 0) > min_mentions,
                            },
                        },
                        "volume_trend": (
                            "increasing"
                            if reddit_data.get("mentions", 0) > min_mentions
                            else "stable"
                        ),
                        "anomalies": [],
                    }
                except Exception as e:
                    sentiment_results[symbol] = {
                        "error": str(e),
                        "overall_score": 0.0,
                        "label": "neutral",
                    }

            return success_response(
                {
                    "sentiment": sentiment_results,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        except Exception as e:
            return error_response(f"Error analyzing social sentiment: {str(e)}", "SOCIAL_ERROR")

    def get_composite_sentiment(
        self,
        symbols: list[str],
        weights: dict[str, float] | None = None,
        include_market_sentiment: bool = True,
    ) -> dict[str, Any]:
        """
        Generate weighted composite sentiment from all sources

        Args:
            symbols: List of ticker symbols
            weights: Custom source weights (optional)
            include_market_sentiment: Include technical indicators

        Returns:
            Dict with composite sentiment
        """
        try:
            # Default weights
            if not weights:
                weights = {
                    "news_sentiment": 0.40,
                    "social_sentiment": 0.30,
                    "market_sentiment": 0.30,
                }

            # Get news sentiment
            news_result = self.analyze_news_sentiment(symbols)
            news_sentiment = news_result.get("sentiment", {}) if news_result.get("success") else {}

            # Get social sentiment
            social_result = self.analyze_social_sentiment(symbols)
            social_sentiment = (
                social_result.get("sentiment", {}) if social_result.get("success") else {}
            )

            composite_results = {}
            for symbol in symbols:
                news_data = news_sentiment.get(symbol, {})
                social_data = social_sentiment.get(symbol, {})

                news_score = news_data.get("overall_score", 0.0)
                social_score = social_data.get("overall_score", 0.0)
                market_score = 0.5  # Neutral default

                # Calculate weighted composite
                composite_score = (
                    news_score * weights["news_sentiment"]
                    + social_score * weights["social_sentiment"]
                    + market_score * weights["market_sentiment"]
                )

                composite_results[symbol] = {
                    "score": composite_score,
                    "label": (
                        "positive"
                        if composite_score > 0.3
                        else "negative"
                        if composite_score < -0.3
                        else "neutral"
                    ),
                    "confidence": 0.8,
                    "components": {
                        "news_sentiment": {
                            "score": news_score,
                            "weight": weights["news_sentiment"],
                            "contribution": news_score * weights["news_sentiment"],
                        },
                        "social_sentiment": {
                            "score": social_score,
                            "weight": weights["social_sentiment"],
                            "contribution": social_score * weights["social_sentiment"],
                        },
                        "market_sentiment": {
                            "score": market_score,
                            "weight": weights["market_sentiment"],
                            "contribution": market_score * weights["market_sentiment"],
                        },
                    },
                    "signal_strength": (
                        "strong"
                        if abs(composite_score) > 0.6
                        else "moderate"
                        if abs(composite_score) > 0.3
                        else "weak"
                    ),
                    "recommendation": (
                        "buy"
                        if composite_score > 0.6
                        else "sell"
                        if composite_score < -0.6
                        else "hold"
                    ),
                    "risk_factors": [],
                }

            return success_response(
                {
                    "composite_sentiment": composite_results,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        except Exception as e:
            return error_response(
                f"Error calculating composite sentiment: {str(e)}", "COMPOSITE_ERROR"
            )

    def detect_sentiment_anomalies(
        self,
        symbols: list[str],
        lookback_hours: int = 72,
        sensitivity: str = "medium",
    ) -> dict[str, Any]:
        """
        Detect unusual sentiment patterns

        Args:
            symbols: List of ticker symbols
            lookback_hours: Historical comparison window
            sensitivity: "low", "medium", "high"

        Returns:
            Dict with detected anomalies
        """
        try:
            # Load historical sentiment
            sentiment_data = load_latest_sentiment()

            anomalies = []
            for symbol in symbols:
                try:
                    current_score, confidence, _ = get_ticker_sentiment(symbol, sentiment_data)
                    current_score_norm = (current_score - 50) / 50.0  # Convert to -1 to +1

                    # Simple anomaly detection: rapid shift detection
                    # In production, would compare with historical data
                    if abs(current_score_norm) > 0.7:
                        anomalies.append(
                            {
                                "symbol": symbol,
                                "type": "extreme_sentiment",
                                "severity": ("high" if sensitivity == "high" else "medium"),
                                "description": f"Sentiment score {current_score_norm:.2f} is extreme",
                                "current_sentiment": current_score_norm,
                                "recommendation": "Monitor closely before trading",
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                except Exception:
                    pass

            return success_response(
                {
                    "anomalies": anomalies,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        except Exception as e:
            return error_response(f"Error detecting anomalies: {str(e)}", "ANOMALY_ERROR")


def main():
    """CLI interface for the skill"""
    parser = argparse.ArgumentParser(description="Sentiment Analyzer Skill")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # analyze_news_sentiment command
    news_parser = subparsers.add_parser("analyze_news_sentiment", help="Analyze news sentiment")
    news_parser.add_argument("--symbols", nargs="+", required=True, help="Ticker symbols")
    news_parser.add_argument(
        "--time-window-hours", type=int, default=24, help="Time window in hours"
    )
    news_parser.add_argument("--sources", nargs="+", help="News sources")

    # analyze_social_sentiment command
    social_parser = subparsers.add_parser(
        "analyze_social_sentiment", help="Analyze social sentiment"
    )
    social_parser.add_argument("--symbols", nargs="+", required=True, help="Ticker symbols")
    social_parser.add_argument("--platforms", nargs="+", help="Platforms to analyze")
    social_parser.add_argument(
        "--time-window-hours", type=int, default=6, help="Time window in hours"
    )

    # get_composite_sentiment command
    composite_parser = subparsers.add_parser(
        "get_composite_sentiment", help="Get composite sentiment"
    )
    composite_parser.add_argument("--symbols", nargs="+", required=True, help="Ticker symbols")
    composite_parser.add_argument(
        "--include-market-sentiment",
        action="store_true",
        help="Include market sentiment",
    )

    # detect_sentiment_anomalies command
    anomaly_parser = subparsers.add_parser(
        "detect_sentiment_anomalies", help="Detect sentiment anomalies"
    )
    anomaly_parser.add_argument("--symbols", nargs="+", required=True, help="Ticker symbols")
    anomaly_parser.add_argument("--lookback-hours", type=int, default=72, help="Lookback window")
    anomaly_parser.add_argument(
        "--sensitivity", choices=["low", "medium", "high"], default="medium"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    analyzer = SentimentAnalyzer()

    if args.command == "analyze_news_sentiment":
        result = analyzer.analyze_news_sentiment(
            symbols=args.symbols,
            time_window_hours=args.time_window_hours,
            sources=args.sources,
        )
    elif args.command == "analyze_social_sentiment":
        result = analyzer.analyze_social_sentiment(
            symbols=args.symbols,
            platforms=args.platforms,
            time_window_hours=args.time_window_hours,
        )
    elif args.command == "get_composite_sentiment":
        result = analyzer.get_composite_sentiment(
            symbols=args.symbols,
            include_market_sentiment=args.include_market_sentiment,
        )
    elif args.command == "detect_sentiment_anomalies":
        result = analyzer.detect_sentiment_anomalies(
            symbols=args.symbols,
            lookback_hours=args.lookback_hours,
            sensitivity=args.sensitivity,
        )
    else:
        print(f"Unknown command: {args.command}")
        return

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
