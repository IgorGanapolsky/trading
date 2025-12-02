#!/usr/bin/env python3
"""
Check bond momentum vs equities to see if BND should be selected.
Simple version using yfinance directly.
"""

import yfinance as yf


def check_bond_momentum():
    """Check current momentum scores for BND vs equity ETFs."""
    print("=" * 80)
    print("BOND MOMENTUM ANALYSIS")
    print("=" * 80)
    print()

    symbols = {
        "SPY": "EQUITY",
        "QQQ": "EQUITY",
        "VOO": "EQUITY",
        "BND": "BOND",
        "VNQ": "REIT",
    }

    results = []

    print("Fetching current data...")
    print("-" * 80)

    for symbol, asset_type in symbols.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="6mo")

            if hist.empty:
                print(f"{symbol:6s}: No data available")
                continue

            current_price = hist["Close"].iloc[-1]

            # Calculate returns
            returns_1m = (
                ((hist["Close"].iloc[-1] / hist["Close"].iloc[-21]) - 1) * 100
                if len(hist) >= 21
                else 0
            )
            returns_3m = (
                ((hist["Close"].iloc[-1] / hist["Close"].iloc[-63]) - 1) * 100
                if len(hist) >= 63
                else 0
            )
            returns_6m = ((hist["Close"].iloc[-1] / hist["Close"].iloc[0]) - 1) * 100

            # Calculate RSI (simplified)
            delta = hist["Close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            rsi_value = rsi.iloc[-1] if not rsi.empty else 50

            # Simple momentum score (weighted)
            momentum_score = returns_1m * 0.5 + returns_3m * 0.3 + returns_6m * 0.2

            results.append(
                {
                    "symbol": symbol,
                    "type": asset_type,
                    "price": current_price,
                    "returns_1m": returns_1m,
                    "returns_3m": returns_3m,
                    "returns_6m": returns_6m,
                    "rsi": rsi_value,
                    "momentum_score": momentum_score,
                }
            )

            print(
                f"{symbol:6s} ({asset_type:6s}): ${current_price:7.2f} | "
                f"1M: {returns_1m:+6.2f}% | 3M: {returns_3m:+6.2f}% | "
                f"6M: {returns_6m:+6.2f}% | RSI: {rsi_value:5.1f}"
            )

        except Exception as e:
            print(f"{symbol:6s}: Error - {e}")

    print()
    print("=" * 80)
    print("MOMENTUM RANKING:")
    print("=" * 80)

    # Sort by momentum score
    results.sort(key=lambda x: x["momentum_score"], reverse=True)

    for i, r in enumerate(results, 1):
        print(
            f"{i}. {r['symbol']:6s} ({r['type']:6s}): {r['momentum_score']:+7.2f} "
            f"(1M: {r['returns_1m']:+6.2f}%, 3M: {r['returns_3m']:+6.2f}%, 6M: {r['returns_6m']:+6.2f}%)"
        )

    print()
    print("=" * 80)

    # Check if BND is winning
    best = results[0] if results else None
    bnd_result = next((r for r in results if r["symbol"] == "BND"), None)

    if best and bnd_result:
        print(f"Best ETF: {best['symbol']} (Momentum Score: {best['momentum_score']:.2f})")
        print(f"BND Score: {bnd_result['momentum_score']:.2f}")

        if best["symbol"] == "BND":
            print("✅ BND IS CURRENTLY THE BEST MOMENTUM PICK!")
            print("   Bonds should be selected on next trade execution.")
        else:
            diff = best["momentum_score"] - bnd_result["momentum_score"]
            print(f"⚠️  BND is {diff:.2f} points behind {best['symbol']}")
            if diff < 5:
                print("   BND is close - monitor for selection opportunity")

    print()
    print("=" * 80)
    print("ALLOCATION ANALYSIS:")
    print("=" * 80)

    daily_allocation = 10.0  # Current R&D allocation
    bond_allocation = daily_allocation * 0.15  # 15% allocation
    reit_allocation = daily_allocation * 0.15  # 15% allocation
    treasury_allocation = daily_allocation * 0.10  # 10% allocation

    print(f"Daily Allocation: ${daily_allocation:.2f}")
    print(f"Bond Allocation (15%): ${bond_allocation:.2f}")
    print(f"REIT Allocation (15%): ${reit_allocation:.2f}")
    print(f"Treasury Allocation (10%): ${treasury_allocation:.2f}")
    print()
    print("Previous Threshold: $1.00 minimum")
    print("New Threshold: $0.50 minimum ✅")
    print()
    print(
        f"Bond orders will execute: {'✅ YES' if bond_allocation >= 0.50 else '❌ NO (too small)'}"
    )
    print(
        f"REIT orders will execute: {'✅ YES' if reit_allocation >= 0.50 else '❌ NO (too small)'}"
    )
    print(
        f"Treasury orders will execute: {'✅ YES' if treasury_allocation >= 0.50 else '❌ NO (too small)'}"
    )

    print()
    print("=" * 80)
    print("STATUS:")
    print("=" * 80)
    print("✅ Threshold lowered from $1.00 to $0.50")
    print("✅ Bonds/REITs/Treasuries can now execute at current allocation levels")
    if best and best["symbol"] == "BND":
        print("✅ BND has best momentum - will be selected on next trade!")
    else:
        print("ℹ️  Equities currently have better momentum than bonds")


if __name__ == "__main__":
    check_bond_momentum()
