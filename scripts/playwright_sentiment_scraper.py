#!/usr/bin/env python3
"""Playwright Sentiment Scraper CLI - Dynamic web scraping for trading sentiment.

This script uses Playwright MCP to scrape sentiment from:
- Reddit (r/wallstreetbets, r/stocks, r/investing, etc.)
- YouTube (financial channels and search results)
- Bogleheads (investment forum discussions)

Usage:
    # Scrape all sources for SPY and QQQ
    python scripts/playwright_sentiment_scraper.py --tickers SPY QQQ

    # Scrape only Reddit
    python scripts/playwright_sentiment_scraper.py --sources reddit --tickers SPY QQQ NVDA

    # Export to JSON
    python scripts/playwright_sentiment_scraper.py --tickers SPY --export-json data/sentiment/output.json

    # Verbose output with all mentions
    python scripts/playwright_sentiment_scraper.py --tickers SPY QQQ --verbose
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.integrations.playwright_mcp.scraper import (
    AggregatedSentiment,
    DataSource,
    SentimentScraper,
    SentimentSignal,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Scrape sentiment from web sources using Playwright MCP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Basic usage - scrape all sources for SPY
    python scripts/playwright_sentiment_scraper.py --tickers SPY

    # Multiple tickers, Reddit only
    python scripts/playwright_sentiment_scraper.py --sources reddit --tickers SPY QQQ NVDA

    # Export results to JSON
    python scripts/playwright_sentiment_scraper.py --tickers SPY --export-json output.json

    # Verbose output with top mentions
    python scripts/playwright_sentiment_scraper.py --tickers SPY QQQ --verbose
        """,
    )

    parser.add_argument(
        "--tickers",
        "-t",
        nargs="+",
        required=True,
        help="Ticker symbols to search for (e.g., SPY QQQ NVDA)",
    )

    parser.add_argument(
        "--sources",
        "-s",
        nargs="+",
        choices=["reddit", "youtube", "bogleheads", "all"],
        default=["all"],
        help="Data sources to scrape (default: all)",
    )

    parser.add_argument(
        "--export-json",
        "-j",
        type=str,
        help="Export results to JSON file",
    )

    parser.add_argument(
        "--export-csv",
        "-c",
        type=str,
        help="Export results to CSV file",
    )

    parser.add_argument(
        "--max-posts",
        "-m",
        type=int,
        default=50,
        help="Maximum posts to scrape per source (default: 50)",
    )

    parser.add_argument(
        "--scroll-depth",
        type=int,
        default=3,
        help="Number of scroll iterations for more content (default: 3)",
    )

    parser.add_argument(
        "--subreddits",
        nargs="+",
        default=None,
        help="Specific subreddits to scrape (default: wallstreetbets, stocks, investing)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output with top mentions",
    )

    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Quiet mode - only output JSON/CSV",
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Run browser in headless mode (default: True)",
    )

    parser.add_argument(
        "--no-headless",
        action="store_false",
        dest="headless",
        help="Run browser with visible window",
    )

    return parser.parse_args()


def get_sentiment_emoji(signal: SentimentSignal) -> str:
    """Get emoji for sentiment signal."""
    return {
        SentimentSignal.BULLISH: "🟢",
        SentimentSignal.BEARISH: "🔴",
        SentimentSignal.NEUTRAL: "🟡",
    }.get(signal, "⚪")


def format_sentiment_score(score: float) -> str:
    """Format weighted score with color indicator."""
    if score > 0.3:
        return f"↑{score:+.2f}"
    elif score < -0.3:
        return f"↓{score:+.2f}"
    else:
        return f"→{score:+.2f}"


def print_results_table(
    results: dict[str, AggregatedSentiment],
    verbose: bool = False,
) -> None:
    """Print results in a formatted table."""
    print("\n" + "=" * 60)
    print("TOP MENTIONED TICKERS")
    print("=" * 60)

    # Sort by total mentions
    sorted_tickers = sorted(
        results.items(),
        key=lambda x: x[1].total_mentions,
        reverse=True,
    )

    for ticker, sentiment in sorted_tickers:
        if sentiment.total_mentions == 0:
            continue

        # Determine overall signal
        if sentiment.bullish_count > sentiment.bearish_count:
            signal = SentimentSignal.BULLISH
        elif sentiment.bearish_count > sentiment.bullish_count:
            signal = SentimentSignal.BEARISH
        else:
            signal = SentimentSignal.NEUTRAL

        emoji = get_sentiment_emoji(signal)
        score_str = format_sentiment_score(sentiment.weighted_score)
        sources_str = ", ".join(s.value for s in sentiment.sources)

        print(
            f"{emoji} {ticker:6} | "
            f"Mentions: {sentiment.total_mentions:3} | "
            f"Bull: {sentiment.bullish_count:2} Bear: {sentiment.bearish_count:2} | "
            f"Score: {score_str} | "
            f"Sources: {sources_str}"
        )

        if verbose and sentiment.top_mentions:
            print("   Top mentions:")
            for mention in sentiment.top_mentions[:3]:
                title_preview = (
                    mention.title[:50] + "..." if len(mention.title) > 50 else mention.title
                )
                print(
                    f"      - [{mention.source.value}] {title_preview} "
                    f"(↑{mention.upvotes} 💬{mention.comments})"
                )

    print("=" * 60)


