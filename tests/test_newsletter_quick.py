#!/usr/bin/env python3
"""Quick test of newsletter analyzer"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.utils.newsletter_analyzer import (
    get_all_signals,
    get_btc_signal,
    get_eth_signal,
)


def main():
    print("=" * 80)
    print("NEWSLETTER ANALYZER QUICK TEST")
    print("=" * 80)
    print()

    # Test BTC signal
    print("Testing BTC signal...")
    btc = get_btc_signal(max_age_days=7)
    if btc:
        print("✅ BTC Signal Found:")
        print(f"   Sentiment: {btc.sentiment.upper()}")
        print(f"   Confidence: {btc.confidence:.0%}")
        if btc.target_price:
            print(f"   Target: ${btc.target_price:,.0f}")
        if btc.source_date:
            print(f"   Date: {btc.source_date}")
        if btc.reasoning:
            print(f"   Reasoning: {btc.reasoning[:100]}...")
    else:
        print("❌ No BTC signal found")

    print()

    # Test ETH signal
    print("Testing ETH signal...")
    eth = get_eth_signal(max_age_days=7)
    if eth:
        print("✅ ETH Signal Found:")
        print(f"   Sentiment: {eth.sentiment.upper()}")
        print(f"   Confidence: {eth.confidence:.0%}")
    else:
        print("⚠️  No ETH signal found")

    print()

    # Test all signals
    all_signals = get_all_signals(max_age_days=7)
    print(f"Total signals available: {len(all_signals)}")
    print()

    if all_signals:
        print("✅ Newsletter integration is working!")
        return 0
    else:
        print("❌ No signals available")
        return 1


if __name__ == "__main__":
    sys.exit(main())
