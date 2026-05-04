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
import ssl
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NamedTuple, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.alpaca_client import (  # noqa: E402
    get_alpaca_client,
    get_alpaca_credentials,
)


class DailyReport(NamedTuple):
    date: str
    traded_today: bool
    orders_today: int
    structures_today: int
    fills_today: int
    positions_count: int
    equity: float
    cash: float
    daily_pnl: float
    total_pnl: float
    last_equity: float
    starting_equity: float = 100000.0


class LatestTrade(NamedTuple):
    date: Optional[str]
    symbol: Optional[str]


def _today_et() -> tuple[str, datetime]:
    """Return today's date string and start-of-day timestamp in America/New_York."""
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("America/New_York")
        now = datetime.now(tz)
        today = now.strftime("%Y-%m-%d")
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return today, start
    except Exception:
        # Fallback to UTC.
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return today, start


def _fetch_fills_count_for_date(date_str: str, paper: bool = True) -> int:
    """Fetch fill count for a given date via Alpaca account activities endpoint."""
    api_key, secret_key = get_alpaca_credentials()
    if not api_key or not secret_key:
        return 0

    host = "paper-api.alpaca.markets" if paper else "api.alpaca.markets"
    url = f"https://{host}/v2/account/activities/FILL?date={date_str}"
    req = urllib.request.Request(
        url,
        headers={
            "accept": "application/json",
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": secret_key,
        },
    )
    ssl_context = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=15, context=ssl_context) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        return 0
    return len(payload)


