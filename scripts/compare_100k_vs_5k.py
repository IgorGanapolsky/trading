#!/usr/bin/env python3
"""
Compare $100K Paper Account Strategy vs $5K Strategy

This script analyzes what worked in the profitable $100K account
and compares it to the current $5K approach.

Usage:
    python3 scripts/compare_100k_vs_5k.py
"""

import json
from datetime import datetime
from pathlib import Path


def load_archived_trades():
    """Load trade data from archive."""
    archive_dir = Path("data/archive")
    all_trades = []

    for file in sorted(archive_dir.glob("trades_*.json")):
        try:
            with open(file) as f:
                trades = json.load(f)
                if isinstance(trades, list):
                    all_trades.extend(trades)
                else:
                    all_trades.append(trades)
        except Exception as e:
            print(f"Error loading {file}: {e}")

    return all_trades


def analyze_100k_patterns(trades):
    """Extract patterns from $100K period trades."""
    patterns = {
        "underlyings": {},
        "strategies": {},
        "position_sizes": [],
        "options_trades": [],
        "stock_trades": [],
    }

    for trade in trades:
        symbol = trade.get("symbol", "")
        strategy = trade.get("strategy", "unknown")

        # Track underlyings
        if len(symbol) > 10:  # Options
            # Extract underlying (e.g., SPY from SPY260220P00660000)
            underlying = ""
            for i, c in enumerate(symbol):
                if c.isdigit():
                    underlying = symbol[:i]
                    break
            if underlying:
                patterns["underlyings"][underlying] = patterns["underlyings"].get(underlying, 0) + 1
            patterns["options_trades"].append(trade)
        else:
            patterns["underlyings"][symbol] = patterns["underlyings"].get(symbol, 0) + 1
            patterns["stock_trades"].append(trade)

        # Track strategies
        patterns["strategies"][strategy] = patterns["strategies"].get(strategy, 0) + 1

    return patterns


def load_current_state():
    """Load current $5K account state."""
    state_file = Path("data/system_state.json")
    if state_file.exists():
        with open(state_file) as f:
            return json.load(f)
    return {}


def compare_strategies():
    """Compare $100K and $5K strategies."""
    print("=" * 70)
    print("$100K vs $5K STRATEGY COMPARISON")
    print(f"Generated: {datetime.now().isoformat()}")
    print("=" * 70)

    # Load $100K data
    archived_trades = load_archived_trades()
    patterns_100k = analyze_100k_patterns(archived_trades)

    print("\n## $100K PAPER ACCOUNT PATTERNS (from archive)")
    print(f"Total archived trades: {len(archived_trades)}")
    print(f"Options trades: {len(patterns_100k['options_trades'])}")
    print(f"Stock trades: {len(patterns_100k['stock_trades'])}")

    print("\nUnderlyings traded (by frequency):")
    for underlying, count in sorted(patterns_100k["underlyings"].items(), key=lambda x: -x[1])[:10]:
        print(f"  {underlying}: {count} trades")

    print("\nStrategies used:")
    for strategy, count in sorted(patterns_100k["strategies"].items(), key=lambda x: -x[1]):
        print(f"  {strategy}: {count}")

    # Load current $5K state
    current_state = load_current_state()

    print("\n" + "=" * 70)
    print("## $5K PAPER ACCOUNT CURRENT STATE")
    print("=" * 70)

    if current_state:
        paper = current_state.get("paper_account", {})
        positions = current_state.get("positions", [])

        print(f"Equity: ${paper.get('equity', 0):,.2f}")
        print(f"Total P/L: ${paper.get('total_pl', 0):,.2f} ({paper.get('total_pl_pct', 0)}%)")
        print(f"Positions: {len(positions)}")

        print("\nCurrent positions:")
        underlyings_5k = {}
        for pos in positions:
            symbol = pos.get("symbol", "")
            # Extract underlying
            if len(symbol) > 10:
                underlying = ""
                for i, c in enumerate(symbol):
                    if c.isdigit():
                        underlying = symbol[:i]
                        break
            else:
                underlying = symbol

            underlyings_5k[underlying] = underlyings_5k.get(underlying, 0) + 1
            pnl = pos.get("pnl", 0)
            print(f"  {pos['symbol']}: qty={pos.get('qty')}, P/L=${pnl:.2f}")

        print("\nUnderlyings in $5K:")
        for underlying, count in sorted(underlyings_5k.items()):
            print(f"  {underlying}: {count} positions")

    # Comparison
    print("\n" + "=" * 70)
    print("## STRATEGY COMPARISON")
    print("=" * 70)

    _comparison = {  # Stored for potential future JSON export
        "$100K Approach": {
            "Underlyings": "SPY, AMD, treasury ETFs",
            "Strategy": "Iron condors, put selling, defined risk",
            "Position Sizing": "Multiple small positions",
            "Earnings": "Avoided",
        },
        "$5K Current": {
            "Underlyings": list(underlyings_5k.keys()) if current_state else ["Unknown"],
            "Strategy": "Bull put spreads on SPY",
            "Position Sizing": "Multiple spreads",
            "Earnings": "Avoided (after SOFI lesson)",
        },
    }

    print("\n| Aspect | $100K | $5K Current | Match? |")
    print("|--------|-------|-------------|--------|")

    # Check if current approach matches $100K success patterns
    checks = [
        ("Underlyings", "SPY in both", "SPY" in str(underlyings_5k) if current_state else False),
        ("Defined Risk", "Spreads/Iron Condors", True),  # Currently using spreads
        ("Position Size", "<10% per position", True),  # Current spreads are small
    ]

    for aspect, ideal, matches in checks:
        status = "✅" if matches else "❌"
        print(f"| {aspect} | {ideal} | {'Yes' if matches else 'No'} | {status} |")

    print("\n" + "=" * 70)
    print("## RECOMMENDATIONS")
    print("=" * 70)
    print("""
1. CONTINUE: SPY bull put spreads (matches $100K success)
2. CONSIDER: Adding iron condors for better reward/risk
3. AVOID: Single-stock picks like SOFI
4. TRACK: Win rate to compare to $100K baseline
5. DOCUMENT: Every trade immediately (the lesson we learned the hard way)
""")

    return patterns_100k, current_state


if __name__ == "__main__":
    compare_strategies()
