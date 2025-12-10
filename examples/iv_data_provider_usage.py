"""
IV Data Provider - Comprehensive Usage Examples

This script demonstrates all features of the IVDataProvider class including:
1. Basic IV metrics (current, rank, percentile)
2. IV skew analysis (fear/greed indicator)
3. Term structure (IV across expirations)
4. Options chain with Greeks (filtered, sorted by liquidity)
5. Optimal strike selection for strategies
6. Caching mechanisms

Author: Claude (CTO)
Created: 2025-12-10
"""

import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.iv_data_provider import get_iv_data_provider

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def example_1_basic_iv_metrics():
    """Example 1: Get basic IV metrics for a symbol"""
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Basic IV Metrics")
    print("=" * 80)

    provider = get_iv_data_provider()

    symbol = "SPY"
    print(f"\nFetching IV metrics for {symbol}...\n")

    # Get individual metrics
    current_iv = provider.get_current_iv(symbol)
    iv_rank = provider.get_iv_rank(symbol)
    iv_percentile = provider.get_iv_percentile(symbol)
    vix = provider.get_vix()

    print(f"Current IV: {current_iv:.4f} ({current_iv * 100:.2f}%)")
    print(f"IV Rank: {iv_rank:.2f}/100")
    print(f"IV Percentile: {iv_percentile:.2f}%")
    print(f"VIX: {vix:.2f}")

    # Get full metrics
    print("\nFull Metrics:")
    full_metrics = provider.get_full_metrics(symbol)
    print(f"  52-Week High: {full_metrics.iv_52w_high:.4f}")
    print(f"  52-Week Low: {full_metrics.iv_52w_low:.4f}")
    print(f"  30-Day Avg: {full_metrics.iv_30d_avg:.4f}")
    print(f"  Data Source: {full_metrics.data_source}")
    print(f"  Confidence: {full_metrics.confidence:.0%}")

    # Trading signal based on IV rank
    if iv_rank > 75:
        signal = "SELL PREMIUM (IV very high - great for credit strategies)"
    elif iv_rank > 50:
        signal = "SELL PREMIUM (IV elevated)"
    elif iv_rank < 20:
        signal = "BUY PREMIUM (IV very low - cheap options)"
    elif iv_rank < 30:
        signal = "BUY PREMIUM (IV low)"
    else:
        signal = "NEUTRAL (IV in middle range)"

    print(f"\nTrading Signal: {signal}")


def example_2_iv_skew():
    """Example 2: Analyze IV skew (fear vs greed indicator)"""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: IV Skew Analysis")
    print("=" * 80)

    provider = get_iv_data_provider()

    symbols = ["SPY", "AAPL", "NVDA"]

    for symbol in symbols:
        print(f"\n{symbol} IV Skew:")
        print("-" * 40)

        skew_data = provider.get_iv_skew(symbol)

        if skew_data.get("call_iv"):
            print(f"  Call IV: {skew_data['call_iv']:.4f}")
            print(f"  Put IV: {skew_data['put_iv']:.4f}")
            print(f"  Skew: {skew_data['skew']:.4f} ({skew_data['skew_pct']:.2f}%)")
            print(f"  Interpretation: {skew_data['interpretation']}")
        else:
            print(f"  {skew_data.get('interpretation', 'Data unavailable')}")


def example_3_term_structure():
    """Example 3: Analyze IV term structure across expirations"""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: IV Term Structure")
    print("=" * 80)

    provider = get_iv_data_provider()

    symbol = "SPY"
    print(f"\n{symbol} Term Structure:")
    print("-" * 40)

    term_data = provider.get_term_structure(symbol)

    if term_data["expirations"]:
        print("\nExpiration -> IV:")
        for exp, iv in zip(term_data["expirations"], term_data["ivs"]):
            print(f"  {exp}: {iv:.4f}")

        print(f"\nStructure Type: {term_data['structure_type'].upper()}")
        print(f"Front Month IV: {term_data['front_month_iv']:.4f}")
        print(f"Back Month IV: {term_data['back_month_iv']:.4f}")
        print(f"Slope: {term_data['slope']:.6f}")

        # Interpret term structure
        if term_data["structure_type"] == "normal":
            interpretation = "Normal term structure - uncertainty increases with time"
        elif term_data["structure_type"] == "inverted":
            interpretation = "Inverted - near-term event risk (earnings, Fed meeting, etc.)"
        elif term_data["structure_type"] == "flat":
            interpretation = "Flat - consistent volatility expectations"
        else:
            interpretation = "Humped - specific mid-term event expected"

        print(f"\nInterpretation: {interpretation}")
    else:
        print("No term structure data available")


