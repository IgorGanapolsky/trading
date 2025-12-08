#!/usr/bin/env python3
"""
Order Verification Script - "Trust but Verify" Layer

This script validates our local trade logs against Alpaca's actual order data.
It ensures that:
1. Every order we logged actually exists in Alpaca
2. Order statuses match reality (filled, rejected, cancelled, etc.)
3. Filled quantities match expectations
4. Fill prices are within acceptable slippage limits (1% warning, 2% error)

Anti-Lying Mandate Compliance:
- Ground truth source: Alpaca API (always)
- Local logs: Unverified until proven correct
- Reports ALL discrepancies clearly
- Fails CI if critical issues detected

Exit codes:
- 0: All orders verified successfully
- 1: Critical issues found (missing orders, high slippage, rejections)

GitHub Actions integration:
- Sets GITHUB_OUTPUT variables for CI workflows
- Provides clear, actionable error messages

Requirements:
- Run `pip install -r requirements.txt` to install dependencies
- Requires alpaca-py>=0.43.2
"""

import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Check for required dependencies
try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import GetOrdersRequest
    from alpaca.trading.enums import QueryOrderStatus
except ImportError as e:
    print(f"\n❌ ERROR: Missing required dependencies")
    print(f"   {e}")
    print(f"\n💡 Install dependencies:")
    print(f"   pip install -r requirements.txt")
    sys.exit(1)

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
PAPER_TRADING = os.getenv("PAPER_TRADING", "true").lower() == "true"

# Slippage thresholds
SLIPPAGE_WARNING_PCT = 1.0  # Warn if slippage > 1%
SLIPPAGE_ERROR_PCT = 2.0    # Fail if slippage > 2%

# Color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def get_trades_log_path() -> Path:
    """Get path to today's trades log file."""
    today = date.today().strftime("%Y-%m-%d")
    return Path(__file__).parent.parent / "data" / f"trades_{today}.json"


def load_local_trades() -> list[dict[str, Any]]:
    """Load today's trades from local log file."""
    trades_path = get_trades_log_path()

    if not trades_path.exists():
        return []

    try:
        with open(trades_path) as f:
            trades = json.load(f)
            return trades if isinstance(trades, list) else []
    except (json.JSONDecodeError, IOError) as e:
        print(f"{Colors.YELLOW}⚠️  Warning: Could not read trades log: {e}{Colors.RESET}")
        return []


def fetch_alpaca_orders(api: TradingClient) -> dict[str, Any]:
    """
    Fetch today's orders from Alpaca API.

    Returns:
        Dictionary mapping order_id -> order object
    """
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Create request for all orders from today
    request = GetOrdersRequest(
        status=QueryOrderStatus.ALL,
        after=today,
        limit=500  # Maximum limit
    )

    orders = api.get_orders(filter=request)

    # Create lookup dictionary
    orders_dict = {}
    for order in orders:
        orders_dict[str(order.id)] = order

    return orders_dict


