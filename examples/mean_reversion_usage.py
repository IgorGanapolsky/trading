"""
Mean Reversion + Momentum Strategy - Usage Examples

This file demonstrates how to use the regime-aware strategy selection system.
"""

import logging

logging.basicConfig(level=logging.INFO)

# Example 1: Using Mean Reversion Strategy Standalone
# ====================================================


def example_mean_reversion_standalone():
    """Use mean reversion strategy directly on SPY."""
    from src.strategies.mean_reversion_strategy import MeanReversionStrategy

    strategy = MeanReversionStrategy(
        rsi_buy_threshold=10.0,  # Buy when RSI(2) < 10
        rsi_sell_threshold=90.0,  # Sell when RSI(2) > 90
        use_trend_filter=True,  # Only buy above 200 SMA
        use_vix_filter=True,  # Boost confidence when VIX elevated
    )

    # Analyze single symbol
    signal = strategy.analyze("SPY")

    print(f"\n{'=' * 60}")
    print(f"MEAN REVERSION SIGNAL - {signal.symbol}")
    print(f"{'=' * 60}")
    print(f"Signal Type: {signal.signal_type}")
    print(f"Confidence: {signal.confidence:.1%}")
    print(f"RSI(2): {signal.rsi_2:.1f}")
    print(f"RSI(5): {signal.rsi_5:.1f}")
    print(f"Price: ${signal.price:.2f}")
    print(f"200 SMA: ${signal.sma_200:.2f}")
    print(f"VIX: {signal.vix:.1f}" if signal.vix else "VIX: N/A")
    print(f"Reason: {signal.reason}")

    if signal.signal_type == "BUY":
        print("\nPOSITION SIZING:")
        print(f"  Suggested Size: {signal.suggested_size_pct:.1%} of capital")
        print(f"  Stop Loss: {signal.stop_loss_pct:.1%}")
        print(f"  Take Profit: {signal.take_profit_pct:.1%}")
    print()


# Example 2: Scan Multiple Symbols
# =================================


def example_scan_universe():
    """Scan multiple ETFs for mean reversion opportunities."""
    from src.strategies.mean_reversion_strategy import MeanReversionStrategy

    strategy = MeanReversionStrategy()

    # Scan major ETFs
    symbols = ["SPY", "QQQ", "IWM", "DIA", "TLT", "GLD"]
    signals = strategy.scan_universe(symbols)

    print(f"\n{'=' * 60}")
    print("UNIVERSE SCAN - Mean Reversion Opportunities")
    print(f"{'=' * 60}\n")

    for signal in signals:
        status = "***" if signal.signal_type == "BUY" else "   "
        print(
            f"{status} {signal.symbol}: {signal.signal_type:4s} | "
            f"RSI(2)={signal.rsi_2:5.1f} | "
            f"Conf={signal.confidence:5.1%} | "
            f"{signal.reason[:40]}..."
        )

    # Get only active signals (BUY/SELL)
    active_signals = strategy.get_active_signals(symbols)

    if active_signals:
        print(f"\n{'=' * 60}")
        print(f"ACTIVE SIGNALS: {len(active_signals)}")
        print(f"{'=' * 60}\n")

        for sig in active_signals:
            print(f"{sig.symbol}: {sig.signal_type} @ {sig.confidence:.1%} confidence")
            print(f"  Reason: {sig.reason}")
            if sig.signal_type == "BUY":
                print(
                    f"  Position: {sig.suggested_size_pct:.1%} | "
                    f"Stop: {sig.stop_loss_pct:.1%} | "
                    f"Target: {sig.take_profit_pct:.1%}"
                )
            print()
    else:
        print("\nNo active signals - market in neutral range")


# Example 3: Regime-Aware Strategy Selection
# ===========================================


def example_regime_aware_selection():
    """Use regime detection to select optimal strategy."""
    from src.strategies.regime_aware_strategy_selector import RegimeAwareStrategySelector

    selector = RegimeAwareStrategySelector()

    # Scenario 1: Strong trend (ADX=35) -> Momentum
    print(f"\n{'=' * 60}")
    print("SCENARIO 1: STRONG TRENDING MARKET (ADX=35)")
    print(f"{'=' * 60}")

    selection = selector.select_strategy(
        symbol="SPY",
        market_data={"adx": 35.0},
        adx=35.0,
    )

    print(f"Selected Strategy: {selection.selected_strategy.value}")
    print(f"Market Regime: {selection.regime}")
    print(
        f"Weights: Momentum={selection.momentum_weight:.1%}, "
        f"MeanReversion={selection.mean_reversion_weight:.1%}"
    )
    print(f"Reason: {selection.reason}")

    # Scenario 2: Weak trend (ADX=15) -> Mean Reversion
    print(f"\n{'=' * 60}")
    print("SCENARIO 2: SIDEWAYS/RANGING MARKET (ADX=15)")
    print(f"{'=' * 60}")

    selection = selector.select_strategy(
        symbol="SPY",
        market_data={"adx": 15.0},
        adx=15.0,
    )

    print(f"Selected Strategy: {selection.selected_strategy.value}")
    print(f"Market Regime: {selection.regime}")
    print(
        f"Weights: Momentum={selection.momentum_weight:.1%}, "
        f"MeanReversion={selection.mean_reversion_weight:.1%}"
    )
    print(f"Reason: {selection.reason}")

    # Scenario 3: Moderate trend (ADX=22) -> Hybrid
    print(f"\n{'=' * 60}")
    print("SCENARIO 3: MODERATE TREND - HYBRID MODE (ADX=22)")
    print(f"{'=' * 60}")

    selection = selector.select_strategy(
        symbol="SPY",
        market_data={"adx": 22.0},
        adx=22.0,
    )

    print(f"Selected Strategy: {selection.selected_strategy.value}")
    print(f"Market Regime: {selection.regime}")
    print(
        f"Weights: Momentum={selection.momentum_weight:.1%}, "
        f"MeanReversion={selection.mean_reversion_weight:.1%}"
    )
    print(f"Reason: {selection.reason}")
    print()