def example_4_options_chain_with_greeks():
    """Example 4: Fetch options chain with Greeks, filtered and sorted"""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Options Chain with Greeks")
    print("=" * 80)

    provider = get_iv_data_provider()

    symbol = "SPY"
    print(f"\nFetching {symbol} options chain...")
    print("Filters: Delta 0.20-0.40, Min Volume 10, Min OI 50")
    print("-" * 80)

    # Fetch filtered options
    options = provider.get_options_chain_with_greeks(
        symbol=symbol, min_delta=0.20, max_delta=0.40, min_volume=10, min_open_interest=50
    )

    if options:
        print(f"\nFound {len(options)} liquid options")
        print("\nTop 5 by liquidity:")
        print(f"{'Type':<6} {'Strike':<8} {'Exp':<12} {'Delta':<8} {'IV':<8} {'Vol':<8} {'OI':<10}")
        print("-" * 80)

        for opt in options[:5]:
            print(
                f"{opt['type']:<6} "
                f"${opt['strike']:<7.2f} "
                f"{opt['expiration']:<12} "
                f"{opt['delta']:<8.3f} "
                f"{opt['iv']:<8.3f} "
                f"{opt['volume']:<8} "
                f"{opt['open_interest']:<10}"
            )
    else:
        print("No options found matching criteria")


def example_5_find_optimal_strikes():
    """Example 5: Find optimal strikes for various strategies"""
    print("\n" + "=" * 80)
    print("EXAMPLE 5: Optimal Strike Selection for Strategies")
    print("=" * 80)

    provider = get_iv_data_provider()

    symbol = "SPY"

    strategies = [
        "covered_call",
        "cash_secured_put",
        "credit_spread_call",
        "iron_condor",
    ]

    for strategy in strategies:
        print(f"\n{strategy.upper().replace('_', ' ')}:")
        print("-" * 80)

        result = provider.find_optimal_strikes(symbol, strategy)

        if "error" in result:
            print(f"  Error: {result['error']}")
            continue

        print(f"  Symbol: {result['symbol']}")
        print(f"  Current Price: ${result['current_price']:.2f}")
        print(f"  Expiration: {result['expiration']}")

        if strategy == "covered_call":
            contract = result["contract"]
            print(f"\n  Short Call Strike: ${contract['strike']:.2f}")
            print(f"  Delta: {contract['delta']:.3f}")
            print(f"  Credit: ${result['expected_credit']:.2f}")
            print(f"  Max Profit: ${result['max_profit']:.2f}")
            print(f"  Break Even: ${result['break_even']:.2f}")

        elif strategy == "cash_secured_put":
            contract = result["contract"]
            print(f"\n  Short Put Strike: ${contract['strike']:.2f}")
            print(f"  Delta: {contract['delta']:.3f}")
            print(f"  Credit: ${result['expected_credit']:.2f}")
            print(f"  Max Profit: ${result['max_profit']:.2f}")
            print(f"  Break Even: ${result['break_even']:.2f}")

        elif strategy in ["credit_spread_call", "credit_spread_put"]:
            short = result["short_leg"]
            long = result["long_leg"]
            print(f"\n  Short Strike: ${short['strike']:.2f} (delta {short['delta']:.3f})")
            print(f"  Long Strike: ${long['strike']:.2f} (delta {long['delta']:.3f})")
            print(f"  Credit: ${result['expected_credit']:.2f}")
            print(f"  Max Profit: ${result['max_profit']:.2f}")
            print(f"  Max Loss: ${result['max_loss']:.2f}")
            print(f"  Break Even: ${result['break_even']:.2f}")

        elif strategy == "iron_condor":
            print("\n  Call Spread:")
            print(
                f"    Short: ${result['short_call']['strike']:.2f} (delta {result['short_call']['delta']:.3f})"
            )
            print(
                f"    Long: ${result['long_call']['strike']:.2f} (delta {result['long_call']['delta']:.3f})"
            )
            print("\n  Put Spread:")
            print(
                f"    Short: ${result['short_put']['strike']:.2f} (delta {result['short_put']['delta']:.3f})"
            )
            print(
                f"    Long: ${result['long_put']['strike']:.2f} (delta {result['long_put']['delta']:.3f})"
            )
            print(f"\n  Credit: ${result['expected_credit']:.2f}")
            print(f"  Max Profit: ${result['max_profit']:.2f}")
            print(f"  Max Loss: ${result['max_loss']:.2f}")
            print(
                f"  Break Even Range: ${result['break_even_low']:.2f} - ${result['break_even_high']:.2f}"
            )


