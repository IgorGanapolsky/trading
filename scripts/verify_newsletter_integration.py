#!/usr/bin/env python3
"""
Verify newsletter integration end-to-end
Tests: MCP file reading, RSS parsing, signal extraction
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.newsletter_analyzer import (
    NewsletterAnalyzer,
    get_all_signals,
    get_btc_signal,
    get_eth_signal,
)


def print_header(title):
    """Print formatted section header"""
    print(f"\n{'=' * 80}")
    print(f"{title:^80}")
    print(f"{'=' * 80}\n")


def test_existing_mcp_files():
    """Test reading existing MCP-populated files"""
    print_header("TEST 1: Reading Existing MCP Files")

    analyzer = NewsletterAnalyzer()
    signals = analyzer.get_latest_signals(max_age_days=7)

    if signals:
        print(f"✅ Found {len(signals)} signals from MCP files\n")

        for ticker, signal in signals.items():
            print(f"{'─' * 80}")
            print(f"  {ticker} Signal")
            print(f"{'─' * 80}")
            print(f"  Sentiment:   {signal.sentiment.upper()} ({signal.confidence:.0%} confidence)")
            print(
                f"  Source Date: {signal.source_date.strftime('%Y-%m-%d %H:%M:%S') if signal.source_date else 'Unknown'}"
            )

            if signal.entry_price:
                print(f"  Entry:       ${signal.entry_price:,.0f}")
            if signal.target_price:
                print(f"  Target:      ${signal.target_price:,.0f}")
            if signal.stop_loss:
                print(f"  Stop Loss:   ${signal.stop_loss:,.0f}")
            if signal.timeframe:
                print(f"  Timeframe:   {signal.timeframe}")
            if signal.reasoning:
                reasoning = signal.reasoning.replace("\n", " ")[:150]
                print(f"  Reasoning:   {reasoning}...")
            print()

        return True
    else:
        print("❌ No signals found from MCP files")
        print("Expected file location: data/newsletter_signals/newsletter_signals_YYYY-MM-DD.json")
        return False


def test_convenience_functions():
    """Test quick-access convenience functions"""
    print_header("TEST 2: Convenience Functions")

    btc = get_btc_signal(max_age_days=7)
    eth = get_eth_signal(max_age_days=7)

    if btc:
        print(f"✅ BTC Signal: {btc.sentiment.upper()} ({btc.confidence:.0%})")
    else:
        print("⚠️  BTC: No signal available")

    if eth:
        print(f"✅ ETH Signal: {eth.sentiment.upper()} ({eth.confidence:.0%})")
    else:
        print("⚠️  ETH: No signal available")

    return btc is not None or eth is not None


def test_rss_fallback():
    """Test RSS feed parsing fallback"""
    print_header("TEST 3: RSS Feed Fallback (Live Network Test)")

    print("📡 Attempting to fetch CoinSnacks RSS feed...")
    print("(This requires internet connection and feedparser package)\n")

    try:
        analyzer = NewsletterAnalyzer()

        # Force RSS parsing by checking the method directly
        signals = analyzer._parse_rss_feed(max_age_days=7)

        if signals:
            print(f"✅ RSS parsing successful! Extracted {len(signals)} signals\n")

            for ticker, signal in signals.items():
                print(
                    f"  {ticker}: {signal.sentiment.upper()} ({signal.confidence:.0%} confidence)"
                )

            return True
        else:
            print("⚠️  RSS feed accessible but no crypto signals found in recent articles")
            print("This is normal if CoinSnacks hasn't published BTC/ETH analysis recently")
            return True  # Not a failure, just no signals

    except Exception as e:
        print(f"❌ RSS fallback failed: {e}")
        print("Possible causes:")
        print("  - feedparser package not installed (pip install feedparser)")
        print("  - Network connectivity issue")
        print("  - CoinSnacks RSS feed URL changed")
        return False


def test_signal_freshness():
    """Check how fresh the signals are"""
    print_header("TEST 4: Signal Freshness Check")

    signals = get_all_signals(max_age_days=7)

    if not signals:
        print("⚠️  No signals available to check freshness")
        return False

    now = datetime.now(timezone.utc)

    for ticker, signal in signals.items():
        if signal.source_date:
            age = now - signal.source_date
            age_hours = age.total_seconds() / 3600
            age_days = age.days

            age_str = f"{age_hours:.1f} hours ago" if age_days == 0 else f"{age_days} days ago"

            freshness = "✅ FRESH" if age_days < 2 else "⚠️  STALE"
            print(f"{ticker}: {freshness} - {age_str}")
        else:
            print(f"{ticker}: ⚠️  No timestamp available")

    return True


def test_integration_readiness():
    """Test if system is ready for weekend crypto trading"""
    print_header("TEST 5: Weekend Crypto Trading Integration")

    btc = get_btc_signal(max_age_days=7)
    eth = get_eth_signal(max_age_days=7)

    issues = []

    # Check if we have signals
    if not btc and not eth:
        issues.append("❌ No crypto signals available for trading")

    # Check BTC signal completeness
    if btc:
        if btc.confidence < 0.5:
            issues.append(f"⚠️  BTC confidence low ({btc.confidence:.0%})")
        if not btc.sentiment:
            issues.append("❌ BTC missing sentiment")

    # Check ETH signal completeness
    if eth:
        if eth.confidence < 0.5:
            issues.append(f"⚠️  ETH confidence low ({eth.confidence:.0%})")
        if not eth.sentiment:
            issues.append("❌ ETH missing sentiment")

    if issues:
        print("Integration Status: ⚠️  ISSUES FOUND\n")
        for issue in issues:
            print(f"  {issue}")
        print("\nRecommendation: System can still trade, but may need manual review")
        return False
    else:
        print("Integration Status: ✅ READY FOR WEEKEND CRYPTO TRADING\n")
        print("Newsletter signals are available and ready for crypto_strategy.py to consume")
        print("\nNext Steps:")
        print("  1. crypto_strategy.py will call get_btc_signal() and get_eth_signal()")
        print("  2. Combine newsletter signals (30%) with MACD/RSI indicators (70%)")
        print("  3. Execute BTC or ETH weekend trades based on combined signal")
        return True


def main():
    """Run all verification tests"""
    print("\n" + "=" * 80)
    print("NEWSLETTER INTEGRATION - END-TO-END VERIFICATION")
    print("=" * 80)
    print(f"\nTest Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Run tests
    results = {
        "MCP Files": test_existing_mcp_files(),
        "Convenience Functions": test_convenience_functions(),
        "RSS Fallback": test_rss_fallback(),
        "Signal Freshness": test_signal_freshness(),
        "Integration Ready": test_integration_readiness(),
    }

    # Summary
    print_header("TEST SUMMARY")

    passed = sum(1 for result in results.values() if result)
    total = len(results)

    for test_name, passed_test in results.items():
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"{status:12} {test_name}")

    print(f"\n{'─' * 80}")
    print(f"Results: {passed}/{total} tests passed ({passed / total:.0%})")
    print(f"{'─' * 80}\n")

    if passed == total:
        print("🎉 ALL TESTS PASSED - Newsletter integration fully functional!")
        return 0
    elif passed >= total * 0.6:
        print("⚠️  PARTIAL SUCCESS - Core functionality works, some issues detected")
        return 0
    else:
        print("❌ INTEGRATION ISSUES - Multiple tests failed, manual review needed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
