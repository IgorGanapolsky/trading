#!/usr/bin/env python3
"""
Options Accumulation Plan Calculator

Calculates the fastest path to options trading eligibility by analyzing:
1. Current positions and their path to threshold
2. Optimal symbol selection for fastest accumulation
3. Required daily investment to reach threshold in target timeframe
"""

import sys

sys.path.append(".")

import yfinance as yf


def analyze_options_path(
    symbols: list[str],
    current_daily_investment: float = 15.0,
    target_shares: int = 50,
    target_months: int = 12,
) -> dict:
    """
    Analyze the path to options trading eligibility.

    Args:
        symbols: List of symbols to analyze
        current_daily_investment: Current daily investment amount
        target_shares: Target number of shares (50 or 100)
        target_months: Target timeframe in months

    Returns:
        Analysis results dictionary
    """
    print("=" * 80)
    print("🎯 OPTIONS ACCUMULATION ANALYSIS")
    print("=" * 80)
    print()
    print(f"Target: {target_shares} shares")
    print(f"Current daily investment: ${current_daily_investment:.2f}/day")
    print(f"Target timeframe: {target_months} months")
    print()

    results = {}
    (target_months * 30 * current_daily_investment) / (target_months * 30)  # Placeholder

    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            current_price = info.get("currentPrice", info.get("regularMarketPrice", 0))

            if current_price == 0:
                continue

            # Calculate requirements
            total_cost = target_shares * current_price
            shares_per_day = current_daily_investment / current_price
            days_at_current = target_shares / shares_per_day if shares_per_day > 0 else float("inf")

            # Calculate required daily investment for target timeframe
            target_days = target_months * 30
            required_daily = total_cost / target_days

            # Calculate monthly premium estimate (rough)
            # Covered call premium typically 0.5-2% of stock price monthly
            estimated_monthly_premium = current_price * target_shares * 0.01  # 1% estimate
            estimated_annual_yield = (estimated_monthly_premium * 12) / total_cost * 100

            results[symbol] = {
                "price": current_price,
                "total_cost": total_cost,
                "days_at_current": days_at_current,
                "years_at_current": days_at_current / 365,
                "required_daily": required_daily,
                "monthly_premium_est": estimated_monthly_premium,
                "annual_yield_est": estimated_annual_yield,
            }

            print(f"📈 {symbol}:")
            print(f"   Current price: ${current_price:.2f}")
            print(f"   Cost for {target_shares} shares: ${total_cost:,.2f}")
            print(
                f"   Days at ${current_daily_investment:.2f}/day: {days_at_current:.0f} ({days_at_current / 365:.1f} years)"
            )
            print(f"   Required daily for {target_months}mo: ${required_daily:.2f}/day")
            print(f"   Est. monthly premium: ${estimated_monthly_premium:.2f}")
            print(f"   Est. annual yield: {estimated_annual_yield:.1f}%")
            print()

        except Exception as e:
            print(f"❌ {symbol}: Error - {e}")
            print()

    # Find best option
    if results:
        fastest = min(results.items(), key=lambda x: x[1]["days_at_current"])
        cheapest = min(results.items(), key=lambda x: x[1]["total_cost"])

        print("=" * 80)
        print("🏆 RECOMMENDATIONS")
        print("=" * 80)
        print()
        print(f"Fastest path: {fastest[0]} ({fastest[1]['days_at_current']:.0f} days)")
        print(f"Cheapest path: {cheapest[0]} (${cheapest[1]['total_cost']:,.2f})")
        print()

        # Best balance
        best_balance = min(
            results.items(),
            key=lambda x: x[1]["days_at_current"] * 0.6 + x[1]["total_cost"] / 1000 * 0.4,
        )
        print(f"Best balance: {best_balance[0]}")
        print(f"  - Days: {best_balance[1]['days_at_current']:.0f}")
        print(f"  - Cost: ${best_balance[1]['total_cost']:,.2f}")
        print(f"  - Required daily: ${best_balance[1]['required_daily']:.2f}/day")
        print()

    return results


def main():
    symbols = ["SPY", "QQQ", "VOO", "NVDA", "GOOGL", "AMZN"]

    print("\n" + "=" * 80)
    print("OPTION 1: Lower Threshold to 50 Shares")
    print("=" * 80)
    analyze_options_path(symbols, current_daily_investment=15.0, target_shares=50)

    print("\n" + "=" * 80)
    print("OPTION 2: Increase Daily Investment to $50/day")
    print("=" * 80)
    analyze_options_path(symbols, current_daily_investment=50.0, target_shares=50)

    print("\n" + "=" * 80)
    print("OPTION 3: Hybrid - $50/day + 50 Shares Threshold")
    print("=" * 80)
    analyze_options_path(symbols, current_daily_investment=50.0, target_shares=50, target_months=8)


if __name__ == "__main__":
    main()
