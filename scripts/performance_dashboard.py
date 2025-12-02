#!/usr/bin/env python3
"""
Performance Dashboard - Visual charts for P/L, win rate, positions
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

api = tradeapi.REST(
    os.getenv("APCA_API_KEY_ID") or os.getenv("ALPACA_API_KEY"),
    os.getenv("APCA_SECRET_KEY") or os.getenv("ALPACA_SECRET_KEY"),
    os.getenv("APCA_API_BASE_URL")
    or os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets"),
    api_version="v2",
)


def load_performance_log():
    """Load performance log data."""
    log_file = DATA_DIR / "performance_log.json"
    if not log_file.exists():
        return []

    with open(log_file) as f:
        data = json.load(f)

    # Handle both dict and list formats
    if isinstance(data, list):
        return data
    elif isinstance(data, dict):
        return data.get("entries", [])
    else:
        return []


def generate_text_chart(values, width=50, height=10):
    """Generate ASCII text chart."""
    if not values:
        return ""

    min_val = min(values)
    max_val = max(values)
    range_val = max_val - min_val if max_val != min_val else 1

    chart = []
    for i in range(height):
        threshold = max_val - (range_val * i / height)
        row = ""
        for val in values:
            if val >= threshold:
                row += "█"
            else:
                row += " "
        chart.append(row)

    return "\n".join(chart)


def display_dashboard():
    """Display performance dashboard."""
    print("=" * 70)
    print("📊 PERFORMANCE DASHBOARD")
    print("=" * 70)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Get account info
    try:
        account = api.get_account()
        equity = float(account.equity)
        cash = float(account.cash)
        portfolio_value = float(account.portfolio_value)

        print("💰 ACCOUNT OVERVIEW")
        print("-" * 70)
        print(f"Equity:        ${equity:,.2f}")
        print(f"Cash:          ${cash:,.2f}")
        print(f"Portfolio:     ${portfolio_value:,.2f}")
        print()
    except Exception as e:
        print(f"⚠️  Error fetching account: {e}")
        print()

    # Get positions
    try:
        positions = api.list_positions()

        if positions:
            print("📦 CURRENT POSITIONS")
            print("-" * 70)

            total_unrealized = 0
            position_data = []

            for pos in positions:
                symbol = pos.symbol
                qty = float(pos.qty)
                entry_price = float(pos.avg_entry_price)
                current_price = float(pos.current_price)
                unrealized_pl = float(pos.unrealized_pl)
                unrealized_plpc = float(pos.unrealized_plpc) * 100
                total_unrealized += unrealized_pl

                position_data.append(
                    {
                        "symbol": symbol,
                        "qty": qty,
                        "entry": entry_price,
                        "current": current_price,
                        "pl": unrealized_pl,
                        "pl_pct": unrealized_plpc,
                    }
                )

                emoji = "🟢" if unrealized_pl > 0 else "🔴"
                print(
                    f"{emoji} {symbol:6s} {qty:8.4f} shares  "
                    f"Entry: ${entry_price:7.2f}  Current: ${current_price:7.2f}  "
                    f"P/L: ${unrealized_pl:+8.2f} ({unrealized_plpc:+.2f}%)"
                )

            print()
            print(f"Total Unrealized P/L: ${total_unrealized:+,.2f}")
            print()

            # P/L chart
            pl_values = [p["pl_pct"] for p in position_data]
            if pl_values:
                print("P/L Distribution:")
                print(generate_text_chart(pl_values, width=50, height=5))
                print()
        else:
            print("📦 No open positions")
            print()
    except Exception as e:
        print(f"⚠️  Error fetching positions: {e}")
        print()

    # Performance over time
    perf_log = load_performance_log()
    if perf_log:
        print("📈 PERFORMANCE OVER TIME")
        print("-" * 70)

        # Last 30 days
        recent = perf_log[-30:]
        [e.get("date", "") for e in recent]
        pl_values = [e.get("pl", 0) for e in recent]
        equity_values = [e.get("equity", 0) for e in recent]

        if pl_values:
            print("P/L Trend (Last 30 Days):")
            print(generate_text_chart(pl_values, width=60, height=8))
            print()

            print(f"Best Day:  ${max(pl_values):+,.2f}")
            print(f"Worst Day: ${min(pl_values):+,.2f}")
            print(f"Avg Daily: ${sum(pl_values) / len(pl_values):+,.2f}")
            print()

        if equity_values:
            starting_equity = equity_values[0] if equity_values else 100000
            current_equity = equity_values[-1] if equity_values else 100000
            total_return = ((current_equity - starting_equity) / starting_equity) * 100

            print("Equity Trend:")
            print(generate_text_chart(equity_values, width=60, height=8))
            print()
            print(f"Starting Equity: ${starting_equity:,.2f}")
            print(f"Current Equity:  ${current_equity:,.2f}")
            print(f"Total Return:    {total_return:+.2f}%")
            print()

    # Trade statistics
    try:
        orders = api.list_orders(status="all", limit=100)
        buy_orders = [o for o in orders if o.side == "buy" and o.status == "filled"]
        sell_orders = [o for o in orders if o.side == "sell" and o.status == "filled"]

        print("📊 TRADE STATISTICS")
        print("-" * 70)
        print(f"Total Buy Orders:  {len(buy_orders)}")
        print(f"Total Sell Orders: {len(sell_orders)}")
        print(f"Open Positions:    {len(positions) if positions else 0}")
        print()
    except Exception as e:
        print(f"⚠️  Error fetching orders: {e}")
        print()

    print("=" * 70)


def main():
    """Run dashboard."""
    display_dashboard()


if __name__ == "__main__":
    main()
