#!/usr/bin/env python3
"""
Daily Trade Verification System

Simple, honest verification that answers:
1. Did we trade today?
2. What positions do we have?
3. Did we make or lose money?

No complexity. No lies. Just facts.
"""

import json
from datetime import datetime
from typing import NamedTuple


class DailyReport(NamedTuple):
    date: str
    traded_today: bool
    orders_today: int
    fills_today: int
    positions_count: int
    equity: float
    cash: float
    daily_pnl: float
    total_pnl: float
    starting_equity: float = 100000.0


def get_alpaca_client():
    """Get Alpaca client or None if not configured."""
    from src.utils.alpaca_client import get_alpaca_client as _get_client

    return _get_client(paper=True)


def verify_today() -> DailyReport:
    """Verify what actually happened today."""
    today = datetime.now().strftime("%Y-%m-%d")

    client = get_alpaca_client()
    if not client:
        print("❌ CRITICAL: Cannot connect to Alpaca!")
        print("   Check ALPACA_API_KEY and ALPACA_SECRET_KEY")
        return DailyReport(
            date=today,
            traded_today=False,
            orders_today=0,
            fills_today=0,
            positions_count=0,
            equity=0,
            cash=0,
            daily_pnl=0,
            total_pnl=0,
        )

    # Get account info
    account = client.get_account()
    equity = float(account.equity)
    cash = float(account.cash)
    starting = 100000.0  # Our starting capital
    total_pnl = equity - starting

    # Get today's orders
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest

    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    try:
        orders_request = GetOrdersRequest(
            status=QueryOrderStatus.ALL,
            after=today_start,
        )
        orders = client.get_orders(filter=orders_request)
        orders_today = len(orders)
        fills_today = len([o for o in orders if o.status.value == "filled"])
    except Exception as e:
        print(f"⚠️ Could not fetch orders: {e}")
        orders_today = 0
        fills_today = 0

    # Get positions
    positions = client.get_all_positions()
    positions_count = len(positions)

    # Calculate daily P/L (approximate - Alpaca doesn't give daily directly)
    # We'll use last_equity from account if available
    try:
        last_equity = float(account.last_equity)
        daily_pnl = equity - last_equity
    except Exception:
        daily_pnl = 0.0

    traded_today = fills_today > 0

    return DailyReport(
        date=today,
        traded_today=traded_today,
        orders_today=orders_today,
        fills_today=fills_today,
        positions_count=positions_count,
        equity=equity,
        cash=cash,
        daily_pnl=daily_pnl,
        total_pnl=total_pnl,
        starting_equity=starting,
    )


def print_report(report: DailyReport):
    """Print a clear, honest report."""
    print("\n" + "=" * 50)
    print(f"📊 DAILY VERIFICATION REPORT - {report.date}")
    print("=" * 50)

    # Trade status - the most important thing
    if report.traded_today:
        print(f"\n✅ TRADED TODAY: {report.fills_today} order(s) filled")
    else:
        print("\n❌ NO TRADES TODAY")
        if report.orders_today > 0:
            print(f"   ⚠️ {report.orders_today} orders submitted but 0 filled")
        else:
            print("   No orders were even submitted")

    # Money status
    print("\n💰 ACCOUNT STATUS:")
    print(f"   Equity:     ${report.equity:,.2f}")
    print(f"   Cash:       ${report.cash:,.2f}")
    print(f"   Positions:  {report.positions_count}")

    # P/L status
    print("\n📈 PROFIT/LOSS:")
    daily_emoji = "🟢" if report.daily_pnl >= 0 else "🔴"
    total_emoji = "🟢" if report.total_pnl >= 0 else "🔴"
    print(f"   Today:  {daily_emoji} ${report.daily_pnl:+,.2f}")
    print(
        f"   Total:  {total_emoji} ${report.total_pnl:+,.2f} ({report.total_pnl / report.starting_equity * 100:+.2f}%)"
    )

    # North Star check
    print("\n🎯 NORTH STAR CHECK:")
    days_elapsed = 0
    try:
        with open("data/system_state.json") as f:
            state = json.load(f)
        days_elapsed = int(state.get("paper_trading", {}).get("current_day", 0))
    except Exception:
        pass
    days_elapsed = max(1, days_elapsed)
    target_daily = 200.0  # $6K/month after-tax ~= $200/day
    expected_profit = days_elapsed * target_daily
    print(f"   Target:  ${expected_profit:,.2f} (${target_daily}/day × {days_elapsed} days)")
    print(f"   Actual:  ${report.total_pnl:,.2f}")
    gap = expected_profit - report.total_pnl
    print(f"   Gap:     ${gap:,.2f} behind target")

    print("\n" + "=" * 50)

    # Save to file for tracking
    save_report(report)


def save_report(report: DailyReport):
    """Save report to JSON for historical tracking."""
    reports_file = "data/verification_reports.json"

    try:
        with open(reports_file) as f:
            reports = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        reports = []

    # Add today's report
    reports.append(
        {
            "date": report.date,
            "traded": report.traded_today,
            "orders": report.orders_today,
            "fills": report.fills_today,
            "positions": report.positions_count,
            "equity": report.equity,
            "daily_pnl": report.daily_pnl,
            "total_pnl": report.total_pnl,
        }
    )

    # Keep last 90 days
    reports = reports[-90:]

    with open(reports_file, "w") as f:
        json.dump(reports, f, indent=2)

    print(f"📁 Report saved to {reports_file}")


def check_consecutive_no_trades():
    """Alert if we haven't traded in multiple days."""
    reports_file = "data/verification_reports.json"

    try:
        with open(reports_file) as f:
            reports = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return

    # Count consecutive days without trades
    consecutive = 0
    for report in reversed(reports):
        if not report.get("traded", False):
            consecutive += 1
        else:
            break

    if consecutive >= 3:
        print(f"\n🚨 ALERT: NO TRADES FOR {consecutive} CONSECUTIVE DAYS!")
        print("   The system may be broken. Investigate immediately.")


if __name__ == "__main__":
    report = verify_today()
    print_report(report)
    check_consecutive_no_trades()
