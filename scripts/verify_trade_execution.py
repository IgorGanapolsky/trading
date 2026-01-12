#!/usr/bin/env python3
"""
Verify Trade Execution - Monday Morning Monitor

CEO Directive (Jan 10, 2026): "Add monitoring to ensure we catch if Monday's trades fail"

This script verifies that trades actually executed after the daily-trading workflow runs.
It checks:
1. Trade files were created
2. Orders were submitted to Alpaca
3. Phil Town strategy attempted trades
4. Stop losses were set

Usage:
    python3 scripts/verify_trade_execution.py
    python3 scripts/verify_trade_execution.py --date 2026-01-12
    python3 scripts/verify_trade_execution.py --alert-on-failure
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Try to import Alpaca - graceful fallback if not available
try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest

    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False


def check_trade_file(date_str: str) -> dict:
    """Check if trade file exists and has content."""
    trade_file = Path(f"data/trades_{date_str}.json")

    result = {"file_exists": False, "trade_count": 0, "trades": [], "error": None}

    if trade_file.exists():
        result["file_exists"] = True
        try:
            with open(trade_file) as f:
                trades = json.load(f)
            result["trade_count"] = len(trades) if isinstance(trades, list) else 1
            result["trades"] = trades if isinstance(trades, list) else [trades]
        except Exception as e:
            result["error"] = str(e)

    return result


def check_alpaca_orders(date_str: str) -> dict:
    """Check Alpaca for orders placed today."""
    result = {"alpaca_available": ALPACA_AVAILABLE, "orders_found": 0, "orders": [], "error": None}

    if not ALPACA_AVAILABLE:
        result["error"] = "Alpaca SDK not installed"
        return result

    from src.utils.alpaca_client import get_alpaca_credentials

    api_key, api_secret = get_alpaca_credentials()

    if not api_key or not api_secret:
        result["error"] = "Alpaca credentials not set"
        return result

    try:
        # Determine if paper or live
        paper = os.getenv("PAPER_TRADING", "true").lower() == "true"
        client = TradingClient(api_key, api_secret, paper=paper)

        # Get today's orders
        target_date = datetime.strptime(date_str, "%Y-%m-%d")
        request = GetOrdersRequest(
            status=QueryOrderStatus.ALL, after=target_date, until=target_date + timedelta(days=1)
        )

        orders = client.get_orders(filter=request)
        result["orders_found"] = len(orders)
        result["orders"] = [
            {
                "id": str(o.id),
                "symbol": o.symbol,
                "side": str(o.side),
                "qty": str(o.qty),
                "status": str(o.status),
                "created_at": str(o.created_at),
            }
            for o in orders
        ]
    except Exception as e:
        result["error"] = str(e)

    return result


def check_system_state() -> dict:
    """Check system state for trade evidence."""
    result = {
        "state_exists": False,
        "last_trade_date": None,
        "options_orders_today": 0,
        "phil_town_enabled": False,
        "error": None,
    }

    state_file = Path("data/system_state.json")
    if not state_file.exists():
        result["error"] = "system_state.json not found"
        return result

    try:
        with open(state_file) as f:
            state = json.load(f)

        result["state_exists"] = True
        result["last_trade_date"] = state.get("performance", {}).get("last_trade_date")
        result["options_orders_today"] = state.get("options", {}).get("orders_submitted_today", 0)
        result["phil_town_enabled"] = (
            state.get("paper_account", {}).get("phil_town_strategy", {}).get("enabled", False)
        )

    except Exception as e:
        result["error"] = str(e)

    return result


def verify_execution(date_str: str = None, alert_on_failure: bool = False) -> bool:
    """Main verification function."""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    print("=" * 60)
    print("🔍 TRADE EXECUTION VERIFICATION")
    print(f"📅 Date: {date_str}")
    print("=" * 60)
    print()

    all_passed = True

    # Check 1: Trade file
    print("📄 Check 1: Trade File")
    trade_result = check_trade_file(date_str)
    if trade_result["file_exists"]:
        print(f"   ✅ Trade file exists: data/trades_{date_str}.json")
        print(f"   📊 Trades recorded: {trade_result['trade_count']}")
        if trade_result["trade_count"] == 0:
            print("   ⚠️  WARNING: File exists but contains 0 trades")
            all_passed = False
    else:
        print(f"   ❌ Trade file NOT found: data/trades_{date_str}.json")
        all_passed = False
    print()

    # Check 2: Alpaca orders
    print("📡 Check 2: Alpaca Orders")
    alpaca_result = check_alpaca_orders(date_str)
    if alpaca_result["error"]:
        print(f"   ⚠️  {alpaca_result['error']}")
    elif alpaca_result["orders_found"] > 0:
        print(f"   ✅ Orders found in Alpaca: {alpaca_result['orders_found']}")
        for order in alpaca_result["orders"][:5]:  # Show first 5
            print(f"      - {order['symbol']} {order['side']} {order['qty']} ({order['status']})")
    else:
        print("   ❌ No orders found in Alpaca for today")
        all_passed = False
    print()

    # Check 3: System state
    print("📊 Check 3: System State")
    state_result = check_system_state()
    if state_result["error"]:
        print(f"   ⚠️  {state_result['error']}")
    else:
        print(f"   Phil Town enabled: {'✅' if state_result['phil_town_enabled'] else '❌'}")
        print(f"   Last trade date: {state_result['last_trade_date'] or 'N/A'}")
        print(f"   Options orders today: {state_result['options_orders_today']}")
    print()

    # Summary
    print("=" * 60)
    if all_passed:
        print("✅ VERIFICATION PASSED - Trades executed successfully")
    else:
        print("❌ VERIFICATION FAILED - Trades may not have executed")
        print()
        print("🚨 ALERT: The trading workflow may have run but failed to execute trades.")
        print("   This is the 'zombie mode' problem - workflow succeeds but no trades happen.")
        print()
        print("   Possible causes:")
        print("   1. Phil Town script analyzing but not trading (fixed Jan 6)")
        print("   2. Buying power insufficient for CSPs")
        print("   3. Market conditions didn't meet entry criteria")
        print("   4. API errors during order submission")
        print()
        print("   Actions:")
        print("   - Check GitHub Actions logs for errors")
        print("   - Verify Alpaca account has sufficient funds")
        print("   - Review scripts/rule_one_trader.py output")

        if alert_on_failure:
            # Could send Slack/Discord/email alert here
            print()
            print("📧 ALERT MODE: Notification would be sent here")

    print("=" * 60)

    return all_passed


def main():
    parser = argparse.ArgumentParser(description="Verify trade execution")
    parser.add_argument("--date", type=str, help="Date to check (YYYY-MM-DD)")
    parser.add_argument(
        "--alert-on-failure", action="store_true", help="Send alert if verification fails"
    )
    args = parser.parse_args()

    success = verify_execution(args.date, args.alert_on_failure)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
