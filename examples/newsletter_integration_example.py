#!/usr/bin/env python3
"""
Newsletter Integration Example - How to use CoinSnacks signals in trading

This example demonstrates:
1. Fetching latest crypto signals
2. Validating signal quality
3. Using signals in trading decisions
4. Risk management with newsletter targets
"""

import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.newsletter_analyzer import (
    NewsletterAnalyzer,
    get_btc_signal,
    get_eth_signal,
)


def should_trade_crypto(
    ticker: str, min_confidence: float = 0.7, max_signal_age_days: int = 7
) -> tuple[bool, str]:
    """
    Determine if we should trade a crypto based on newsletter signals.

    Args:
        ticker: Crypto ticker (BTC or ETH)
        min_confidence: Minimum confidence threshold (0.0-1.0)
        max_signal_age_days: Maximum age of signal in days

    Returns:
        Tuple of (should_trade, reason)
    """
    # Get signal for ticker
    if ticker == "BTC":
        signal = get_btc_signal(max_age_days=max_signal_age_days)
    elif ticker == "ETH":
        signal = get_eth_signal(max_age_days=max_signal_age_days)
    else:
        return False, f"Unsupported ticker: {ticker}"

    # Check if signal exists
    if not signal:
        return False, f"No newsletter signal found for {ticker}"

    # Check signal age
    signal_age = (datetime.now(signal.source_date.tzinfo) - signal.source_date).days
    if signal_age > max_signal_age_days:
        return False, f"Signal too old ({signal_age} days)"

    # Check confidence
    if signal.confidence < min_confidence:
        return False, f"Confidence too low ({signal.confidence:.2f} < {min_confidence})"

    # Check sentiment
    if signal.sentiment != "bullish":
        return False, f"Not bullish (sentiment: {signal.sentiment})"

    # All checks passed
    reason = (
        f"Newsletter signal: {signal.sentiment} "
        f"(confidence: {signal.confidence:.2f}, "
        f"age: {signal_age} days)"
    )
    return True, reason


def get_trading_parameters(ticker: str) -> dict:
    """
    Get trading parameters from newsletter signal.

    Args:
        ticker: Crypto ticker (BTC or ETH)

    Returns:
        Dictionary with entry_price, target_price, stop_loss
    """
    # Get signal
    if ticker == "BTC":
        signal = get_btc_signal()
    elif ticker == "ETH":
        signal = get_eth_signal()
    else:
        return {}

    if not signal:
        return {}

    # Extract parameters
    return {
        "entry_price": signal.entry_price,
        "target_price": signal.target_price,
        "stop_loss": signal.stop_loss,
        "timeframe": signal.timeframe,
        "sentiment": signal.sentiment,
        "confidence": signal.confidence,
        "reasoning": signal.reasoning,
    }


def calculate_position_size_with_newsletter(
    ticker: str,
    account_value: float,
    max_risk_pct: float = 0.02,  # 2% max risk per trade
) -> float:
    """
    Calculate position size using newsletter stop-loss.

    Args:
        ticker: Crypto ticker
        account_value: Total account value
        max_risk_pct: Maximum risk as percentage of account

    Returns:
        Position size in dollars
    """
    params = get_trading_parameters(ticker)

    if not params.get("entry_price") or not params.get("stop_loss"):
        return 0.0

    entry = params["entry_price"]
    stop = params["stop_loss"]

    # Calculate risk per share
    risk_per_unit = abs(entry - stop)

    # Calculate max dollar risk
    max_risk_dollars = account_value * max_risk_pct

    # Calculate position size
    position_size = max_risk_dollars / risk_per_unit

    return position_size


