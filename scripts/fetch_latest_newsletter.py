#!/usr/bin/env python3
"""
Fetch latest CoinSnacks newsletter and extract crypto signals
Saves signals to data/newsletter_signals/newsletter_signals_YYYY-MM-DD.json
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.newsletter_analyzer import NewsletterAnalyzer


def main():
    print("=" * 80)
    print("FETCHING LATEST COINSNACKS NEWSLETTER")
    print("=" * 80)
    print()

    analyzer = NewsletterAnalyzer()

    print("📡 Parsing CoinSnacks RSS feed...")
    print("URL: https://medium.com/feed/coinsnacks")
    print()

    try:
        # Try RSS feed parsing (will use fallback method)
        signals = analyzer._parse_rss_feed(max_age_days=7)

        if signals:
            print(f"✅ Successfully extracted {len(signals)} signals")
            print()

            # Display signals
            for ticker, signal in signals.items():
                print(f"{'─' * 80}")
                print(f"{ticker} SIGNAL")
                print(f"{'─' * 80}")
                print(
                    f"Sentiment:   {signal.sentiment.upper()} ({signal.confidence:.0%} confidence)"
                )
                print(f"Source Date: {signal.source_date.strftime('%Y-%m-%d %H:%M:%S UTC')}")

                if signal.entry_price:
                    print(f"Entry:       ${signal.entry_price:,.0f}")
                if signal.target_price:
                    print(f"Target:      ${signal.target_price:,.0f}")
                if signal.stop_loss:
                    print(f"Stop Loss:   ${signal.stop_loss:,.0f}")
                if signal.timeframe:
                    print(f"Timeframe:   {signal.timeframe}")
                if signal.reasoning:
                    reasoning = signal.reasoning[:200].replace("\n", " ")
                    print(f"Reasoning:   {reasoning}...")
                print()

            # Save signals
            print("💾 Saving signals...")
            saved_path = analyzer.save_signals(signals)
            print(f"✅ Saved to: {saved_path}")
            print()

            return 0

        else:
            print("⚠️  No crypto signals found in recent CoinSnacks articles")
            print()
            print("Possible reasons:")
            print("  - No recent articles mention BTC or ETH trading signals")
            print("  - Articles are older than 7 days")
            print("  - RSS feed format changed")
            print()
            return 1

    except Exception as e:
        print(f"❌ Error fetching newsletter: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
