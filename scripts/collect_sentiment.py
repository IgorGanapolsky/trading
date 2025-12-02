#!/usr/bin/env python3
"""
Pre-Market Sentiment Collection Script

Runs at 8:00 AM ET (before 9:35 AM market execution) to collect sentiment
from Reddit and news sources. This ensures fresh sentiment data is available
when strategies execute.

Schedule with cron:
    0 8 * * 1-5 cd /path/to/trading && venv/bin/python scripts/collect_sentiment.py

Or run manually:
    python scripts/collect_sentiment.py
    python scripts/collect_sentiment.py --force-refresh
    python scripts/collect_sentiment.py --test  # Test with minimal data
"""

import argparse
import logging
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.news_sentiment import NewsSentimentAggregator
from src.utils.reddit_sentiment import RedditSentiment

# Optional RAG store ingestion (graceful degradation if not available)
try:
    from rag_store import ingest_news_snapshot, ingest_reddit_snapshot

    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

from src.utils.sentiment_loader import (
    get_market_regime,
    load_latest_sentiment,
    print_sentiment_summary,
)

logger = logging.getLogger(__name__)

if not RAG_AVAILABLE:
    logger.warning("RAG store not available - skipping sentiment ingestion")


def collect_reddit_sentiment(force_refresh: bool = False, test_mode: bool = False) -> bool:
    """
    Collect sentiment from Reddit.

    Args:
        force_refresh: Ignore cache and fetch fresh data
        test_mode: Use minimal data for testing

    Returns:
        True if successful, False otherwise
    """
    logger.info("=" * 80)
    logger.info("COLLECTING REDDIT SENTIMENT")
    logger.info("=" * 80)

    try:
        scraper = RedditSentiment()

        # Configure based on mode
        if test_mode:
            subreddits = ["wallstreetbets"]  # Just one subreddit for testing
            limit_per_sub = 10
        else:
            subreddits = None  # Use defaults
            limit_per_sub = 25

        # Collect sentiment
        sentiment_data = scraper.collect_daily_sentiment(
            subreddits=subreddits,
            limit_per_sub=limit_per_sub,
            force_refresh=force_refresh,
        )

        # Log summary
        meta = sentiment_data.get("meta", {})
        logger.info("✓ Reddit sentiment collected successfully")
        logger.info(f"  Date: {meta.get('date')}")
        logger.info(f"  Total Posts: {meta.get('total_posts')}")
        logger.info(f"  Total Tickers: {meta.get('total_tickers')}")
        logger.info(f"  Subreddits: {', '.join(['r/' + s for s in meta.get('subreddits', [])])}")

        if RAG_AVAILABLE:
            try:
                ingest_reddit_snapshot(sentiment_data)
                logger.info("✓ Reddit sentiment ingested into RAG store")
            except Exception as ingest_error:  # noqa: BLE001
                logger.error(f"Failed to ingest Reddit sentiment: {ingest_error}", exc_info=True)

        return True

    except ValueError as e:
        # Missing API credentials
        logger.error(f"✗ Reddit API credentials not configured: {e}")
        logger.error("  To use Reddit sentiment:")
        logger.error("  1. Create app at: https://www.reddit.com/prefs/apps")
        logger.error("  2. Add REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET to .env")
        return False

    except Exception as e:
        logger.error(f"✗ Failed to collect Reddit sentiment: {e}", exc_info=True)
        return False


