#!/usr/bin/env python3
"""
Test script for NewsletterAnalyzer - demonstrates CoinSnacks signal extraction

Tests both:
1. Reading MCP-populated JSON files
2. Parsing article content for signals
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.newsletter_analyzer import (
    NewsletterAnalyzer,
    get_btc_signal,
    get_eth_signal,
)


def test_article_parsing():
    """Test parsing of sample newsletter article"""
    print("\n" + "=" * 80)
    print("TEST 1: Article Parsing")
    print("=" * 80)

    sample_article = """
    Bitcoin Bullish Breakout Analysis - November 17, 2025

    BTC is showing strong bullish momentum above the key $45,000 support level.
    Technical indicators are aligning for a potential breakout:

    - RSI at 42 (oversold conditions)
    - MACD crossing bullish on the 4H chart
    - Volume increasing on upward moves
    - Golden cross forming on daily timeframe

    Trade Setup:
    Entry: $45,500 (current support hold)
    Target 1: $48,000 (previous resistance)
    Target 2: $52,000 (major psychological level)
    Stop Loss: $43,000 (below key support)

    This is a medium-term swing trade with high probability setup.
    Risk/reward ratio of 1:3 makes this attractive for position building.

    Ethereum Analysis:

    ETH facing headwinds at $2,400 resistance. Volume declining and
    RSI showing bearish divergence. Potential retest of $2,100 support
    zone. Waiting for confirmation before entry.

    Recommendation: Caution on ETH, bullish on BTC.
    """

    analyzer = NewsletterAnalyzer()
    signals = analyzer.parse_article(sample_article)

    print(f"\nExtracted {len(signals)} signals from article:\n")

    for ticker, signal in signals.items():
        print(f"{ticker} Signal:")
        print(f"  Sentiment: {signal.sentiment.upper()} (confidence: {signal.confidence:.2f})")
        if signal.entry_price:
            print(f"  Entry: ${signal.entry_price:,.0f}")
        if signal.target_price:
            print(f"  Target: ${signal.target_price:,.0f}")
        if signal.stop_loss:
            print(f"  Stop Loss: ${signal.stop_loss:,.0f}")
        if signal.timeframe:
            print(f"  Timeframe: {signal.timeframe}")
        if signal.reasoning:
            print(f"  Reasoning: {signal.reasoning[:150]}...")
        print()


def test_mcp_file_reading():
    """Test reading MCP-populated JSON files"""
    print("\n" + "=" * 80)
    print("TEST 2: MCP-Populated File Reading")
    print("=" * 80)

    analyzer = NewsletterAnalyzer()

    # Try to load latest signals
    signals = analyzer.get_latest_signals(max_age_days=30)

    if signals:
        print(f"\nLoaded {len(signals)} signals from MCP files:\n")
        for ticker, signal in signals.items():
            print(f"{ticker} Signal (from {signal.source_date.strftime('%Y-%m-%d')}):")
            print(f"  Sentiment: {signal.sentiment.upper()} (confidence: {signal.confidence:.2f})")
            if signal.entry_price:
                print(f"  Entry: ${signal.entry_price:,.0f}")
            if signal.target_price:
                print(f"  Target: ${signal.target_price:,.0f}")
            print()
    else:
        print("\nNo MCP-populated signals found.")
        print(
            "To populate, create files in: data/newsletter_signals/newsletter_signals_YYYY-MM-DD.json"
        )
        print("See data/newsletter_signals/newsletter_signals_example.json for format")


def test_convenience_functions():
    """Test convenience functions for quick access"""
    print("\n" + "=" * 80)
    print("TEST 3: Convenience Functions")
    print("=" * 80)

    btc_signal = get_btc_signal(max_age_days=30)
    eth_signal = get_eth_signal(max_age_days=30)

    if btc_signal:
        print(f"\nBTC: {btc_signal.sentiment.upper()} ({btc_signal.confidence:.2f} confidence)")
    else:
        print("\nBTC: No signal available")

    if eth_signal:
        print(f"ETH: {eth_signal.sentiment.upper()} ({eth_signal.confidence:.2f} confidence)")
    else:
        print("ETH: No signal available")


def test_signal_persistence():
    """Test saving and loading signals"""
    print("\n" + "=" * 80)
    print("TEST 4: Signal Persistence")
    print("=" * 80)

    analyzer = NewsletterAnalyzer()

    # Parse sample article
    sample_article = """
    BTC breaking above $46k resistance with strong volume.
    Target: $50k. Stop loss: $44k. This is a bullish short-term trade.
    """

    signals = analyzer.parse_article(sample_article)

    if signals:
        # Save signals
        file_path = analyzer.save_signals(signals)
        print(f"\nSaved signals to: {file_path}")

        # Reload to verify
        reloaded_signals = analyzer.get_latest_signals(max_age_days=1)
        if reloaded_signals:
            print(f"Successfully reloaded {len(reloaded_signals)} signals")
        else:
            print("WARNING: Could not reload saved signals")
    else:
        print("\nNo signals extracted from sample article")


def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("COINSNACKS NEWSLETTER ANALYZER - TEST SUITE")
    print("=" * 80)

    test_article_parsing()
    test_mcp_file_reading()
    test_convenience_functions()
    test_signal_persistence()

    print("\n" + "=" * 80)
    print("TESTS COMPLETE")
    print("=" * 80)
    print("\nIntegration Instructions:")
    print("1. In Claude Desktop: Use MCP RSS tool to fetch CoinSnacks articles")
    print(
        "2. Extract signals and save to: data/newsletter_signals/newsletter_signals_YYYY-MM-DD.json"
    )
    print("3. Trading script calls: get_btc_signal() or get_eth_signal()")
    print("4. Fallback: RSS parsing happens automatically if no MCP files found")


if __name__ == "__main__":
    main()
