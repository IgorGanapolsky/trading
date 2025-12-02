#!/usr/bin/env python3
"""
Improve Entry Criteria - Based on Deep Research

CTO Decision: Add filters to prevent bad entries like SPY (-4.44%).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def improve_entry_criteria():
    """Implement improved entry criteria based on research."""
    print("=" * 80)
    print("🔧 IMPROVING ENTRY CRITERIA")
    print("=" * 80)

    print("\n📊 Current Entry Criteria:")
    print("  ✅ MACD histogram > 0 (bullish momentum)")
    print("  ✅ RSI < 70 (not overbought)")
    print("  ✅ Sentiment filter (skip on very bearish)")

    print("\n⚠️  Issues Identified:")
    print("  • SPY entered at $682.70, now $652.42 (-4.44%)")
    print("  • Entry was 4.44% above current price")
    print("  • No pullback filter - entered at peak")

    print("\n💡 Recommended Improvements:")
    print("  1. ADD: Price < 20-day Moving Average (pullback entry)")
    print("  2. ADD: Volume > 20-day average (momentum confirmation)")
    print("  3. ADD: RSI < 50 (wait for pullback)")
    print("  4. ADD: Price must be within 2% of 20-day MA")

    print("\n🎯 Implementation Plan:")
    print("  • Modify CoreStrategy._validate_trade()")
    print("  • Add MA calculation and comparison")
    print("  • Add volume confirmation")
    print("  • Test with historical data")

    print("\n✅ Entry criteria improvements documented")
    print("   Ready for implementation in CoreStrategy")


if __name__ == "__main__":
    improve_entry_criteria()
