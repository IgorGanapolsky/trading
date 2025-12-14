#!/usr/bin/env python3
"""
Test YouTube Sentiment Integration

Verifies that the YouTube sentiment analyzer can extract sentiment from
cached transcripts and analysis files.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.unified_sentiment import UnifiedSentiment


def test_youtube_sentiment():
    """Test YouTube sentiment extraction from cached data."""
    print("\n" + "=" * 80)
    print("YouTube Sentiment Integration Test")
    print("=" * 80)

    # Initialize with only YouTube enabled
    analyzer = UnifiedSentiment(
        enable_news=False, enable_reddit=False, enable_youtube=True
    )

    # Test stocks that should be in cached transcripts
    test_stocks = ["NVDA", "AMZN", "PLTR", "UBER", "TSLA", "AAPL"]

    results = []
    for symbol in test_stocks:
        result = analyzer.get_ticker_sentiment(symbol, use_cache=False)
        yt_data = result["sources"]["youtube"]

        results.append(
            {
                "symbol": symbol,
                "score": yt_data["score"],
                "confidence": yt_data["confidence"],
                "available": yt_data["available"],
                "analyses_found": yt_data["raw_data"].get("analyses_found", 0),
                "total_keywords": yt_data["raw_data"].get("total_keywords", 0),
                "signal": result["signal"],
            }
        )

    # Print results
    print(f"\n{'Symbol':<10} {'Available':<12} {'Score':<10} {'Confidence':<12} {'Signal':<12} {'Sources'}")
    print("-" * 80)

    for r in results:
        available = "✓" if r["available"] and r["analyses_found"] > 0 else "✗"
        print(
            f"{r['symbol']:<10} {available:<12} "
            f"{r['score']:>6.3f}    {r['confidence']:>6.1%}      "
            f"{r['signal']:<12} {r['analyses_found']}"
        )

    # Verify at least some stocks have data
    stocks_with_data = sum(1 for r in results if r["analyses_found"] > 0)

    print("\n" + "=" * 80)
    print(f"Results: {stocks_with_data}/{len(test_stocks)} stocks found in YouTube data")
    print("=" * 80)

    if stocks_with_data > 0:
        print("✓ YouTube sentiment integration is WORKING\n")
        return True
    else:
        print("✗ YouTube sentiment integration FAILED - no data found\n")
        return False


def test_directory_structure():
    """Verify YouTube analysis directories exist."""
    print("\n" + "=" * 80)
    print("Directory Structure Test")
    print("=" * 80)

    dirs = {
        "Analysis output": Path("docs/youtube_analysis"),
        "Cached transcripts": Path("data/youtube_cache"),
    }

    all_exist = True
    for name, path in dirs.items():
        exists = path.exists()
        status = "✓" if exists else "✗"
        print(f"{status} {name}: {path}")
        if exists and path.is_dir():
            file_count = len(list(path.glob("*")))
            print(f"  → {file_count} files")
        all_exist = all_exist and exists

    print("=" * 80)
    if all_exist:
        print("✓ All directories exist\n")
        return True
    else:
        print("✗ Some directories missing\n")
        return False


if __name__ == "__main__":
    dir_test = test_directory_structure()
    sentiment_test = test_youtube_sentiment()

    if dir_test and sentiment_test:
        print("✓ All tests passed!")
        sys.exit(0)
    else:
        print("✗ Some tests failed")
        sys.exit(1)
