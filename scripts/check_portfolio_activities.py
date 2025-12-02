#!/usr/bin/env python3
"""
Query Alpaca Portfolio Activities (trades, dividends, etc.)
"""

import os
import sys
from datetime import datetime

import alpaca_trade_api as tradeapi
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def main():
    # Get API credentials
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    paper_trading = os.getenv("PAPER_TRADING", "true").lower() == "true"

    if not api_key or not secret_key:
        print("ERROR: Missing ALPACA_API_KEY or ALPACA_SECRET_KEY in .env")
        sys.exit(1)

    # Initialize API
    base_url = "https://paper-api.alpaca.markets" if paper_trading else "https://api.alpaca.markets"
    api = tradeapi.REST(api_key, secret_key, base_url, api_version="v2")

    print("=" * 80)
    print("ALPACA PORTFOLIO ACTIVITIES")
    print(f"Query Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()

    try:
        # Get activities since Oct 29
        activities = api.get_activities(activity_types="FILL", date="2025-10-29", direction="desc")

        print("📊 ALL FILL ACTIVITIES (Since Oct 29, 2025)")
        print("-" * 80)

        if not activities:
            print("No fill activities found")
        else:
            print(f"Found {len(activities)} fill activities\n")

            buy_total = 0
            sell_total = 0

            for activity in activities:
                # Handle pandas Timestamp
                if hasattr(activity.transaction_time, "to_pydatetime"):
                    trans_time = activity.transaction_time.to_pydatetime()
                else:
                    trans_time = datetime.fromisoformat(
                        str(activity.transaction_time).replace("Z", "+00:00")
                    )

                symbol = activity.symbol
                side = activity.side
                qty = float(activity.qty)
                price = float(activity.price)
                total = qty * price

                if side == "buy":
                    buy_total += total
                else:
                    sell_total += total

                print(
                    f"{trans_time.strftime('%Y-%m-%d %H:%M:%S')} | {side.upper():4s} | {symbol:6s} | Qty: {qty:8.4f} | Price: ${price:8.2f} | Total: ${total:9.2f}"
                )

            print()
            print(f"Total Buys:  ${buy_total:,.2f}")
            print(f"Total Sells: ${sell_total:,.2f}")
            print(f"Net Investment: ${buy_total - sell_total:,.2f}")

        print()
        print("=" * 80)

        # Get portfolio history
        print("\n📈 PORTFOLIO HISTORY (Last 7 Days)")
        print("-" * 80)

        history = api.get_portfolio_history(period="1W", timeframe="1D")

        if history:
            print(f"Base Value: ${float(history.base_value):,.2f}")
            print("\nDaily Equity:")

            # Get timestamps and equity values
            timestamps = history.timestamp if hasattr(history, "timestamp") else []
            equity = history.equity if hasattr(history, "equity") else []
            profit_loss = history.profit_loss if hasattr(history, "profit_loss") else []
            profit_loss_pct = history.profit_loss_pct if hasattr(history, "profit_loss_pct") else []

            for i, ts in enumerate(timestamps):
                dt = datetime.fromtimestamp(ts)
                eq = equity[i] if i < len(equity) else 0
                pl = profit_loss[i] if i < len(profit_loss) else 0
                pl_pct = profit_loss_pct[i] if i < len(profit_loss_pct) else 0

                print(
                    f"  {dt.strftime('%Y-%m-%d')}: ${eq:,.2f} | P/L: ${pl:+,.2f} ({pl_pct * 100:+.2f}%)"
                )

        print()
        print("=" * 80)

    except Exception as e:
        print(f"ERROR querying Alpaca API: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
