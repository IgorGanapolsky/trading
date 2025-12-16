#!/usr/bin/env python3
"""
Quick verification script for checking account status, positions, and P&L.

Usage:
    python3 scripts/verify_trades.py
    python3 scripts/verify_trades.py --crypto-only
    python3 scripts/verify_trades.py --date 2025-12-13
"""

import argparse
import os
from datetime import datetime

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import QueryOrderStatus
from alpaca.trading.requests import GetOrdersRequest


def load_env():
    """Load environment variables from .env file."""
    from pathlib import Path

    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.strip() and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()


def verify_account(client: TradingClient) -> dict:
    """Get account status and equity."""
    account = client.get_account()
    return {
        "cash": float(account.cash),
        "portfolio_value": float(account.portfolio_value),
        "equity": float(account.equity),
        "buying_power": float(account.buying_power),
    }


def verify_positions(client: TradingClient) -> list:
    """Get current positions with P&L."""
    positions = client.get_all_positions()

    results = []
    total_pnl = 0

    for pos in positions:
        pnl = float(pos.unrealized_pl)
        pnl_pct = float(pos.unrealized_plpc) * 100
        total_pnl += pnl

        results.append(
            {
                "symbol": pos.symbol,
                "qty": float(pos.qty),
                "entry_price": float(pos.avg_entry_price),
                "current_price": float(pos.current_price),
                "market_value": float(pos.market_value),
                "unrealized_pl": pnl,
                "unrealized_plpc": pnl_pct,
            }
        )

    return results, total_pnl


def verify_orders(client: TradingClient, date: str = None) -> list:
    """Get recent orders for a specific date."""
    request = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=100)

    orders = client.get_orders(filter=request)

    if date:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
        orders = [o for o in orders if o.created_at.date() == target_date]

    results = []
    for order in orders:
        filled_price = float(order.filled_avg_price) if order.filled_avg_price else 0
        filled_qty = float(order.filled_qty) if order.filled_qty else 0

        results.append(
            {
                "created_at": order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "symbol": order.symbol,
                "side": order.side.value,
                "qty": float(order.qty) if order.qty else 0,
                "filled_qty": filled_qty,
                "status": order.status.value,
                "filled_price": filled_price,
                "order_type": order.type.value,
            }
        )

    return results


def main():
    parser = argparse.ArgumentParser(description="Verify trades and account status")
    parser.add_argument("--date", type=str, help="Filter orders by date (YYYY-MM-DD)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    # Load environment
    load_env()

    # Create client
    client = TradingClient(
        api_key=os.getenv("ALPACA_API_KEY"), secret_key=os.getenv("ALPACA_SECRET_KEY"), paper=True
    )

    if args.json:
        import json

        account = verify_account(client)
        positions, total_pnl = verify_positions(client)
        orders = verify_orders(client, args.date)

        print(
            json.dumps(
                {
                    "account": account,
                    "positions": positions,
                    "total_unrealized_pl": total_pnl,
                    "orders": orders,
                },
                indent=2,
            )
        )
        return

    # Account status
    print("💰 ACCOUNT STATUS")
    print("=" * 60)
    account = verify_account(client)
    print(f"Cash:            ${account['cash']:,.2f}")
    print(f"Portfolio Value: ${account['portfolio_value']:,.2f}")
    print(f"Equity:          ${account['equity']:,.2f}")
    print(f"Buying Power:    ${account['buying_power']:,.2f}")
    print()

    # Positions
    print("📊 POSITIONS")
    print("=" * 60)
    positions, total_pnl = verify_positions(client)

    if positions:
        for pos in positions:
            print(f"\n{pos['symbol']}:")
            print(f"  Quantity:      {pos['qty']:,.6f}")
            print(f"  Entry Price:   ${pos['entry_price']:,.2f}")
            print(f"  Current Price: ${pos['current_price']:,.2f}")
            print(f"  Market Value:  ${pos['market_value']:,.2f}")
            print(
                f"  Unrealized P&L: ${pos['unrealized_pl']:+,.2f} ({pos['unrealized_plpc']:+.2f}%)"
            )

        print(f"\n{'─' * 60}")
        print(f"TOTAL UNREALIZED P&L: ${total_pnl:+,.2f}")
    else:
        print("No positions found")

    print()

    # Orders
    date_str = f" ({args.date})" if args.date else ""
    print("📝 ORDERS" + date_str)
    print("=" * 60)
    orders = verify_orders(client, args.date)

    if orders:
        for order in orders[:20]:  # Show first 20
            print(
                f"{order['created_at']}: {order['symbol']} {order['side']} {order['filled_qty']:.6f}"
            )
            print(f"  Status: {order['status']} | Price: ${order['filled_price']:,.2f}")

        if len(orders) > 20:
            print(f"\n... and {len(orders) - 20} more orders")
    else:
        print("No orders found")


if __name__ == "__main__":
    main()
