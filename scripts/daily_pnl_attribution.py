#!/usr/bin/env python3
"""
Daily P&L Attribution Report - Prevents LL-020/LL-035 blind spots.

This script runs daily to show EXACTLY which strategies are making money
so we never miss an obvious insight like "options = 100% of profits" again.

Usage:
    python3 scripts/daily_pnl_attribution.py
    python3 scripts/daily_pnl_attribution.py --days 30  # Last 30 days

Created: Dec 15, 2025
Lesson: LL-020 - Options Primary Strategy (missed for 3 days)
"""

import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def load_trade_files(days: int = 30) -> list[dict]:
    """Load all trade files from the last N days."""
    trades = []
    data_dir = PROJECT_ROOT / "data"
    cutoff = datetime.now() - timedelta(days=days)
    
    for trade_file in data_dir.glob("trades_*.json"):
        try:
            # Parse date from filename
            date_str = trade_file.stem.replace("trades_", "")
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
            
            if file_date >= cutoff:
                with open(trade_file) as f:
                    day_trades = json.load(f)
                    for trade in day_trades:
                        trade["file_date"] = date_str
                    trades.extend(day_trades)
        except (ValueError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load {trade_file}: {e}")
    
    return trades


def load_system_state() -> dict:
    """Load current system state."""
    state_file = PROJECT_ROOT / "data" / "system_state.json"
    if state_file.exists():
        with open(state_file) as f:
            return json.load(f)
    return {}


def categorize_trade(trade: dict) -> str:
    """Categorize a trade by strategy type."""
    symbol = trade.get("symbol", "")
    strategy = trade.get("strategy", "")
    
    # Options
    if "P0" in symbol or "C0" in symbol or "options" in strategy.lower():
        return "OPTIONS"
    
    # Crypto
    if symbol.endswith("USD") or "crypto" in strategy.lower():
        return "CRYPTO"
    
    # Bonds
    if symbol in ["BIL", "SHY", "IEF", "TLT", "GOVT", "ZROZ"]:
        return "BONDS"
    
    # REITs
    if symbol in ["VNQ", "O", "VICI", "AMT", "CCI", "DLR", "EQIX", "PLD"]:
        return "REITS"
    
    # Precious Metals
    if symbol in ["GLD", "SLV", "IAU"]:
        return "PRECIOUS_METALS"
    
    # Core ETFs
    if symbol in ["SPY", "QQQ", "VOO", "IWM", "DIA"]:
        return "CORE_ETFS"
    
    # Growth stocks
    if symbol in ["NVDA", "GOOGL", "AMZN", "MSFT", "AMD", "AAPL"]:
        return "GROWTH_STOCKS"
    
    return "OTHER"


def calculate_pnl_attribution(trades: list[dict], state: dict) -> dict:
    """Calculate P&L attribution by strategy."""
    attribution = defaultdict(lambda: {
        "realized_pl": 0.0,
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "symbols": set()
    })
    
    # Process closed trades from system state
    for trade in state.get("performance", {}).get("closed_trades", []):
        category = categorize_trade(trade)
        pl = trade.get("pl", 0)
        
        attribution[category]["realized_pl"] += pl
        attribution[category]["trades"] += 1
        attribution[category]["symbols"].add(trade.get("symbol", ""))
        
        if pl > 0:
            attribution[category]["wins"] += 1
        elif pl < 0:
            attribution[category]["losses"] += 1
    
    # Convert sets to lists for JSON serialization
    for cat in attribution:
        attribution[cat]["symbols"] = list(attribution[cat]["symbols"])
        
        # Calculate win rate
        total = attribution[cat]["wins"] + attribution[cat]["losses"]
        if total > 0:
            attribution[cat]["win_rate"] = (attribution[cat]["wins"] / total) * 100
        else:
            attribution[cat]["win_rate"] = 0.0
    
    return dict(attribution)


def generate_report(attribution: dict) -> str:
    """Generate a formatted P&L attribution report."""
    lines = []
    lines.append("=" * 70)
    lines.append("📊 DAILY P&L ATTRIBUTION REPORT")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 70)
    lines.append("")
    
    # Sort by P/L descending
    sorted_cats = sorted(
        attribution.items(),
        key=lambda x: x[1]["realized_pl"],
        reverse=True
    )
    
    total_pl = sum(a["realized_pl"] for _, a in sorted_cats)
    
    # Header
    lines.append(f"{'Strategy':<20} {'P/L':>12} {'% of Total':>12} {'Win Rate':>10} {'Trades':>8}")
    lines.append("-" * 70)
    
    # Each strategy
    for category, data in sorted_cats:
        pl = data["realized_pl"]
        pct = (pl / total_pl * 100) if total_pl != 0 else 0
        wr = data["win_rate"]
        trades = data["trades"]
        
        # Emoji indicator
        if pl > 0:
            emoji = "🟢"
        elif pl < 0:
            emoji = "🔴"
        else:
            emoji = "⚪"
        
        lines.append(f"{emoji} {category:<17} ${pl:>10,.2f} {pct:>11.1f}% {wr:>9.0f}% {trades:>8}")
    
    lines.append("-" * 70)
    lines.append(f"{'TOTAL':<20} ${total_pl:>10,.2f}")
    lines.append("")
    
    # Insights
    lines.append("=" * 70)
    lines.append("🎯 KEY INSIGHTS")
    lines.append("=" * 70)
    
    if sorted_cats:
        top_cat, top_data = sorted_cats[0]
        top_pct = (top_data["realized_pl"] / total_pl * 100) if total_pl != 0 else 0
        
        if top_pct >= 80:
            lines.append(f"⚠️  CONCENTRATION ALERT: {top_cat} generates {top_pct:.0f}% of profits!")
            lines.append(f"   → Consider increasing {top_cat} allocation")
        
        if top_data["win_rate"] >= 70:
            lines.append(f"✅ {top_cat} has {top_data['win_rate']:.0f}% win rate - PROVEN WINNER")
        
        # Find losers
        losers = [(c, d) for c, d in sorted_cats if d["realized_pl"] < 0]
        for cat, data in losers:
            if data["trades"] >= 3:  # Only flag if enough data
                lines.append(f"❌ {cat} is LOSING money (${data['realized_pl']:.2f}) - REVIEW STRATEGY")
    
    lines.append("")
    
    # Recommendations
    lines.append("=" * 70)
    lines.append("📋 RECOMMENDED ACTIONS")
    lines.append("=" * 70)
    
    if sorted_cats:
        top_cat, top_data = sorted_cats[0]
        current_allocation = 0.35 if top_cat == "OPTIONS" else 0.10  # Rough estimate
        
        if top_data["win_rate"] >= 60 and top_data["realized_pl"] > 0:
            lines.append(f"1. INCREASE {top_cat} allocation (currently proven winner)")
            lines.append(f"2. Query RAG for '{top_cat.lower()} strategy optimization'")
        
        for cat, data in sorted_cats:
            if data["trades"] >= 3 and data["win_rate"] <= 30:
                lines.append(f"3. REDUCE or PAUSE {cat} (win rate: {data['win_rate']:.0f}%)")
    
    lines.append("")
    lines.append("Run: python3 scripts/mandatory_rag_check.py '<strategy> optimization'")
    lines.append("")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="P&L Attribution Report")
    parser.add_argument("--days", type=int, default=30, help="Days to analyze")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()
    
    # Load data
    trades = load_trade_files(args.days)
    state = load_system_state()
    
    # Calculate attribution
    attribution = calculate_pnl_attribution(trades, state)
    
    if args.json:
        print(json.dumps(attribution, indent=2))
    else:
        report = generate_report(attribution)
        print(report)
        
        # Save report
        report_file = PROJECT_ROOT / "reports" / f"pnl_attribution_{datetime.now().strftime('%Y%m%d')}.md"
        report_file.parent.mkdir(exist_ok=True)
        with open(report_file, "w") as f:
            f.write(report)
        print(f"Report saved to: {report_file}")


if __name__ == "__main__":
    main()
