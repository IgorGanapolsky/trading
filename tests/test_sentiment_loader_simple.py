#!/usr/bin/env python3
"""
Simple Sentiment Loader Test

Tests just the sentiment_loader module without importing heavy dependencies.

Run:
    python tests/test_sentiment_loader_simple.py
"""

import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.sentiment_loader import (
    get_market_regime,
    get_ticker_sentiment,
    is_sentiment_fresh,
    load_latest_sentiment,
    normalize_sentiment_score,
    print_sentiment_summary,
)

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")


def main():
    print("\n" + "=" * 80)
    print("SENTIMENT LOADER SIMPLE TEST")
    print("=" * 80 + "\n")

    # Test 1: Load sentiment data
    print("TEST 1: Loading sentiment data...")
    try:
        sentiment_data = load_latest_sentiment()
        print("✓ Successfully loaded sentiment data")
        print(f"  Date: {sentiment_data['meta']['date']}")
        print(f"  Sources: {', '.join(sentiment_data['meta']['sources'])}")
        print(f"  Tickers: {len(sentiment_data['sentiment_by_ticker'])}")
    except Exception as e:
        print(f"✗ Failed to load sentiment data: {e}")
        return False

    # Test 2: Check freshness
    print("\nTEST 2: Checking data freshness...")
    try:
        is_fresh = is_sentiment_fresh(sentiment_data)
        freshness = sentiment_data["meta"]["freshness"]
        days_old = sentiment_data["meta"]["days_old"]
        print(f"✓ Freshness check: {freshness} ({days_old} days old)")
        print(f"  Is fresh: {is_fresh}")
    except Exception as e:
        print(f"✗ Freshness check failed: {e}")
        return False

    # Test 3: Get ticker sentiment
    print("\nTEST 3: Getting ticker sentiment...")
    test_tickers = ["SPY", "NVDA", "GOOGL", "TSLA", "AAPL"]
    try:
        for ticker in test_tickers:
            score, confidence, regime = get_ticker_sentiment(ticker, sentiment_data)
            print(
                f"  {ticker:<6}: score={score:>6.2f}, confidence={confidence:<6}, regime={regime}"
            )
        print("✓ All ticker lookups succeeded")
    except Exception as e:
        print(f"✗ Ticker lookup failed: {e}")
        return False

    # Test 4: Get market regime
    print("\nTEST 4: Getting market regime...")
    try:
        regime = get_market_regime(sentiment_data)
        print(f"✓ Market regime: {regime.upper()}")
    except Exception as e:
        print(f"✗ Market regime check failed: {e}")
        return False

    # Test 5: Normalization
    print("\nTEST 5: Testing score normalization...")
    try:
        test_cases = [
            ("reddit", 100, 100.0),
            ("reddit", 0, 50.0),
            ("reddit", -100, 0.0),
            ("news", 50, 75.0),
            ("news", -50, 25.0),
        ]
        all_passed = True
        for source, raw, expected in test_cases:
            actual = normalize_sentiment_score(raw, source)
            if abs(actual - expected) < 0.1:
                print(f"  ✓ {source:<12} {raw:>5} → {actual:.1f} (expected {expected:.1f})")
            else:
                print(f"  ✗ {source:<12} {raw:>5} → {actual:.1f} (expected {expected:.1f})")
                all_passed = False

        if all_passed:
            print("✓ All normalization tests passed")
    except Exception as e:
        print(f"✗ Normalization test failed: {e}")
        return False

    # Test 6: Print summary
    print("\nTEST 6: Printing sentiment summary...")
    try:
        print_sentiment_summary(sentiment_data)
        print("✓ Summary printed successfully")
    except Exception as e:
        print(f"✗ Summary print failed: {e}")
        return False

    print("\n" + "=" * 80)
    print("✓ ALL TESTS PASSED")
    print("=" * 80 + "\n")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
