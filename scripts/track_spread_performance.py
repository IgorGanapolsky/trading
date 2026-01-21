#!/usr/bin/env python3
"""
Track credit spread performance for data-driven strategy decisions.

Usage:
    # Add a trade
    python3 scripts/track_spread_performance.py add --symbol SOFI --premium 85 --pnl 85 --win
    python3 scripts/track_spread_performance.py add --symbol F --premium 100 --pnl -125 --loss

    # View summary
    python3 scripts/track_spread_performance.py summary

    # Check if ready for scaling decision
    python3 scripts/track_spread_performance.py decision

CEO Directive: Let real data decide strategy, not projections.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

DATA_FILE = Path(__file__).parent.parent / "data" / "spread_performance.json"


def load_data() -> dict:
    """Load performance data."""
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            return json.load(f)
    return {
        "meta": {"created": datetime.now().strftime("%Y-%m-%d")},
        "summary": {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate_pct": 0,
            "total_premium_collected": 0,
            "total_pnl": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "profit_factor": 0,
            "start_date": datetime.now().strftime("%Y-%m-%d"),
            "days_tracked": 0,
        },
        "trades": [],
    }


def save_data(data: dict) -> None:
    """Save performance data."""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def recalculate_summary(data: dict) -> None:
    """Recalculate summary statistics from trades."""
    trades = data["trades"]
    if not trades:
        return

    wins = [t for t in trades if t["is_win"]]
    losses = [t for t in trades if not t["is_win"]]

    total_wins_pnl = sum(t["pnl"] for t in wins)
    total_losses_pnl = sum(abs(t["pnl"]) for t in losses)

    data["summary"]["total_trades"] = len(trades)
    data["summary"]["wins"] = len(wins)
    data["summary"]["losses"] = len(losses)
    data["summary"]["win_rate_pct"] = round(len(wins) / len(trades) * 100, 1) if trades else 0
    data["summary"]["total_premium_collected"] = sum(t["premium"] for t in trades)
    data["summary"]["total_pnl"] = sum(t["pnl"] for t in trades)
    data["summary"]["avg_win"] = round(total_wins_pnl / len(wins), 2) if wins else 0
    data["summary"]["avg_loss"] = round(total_losses_pnl / len(losses), 2) if losses else 0
    data["summary"]["profit_factor"] = (
        round(total_wins_pnl / total_losses_pnl, 2) if total_losses_pnl > 0 else float("inf")
    )

    # Calculate days tracked
    start = datetime.strptime(data["summary"]["start_date"], "%Y-%m-%d")
    data["summary"]["days_tracked"] = (datetime.now() - start).days


def add_trade(symbol: str, premium: float, pnl: float, is_win: bool) -> None:
    """Add a new trade to the tracker."""
    data = load_data()

    trade = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "symbol": symbol.upper(),
        "premium": premium,
        "pnl": pnl,
        "is_win": is_win,
        "trade_num": len(data["trades"]) + 1,
    }

    data["trades"].append(trade)
    recalculate_summary(data)
    save_data(data)

    print(f"{'WIN' if is_win else 'LOSS'}: {symbol} | Premium: ${premium} | P/L: ${pnl}")
    print(
        f"Running: {data['summary']['wins']}W-{data['summary']['losses']}L ({data['summary']['win_rate_pct']}%)"
    )


def show_summary() -> None:
    """Display performance summary."""
    data = load_data()
    s = data["summary"]

    print("=" * 50)
    print("CREDIT SPREAD PERFORMANCE TRACKER")
    print("=" * 50)
    print(f"Tracking since: {s['start_date']} ({s['days_tracked']} days)")
    print(f"Total trades: {s['total_trades']}")
    print(f"Record: {s['wins']}W - {s['losses']}L")
    print(f"Win Rate: {s['win_rate_pct']}%")
    print("-" * 50)
    print(f"Total P/L: ${s['total_pnl']:,.2f}")
    print(f"Avg Win: ${s['avg_win']:,.2f}")
    print(f"Avg Loss: ${s['avg_loss']:,.2f}")
    print(f"Profit Factor: {s['profit_factor']}")
    print("=" * 50)

    # Show recent trades
    if data["trades"]:
        print("\nRecent trades:")
        for t in data["trades"][-5:]:
            status = "WIN" if t["is_win"] else "LOSS"
            print(f"  #{t['trade_num']} {t['date']} {t['symbol']}: {status} ${t['pnl']}")


def check_decision() -> None:
    """Check if ready for scaling decision."""
    data = load_data()
    s = data["summary"]

    print("\n" + "=" * 50)
    print("DECISION CHECKPOINT")
    print("=" * 50)

    trades_needed = 30 - s["total_trades"]
    days_needed = 90 - s["days_tracked"]

    if s["total_trades"] >= 30 or s["days_tracked"] >= 90:
        print("READY FOR DECISION")
        print("-" * 50)

        if s["win_rate_pct"] >= 70:
            print("WIN RATE: EXCELLENT (>=70%)")
            print("RECOMMENDATION: Scale to 3-5 spreads/week")
        elif s["win_rate_pct"] >= 60:
            print("WIN RATE: ACCEPTABLE (>=60%)")
            print("RECOMMENDATION: Maintain 2-3 spreads/week")
        else:
            print("WIN RATE: BELOW THRESHOLD (<60%)")
            print("RECOMMENDATION: Reassess strategy or targets")

        if s["profit_factor"] >= 1.5:
            print(f"PROFIT FACTOR: HEALTHY ({s['profit_factor']})")
        elif s["profit_factor"] >= 1.0:
            print(f"PROFIT FACTOR: MARGINAL ({s['profit_factor']})")
        else:
            print(f"PROFIT FACTOR: UNPROFITABLE ({s['profit_factor']})")
    else:
        print("NOT YET READY")
        print(f"Need: {max(trades_needed, 0)} more trades OR {max(days_needed, 0)} more days")
        print(f"Current: {s['total_trades']} trades, {s['days_tracked']} days")


def main():
    parser = argparse.ArgumentParser(description="Track credit spread performance")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Add trade command
    add_parser = subparsers.add_parser("add", help="Add a trade")
    add_parser.add_argument("--symbol", required=True, help="Stock symbol")
    add_parser.add_argument("--premium", type=float, required=True, help="Premium collected")
    add_parser.add_argument("--pnl", type=float, required=True, help="Final P/L")
    group = add_parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--win", action="store_true", help="Trade was profitable")
    group.add_argument("--loss", action="store_true", help="Trade was a loss")

    # Summary command
    subparsers.add_parser("summary", help="Show performance summary")

    # Decision command
    subparsers.add_parser("decision", help="Check if ready for scaling decision")

    args = parser.parse_args()

    if args.command == "add":
        add_trade(args.symbol, args.premium, args.pnl, args.win)
    elif args.command == "summary":
        show_summary()
    elif args.command == "decision":
        show_summary()
        check_decision()


if __name__ == "__main__":
    main()