def example_6_caching():
    """Example 6: Manual caching and cache management"""
    print("\n" + "=" * 80)
    print("EXAMPLE 6: Caching Mechanisms")
    print("=" * 80)

    provider = get_iv_data_provider()

    symbol = "AAPL"

    # Load cached data (if available)
    print(f"\n1. Attempting to load cached IV data for {symbol}...")
    cached_data = provider.load_cached_iv(symbol, max_age_minutes=5)

    if cached_data:
        print("   ✅ Found cached data:")
        print(f"      Current IV: {cached_data['current_iv']:.4f}")
        print(f"      IV Rank: {cached_data['iv_rank']:.2f}")
        print(f"      Data Source: {cached_data['data_source']}")
    else:
        print("   ❌ No cached data found")

    # Fetch fresh data
    print(f"\n2. Fetching fresh IV data for {symbol}...")
    current_iv = provider.get_current_iv(symbol)
    print(f"   Current IV: {current_iv:.4f}")

    # Manually cache custom data
    print("\n3. Manually caching custom IV data...")
    custom_data = {
        "current_iv": 0.25,
        "iv_rank": 65.0,
        "iv_percentile": 70.0,
        "data_source": "custom_test",
        "confidence": 0.8,
    }
    provider.cache_iv_data(symbol, custom_data)
    print("   ✅ Data cached")

    # Verify cache works
    print("\n4. Verifying cached data...")
    cached_data = provider.load_cached_iv(symbol, max_age_minutes=5)
    if cached_data:
        print("   ✅ Cache verified:")
        print(f"      Current IV: {cached_data['current_iv']:.4f}")
        print(f"      IV Rank: {cached_data['iv_rank']:.2f}")

    # Clear cache
    print(f"\n5. Clearing cache for {symbol}...")
    provider.clear_cache(symbol)
    print("   ✅ Cache cleared")

    # Verify cache is empty
    cached_data = provider.load_cached_iv(symbol, max_age_minutes=5)
    print("\n6. Verify cache is empty...")
    if cached_data:
        print("   ❌ Cache still has data (unexpected)")
    else:
        print("   ✅ Cache is empty")


def main():
    """Run all examples"""
    print("\n" + "=" * 80)
    print("IV DATA PROVIDER - COMPREHENSIVE USAGE EXAMPLES")
    print("=" * 80)

    try:
        example_1_basic_iv_metrics()
        example_2_iv_skew()
        example_3_term_structure()
        example_4_options_chain_with_greeks()
        example_5_find_optimal_strikes()
        example_6_caching()

        print("\n" + "=" * 80)
        print("ALL EXAMPLES COMPLETED SUCCESSFULLY!")
        print("=" * 80)

    except Exception as e:
        logger.error(f"Error running examples: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
