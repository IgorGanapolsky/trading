#!/usr/bin/env python3
"""
Trade Journal - Detailed analysis of each trade with reasoning
"""

import json
import os
from datetime import datetime
from pathlib import Path

import alpaca_trade_api as tradeapi
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
JOURNAL_DIR = DATA_DIR / "trade_journal"
JOURNAL_DIR.mkdir(exist_ok=True)

api = tradeapi.REST(
    os.getenv("APCA_API_KEY_ID") or os.getenv("ALPACA_API_KEY"),
    os.getenv("APCA_SECRET_KEY") or os.getenv("ALPACA_SECRET_KEY"),
    os.getenv("APCA_API_BASE_URL")
    or os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets"),
    api_version="v2",
)


def get_trade_context(symbol, entry_date=None):
    """Get market context for a trade."""
    try:
        # Get recent bars
        bars = api.get_bars(symbol, tradeapi.TimeFrame.Day, limit=30).df

        if bars.empty:
            return {}

        current_price = float(bars["close"].iloc[-1])
        high_30d = float(bars["high"].max())
        low_30d = float(bars["low"].min())
        volatility = float(bars["close"].pct_change().std() * 100)

        return {
            "current_price": current_price,
            "high_30d": high_30d,
            "low_30d": low_30d,
            "volatility_30d": volatility,
            "price_range_30d": high_30d - low_30d,
        }
    except Exception as e:
        return {"error": str(e)}


def record_trade_entry(symbol, entry_price, quantity, tier, reason, indicators=None):
    """Record a new trade entry in the journal."""
    trade_id = f"{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    context = get_trade_context(symbol)

    entry = {
        "trade_id": trade_id,
        "symbol": symbol,
        "tier": tier,
        "entry": {
            "timestamp": datetime.now().isoformat(),
            "price": entry_price,
            "quantity": quantity,
            "value": entry_price * quantity,
            "reason": reason,
            "indicators": indicators or {},
        },
        "context": context,
        "status": "open",
        "notes": [],
    }

    # Save to journal
    journal_file = JOURNAL_DIR / f"{trade_id}.json"
    with open(journal_file, "w") as f:
        json.dump(entry, f, indent=2)

    # Update index
    update_journal_index(entry)

    return trade_id


def record_trade_exit(trade_id, exit_price, exit_reason, pnl, pnl_pct):
    """Record trade exit in the journal."""
    journal_file = JOURNAL_DIR / f"{trade_id}.json"

    if not journal_file.exists():
        print(f"⚠️  Trade journal entry not found: {trade_id}")
        return

    with open(journal_file) as f:
        entry = json.load(f)

    entry["exit"] = {
        "timestamp": datetime.now().isoformat(),
        "price": exit_price,
        "reason": exit_reason,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
    }

    entry["status"] = "closed"

    # Calculate holding period
    if "entry" in entry:
        entry_date = datetime.fromisoformat(entry["entry"]["timestamp"])
        exit_date = datetime.fromisoformat(entry["exit"]["timestamp"])
        holding_days = (exit_date - entry_date).days
        entry["holding_days"] = holding_days

    # Add analysis
    entry["analysis"] = analyze_trade(entry)

    # Save
    with open(journal_file, "w") as f:
        json.dump(entry, f, indent=2)

    # Update index
    update_journal_index(entry)

    return entry


def analyze_trade(entry):
    """Analyze a completed trade."""
    if entry["status"] != "closed":
        return {}

    analysis = {
        "outcome": "win" if entry["exit"]["pnl"] > 0 else "loss",
        "performance": (
            "excellent"
            if entry["exit"]["pnl_pct"] > 5
            else (
                "good"
                if entry["exit"]["pnl_pct"] > 2
                else "poor"
                if entry["exit"]["pnl_pct"] < -3
                else "acceptable"
            )
        ),
    }

    # Check if stop-loss was hit
    if "stop-loss" in entry["exit"]["reason"].lower():
        analysis["stop_loss_hit"] = True
        analysis["risk_management"] = (
            "effective" if entry["exit"]["pnl_pct"] > -5 else "needs_improvement"
        )

    # Check if take-profit was hit
    if "take-profit" in entry["exit"]["reason"].lower():
        analysis["take_profit_hit"] = True

    return analysis


def update_journal_index(entry):
    """Update the journal index file."""
    index_file = JOURNAL_DIR / "index.json"

    if index_file.exists():
        with open(index_file) as f:
            index = json.load(f)
    else:
        index = {"trades": []}

    # Add or update entry
    trade_id = entry["trade_id"]
    existing = next((t for t in index["trades"] if t["trade_id"] == trade_id), None)

    if existing:
        index["trades"].remove(existing)

    index["trades"].append(
        {
            "trade_id": trade_id,
            "symbol": entry["symbol"],
            "tier": entry["tier"],
            "status": entry["status"],
            "entry_date": entry["entry"]["timestamp"],
            "exit_date": entry.get("exit", {}).get("timestamp"),
            "pnl": entry.get("exit", {}).get("pnl", 0),
            "pnl_pct": entry.get("exit", {}).get("pnl_pct", 0),
        }
    )

    # Sort by entry date (newest first)
    index["trades"].sort(key=lambda x: x["entry_date"], reverse=True)

    with open(index_file, "w") as f:
        json.dump(index, f, indent=2)


def get_journal_summary():
    """Get summary of all trades."""
    index_file = JOURNAL_DIR / "index.json"

    if not index_file.exists():
        return {
            "total_trades": 0,
            "open_trades": 0,
            "closed_trades": 0,
            "win_rate": 0.0,
            "total_pnl": 0.0,
        }

    with open(index_file) as f:
        index = json.load(f)

    trades = index.get("trades", [])
    closed = [t for t in trades if t["status"] == "closed"]
    wins = [t for t in closed if t["pnl"] > 0]

    return {
        "total_trades": len(trades),
        "open_trades": len([t for t in trades if t["status"] == "open"]),
        "closed_trades": len(closed),
        "win_rate": len(wins) / len(closed) * 100 if closed else 0.0,
        "total_pnl": sum(t["pnl"] for t in closed),
        "avg_pnl": sum(t["pnl"] for t in closed) / len(closed) if closed else 0.0,
    }


def main():
    """Display trade journal summary."""
    summary = get_journal_summary()

    print("=" * 60)
    print("📔 TRADE JOURNAL SUMMARY")
    print("=" * 60)
    print(f"Total Trades: {summary['total_trades']}")
    print(f"Open: {summary['open_trades']} | Closed: {summary['closed_trades']}")
    print(f"Win Rate: {summary['win_rate']:.1f}%")
    print(f"Total P/L: ${summary['total_pnl']:+,.2f}")
    print(f"Avg P/L: ${summary['avg_pnl']:+,.2f}")
    print()
    print(f"Journal location: {JOURNAL_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
