#!/usr/bin/env python3
"""
Direct Alpaca API Query Script
Gets real-time account status, positions, and order history
"""

import os
import sys
from datetime import datetime

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import QueryOrderStatus
from alpaca.trading.requests import GetOrdersRequest
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
    api = TradingClient(api_key=api_key, secret_key=secret_key, paper=paper_trading)

    print("=" * 80)
    print("ALPACA ACCOUNT STATUS - REAL-TIME DATA")
    print(f"Environment: {'PAPER TRADING' if paper_trading else 'LIVE TRADING'}")
    print(f"Query Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()

    try:
        # Get account info
        print("📊 ACCOUNT OVERVIEW")
        print("-" * 80)
        account = api.get_account()

        equity = float(account.equity)
        cash = float(account.cash)
        buying_power = float(account.buying_power)
        portfolio_value = float(account.portfolio_value)
        last_equity = float(account.last_equity)

        # Calculate P/L
        total_pl = equity - last_equity
        total_pl_pct = (total_pl / last_equity * 100) if last_equity > 0 else 0

        print(f"Account Status: {account.status}")
        print(f"Current Equity: ${equity:,.2f}")
        print(f"Cash: ${cash:,.2f}")
        print(f"Buying Power: ${buying_power:,.2f}")
        print(f"Portfolio Value: ${portfolio_value:,.2f}")
        print(f"Last Equity (Previous Close): ${last_equity:,.2f}")
        print(f"Today's P/L: ${total_pl:+.2f} ({total_pl_pct:+.2f}%)")
        print()

        # Get current positions
        print("📈 CURRENT POSITIONS")
        print("-" * 80)
        positions = api.get_all_positions()

        if not positions:
            print("No open positions")
        else:
            total_position_value = 0
            total_unrealized_pl = 0

            for pos in positions:
                symbol = pos.symbol
                qty = float(pos.qty)
                current_price = float(pos.current_price)
                market_value = float(pos.market_value)
                cost_basis = float(pos.cost_basis)
                unrealized_pl = float(pos.unrealized_pl)
                unrealized_plpc = float(pos.unrealized_plpc) * 100
                avg_entry = float(pos.avg_entry_price)

                total_position_value += market_value
                total_unrealized_pl += unrealized_pl

                print(f"\n{symbol}:")
                print(f"  Quantity: {qty}")
                print(f"  Avg Entry Price: ${avg_entry:.2f}")
                print(f"  Current Price: ${current_price:.2f}")
                print(f"  Market Value: ${market_value:.2f}")
                print(f"  Cost Basis: ${cost_basis:.2f}")
                print(f"  Unrealized P/L: ${unrealized_pl:+.2f} ({unrealized_plpc:+.2f}%)")

            print(f"\nTOTAL Position Value: ${total_position_value:.2f}")
            print(f"TOTAL Unrealized P/L: ${total_unrealized_pl:+.2f}")

        print()

        # Get order history since Oct 29
        print("📋 ORDER HISTORY (Since Oct 29, 2025)")
        print("-" * 80)

        # Get all orders (last 500)
        request = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=500, nested=True)
        orders = api.get_orders(filter=request)

        # Filter orders since Oct 29
        start_date = datetime(2025, 10, 29)
        relevant_orders = []

        for order in orders:
            # Handle pandas Timestamp
            if hasattr(order.created_at, "to_pydatetime"):
                order_time = order.created_at.to_pydatetime()
            else:
                order_time = datetime.fromisoformat(str(order.created_at).replace("Z", "+00:00"))

            if order_time.replace(tzinfo=None) >= start_date:
                relevant_orders.append(order)

        if not relevant_orders:
            print("No orders found since Oct 29, 2025")
        else:
            print(f"Found {len(relevant_orders)} orders since Oct 29\n")

            filled_orders = []
            cancelled_orders = []
            pending_orders = []

            for order in sorted(relevant_orders, key=lambda x: x.created_at):
                # Handle pandas Timestamp
                if hasattr(order.created_at, "to_pydatetime"):
                    order_time = order.created_at.to_pydatetime()
                else:
                    order_time = datetime.fromisoformat(
                        str(order.created_at).replace("Z", "+00:00")
                    )
                symbol = order.symbol
                side = order.side
                qty = order.qty
                status = order.status

                if status == "filled":
                    filled_price = float(order.filled_avg_price) if order.filled_avg_price else 0
                    filled_qty = float(order.filled_qty) if order.filled_qty else 0
                    filled_orders.append(
                        {
                            "time": order_time,
                            "symbol": symbol,
                            "side": side,
                            "qty": filled_qty,
                            "price": filled_price,
                            "total": filled_qty * filled_price,
                        }
                    )
                    print(
                        f"{order_time.strftime('%Y-%m-%d %H:%M:%S')} | {status.upper():10s} | {side.upper():4s} | {symbol:6s} | Qty: {filled_qty:6.2f} | Price: ${filled_price:7.2f} | Total: ${filled_qty * filled_price:9.2f}"
                    )
                elif status in ["cancelled", "expired", "rejected"]:
                    cancelled_orders.append(order)
                    print(
                        f"{order_time.strftime('%Y-%m-%d %H:%M:%S')} | {status.upper():10s} | {side.upper():4s} | {symbol:6s} | Qty: {qty}"
                    )
                else:
                    pending_orders.append(order)
                    print(
                        f"{order_time.strftime('%Y-%m-%d %H:%M:%S')} | {status.upper():10s} | {side.upper():4s} | {symbol:6s} | Qty: {qty}"
                    )

            print()
            print(
                f"Summary: {len(filled_orders)} filled, {len(cancelled_orders)} cancelled/rejected, {len(pending_orders)} pending"
            )

            if filled_orders:
                total_invested = sum(o["total"] for o in filled_orders if o["side"] == "buy")
                print(f"Total Invested (Filled Buy Orders): ${total_invested:.2f}")

        print()
        print("=" * 80)
        print("Query Complete")
        print("=" * 80)

    except Exception as e:
        print(f"ERROR querying Alpaca API: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