def _count_structures_from_trade_file(date_str: str) -> int:
    """Count strategy structures (not Alpaca-synced fills) from data/trades_{date}.json."""
    trades_path = Path("data") / f"trades_{date_str}.json"
    if not trades_path.exists():
        return 0
    try:
        payload = json.loads(trades_path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    if not isinstance(payload, list):
        return 0

    structures = 0
    for item in payload:
        if not isinstance(item, dict):
            continue
        if item.get("strategy") == "alpaca_sync":
            continue
        # Structure heuristics: order_ids present OR multi-leg dict recorded by strategy.
        if item.get("order_ids") or (isinstance(item.get("legs"), dict) and item.get("underlying")):
            structures += 1
    return structures


def _extract_latest_trade_from_orders(client: Any) -> Optional[LatestTrade]:
    """Best-effort latest fill lookup to keep last_trade_date fresh even if sync lagged."""
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest

    from src.utils.trade_activity import parse_trade_timestamp

    try:
        orders_request = GetOrdersRequest(status=QueryOrderStatus.CLOSED, limit=50, nested=True)
        orders = client.get_orders(filter=orders_request)
    except TypeError:
        orders_request = GetOrdersRequest(status=QueryOrderStatus.CLOSED, limit=50)
        orders = client.get_orders(filter=orders_request)
    except Exception:
        return None

    for order in orders:
        filled_at = parse_trade_timestamp(getattr(order, "filled_at", None))
        if filled_at is None:
            continue

        symbol = getattr(order, "symbol", None)
        if not symbol:
            for leg in getattr(order, "legs", None) or []:
                leg_symbol = (
                    leg.get("symbol") if isinstance(leg, dict) else getattr(leg, "symbol", None)
                )
                if leg_symbol:
                    symbol = str(leg_symbol)
                    break

        if filled_at.tzinfo is None:
            filled_at = filled_at.replace(tzinfo=timezone.utc)
        else:
            filled_at = filled_at.astimezone(timezone.utc)

        return LatestTrade(
            date=filled_at.date().isoformat(), symbol=str(symbol) if symbol else None
        )

    return None


def _report_payload(report: DailyReport) -> dict[str, Any]:
    return {
        "date": report.date,
        "traded": report.traded_today,
        "orders": report.orders_today,
        "structures": report.structures_today,
        "fills": report.fills_today,
        "positions": report.positions_count,
        "equity": report.equity,
        "last_equity": report.last_equity,
        "daily_pnl": report.daily_pnl,
        "total_pnl": report.total_pnl,
    }


def _dedupe_reports_by_date(rows: list[Any]) -> list[dict[str, Any]]:
    latest_by_date: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        date_value = row.get("date")
        if not isinstance(date_value, str) or not date_value.strip():
            continue
        latest_by_date[date_value.strip()] = row
    return [latest_by_date[date_key] for date_key in sorted(latest_by_date)]


def _calculate_trading_days_since_last_trade(last_trade_date: Optional[str]) -> Optional[int]:
    if not last_trade_date:
        return None

    try:
        from monitor_trade_activity import calculate_days_since_trade

        return int(calculate_days_since_trade(last_trade_date))
    except Exception:
        return None


def _update_system_state_from_report(
    report: DailyReport, *, latest_trade: Optional[LatestTrade] = None
) -> None:
    """Mirror canonical intraday metrics into data/system_state.json to prevent UI mismatches."""
    state_path = Path("data") / "system_state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        if not isinstance(state, dict):
            state = {}
    except Exception:
        state = {}

    state.setdefault("paper_account", {})
    state.setdefault("trades", {})
    state.setdefault("meta", {})
    state.setdefault("sync_health", {})
    now_iso = datetime.now(timezone.utc).isoformat()

    state["paper_account"]["equity"] = report.equity
    state["paper_account"]["current_equity"] = report.equity
    state["paper_account"]["cash"] = report.cash
    state["paper_account"]["last_equity"] = report.last_equity
    state["paper_account"]["positions_count"] = int(report.positions_count)
    state["paper_account"]["daily_change"] = round(float(report.daily_pnl or 0.0), 2)

    state["trades"]["metrics_date"] = report.date
    state["trades"]["orders_today"] = int(report.orders_today)
    state["trades"]["structures_today"] = int(report.structures_today)
    state["trades"]["fills_today"] = int(report.fills_today)
    # Backward-compat fields for older dashboards.
    state["trades"]["today_trades"] = int(report.fills_today)
    state["trades"]["total_trades_today"] = int(report.fills_today)
    if latest_trade and latest_trade.date:
        state["trades"]["last_trade_date"] = latest_trade.date
    if latest_trade and latest_trade.symbol:
        state["trades"]["last_trade_symbol"] = latest_trade.symbol
    elif report.traded_today:
        state["trades"]["last_trade_symbol"] = state["trades"].get("last_trade_symbol")

    state["meta"]["last_updated"] = now_iso
    state["meta"]["last_daily_verification_at"] = now_iso
    state["meta"]["verification_source"] = "daily_verification.py"
    state["sync_health"]["last_attempt"] = now_iso
    state["sync_health"]["sync_source"] = "daily_verification.py"
    state["last_updated"] = now_iso

    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = state_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp_path.replace(state_path)


def verify_today() -> DailyReport:
    """Verify what actually happened today."""
    today, today_start = _today_et()

    client = get_alpaca_client()
    if not client:
        print("❌ CRITICAL: Cannot connect to Alpaca!")
        print("   Check ALPACA_API_KEY and ALPACA_SECRET_KEY")
        return DailyReport(
            date=today,
            traded_today=False,
            orders_today=0,
            structures_today=0,
            fills_today=0,
            positions_count=0,
            equity=0,
            cash=0,
            daily_pnl=0,
            total_pnl=0,
            last_equity=0,
        )

    # Get account info
    account = client.get_account()
    equity = float(account.equity)
    cash = float(account.cash)
    starting = 100000.0  # Our starting capital
    total_pnl = equity - starting
    try:
        last_equity = float(account.last_equity)
    except Exception:
        last_equity = 0.0

    # Get today's orders
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest

    try:
        orders_request = GetOrdersRequest(
            status=QueryOrderStatus.ALL,
            after=today_start,
            nested=True,
        )
        orders = client.get_orders(filter=orders_request)
        orders_today = len(orders)
    except Exception as e:
        print(f"⚠️ Could not fetch orders: {e}")
        orders_today = 0

    # Get positions
    positions = client.get_all_positions()
    positions_count = len(positions)

    # Calculate daily P/L from Alpaca last_equity (canonical).
    daily_pnl = equity - last_equity if last_equity else 0.0

    # Fills are per-execution; fetch from Alpaca activities endpoint for accuracy.
    try:
        fills_today = _fetch_fills_count_for_date(today, paper=True)
    except Exception as e:
        print(f"⚠️ Could not fetch fills from account activities: {e}")
        fills_today = 0

    # "Structures" are strategy-level entries recorded to the trades file.
    structures_today = _count_structures_from_trade_file(today)

    latest_trade = _extract_latest_trade_from_orders(client)
    traded_today = fills_today > 0

    report = DailyReport(
        date=today,
        traded_today=traded_today,
        orders_today=orders_today,
        structures_today=structures_today,
        fills_today=fills_today,
        positions_count=positions_count,
        equity=equity,
        cash=cash,
        daily_pnl=daily_pnl,
        total_pnl=total_pnl,
        last_equity=last_equity,
        starting_equity=starting,
    )
    _update_system_state_from_report(report, latest_trade=latest_trade)
    return report


def print_report(report: DailyReport):
    """Print a clear, honest report."""
    print("\n" + "=" * 50)
    print(f"📊 DAILY VERIFICATION REPORT - {report.date}")
    print("=" * 50)

    # Trade status - the most important thing
    if report.traded_today:
        print(
            f"\n✅ ACTIVITY TODAY: {report.structures_today} structure(s), {report.fills_today} fill(s)"
        )
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

    reports.append(_report_payload(report))
    reports = _dedupe_reports_by_date(reports)

    # Keep last 90 days
    reports = reports[-90:]

    with open(reports_file, "w") as f:
        json.dump(reports, f, indent=2)

    print(f"📁 Report saved to {reports_file}")


def check_consecutive_no_trades():
    """Alert if we haven't traded in multiple days."""
    try:
        state = json.loads(Path("data/system_state.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        state = {}

    last_trade_date = None
    if isinstance(state, dict):
        last_trade_date = state.get("trades", {}).get("last_trade_date")

    trading_days_without_activity = _calculate_trading_days_since_last_trade(last_trade_date)
    if trading_days_without_activity is None:
        reports_file = "data/verification_reports.json"
        try:
            with open(reports_file) as f:
                reports = _dedupe_reports_by_date(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError):
            return

        trading_days_without_activity = 0
        for report in reversed(reports):
            if not report.get("traded", False):
                trading_days_without_activity += 1
            else:
                break

    if trading_days_without_activity >= 3:
        print(f"\n🚨 ALERT: NO TRADES FOR {trading_days_without_activity} TRADING DAYS!")
        print("   The system may be broken. Investigate immediately.")


if __name__ == "__main__":
    report = verify_today()
    print_report(report)
    check_consecutive_no_trades()