def print_summary(results: dict[str, AggregatedSentiment]) -> None:
    """Print summary statistics."""
    total_mentions = sum(r.total_mentions for r in results.values())
    bullish_total = sum(r.bullish_count for r in results.values())
    bearish_total = sum(r.bearish_count for r in results.values())

    print("\n📊 SUMMARY")
    print("-" * 40)
    print(f"Total mentions found: {total_mentions}")
    print(f"Bullish signals: {bullish_total} ({bullish_total / max(total_mentions, 1) * 100:.1f}%)")
    print(f"Bearish signals: {bearish_total} ({bearish_total / max(total_mentions, 1) * 100:.1f}%)")

    # Most bullish/bearish tickers
    if results:
        most_bullish = max(results.items(), key=lambda x: x[1].weighted_score)
        most_bearish = min(results.items(), key=lambda x: x[1].weighted_score)

        if most_bullish[1].total_mentions > 0:
            print(f"Most bullish: {most_bullish[0]} (score: {most_bullish[1].weighted_score:+.2f})")
        if most_bearish[1].total_mentions > 0:
            print(f"Most bearish: {most_bearish[0]} (score: {most_bearish[1].weighted_score:+.2f})")


def export_to_json(
    results: dict[str, AggregatedSentiment],
    filepath: str,
) -> None:
    """Export results to JSON file."""
    output_path = Path(filepath)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    export_data = {
        "timestamp": datetime.now().isoformat(),
        "tickers": {},
    }

    for ticker, sentiment in results.items():
        export_data["tickers"][ticker] = {
            "total_mentions": sentiment.total_mentions,
            "bullish_count": sentiment.bullish_count,
            "bearish_count": sentiment.bearish_count,
            "neutral_count": sentiment.neutral_count,
            "avg_confidence": sentiment.avg_confidence,
            "weighted_score": sentiment.weighted_score,
            "sources": [s.value for s in sentiment.sources],
            "top_mentions": [
                {
                    "source": m.source.value,
                    "title": m.title,
                    "url": m.url,
                    "sentiment": m.sentiment.value,
                    "confidence": m.confidence,
                    "upvotes": m.upvotes,
                    "comments": m.comments,
                }
                for m in sentiment.top_mentions
            ],
        }

    output_path.write_text(json.dumps(export_data, indent=2))
    print(f"\n✅ Results exported to: {output_path}")


def export_to_csv(
    results: dict[str, AggregatedSentiment],
    filepath: str,
) -> None:
    """Export results to CSV file."""
    output_path = Path(filepath)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["ticker,total_mentions,bullish,bearish,neutral,weighted_score,sources"]

    for ticker, sentiment in results.items():
        sources = ";".join(s.value for s in sentiment.sources)
        lines.append(
            f"{ticker},{sentiment.total_mentions},{sentiment.bullish_count},"
            f"{sentiment.bearish_count},{sentiment.neutral_count},"
            f"{sentiment.weighted_score:.4f},{sources}"
        )

    output_path.write_text("\n".join(lines))
    print(f"\n✅ Results exported to: {output_path}")


async def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Configure logging based on verbosity
    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
    elif args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Parse sources
    if "all" in args.sources:
        sources = list(DataSource)
    else:
        sources = [DataSource(s) for s in args.sources]

    # Normalize tickers
    tickers = [t.upper() for t in args.tickers]

    if not args.quiet:
        print(f"\n🔍 Scraping sentiment for: {', '.join(tickers)}")
        print(f"📡 Sources: {', '.join(s.value for s in sources)}")
        print("-" * 40)

    try:
        # Create scraper and run
        scraper = SentimentScraper(
            max_posts_per_source=args.max_posts,
            scroll_depth=args.scroll_depth,
        )

        # Override client headless setting
        scraper.client.headless = args.headless

        results = await scraper.scrape_all(tickers, sources)

        # Output results
        if not args.quiet:
            print_results_table(results, verbose=args.verbose)
            print_summary(results)

        # Export if requested
        if args.export_json:
            export_to_json(results, args.export_json)

        if args.export_csv:
            export_to_csv(results, args.export_csv)

        return 0

    except KeyboardInterrupt:
        print("\n\n⚠️ Scraping interrupted by user")
        return 1
    except Exception as e:
        logger.error("Scraping failed: %s", e)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