def verify_order(
    trade: dict[str, Any],
    alpaca_orders: dict[str, Any]
) -> dict[str, Any]:
    """
    Verify a single trade against Alpaca's records.

    Returns:
        Dictionary with verification results:
        - exists: bool - Order exists in Alpaca
        - status_match: bool - Status matches expectation
        - quantity_match: bool - Filled qty matches (if applicable)
        - slippage_ok: bool - Slippage within limits
        - slippage_pct: float - Actual slippage percentage
        - issues: list[str] - List of issues found
    """
    result = {
        "symbol": trade.get("symbol", "UNKNOWN"),
        "exists": False,
        "status_match": False,
        "quantity_match": False,
        "slippage_ok": True,
        "slippage_pct": None,
        "slippage_usd": None,
        "issues": []
    }

    # Check if trade has order_id
    order_id = trade.get("order_id")
    if not order_id:
        result["issues"].append("No order_id in local log (cannot verify)")
        return result

    # Check if order exists in Alpaca
    alpaca_order = alpaca_orders.get(str(order_id))
    if not alpaca_order:
        result["issues"].append(f"Order {order_id} NOT FOUND in Alpaca")
        return result

    result["exists"] = True
    result["alpaca_status"] = str(alpaca_order.status)

    # Verify status
    expected_status = trade.get("status", "").upper()
    actual_status = str(alpaca_order.status).upper()

    # Map common status variations
    status_map = {
        "FILLED": ["FILLED"],
        "PARTIAL": ["PARTIALLY_FILLED", "PARTIAL_FILL"],
        "REJECTED": ["REJECTED", "CANCELED", "CANCELLED"],
        "PENDING": ["NEW", "ACCEPTED", "PENDING_NEW", "PENDING_CANCEL", "PENDING_REPLACE"]
    }

    # Check if statuses match (with variations)
    status_matches = False
    for expected_group, actual_group in status_map.items():
        if expected_status in actual_group and actual_status in actual_group:
            status_matches = True
            break

    # Direct match also counts
    if expected_status == actual_status:
        status_matches = True

    result["status_match"] = status_matches

    if not status_matches:
        result["issues"].append(
            f"Status mismatch: logged={expected_status}, actual={actual_status}"
        )

    # Verify quantity (only for filled/partial orders)
    if actual_status in ["FILLED", "PARTIALLY_FILLED"]:
        logged_qty = trade.get("quantity", 0)
        filled_qty = float(alpaca_order.filled_qty) if alpaca_order.filled_qty else 0

        # Allow small rounding differences (0.01%)
        qty_tolerance = max(logged_qty * 0.0001, 0.00001)

        if abs(filled_qty - logged_qty) <= qty_tolerance:
            result["quantity_match"] = True
        else:
            result["quantity_match"] = False
            result["issues"].append(
                f"Quantity mismatch: logged={logged_qty}, filled={filled_qty}"
            )
    else:
        # For non-filled orders, quantity check N/A
        result["quantity_match"] = True

    # Verify slippage (only if we have both prices)
    logged_price = trade.get("price")
    filled_price = float(alpaca_order.filled_avg_price) if alpaca_order.filled_avg_price else None

    if logged_price and filled_price:
        # Calculate slippage percentage
        slippage_pct = ((filled_price - logged_price) / logged_price) * 100

        # For sells, flip the sign (we want higher prices)
        if trade.get("action") == "SELL":
            slippage_pct = -slippage_pct

        result["slippage_pct"] = slippage_pct

        # Calculate dollar slippage
        filled_qty = float(alpaca_order.filled_qty) if alpaca_order.filled_qty else 0
        slippage_usd = (filled_price - logged_price) * filled_qty
        if trade.get("action") == "SELL":
            slippage_usd = -slippage_usd
        result["slippage_usd"] = slippage_usd

        # Check slippage thresholds
        if abs(slippage_pct) > SLIPPAGE_ERROR_PCT:
            result["slippage_ok"] = False
            result["issues"].append(
                f"CRITICAL: Slippage {slippage_pct:+.2f}% exceeds {SLIPPAGE_ERROR_PCT}% limit"
            )
        elif abs(slippage_pct) > SLIPPAGE_WARNING_PCT:
            result["issues"].append(
                f"WARNING: Slippage {slippage_pct:+.2f}% exceeds {SLIPPAGE_WARNING_PCT}% threshold"
            )

    # Check for rejections
    if actual_status in ["REJECTED", "CANCELED", "CANCELLED", "EXPIRED"]:
        result["issues"].append(f"Order was {actual_status}")

    return result


