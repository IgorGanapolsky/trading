#!/usr/bin/env python3
"""
Analyze Cash-Secured Put opportunities for specific tickers.

Calculate maximum daily options income with given buying power.
Target: $20-30 stocks, 30-45 DTE, 20-30 delta puts.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Use project's yfinance wrapper for graceful fallbacks
from src.utils import yfinance_wrapper as yf

try:
    import numpy as np
    import pandas as pd
except ImportError:
    print("ERROR: numpy and pandas are required. Install with: pip install numpy pandas")
    sys.exit(1)


def get_current_price(symbol: str) -> float:
    """Get current stock price."""
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="1d")
        if data.empty:
            return 0
        return float(data["Close"].iloc[-1])
    except Exception as e:
        print(f"  Error getting price for {symbol}: {e}")
        return 0


def analyze_put_options(
    symbol: str,
    buying_power: float,
    min_dte: int = 30,
    max_dte: int = 45,
    target_delta_low: float = -0.30,
    target_delta_high: float = -0.20,
) -> dict:
    """
    Analyze put options for a symbol and calculate potential income.

    Args:
        symbol: Stock ticker
        buying_power: Available cash for collateral
        min_dte: Minimum days to expiration
        max_dte: Maximum days to expiration
        target_delta_low: Lower bound for delta (e.g., -0.30)
        target_delta_high: Upper bound for delta (e.g., -0.20)

    Returns:
        dict with analysis results
    """
    try:
        ticker = yf.Ticker(symbol)
        current_price = get_current_price(symbol)

        if current_price == 0:
            return {
                "symbol": symbol,
                "error": "Could not get current price",
                "current_price": 0,
            }

        # Check if price is in target range
        if current_price < 20 or current_price > 30:
            print(f"  ⚠️  {symbol} price ${current_price:.2f} is outside $20-30 range")

        # Get option expirations
        expirations = ticker.options
        if not expirations:
            return {
                "symbol": symbol,
                "error": "No options available",
                "current_price": current_price,
            }

        # Filter expirations within DTE range
        today = datetime.now()
        valid_expirations = []

        for exp in expirations:
            exp_date = datetime.strptime(exp, "%Y-%m-%d")
            dte = (exp_date - today).days
            if min_dte <= dte <= max_dte:
                valid_expirations.append((exp, dte))

        if not valid_expirations:
            # Use closest expiration
            exp = expirations[0]
            exp_date = datetime.strptime(exp, "%Y-%m-%d")
            dte = (exp_date - today).days
            valid_expirations = [(exp, dte)]
            print(f"  ⚠️  No expirations in {min_dte}-{max_dte} DTE range, using {dte} DTE")

        # Analyze puts for the first valid expiration (closest to target)
        best_expiration, dte = valid_expirations[0]
        option_chain = ticker.option_chain(best_expiration)
        puts = option_chain.puts

        if puts.empty:
            return {
                "symbol": symbol,
                "error": "No put options found",
                "current_price": current_price,
            }

        # Filter puts with delta in target range
        puts_with_delta = puts[puts["delta"].notna()].copy()

        # Target delta range (puts have negative delta)
        target_puts = puts_with_delta[
            (puts_with_delta["delta"] >= target_delta_low) &
            (puts_with_delta["delta"] <= target_delta_high)
        ]

        if target_puts.empty:
            # Relax criteria - find closest delta
            if not puts_with_delta.empty:
                puts_with_delta["delta_diff"] = abs(
                    puts_with_delta["delta"] - (target_delta_low + target_delta_high) / 2
                )
                target_puts = puts_with_delta.nsmallest(3, "delta_diff")
                print(f"  ⚠️  No puts in exact delta range, showing closest matches")

        if target_puts.empty:
            return {
                "symbol": symbol,
                "error": "No puts in target delta range",
                "current_price": current_price,
            }

        # Calculate metrics for best options
        results = []
        for idx, row in target_puts.iterrows():
            strike = float(row["strike"])
            bid = float(row.get("bid", 0) or 0)
            ask = float(row.get("ask", 0) or 0)
            mid = (bid + ask) / 2 if bid > 0 and ask > 0 else 0

            if mid == 0:
                continue

            delta = float(row.get("delta", 0))
            iv = float(row.get("impliedVolatility", 0) or 0)

            # Calculate collateral required (strike * 100 shares)
            collateral_per_contract = strike * 100

            # Max contracts we can sell with available buying power
            max_contracts = int(buying_power // collateral_per_contract)

            if max_contracts == 0:
                continue

            # Premium per contract
            premium_per_contract = mid * 100

            # Total premium collected
            total_premium = premium_per_contract * max_contracts

            # Daily income (theta decay approximation)
            daily_income = total_premium / dte if dte > 0 else 0

            # Weekly income
            weekly_income = daily_income * 7

            # Annualized return on collateral
            total_collateral = collateral_per_contract * max_contracts
            annualized_return = (total_premium / total_collateral) * (365 / dte) if dte > 0 else 0

            # Premium as % of stock price
            premium_pct = (mid / current_price) * 100 if current_price > 0 else 0

            # Premium to collateral ratio (what we collect vs what we risk)
            premium_to_collateral = (total_premium / total_collateral) * 100

            results.append({
                "strike": strike,
                "delta": delta,
                "bid": bid,
                "ask": ask,
                "mid": mid,
                "iv": iv,
                "dte": dte,
                "expiration": best_expiration,
                "collateral_per_contract": collateral_per_contract,
                "max_contracts": max_contracts,
                "premium_per_contract": premium_per_contract,
                "total_premium": total_premium,
                "total_collateral": total_collateral,
                "daily_income": daily_income,
                "weekly_income": weekly_income,
                "annualized_return": annualized_return,
                "premium_pct": premium_pct,
                "premium_to_collateral": premium_to_collateral,
            })

        if not results:
            return {
                "symbol": symbol,
                "error": "No valid options after filtering",
                "current_price": current_price,
            }

        # Sort by total premium (maximize income)
        results.sort(key=lambda x: x["total_premium"], reverse=True)

        return {
            "symbol": symbol,
            "current_price": current_price,
            "options": results,
            "best_option": results[0],
        }

    except Exception as e:
        return {
            "symbol": symbol,
            "error": str(e),
            "current_price": 0,
        }


def main():
    # User parameters
    BUYING_POWER = 2487.77
    TICKERS = ["SOFI", "F", "BAC", "PLTR", "AMD"]

    print("=" * 80)
    print("CASH-SECURED PUT ANALYSIS - Phil Town Style")
    print("=" * 80)
    print(f"Buying Power: ${BUYING_POWER:,.2f}")
    print(f"Target Tickers: {', '.join(TICKERS)}")
    print(f"Target Price Range: $20-30")
    print(f"Target DTE: 30-45 days")
    print(f"Target Delta: 20-30 (0.20-0.30)")
    print("=" * 80)
    print()

    all_results = []

    for ticker in TICKERS:
        print(f"\n{'='*60}")
        print(f"Analyzing {ticker}...")
        print(f"{'='*60}")

        result = analyze_put_options(
            ticker,
            BUYING_POWER,
            min_dte=30,
            max_dte=45,
            target_delta_low=-0.30,
            target_delta_high=-0.20,
        )

        if "error" in result:
            print(f"  ❌ {result['error']}")
            if result.get("current_price"):
                print(f"  Current price: ${result['current_price']:.2f}")
            continue

        current_price = result["current_price"]
        best = result["best_option"]

        print(f"\n📊 Current Price: ${current_price:.2f}")
        print(f"\n🎯 BEST OPPORTUNITY:")
        print(f"  Strike: ${best['strike']:.2f} ({abs(best['delta']):.2f} delta)")
        print(f"  Expiration: {best['expiration']} ({best['dte']} DTE)")
        print(f"  Premium: ${best['mid']:.2f}/share ({best['premium_pct']:.2f}% of stock price)")
        print(f"  IV: {best['iv']:.1%}")
        print(f"\n💰 INCOME ANALYSIS:")
        print(f"  Max Contracts: {best['max_contracts']}")
        print(f"  Premium per Contract: ${best['premium_per_contract']:.2f}")
        print(f"  Total Premium Collected: ${best['total_premium']:.2f}")
        print(f"  Total Collateral Required: ${best['total_collateral']:.2f}")
        print(f"\n📈 RETURNS:")
        print(f"  Daily Income: ${best['daily_income']:.2f}/day")
        print(f"  Weekly Income: ${best['weekly_income']:.2f}/week")
        print(f"  Annualized Return: {best['annualized_return']:.2%}")
        print(f"  Premium/Collateral Ratio: {best['premium_to_collateral']:.3f}%")

        all_results.append(result)

        # Show top 3 alternatives
        if len(result["options"]) > 1:
            print(f"\n📋 Alternative Options:")
            for i, opt in enumerate(result["options"][1:4], 1):
                print(f"  {i}. Strike ${opt['strike']:.2f} (δ={abs(opt['delta']):.2f}): "
                      f"${opt['total_premium']:.2f} total premium, "
                      f"${opt['daily_income']:.2f}/day")

    # Summary comparison
    print("\n\n" + "=" * 80)
    print("SUMMARY - BEST OPPORTUNITIES BY METRIC")
    print("=" * 80)

    valid_results = [r for r in all_results if "best_option" in r]

    if not valid_results:
        print("❌ No valid opportunities found")
        return

    # Best total premium
    print("\n🏆 HIGHEST TOTAL PREMIUM:")
    by_premium = sorted(valid_results, key=lambda x: x["best_option"]["total_premium"], reverse=True)
    for i, r in enumerate(by_premium[:3], 1):
        best = r["best_option"]
        print(f"  {i}. {r['symbol']}: ${best['total_premium']:.2f} "
              f"({best['max_contracts']} contracts × ${best['premium_per_contract']:.2f})")

    # Best daily income
    print("\n💵 HIGHEST DAILY INCOME:")
    by_daily = sorted(valid_results, key=lambda x: x["best_option"]["daily_income"], reverse=True)
    for i, r in enumerate(by_daily[:3], 1):
        best = r["best_option"]
        print(f"  {i}. {r['symbol']}: ${best['daily_income']:.2f}/day "
              f"(${best['weekly_income']:.2f}/week)")

    # Best annualized return
    print("\n📊 HIGHEST ANNUALIZED RETURN:")
    by_return = sorted(valid_results, key=lambda x: x["best_option"]["annualized_return"], reverse=True)
    for i, r in enumerate(by_return[:3], 1):
        best = r["best_option"]
        print(f"  {i}. {r['symbol']}: {best['annualized_return']:.2%} "
              f"({best['dte']} DTE, ${best['strike']:.2f} strike)")

    # Best premium/collateral ratio
    print("\n⚡ BEST PREMIUM-TO-COLLATERAL RATIO:")
    by_ratio = sorted(valid_results, key=lambda x: x["best_option"]["premium_to_collateral"], reverse=True)
    for i, r in enumerate(by_ratio[:3], 1):
        best = r["best_option"]
        print(f"  {i}. {r['symbol']}: {best['premium_to_collateral']:.3f}% "
              f"(${best['total_premium']:.2f} premium on ${best['total_collateral']:.2f} collateral)")

    # FINAL RECOMMENDATION
    print("\n\n" + "=" * 80)
    print("✨ RECOMMENDATION")
    print("=" * 80)

    top_pick = by_premium[0]
    best = top_pick["best_option"]

    print(f"\n🎯 With ${BUYING_POWER:.2f} buying power, sell puts on {top_pick['symbol']}:")
    print(f"  • Strike: ${best['strike']:.2f}")
    print(f"  • Expiration: {best['expiration']} ({best['dte']} DTE)")
    print(f"  • Contracts: {best['max_contracts']}")
    print(f"  • Premium Collected: ${best['total_premium']:.2f}")
    print(f"  • Daily Income: ${best['daily_income']:.2f}")
    print(f"  • Weekly Income: ${best['weekly_income']:.2f}")
    print(f"  • Annualized Return: {best['annualized_return']:.2%}")
    print(f"\n💡 Risk: If assigned, you buy {best['max_contracts'] * 100} shares of {top_pick['symbol']}")
    print(f"    at ${best['strike']:.2f}, requiring ${best['total_collateral']:.2f} cash.")
    print(f"    Your effective cost basis: ${best['strike'] - best['mid']:.2f} "
          f"(strike minus premium received)")
    print()


if __name__ == "__main__":
    main()
