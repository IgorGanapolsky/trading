#!/usr/bin/env python3
"""
Validate newsletter signal data quality
Checks for common issues like sentiment/reasoning mismatches, invalid price logic
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.newsletter_analyzer import CryptoSignal, NewsletterAnalyzer


def validate_signal(ticker: str, signal: CryptoSignal) -> list[str]:
    """
    Validate a single crypto signal for data quality issues

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    warnings = []

    # Check sentiment vs reasoning consistency
    if signal.sentiment and signal.reasoning:
        reasoning_lower = signal.reasoning.lower()

        bullish_words = [
            "bullish",
            "buy",
            "long",
            "breakout",
            "rally",
            "uptrend",
            "pump",
            "calls",
        ]
        bearish_words = [
            "bearish",
            "sell",
            "short",
            "breakdown",
            "dump",
            "downtrend",
            "crash",
            "puts",
        ]

        bullish_count = sum(1 for word in bullish_words if word in reasoning_lower)
        bearish_count = sum(1 for word in bearish_words if word in reasoning_lower)

        if signal.sentiment == "bullish" and bearish_count > bullish_count:
            errors.append(
                f"❌ Sentiment is 'bullish' but reasoning contains more bearish language ({bearish_count} vs {bullish_count})"
            )
        elif signal.sentiment == "bearish" and bullish_count > bearish_count:
            errors.append(
                f"❌ Sentiment is 'bearish' but reasoning contains more bullish language ({bullish_count} vs {bearish_count})"
            )

    # Check price logic
    if signal.entry_price and signal.target_price:
        if signal.sentiment == "bullish" and signal.target_price <= signal.entry_price:
            errors.append(
                f"❌ Bullish signal but target (${signal.target_price:,.0f}) ≤ entry (${signal.entry_price:,.0f})"
            )
        elif signal.sentiment == "bearish" and signal.target_price >= signal.entry_price:
            errors.append(
                f"❌ Bearish signal but target (${signal.target_price:,.0f}) ≥ entry (${signal.entry_price:,.0f})"
            )

    # Check stop loss logic
    if signal.entry_price and signal.stop_loss:
        if signal.sentiment == "bullish" and signal.stop_loss >= signal.entry_price:
            errors.append(
                f"❌ Bullish signal but stop loss (${signal.stop_loss:,.0f}) ≥ entry (${signal.entry_price:,.0f})"
            )
        elif signal.sentiment == "bearish" and signal.stop_loss <= signal.entry_price:
            errors.append(
                f"❌ Bearish signal but stop loss (${signal.stop_loss:,.0f}) ≤ entry (${signal.entry_price:,.0f})"
            )

    # Check for missing critical fields
    if not signal.entry_price:
        warnings.append("⚠️  Missing entry price")
    if not signal.target_price:
        warnings.append("⚠️  Missing target price")
    if not signal.stop_loss:
        warnings.append("⚠️  Missing stop loss (risk management gap)")
    if not signal.timeframe:
        warnings.append("⚠️  Missing timeframe")

    # Check confidence level
    if signal.confidence < 0.5:
        warnings.append(f"⚠️  Low confidence: {signal.confidence:.0%}")

    # Check signal freshness
    if signal.source_date:
        age = datetime.now(timezone.utc) - signal.source_date
        if age > timedelta(days=3):
            warnings.append(f"⚠️  Stale signal: {age.days} days old")

    return errors, warnings


def validate_all_signals(max_age_days: int = 7) -> bool:
    """
    Validate all available newsletter signals

    Returns:
        True if all signals valid, False if any errors found
    """
    print("=" * 80)
    print("NEWSLETTER SIGNAL VALIDATION")
    print("=" * 80)
    print()

    analyzer = NewsletterAnalyzer()
    signals = analyzer.get_latest_signals(max_age_days)

    if not signals:
        print("⚠️  No signals found to validate")
        print(
            f"Checked: data/newsletter_signals/newsletter_signals_*.json (last {max_age_days} days)"
        )
        print()
        return False

    print(f"Found {len(signals)} signals to validate")
    print()

    all_valid = True
    total_errors = 0
    total_warnings = 0

    for ticker, signal in signals.items():
        print(f"{'─' * 80}")
        print(f"{ticker} VALIDATION")
        print(f"{'─' * 80}")
        print(f"Sentiment:   {signal.sentiment.upper()} ({signal.confidence:.0%} confidence)")
        print(
            f"Source Date: {signal.source_date.strftime('%Y-%m-%d %H:%M:%S UTC') if signal.source_date else 'Unknown'}"
        )

        if signal.entry_price:
            print(f"Entry:       ${signal.entry_price:,.0f}")
        if signal.target_price:
            print(f"Target:      ${signal.target_price:,.0f}")
        if signal.stop_loss:
            print(f"Stop Loss:   ${signal.stop_loss:,.0f}")

        print()

        errors, warnings = validate_signal(ticker, signal)

        if errors:
            print("ERRORS:")
            for error in errors:
                print(f"  {error}")
            print()
            all_valid = False
            total_errors += len(errors)

        if warnings:
            print("WARNINGS:")
            for warning in warnings:
                print(f"  {warning}")
            print()
            total_warnings += len(warnings)

        if not errors and not warnings:
            print("✅ VALID - No issues detected")
            print()

    print("=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    print(f"Total Signals:  {len(signals)}")
    print(f"Total Errors:   {total_errors}")
    print(f"Total Warnings: {total_warnings}")
    print()

    if all_valid and total_warnings == 0:
        print("🎉 ALL SIGNALS VALID - Ready for trading")
        return True
    elif all_valid:
        print("⚠️  SIGNALS VALID but with warnings - Review recommended")
        return True
    else:
        print("❌ VALIDATION FAILED - Fix errors before trading")
        return False


def main():
    """Run validation"""
    is_valid = validate_all_signals(max_age_days=7)
    return 0 if is_valid else 1


if __name__ == "__main__":
    sys.exit(main())