# Example 4: Combined Signal from Both Strategies
# ================================================


def example_combined_signals():
    """Get weighted signals from both strategies."""
    from src.strategies.regime_aware_strategy_selector import RegimeAwareStrategySelector

    selector = RegimeAwareStrategySelector()

    # Hybrid mode example (ADX=22)
    selection = selector.select_strategy("SPY", adx=22.0)

    print(f"\n{'=' * 60}")
    print("COMBINED SIGNAL - HYBRID MODE")
    print(f"{'=' * 60}")

    # Get combined signal
    combined = selector.get_combined_signal("SPY", selection)

    print(f"Symbol: {combined['symbol']}")
    print(f"Regime: {combined['regime']}")
    print(f"Strategy: {combined['selected_strategy']}")
    print(f"Combined Confidence: {combined['combined_confidence']:.1%}")
    print(f"\nReason: {combined['reason']}")

    # Show individual signals
    if "momentum" in combined["signals"]:
        momentum = combined["signals"]["momentum"]
        print(f"\nMomentum Signal (weight={momentum['weight']:.1%}):")
        print(f"  Score: {momentum.get('score', 0):.2f}")
        if "indicators" in momentum:
            print(f"  Indicators: {momentum['indicators']}")

    if "mean_reversion" in combined["signals"]:
        mr = combined["signals"]["mean_reversion"]
        print(f"\nMean Reversion Signal (weight={mr['weight']:.1%}):")
        print(f"  Type: {mr.get('signal_type', 'N/A')}")
        print(f"  Confidence: {mr.get('confidence', 0):.1%}")
        print(f"  RSI(2): {mr.get('rsi_2', 0):.1f}")
        print(f"  Reason: {mr.get('reason', 'N/A')}")
    print()


# Example 5: Integration with Trading System
# ===========================================


def example_trading_integration():
    """Show how to integrate with existing trading system."""
    print(f"\n{'=' * 60}")
    print("TRADING SYSTEM INTEGRATION EXAMPLE")
    print(f"{'=' * 60}\n")

    # Pseudo-code for integration
    code = """
# In your main trading loop:

from src.strategies.regime_aware_strategy_selector import RegimeAwareStrategySelector
from src.strategies.legacy_momentum import LegacyMomentumCalculator
from src.strategies.mean_reversion_strategy import MeanReversionStrategy

selector = RegimeAwareStrategySelector()

# For each symbol in your universe
for symbol in ["SPY", "QQQ", "IWM"]:
    # 1. Get market data (including ADX)
    momentum_calc = LegacyMomentumCalculator()
    momentum_result = momentum_calc.evaluate(symbol)
    adx = momentum_result.indicators.get("adx", 15.0)

    # 2. Select optimal strategy based on regime
    selection = selector.select_strategy(
        symbol=symbol,
        market_data=momentum_result.indicators,
        adx=adx
    )

    # 3. Get combined signal
    combined = selector.get_combined_signal(symbol, selection)

    # 4. Execute trade if confidence high enough
    if combined["combined_confidence"] > 0.7:
        if selection.momentum_weight > selection.mean_reversion_weight:
            # Execute momentum trade
            print(f"{symbol}: MOMENTUM BUY (ADX={adx:.1f}, Score={momentum_result.score:.2f})")
        else:
            # Execute mean reversion trade
            mr_strategy = MeanReversionStrategy()
            mr_signal = mr_strategy.analyze(symbol)
            if mr_signal.signal_type == "BUY":
                print(f"{symbol}: MEAN REVERSION BUY (RSI={mr_signal.rsi_2:.1f})")
    """

    print(code)


# Main execution
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("MEAN REVERSION + MOMENTUM STRATEGY EXAMPLES")
    print("=" * 60)

    try:
        # Run examples
        print("\n[1/5] Mean Reversion Standalone")
        example_mean_reversion_standalone()
    except Exception as e:
        print(f"Example 1 error: {e}")

    try:
        print("\n[2/5] Scan Universe")
        example_scan_universe()
    except Exception as e:
        print(f"Example 2 error: {e}")

    try:
        print("\n[3/5] Regime-Aware Selection")
        example_regime_aware_selection()
    except Exception as e:
        print(f"Example 3 error: {e}")

    try:
        print("\n[4/5] Combined Signals")
        example_combined_signals()
    except Exception as e:
        print(f"Example 4 error: {e}")

    print("\n[5/5] Trading Integration")
    example_trading_integration()

    print("\n" + "=" * 60)
    print("Examples complete!")
    print("See docs/mean-reversion-momentum-complementarity.md for more details")
    print("=" * 60 + "\n")
