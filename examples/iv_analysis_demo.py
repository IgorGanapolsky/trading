#!/usr/bin/env python3
"""
IV Analysis Demo

Demonstrates real-time IV data integration and analysis.

This script shows how to:
1. Fetch option chains and analyze IV metrics
2. Detect IV regimes and trading opportunities
3. Build volatility surfaces and find arbitrage
4. Generate trading alerts

Usage:
    python3 examples/iv_analysis_demo.py
    python3 examples/iv_analysis_demo.py --symbol AAPL
    python3 examples/iv_analysis_demo.py --watchlist SPY,QQQ,IWM

Author: Claude (CTO)
Created: 2025-12-10
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.options.iv_data_integration import (
    IVAlerts,
    IVDataFetcher,
    VolatilitySurface,
)


def analyze_symbol(
    symbol: str, fetcher: IVDataFetcher, alerts_system: IVAlerts, show_surface: bool = False
):
    """Comprehensive IV analysis for a single symbol"""

    print(f"\n{'=' * 80}")
    print(f"IV ANALYSIS: {symbol}")
    print(f"{'=' * 80}\n")

    # Get comprehensive metrics
    metrics = fetcher.get_iv_metrics(symbol)

    # Display metrics
    print("📊 CURRENT IV METRICS:")
    print(f"   Current Price: ${metrics.current_price:.2f}")
    print(f"   ATM IV: {metrics.atm_iv:.2%}")
    print(f"   IV Percentile: {metrics.iv_percentile:.1f}% (52-week)")
    print(f"   IV Rank: {metrics.iv_rank:.1f}%")
    print(f"   IV Regime: {metrics.iv_regime.value.upper()}")
    print(f"   52W Range: {metrics.iv_52w_low:.2%} - {metrics.iv_52w_high:.2%}")
    print(f"   Mean IV (1Y): {metrics.mean_iv_252d:.2%} ± {metrics.std_iv_252d:.2%}")
    print()

    print("📈 IV STRUCTURE:")
    print(f"   Put/Call Skew: {metrics.put_call_iv_skew:.2%}")
    if metrics.put_call_iv_skew < -0.03:
        print("      → Bearish skew (puts expensive)")
    elif metrics.put_call_iv_skew > 0.03:
        print("      → Bullish skew (calls expensive)")
    else:
        print("      → Neutral skew")

    print(f"   Term Structure Slope: {metrics.term_structure_slope:.6f}")
    if metrics.term_structure_slope > 0:
        print("      → Normal (backwardation)")
    elif metrics.term_structure_slope < -0.001:
        print("      → ⚠️ INVERTED (contango) - Fear indicator!")
    else:
        print("      → Flat")
    print()

    # Recommendation
    print("💡 TRADING RECOMMENDATION:")
    print(f"   {metrics.recommendation}")
    if metrics.recommendation == "SELL_VOL":
        print("   → Strategies: Iron condors, credit spreads, covered calls")
    elif metrics.recommendation == "BUY_VOL":
        print("   → Strategies: Long calls/puts, debit spreads, straddles")
    else:
        print("   → Strategy: Wait for clearer edge or use neutral strategies")
    print()

    # Check alerts
    alerts = alerts_system.check_all_alerts(symbol)
    if alerts:
        print("🚨 ACTIVE ALERTS:")
        for alert in alerts:
            urgency_icon = {"LOW": "ℹ️", "MEDIUM": "⚠️", "HIGH": "🔥", "CRITICAL": "🚨"}.get(
                alert.urgency, ""
            )
            print(f"\n   {urgency_icon} [{alert.urgency}] {alert.alert_type}")
            print(f"   Message: {alert.message}")
            print(f"   Action: {alert.recommended_action}")
    else:
        print("✅ No alerts triggered - Normal conditions")

    # Volatility surface analysis (optional)
    if show_surface:
        print("\n" + "=" * 80)
        print("VOLATILITY SURFACE ANALYSIS")
        print("=" * 80 + "\n")

        surface_builder = VolatilitySurface(fetcher)
        surface = surface_builder.build_surface(symbol)

        if surface:
            print(f"Surface points: {len(surface)}")

            # Show sample points
            print("\nSample Surface Points:")
            for point in surface[:5]:
                print(
                    f"   Strike: ${point.strike:.2f}, DTE: {point.dte}d, "
                    f"IV: {point.iv:.2%}, Type: {point.option_type}"
                )

            # Test interpolation
            test_strike = metrics.current_price
            test_dte = 30
            interp_iv = surface_builder.interpolate_iv(surface, test_strike, test_dte)
            if interp_iv:
                print(f"\nInterpolated IV (${test_strike:.2f}, {test_dte}d): {interp_iv:.2%}")

            # Check arbitrage
            opportunities = surface_builder.detect_arbitrage_opportunities(surface)
            if opportunities:
                print(f"\n⚡ Arbitrage Opportunities Found: {len(opportunities)}")
                for opp in opportunities[:3]:
                    print(
                        f"   - {opp['type']}: Strike ${opp['strike']:.2f}, Severity {opp['severity']:.2%}"
                    )
            else:
                print("\n✅ No arbitrage opportunities detected")

    print(f"\n{'=' * 80}\n")


def main():
    """Main demo function"""
    parser = argparse.ArgumentParser(description="IV Analysis Demo")
    parser.add_argument("--symbol", default="SPY", help="Symbol to analyze (default: SPY)")
    parser.add_argument("--watchlist", help="Comma-separated list of symbols to analyze")
    parser.add_argument("--surface", action="store_true", help="Show volatility surface analysis")
    parser.add_argument(
        "--paper", action="store_true", default=True, help="Use paper trading (default: True)"
    )

    args = parser.parse_args()

    # Initialize components
    print("\n🚀 Initializing IV Data Integration System...\n")
    fetcher = IVDataFetcher(paper=args.paper, cache_ttl_minutes=5)
    alerts_system = IVAlerts(fetcher)

    # Determine symbols to analyze
    if args.watchlist:
        symbols = [s.strip().upper() for s in args.watchlist.split(",")]
    else:
        symbols = [args.symbol.upper()]

    # Analyze each symbol
    for symbol in symbols:
        try:
            analyze_symbol(symbol, fetcher, alerts_system, show_surface=args.surface)
        except Exception as e:
            print(f"\n❌ Error analyzing {symbol}: {e}\n")
            import traceback

            traceback.print_exc()

    print("\n✅ Analysis complete!\n")


if __name__ == "__main__":
    main()
