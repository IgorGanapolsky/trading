#!/usr/bin/env python3
"""
Standalone script to update performance log with current account status.
Can be run independently of trading execution to capture daily P/L.
Also ensures daily trades are synced from Alpaca if the local trades file is missing.
"""

import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

import alpaca.trading.client as trading_client
from alpaca.trading.enums import QueryOrderStatus
from alpaca.trading.requests import GetOrdersRequest
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup paths
DATA_DIR = Path(__file__).parent.parent / "data"
PERF_FILE = DATA_DIR / "performance_log.json"


def get_account_summary(client=None):
    """Get current account performance from Alpaca API"""
    paper_trading = os.getenv("PAPER_TRADING", "true").lower() == "true"

    if client is None:
        from src.utils.alpaca_client import get_alpaca_credentials

        api_key, secret_key = get_alpaca_credentials()

        if not api_key or not secret_key:
            print("ERROR: Missing ALPACA_API_KEY or ALPACA_SECRET_KEY in .env")
            sys.exit(1)

        client = trading_client.TradingClient(api_key, secret_key, paper=paper_trading)

    account = client.get_account()

    # CRITICAL: Use correct starting balance based on account type
    # Live account: $20 starting (Jan 3, 2026)
    # Paper account: $100,000 starting
    if paper_trading:
        starting_balance = 100000.0
        account_type = "PAPER"
    else:
        starting_balance = 20.0  # Live account fresh start Jan 3, 2026
        account_type = "LIVE"

    print(f"📊 Account Type: {account_type} (starting balance: ${starting_balance:,.2f})")

    return {
        "equity": float(account.equity),
        "cash": float(account.cash),
        "buying_power": float(account.buying_power),
        "pl": float(account.equity) - starting_balance,
        "pl_pct": ((float(account.equity) - starting_balance) / starting_balance) * 100,
        "account_type": account_type,
        "starting_balance": starting_balance,
    }


def sync_daily_trades(client):
    """Fetch today's trades from Alpaca and save if local file missing."""
    today = date.today()
    trades_file = DATA_DIR / f"trades_{today.isoformat()}.json"

    if trades_file.exists():
        print(f"✅ Trades file for {today} already exists. Skipping sync.")
        return

    print(f"Testing for trades from Alpaca for {today}...")

    try:
        # Get filled orders from today
        request_params = GetOrdersRequest(
            status=QueryOrderStatus.CLOSED,
            after=datetime.combine(today, datetime.min.time()),
            limit=500,
        )

        orders = client.get_orders(filter=request_params)

        if not orders:
            print("ℹ️ No trades found on Alpaca for today.")
            return

        trades = []
        for order in orders:
            # Check filled_at to be sure it's today
            if order.filled_at and order.filled_at.date() == today:
                trades.append(
                    {
                        "symbol": order.symbol,
                        "action": order.side.name,
                        "amount": float(order.filled_avg_price or 0) * float(order.filled_qty or 0),
                        "quantity": float(order.filled_qty or 0),
                        "price": float(order.filled_avg_price or 0),
                        "timestamp": order.filled_at.isoformat(),
                        "status": "FILLED",
                        "strategy": "Unknown (Synced)",
                        "reason": "Synced from Alpaca",
                        "mode": "PAPER",
                    }
                )

        if trades:
            print(f"✅ Recovered {len(trades)} trades from Alpaca.")
            with open(trades_file, "w") as f:
                json.dump(trades, f, indent=4)
        else:
            print("ℹ️ No filled trades found for today (after filtering).")

    except Exception as e:
        print(f"⚠️ Failed to sync trades: {e}")


def update_performance_log():
    """Update daily performance log"""
    print("=" * 70)
    print("📊 UPDATING PERFORMANCE LOG")
    print("=" * 70)

    # Initialize client once
    from src.utils.alpaca_client import get_alpaca_credentials

    api_key, secret_key = get_alpaca_credentials()
    paper_trading = os.getenv("PAPER_TRADING", "true").lower() == "true"

    if not api_key or not secret_key:
        print("ERROR: Missing ALPACA_API_KEY or ALPACA_SECRET_KEY in .env")
        sys.exit(1)

    client = trading_client.TradingClient(api_key, secret_key, paper=paper_trading)

    # Sync trades first
    sync_daily_trades(client)

    # Load existing data
    perf_data = []
    if PERF_FILE.exists():
        with open(PERF_FILE) as f:
            perf_data = json.load(f)
        print(f"✅ Loaded {len(perf_data)} existing entries")
    else:
        print("📝 Creating new performance log")

    # Get current account status
    print("\n📡 Fetching current account status from Alpaca...")
    summary = get_account_summary(client)
    summary["date"] = date.today().isoformat()
    summary["timestamp"] = datetime.now().isoformat()

    # Check if entry for today already exists
    today = date.today().isoformat()
    existing_today = [e for e in perf_data if e.get("date") == today]

    if existing_today:
        print(f"⚠️  Entry for today ({today}) already exists")
        print(
            f"   Existing: Equity ${existing_today[0]['equity']:,.2f}, P/L ${existing_today[0]['pl']:+,.2f}"
        )
        print(f"   New:      Equity ${summary['equity']:,.2f}, P/L ${summary['pl']:+,.2f}")

        # Update existing entry
        for i, entry in enumerate(perf_data):
            if entry.get("date") == today:
                perf_data[i] = summary
                print("   ✅ Updated existing entry")
                break
    else:
        # Append new entry
        perf_data.append(summary)
        print(f"✅ Added new entry for {today}")

    # Save updated log
    with open(PERF_FILE, "w") as f:
        json.dump(perf_data, f, indent=2)

    print("\n" + "=" * 70)
    print("📊 PERFORMANCE SUMMARY")
    print("=" * 70)
    print(f"Date:        {summary['date']}")
    print(f"Equity:      ${summary['equity']:,.2f}")
    print(f"Cash:        ${summary['cash']:,.2f}")
    print(f"Buying Power: ${summary['buying_power']:,.2f}")
    print(f"P/L:         ${summary['pl']:+,.2f} ({summary['pl_pct']:+.2f}%)")
    print(f"Timestamp:   {summary['timestamp']}")
    print("=" * 70)

    return summary


if __name__ == "__main__":
    try:
        update_performance_log()
        print("\n✅ Performance log updated successfully!")
    except Exception as e:
        print(f"\n❌ Error updating performance log: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