def example_daily_trading_workflow():
    """
    Example: How to integrate newsletter signals into daily trading
    """
    print("\n" + "=" * 80)
    print("DAILY TRADING WORKFLOW - NEWSLETTER INTEGRATION EXAMPLE")
    print("=" * 80)

    # Example account parameters
    account_value = 100000  # $100k
    cryptos_to_check = ["BTC", "ETH"]

    print(f"\nAccount Value: ${account_value:,.0f}")
    print(f"Cryptos to Check: {', '.join(cryptos_to_check)}")
    print(f"Max Risk per Trade: 2% (${account_value * 0.02:,.0f})")

    print("\n" + "-" * 80)
    print("CHECKING NEWSLETTER SIGNALS")
    print("-" * 80)

    for ticker in cryptos_to_check:
        print(f"\n{ticker}:")

        # Check if we should trade
        should_trade, reason = should_trade_crypto(ticker, min_confidence=0.7)
        print(f"  Should Trade: {should_trade}")
        print(f"  Reason: {reason}")

        if should_trade:
            # Get trading parameters
            params = get_trading_parameters(ticker)

            print("\n  Trading Parameters:")
            if params.get("entry_price"):
                print(f"    Entry: ${params['entry_price']:,.0f}")
            if params.get("target_price"):
                print(f"    Target: ${params['target_price']:,.0f}")
            if params.get("stop_loss"):
                print(f"    Stop Loss: ${params['stop_loss']:,.0f}")
            if params.get("timeframe"):
                print(f"    Timeframe: {params['timeframe']}")

            # Calculate position size
            if params.get("entry_price") and params.get("stop_loss"):
                position_size = calculate_position_size_with_newsletter(ticker, account_value)
                print(f"\n  Calculated Position Size: ${position_size:,.0f}")

                # Calculate risk/reward
                entry = params["entry_price"]
                target = params.get("target_price")
                stop = params["stop_loss"]

                risk = abs(entry - stop)
                reward = abs(target - entry) if target else 0

                if risk > 0:
                    rr_ratio = reward / risk
                    print(f"  Risk/Reward Ratio: {rr_ratio:.2f}")

            # Show reasoning
            if params.get("reasoning"):
                print("\n  Newsletter Reasoning:")
                print(f"    {params['reasoning'][:150]}...")


def example_risk_management():
    """
    Example: Using newsletter signals for risk management
    """
    print("\n" + "=" * 80)
    print("RISK MANAGEMENT - NEWSLETTER INTEGRATION EXAMPLE")
    print("=" * 80)

    analyzer = NewsletterAnalyzer()
    signals = analyzer.get_latest_signals(max_age_days=7)

    if not signals:
        print("\nNo signals available for risk management demo")
        return

    print(f"\nFound {len(signals)} newsletter signal(s)")

    for ticker, signal in signals.items():
        print(f"\n{ticker} Risk Assessment:")
        print(f"  Sentiment: {signal.sentiment.upper()}")
        print(f"  Confidence: {signal.confidence:.2%}")

        if signal.stop_loss and signal.entry_price:
            risk = abs(signal.entry_price - signal.stop_loss)
            risk_pct = (risk / signal.entry_price) * 100
            print(f"  Risk per Unit: ${risk:,.0f} ({risk_pct:.1f}%)")

        if signal.target_price and signal.entry_price:
            reward = abs(signal.target_price - signal.entry_price)
            reward_pct = (reward / signal.entry_price) * 100
            print(f"  Reward per Unit: ${reward:,.0f} ({reward_pct:.1f}%)")

        if signal.stop_loss and signal.target_price and signal.entry_price:
            risk = abs(signal.entry_price - signal.stop_loss)
            reward = abs(signal.target_price - signal.entry_price)
            rr_ratio = reward / risk if risk > 0 else 0
            print(f"  Risk/Reward Ratio: {rr_ratio:.2f}")

            if rr_ratio >= 2.0:
                print("  ✅ GOOD SETUP: Risk/reward >= 2:1")
            elif rr_ratio >= 1.5:
                print("  ⚠️  ACCEPTABLE: Risk/reward >= 1.5:1")
            else:
                print("  ❌ POOR SETUP: Risk/reward < 1.5:1")


def example_signal_monitoring():
    """
    Example: Monitoring signal freshness and quality
    """
    print("\n" + "=" * 80)
    print("SIGNAL MONITORING - NEWSLETTER INTEGRATION EXAMPLE")
    print("=" * 80)

    NewsletterAnalyzer()

    # Check signal freshness
    for ticker in ["BTC", "ETH"]:
        print(f"\n{ticker} Signal Status:")

        # Try different age thresholds
        for max_age in [1, 3, 7, 14]:
            if ticker == "BTC":
                signal = get_btc_signal(max_age_days=max_age)
            else:
                signal = get_eth_signal(max_age_days=max_age)

            if signal:
                age = (datetime.now(signal.source_date.tzinfo) - signal.source_date).days
                print(f"  ✅ Signal found (age: {age} days, confidence: {signal.confidence:.2f})")
                break
            elif max_age == 14:
                print(f"  ❌ No signal found (checked last {max_age} days)")


def main():
    """Run all examples"""
    print("\n" + "=" * 80)
    print("NEWSLETTER ANALYZER - INTEGRATION EXAMPLES")
    print("=" * 80)

    example_daily_trading_workflow()
    example_risk_management()
    example_signal_monitoring()

    print("\n" + "=" * 80)
    print("EXAMPLES COMPLETE")
    print("=" * 80)
    print("\nNext Steps:")
    print("1. Review docs/newsletter_analyzer_integration.md")
    print("2. Integrate into your trading script (autonomous_trader.py)")
    print("3. Set up weekly MCP task to populate signals")
    print("4. Monitor signal quality and adjust confidence thresholds")


if __name__ == "__main__":
    main()
