#!/usr/bin/env python3
"""
Fetch complete trade history from $100K paper trading account.

This script pulls ALL historical trades and analyzes what worked.
Run via GitHub Actions with ALPACA_PAPER_TRADING_API_KEY credentials.

Created: Jan 14, 2026
Purpose: Learn from our $100K account profits that we IGNORED
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path


def main():
    """Fetch and analyze $100K account trade history."""
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.enums import QueryOrderStatus
        from alpaca.trading.requests import GetOrdersRequest
    except ImportError:
        print("ERROR: alpaca-py not installed")
        return

    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")

    if not api_key or not secret_key:
        print("ERROR: Missing Alpaca credentials")
        return

    print("=" * 70)
    print("$100K PAPER ACCOUNT - COMPLETE TRADE HISTORY ANALYSIS")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 70)

    client = TradingClient(api_key, secret_key, paper=True)

    # Get account info
    account = client.get_account()
    equity = float(account.equity)
    print(f"\nCurrent Equity: ${equity:,.2f}")

    # Fetch ALL closed orders (going back 90 days)
    start_date = datetime.now() - timedelta(days=90)

    print(f"\nFetching orders since {start_date.date()}...")

    request = GetOrdersRequest(status=QueryOrderStatus.CLOSED, after=start_date, limit=500)

    orders = client.get_orders(filter=request)
    filled_orders = [o for o in orders if str(o.status) == "filled"]

    print(f"Total filled orders: {len(filled_orders)}")

    # Analyze trades
    trades_by_symbol = {}
    options_trades = []
    stock_trades = []

    for order in filled_orders:
        symbol = order.symbol
        side = str(order.side)
        qty = float(order.filled_qty) if order.filled_qty else 0
        avg_price = float(order.filled_avg_price) if order.filled_avg_price else 0
        filled_at = order.filled_at

        trade = {
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": avg_price,
            "notional": qty * avg_price,
            "filled_at": str(filled_at),
            "order_type": str(order.type),
        }

        # Track by symbol
        if symbol not in trades_by_symbol:
            trades_by_symbol[symbol] = []
        trades_by_symbol[symbol].append(trade)

        # Separate options vs stocks
        if len(symbol) > 10:  # Options have long symbols
            options_trades.append(trade)
        else:
            stock_trades.append(trade)

    # Output analysis
    print("\n" + "=" * 70)
    print("TRADES BY SYMBOL")
    print("=" * 70)

    for symbol, trades in sorted(trades_by_symbol.items(), key=lambda x: len(x[1]), reverse=True):
        total_notional = sum(t["notional"] for t in trades)
        buys = len([t for t in trades if "buy" in t["side"].lower()])
        sells = len([t for t in trades if "sell" in t["side"].lower()])
        print(f"\n{symbol}:")
        print(f"  Total trades: {len(trades)} (buys: {buys}, sells: {sells})")
        print(f"  Total notional: ${total_notional:,.2f}")
        for t in trades[-5:]:  # Show last 5 trades
            print(f"    {t['side']:4} {t['qty']:.2f} @ ${t['price']:.2f} on {t['filled_at'][:10]}")

    print("\n" + "=" * 70)
    print("OPTIONS TRADES SUMMARY")
    print("=" * 70)
    print(f"Total options trades: {len(options_trades)}")

    # Group options by underlying
    options_by_underlying = {}
    for trade in options_trades:
        # Extract underlying from option symbol (e.g., AMD260116P00200000 -> AMD)
        underlying = ""
        for i, char in enumerate(trade["symbol"]):
            if char.isdigit():
                underlying = trade["symbol"][:i]
                break

        if underlying not in options_by_underlying:
            options_by_underlying[underlying] = []
        options_by_underlying[underlying].append(trade)

    for underlying, trades in sorted(
        options_by_underlying.items(), key=lambda x: len(x[1]), reverse=True
    ):
        sells = [t for t in trades if "sell" in t["side"].lower()]
        buys = [t for t in trades if "buy" in t["side"].lower()]
        sell_premium = sum(t["notional"] for t in sells)
        buy_premium = sum(t["notional"] for t in buys)
        net_premium = sell_premium - buy_premium

        print(f"\n{underlying} Options:")
        print(f"  Sells: {len(sells)} (collected ${sell_premium:,.2f})")
        print(f"  Buys: {len(buys)} (spent ${buy_premium:,.2f})")
        print(f"  Net premium: ${net_premium:,.2f}")

    print("\n" + "=" * 70)
    print("STOCK/ETF TRADES SUMMARY")
    print("=" * 70)
    print(f"Total stock/ETF trades: {len(stock_trades)}")

    # Save full data to JSON
    output_data = {
        "fetch_timestamp": datetime.now().isoformat(),
        "account_equity": equity,
        "total_filled_orders": len(filled_orders),
        "options_trades_count": len(options_trades),
        "stock_trades_count": len(stock_trades),
        "trades_by_symbol": {k: v for k, v in trades_by_symbol.items()},
        "options_by_underlying": {k: v for k, v in options_by_underlying.items()},
    }

    output_file = Path("data/100k_trade_history_analysis.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(output_data, indent=2, default=str))
    print(f"\n✅ Full data saved to {output_file}")

    # Create lesson learned
    lesson_content = f"""# Lesson Learned: $100K Paper Account Trade Analysis

## Date: {datetime.now().strftime("%Y-%m-%d")}
## Severity: HIGH

## Summary
Analysis of {len(filled_orders)} filled orders from the $100K paper trading account.

## Key Findings

### Options Trading
- Total options trades: {len(options_trades)}
- Underlyings traded: {", ".join(options_by_underlying.keys())}

### What Worked
"""

    # Add top performers
    for underlying, trades in sorted(
        options_by_underlying.items(), key=lambda x: len(x[1]), reverse=True
    )[:3]:
        sells = [t for t in trades if "sell" in t["side"].lower()]
        buys = [t for t in trades if "buy" in t["side"].lower()]
        sell_premium = sum(t["notional"] for t in sells)
        buy_premium = sum(t["notional"] for t in buys)
        net = sell_premium - buy_premium
        lesson_content += f"- **{underlying}**: Net premium ${net:,.2f} from {len(trades)} trades\n"

    lesson_content += f"""
### Stock/ETF Trading
- Total trades: {len(stock_trades)}

## Application to $5K Account
- Focus on underlyings that generated consistent premium
- Use same strike selection methodology that worked
- Apply position sizing proportionally

## Action Items
- [ ] Replicate successful strategies on $5K account
- [ ] Track win rate by underlying
- [ ] Compare $5K results to $100K baseline
"""

    lesson_file = Path("rag_knowledge/lessons_learned/ll_203_100k_account_analysis_jan14.md")
    lesson_file.parent.mkdir(parents=True, exist_ok=True)
    lesson_file.write_text(lesson_content)
    print(f"✅ Lesson saved to {lesson_file}")

    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