def write_github_output(stats: dict[str, Any]) -> None:
    """Write results to GITHUB_OUTPUT for CI integration."""
    github_output = os.getenv("GITHUB_OUTPUT")
    if not github_output:
        return

    try:
        with open(github_output, "a") as f:
            f.write(f"orders_verified={str(stats['all_verified']).lower()}\n")
            f.write(f"orders_filled={stats['filled_count']}\n")
            f.write(f"orders_rejected={stats['rejected_count']}\n")
            f.write(f"orders_missing={stats['missing_count']}\n")
            f.write(f"orders_slippage_errors={stats['slippage_errors']}\n")
    except Exception as e:
        print(f"{Colors.YELLOW}⚠️  Could not write to GITHUB_OUTPUT: {e}{Colors.RESET}")


def main() -> int:
    """Main verification routine."""
    print(f"\n{Colors.BOLD}{'=' * 80}{Colors.RESET}")
    print(f"{Colors.BOLD}📋 ORDER VERIFICATION REPORT - Trust but Verify{Colors.RESET}")
    print(f"{Colors.BOLD}{'=' * 80}{Colors.RESET}\n")

    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')}")
    print(f"🌐 Mode: {'Paper Trading' if PAPER_TRADING else 'Live Trading'}")
    print()

    # Validate credentials
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        print(f"{Colors.RED}❌ ERROR: Missing ALPACA_API_KEY or ALPACA_SECRET_KEY{Colors.RESET}")
        return 1

    # Load local trades
    print(f"{Colors.BLUE}📖 Loading local trade logs...{Colors.RESET}")
    local_trades = load_local_trades()

    if not local_trades:
        print(f"{Colors.YELLOW}⚠️  No trades found in local log for today{Colors.RESET}")
        print(f"   Log path: {get_trades_log_path()}")
        print(f"\n{Colors.GREEN}✅ VERIFICATION PASSED: No trades to verify{Colors.RESET}\n")

        # Write GitHub output (all zeros)
        write_github_output({
            "all_verified": True,
            "filled_count": 0,
            "rejected_count": 0,
            "missing_count": 0,
            "slippage_errors": 0
        })
        return 0

    print(f"{Colors.GREEN}   Found {len(local_trades)} logged trades{Colors.RESET}\n")

    # Initialize Alpaca client
    print(f"{Colors.BLUE}🌐 Connecting to Alpaca API...{Colors.RESET}")
    try:
        api = TradingClient(
            api_key=ALPACA_API_KEY,
            secret_key=ALPACA_SECRET_KEY,
            paper=PAPER_TRADING
        )
    except Exception as e:
        print(f"{Colors.RED}❌ ERROR: Failed to connect to Alpaca: {e}{Colors.RESET}")
        return 1

    # Fetch Alpaca orders
    print(f"{Colors.BLUE}📥 Fetching orders from Alpaca...{Colors.RESET}")
    try:
        alpaca_orders = fetch_alpaca_orders(api)
        print(f"{Colors.GREEN}   Found {len(alpaca_orders)} orders in Alpaca{Colors.RESET}\n")
    except Exception as e:
        print(f"{Colors.RED}❌ ERROR: Failed to fetch Alpaca orders: {e}{Colors.RESET}")
        return 1

    # Verify each trade
    print(f"{Colors.BOLD}{'─' * 80}{Colors.RESET}")
    print(f"{Colors.BOLD}🔍 VERIFICATION RESULTS{Colors.RESET}")
    print(f"{Colors.BOLD}{'─' * 80}{Colors.RESET}\n")

    results = []
    stats = {
        "total": len(local_trades),
        "verified": 0,
        "missing_count": 0,
        "filled_count": 0,
        "rejected_count": 0,
        "slippage_errors": 0,
        "has_errors": False
    }

    for i, trade in enumerate(local_trades, 1):
        symbol = trade.get("symbol", "UNKNOWN")
        action = trade.get("action", "UNKNOWN")

        print(f"{Colors.BOLD}[{i}/{len(local_trades)}] {symbol} - {action}{Colors.RESET}")

        result = verify_order(trade, alpaca_orders)
        results.append(result)

        # Print verification details
        if result["exists"]:
            print(f"  ✅ Order found in Alpaca (ID: {trade.get('order_id')})")
            print(f"  📊 Status: {result.get('alpaca_status', 'UNKNOWN')}")

            if result["slippage_pct"] is not None:
                slippage_color = Colors.GREEN
                if abs(result["slippage_pct"]) > SLIPPAGE_ERROR_PCT:
                    slippage_color = Colors.RED
                elif abs(result["slippage_pct"]) > SLIPPAGE_WARNING_PCT:
                    slippage_color = Colors.YELLOW

                print(f"  💰 Slippage: {slippage_color}{result['slippage_pct']:+.2f}%{Colors.RESET} "
                      f"(${result.get('slippage_usd', 0):+.4f})")

            # Update stats
            if result.get('alpaca_status') == "filled":
                stats["filled_count"] += 1
            elif result.get('alpaca_status') in ["rejected", "canceled", "cancelled"]:
                stats["rejected_count"] += 1
        else:
            print(f"  {Colors.RED}❌ Order NOT FOUND in Alpaca{Colors.RESET}")
            stats["missing_count"] += 1

        # Print issues
        if result["issues"]:
            for issue in result["issues"]:
                if "CRITICAL" in issue:
                    print(f"  {Colors.RED}🚨 {issue}{Colors.RESET}")
                    stats["has_errors"] = True
                    if "slippage" in issue.lower():
                        stats["slippage_errors"] += 1
                elif "WARNING" in issue:
                    print(f"  {Colors.YELLOW}⚠️  {issue}{Colors.RESET}")
                else:
                    print(f"  {Colors.YELLOW}ℹ️  {issue}{Colors.RESET}")
                    if "NOT FOUND" in issue:
                        stats["has_errors"] = True
        else:
            print(f"  {Colors.GREEN}✅ All checks passed{Colors.RESET}")
            stats["verified"] += 1

        print()  # Blank line between orders

    # Summary
    print(f"{Colors.BOLD}{'─' * 80}{Colors.RESET}")
    print(f"{Colors.BOLD}📊 SUMMARY{Colors.RESET}")
    print(f"{Colors.BOLD}{'─' * 80}{Colors.RESET}\n")

    print(f"Total trades logged:     {stats['total']}")
    print(f"✅ Verified:             {stats['verified']}")
    print(f"📈 Filled:               {stats['filled_count']}")
    print(f"❌ Rejected/Cancelled:   {stats['rejected_count']}")
    print(f"🔍 Missing from Alpaca:  {stats['missing_count']}")
    print(f"⚠️  Slippage errors:      {stats['slippage_errors']}")

    # Final verdict
    print()
    all_verified = stats["verified"] == stats["total"] and not stats["has_errors"]
    stats["all_verified"] = all_verified

    if all_verified:
        print(f"{Colors.GREEN}{Colors.BOLD}✅ VERIFICATION PASSED{Colors.RESET}")
        print(f"{Colors.GREEN}   All orders verified successfully against Alpaca API{Colors.RESET}")
        exit_code = 0
    else:
        print(f"{Colors.RED}{Colors.BOLD}❌ VERIFICATION FAILED{Colors.RESET}")
        if stats["missing_count"] > 0:
            print(f"{Colors.RED}   {stats['missing_count']} orders missing from Alpaca{Colors.RESET}")
        if stats["slippage_errors"] > 0:
            print(f"{Colors.RED}   {stats['slippage_errors']} orders with excessive slippage{Colors.RESET}")
        if stats["rejected_count"] > 0:
            print(f"{Colors.YELLOW}   {stats['rejected_count']} orders rejected/cancelled{Colors.RESET}")
        exit_code = 1

    # Write GitHub Actions output
    write_github_output(stats)

    print(f"\n{Colors.BOLD}{'=' * 80}{Colors.RESET}\n")

    return exit_code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚠️  Verification interrupted by user{Colors.RESET}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Colors.RED}❌ FATAL ERROR: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