def collect_news_sentiment(tickers: list, test_mode: bool = False) -> bool:
    """
    Collect sentiment from financial news sources.

    Args:
        tickers: List of ticker symbols to analyze
        test_mode: Use minimal data for testing

    Returns:
        True if successful, False otherwise
    """
    logger.info("=" * 80)
    logger.info("COLLECTING NEWS SENTIMENT")
    logger.info("=" * 80)

    try:
        aggregator = NewsSentimentAggregator()

        # Configure based on mode
        if test_mode:
            tickers = ["SPY"]  # Just one ticker for testing

        logger.info(f"Analyzing {len(tickers)} tickers: {', '.join(tickers)}")

        # Analyze sentiment
        report = aggregator.analyze_tickers(tickers)

        # Save report
        filepath = aggregator.save_report(report)

        # Log summary
        logger.info("✓ News sentiment collected successfully")
        logger.info(f"  Date: {report.meta['date']}")
        logger.info(f"  Tickers Analyzed: {report.meta['tickers_analyzed']}")
        logger.info(f"  Sources: {', '.join(report.meta['sources'])}")
        logger.info(f"  Saved to: {filepath}")

        if RAG_AVAILABLE:
            try:
                # Convert dataclasses to plain dict for ingestion
                report_dict = {
                    "meta": report.meta,
                    "sentiment_by_ticker": {
                        ticker: asdict(sentiment)
                        for ticker, sentiment in report.sentiment_by_ticker.items()
                    },
                }
                ingest_news_snapshot(report_dict)
                logger.info("✓ News sentiment ingested into RAG store")
            except Exception as ingest_error:  # noqa: BLE001
                logger.error(f"Failed to ingest news sentiment: {ingest_error}", exc_info=True)

        return True

    except Exception as e:
        logger.error(f"✗ Failed to collect news sentiment: {e}", exc_info=True)
        return False


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Collect pre-market sentiment data for trading system"
    )
    parser.add_argument(
        "--force-refresh", action="store_true", help="Ignore cache and fetch fresh data"
    )
    parser.add_argument("--test", action="store_true", help="Test mode - collect minimal data")
    parser.add_argument("--reddit-only", action="store_true", help="Collect only Reddit sentiment")
    parser.add_argument("--news-only", action="store_true", help="Collect only news sentiment")
    parser.add_argument(
        "--tickers",
        type=str,
        default="SPY,QQQ,VOO,NVDA,GOOGL,AMZN,TSLA,MSFT,AAPL",
        help="Comma-separated list of tickers for news analysis",
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("\n" + "=" * 80)
    print("PRE-MARKET SENTIMENT COLLECTION")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if args.test:
        print("MODE: TEST (minimal data)")
    if args.force_refresh:
        print("OPTION: Force refresh (ignore cache)")
    print("=" * 80 + "\n")

    # Parse tickers
    tickers = [t.strip() for t in args.tickers.split(",")]

    # Collect sentiment from sources
    reddit_success = False
    news_success = False

    if not args.news_only:
        reddit_success = collect_reddit_sentiment(
            force_refresh=args.force_refresh, test_mode=args.test
        )
        print()

    if not args.reddit_only:
        news_success = collect_news_sentiment(tickers=tickers, test_mode=args.test)
        print()

    # Summary
    print("=" * 80)
    print("COLLECTION SUMMARY")
    print("=" * 80)

    if not args.news_only:
        status = "✓ SUCCESS" if reddit_success else "✗ FAILED"
        print(f"Reddit Sentiment: {status}")

    if not args.reddit_only:
        status = "✓ SUCCESS" if news_success else "✗ FAILED"
        print(f"News Sentiment: {status}")

    # Load and display combined sentiment
    print()
    print("=" * 80)
    print("COMBINED SENTIMENT DATA")
    print("=" * 80)

    try:
        sentiment_data = load_latest_sentiment()
        print_sentiment_summary(sentiment_data)

        # Show market regime
        market_regime = get_market_regime(sentiment_data)
        print(f"Market Regime: {market_regime.upper()}")

        if market_regime == "risk_off":
            print("⚠️  WARNING: RISK-OFF detected - strategies may skip trades")
        elif market_regime == "risk_on":
            print("✓ RISK-ON: Favorable conditions for growth strategies")
        else:
            print("ℹ️  NEUTRAL: Normal market conditions")

    except Exception as e:
        logger.error(f"Failed to load combined sentiment: {e}")

    print("\n" + "=" * 80)
    print("SENTIMENT COLLECTION COMPLETE")
    print("=" * 80 + "\n")

    # Exit with appropriate code
    overall_success = (reddit_success or args.news_only) and (news_success or args.reddit_only)

    if overall_success:
        logger.info("✓ All sentiment collection completed successfully")
        sys.exit(0)
    else:
        logger.error("✗ Some sentiment collection failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
