#!/usr/bin/env python3
"""
Trade Activity Monitor - Detects "Zombie Mode"

PROBLEM: Trading workflow can report "success" but execute ZERO trades.
This happened for 13 days (Dec 23 - Jan 5, 2026) due to max_positions=3 bug.

SOLUTION: This script checks for actual trade activity and alerts if:
1. No trades for 3+ consecutive trading days
2. Workflow claims success but no trade files exist
3. Trade count is suspiciously low

Usage:
    python scripts/monitor_trade_activity.py
    python scripts/monitor_trade_activity.py --days 5 --alert-threshold 3
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# US Market holidays 2026 (approximate)
US_HOLIDAYS_2026 = {
    "2026-01-01",  # New Year's Day
    "2026-01-19",  # MLK Day
    "2026-02-16",  # Presidents Day
    "2026-04-03",  # Good Friday
    "2026-05-25",  # Memorial Day
    "2026-07-03",  # Independence Day (observed)
    "2026-09-07",  # Labor Day
    "2026-11-26",  # Thanksgiving
    "2026-12-25",  # Christmas
}


def is_trading_day(date: datetime) -> bool:
    """Check if a date is a US trading day."""
    # Weekend check
    if date.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False
    # Holiday check
    date_str = date.strftime("%Y-%m-%d")
    if date_str in US_HOLIDAYS_2026:
        return False
    return True


def get_trading_days(start_date: datetime, end_date: datetime) -> list:
    """Get list of trading days between two dates."""
    trading_days = []
    current = start_date
    while current <= end_date:
        if is_trading_day(current):
            trading_days.append(current)
        current += timedelta(days=1)
    return trading_days


def get_trade_files(data_dir: Path, days: int = 7) -> dict:
    """Get trade files from the last N days."""
    trade_files = {}
    today = datetime.now()

    for i in range(days):
        check_date = today - timedelta(days=i)
        date_str = check_date.strftime("%Y-%m-%d")
        file_path = data_dir / f"trades_{date_str}.json"

        if file_path.exists():
            try:
                with open(file_path) as f:
                    trades = json.load(f)
                    trade_count = len(trades) if isinstance(trades, list) else 0
                    trade_files[date_str] = {
                        "exists": True,
                        "count": trade_count,
                        "path": str(file_path)
                    }
            except (json.JSONDecodeError, Exception) as e:
                trade_files[date_str] = {
                    "exists": True,
                    "count": 0,
                    "error": str(e)
                }
        else:
            trade_files[date_str] = {"exists": False, "count": 0}

    return trade_files


def get_last_trade_date(data_dir: Path) -> str | None:
    """Find the most recent trade file."""
    trade_files = sorted(data_dir.glob("trades_*.json"), reverse=True)

    for f in trade_files:
        # Extract date from filename: trades_YYYY-MM-DD.json
        try:
            date_str = f.stem.replace("trades_", "")
            # Validate it's a real date
            datetime.strptime(date_str, "%Y-%m-%d")
            return date_str
        except ValueError:
            continue

    return None


def calculate_days_since_trade(last_trade_date: str) -> int:
    """Calculate trading days since last trade."""
    if not last_trade_date:
        return 999  # No trades ever

    last_date = datetime.strptime(last_trade_date, "%Y-%m-%d")
    today = datetime.now()

    # Count trading days between last trade and today
    trading_days = get_trading_days(last_date + timedelta(days=1), today)
    return len(trading_days)


def check_system_state(data_dir: Path) -> dict:
    """Check system_state.json for trade activity."""
    state_file = data_dir / "system_state.json"

    if not state_file.exists():
        return {"error": "system_state.json not found"}

    try:
        with open(state_file) as f:
            state = json.load(f)

        return {
            "last_trade_date": state.get("trades", {}).get("last_trade_date"),
            "total_trades_today": state.get("trades", {}).get("total_trades_today", 0),
            "last_sync": state.get("meta", {}).get("last_sync"),
            "paper_positions": state.get("paper_account", {}).get("positions_count", 0),
        }
    except Exception as e:
        return {"error": str(e)}


def run_monitoring(
    data_dir: Path,
    days_to_check: int = 7,
    alert_threshold: int = 3,
    verbose: bool = False
) -> dict:
    """
    Run trade activity monitoring.

    Args:
        data_dir: Path to data directory
        days_to_check: Number of days to look back
        alert_threshold: Alert if no trades for this many trading days
        verbose: Print detailed output

    Returns:
        dict with monitoring results and alert status
    """
    results = {
        "timestamp": datetime.now().isoformat(),
        "alert": False,
        "alert_reason": None,
        "days_since_trade": 0,
        "trading_days_without_activity": 0,
        "last_trade_date": None,
        "trade_files": {},
        "system_state": {},
        "recommendations": []
    }

    # Get trade files
    trade_files = get_trade_files(data_dir, days_to_check)
    results["trade_files"] = trade_files

    # Get last trade date
    last_trade_date = get_last_trade_date(data_dir)
    results["last_trade_date"] = last_trade_date

    # Calculate days since trade
    days_since = calculate_days_since_trade(last_trade_date)
    results["days_since_trade"] = days_since

    # Count trading days without activity
    today = datetime.now()
    if last_trade_date:
        last_date = datetime.strptime(last_trade_date, "%Y-%m-%d")
        trading_days = get_trading_days(last_date + timedelta(days=1), today)
        results["trading_days_without_activity"] = len(trading_days)
    else:
        results["trading_days_without_activity"] = 999

    # Check system state
    results["system_state"] = check_system_state(data_dir)

    # Determine alert status
    if results["trading_days_without_activity"] >= alert_threshold:
        results["alert"] = True
        results["alert_reason"] = (
            f"NO TRADES FOR {results['trading_days_without_activity']} TRADING DAYS! "
            f"Last trade: {last_trade_date or 'NEVER'}. "
            f"Threshold: {alert_threshold} days."
        )
        results["recommendations"].append(
            "CHECK: max_positions config in simple_daily_trader.py"
        )
        results["recommendations"].append(
            "CHECK: Workflow logs for 'Max positions reached' messages"
        )
        results["recommendations"].append(
            "CHECK: API credentials are valid"
        )

    # Check for zombie mode (workflow success but no trades)
    state = results["system_state"]
    if state.get("total_trades_today") == 0 and is_trading_day(today):
        if today.hour >= 16:  # After market close
            results["alert"] = True
            results["alert_reason"] = (
                f"ZOMBIE MODE DETECTED: Today is a trading day but total_trades_today=0. "
                f"System may be running but not executing trades."
            )

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Monitor trade activity and detect zombie mode"
    )
    parser.add_argument(
        "--days", type=int, default=7,
        help="Number of days to check (default: 7)"
    )
    parser.add_argument(
        "--alert-threshold", type=int, default=3,
        help="Alert if no trades for N trading days (default: 3)"
    )
    parser.add_argument(
        "--data-dir", type=str, default="data",
        help="Path to data directory (default: data)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON"
    )
    parser.add_argument(
        "--github-output", action="store_true",
        help="Set GitHub Actions output variables"
    )

    args = parser.parse_args()

    # Find data directory
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        # Try relative to script location
        script_dir = Path(__file__).parent.parent
        data_dir = script_dir / "data"

    if not data_dir.exists():
        logger.error(f"Data directory not found: {data_dir}")
        sys.exit(1)

    # Run monitoring
    results = run_monitoring(
        data_dir=data_dir,
        days_to_check=args.days,
        alert_threshold=args.alert_threshold,
        verbose=args.verbose
    )

    # Output results
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("=" * 60)
        print("TRADE ACTIVITY MONITOR")
        print("=" * 60)
        print(f"Timestamp: {results['timestamp']}")
        print(f"Last Trade Date: {results['last_trade_date'] or 'NEVER'}")
        print(f"Trading Days Without Activity: {results['trading_days_without_activity']}")
        print(f"Alert Threshold: {args.alert_threshold} days")
        print()

        if results["alert"]:
            print("!" * 60)
            print("ALERT: " + results["alert_reason"])
            print("!" * 60)
            print()
            print("Recommendations:")
            for rec in results["recommendations"]:
                print(f"  - {rec}")
        else:
            print("STATUS: OK - Trade activity within normal parameters")

        print()
        print("Recent Trade Files:")
        for date, info in sorted(results["trade_files"].items(), reverse=True):
            status = f"({info['count']} trades)" if info["exists"] else "(no file)"
            print(f"  {date}: {status}")

    # GitHub Actions output
    if args.github_output:
        github_output = os.environ.get("GITHUB_OUTPUT")
        if github_output:
            with open(github_output, "a") as f:
                f.write(f"alert={str(results['alert']).lower()}\n")
                f.write(f"days_since_trade={results['days_since_trade']}\n")
                f.write(f"alert_reason={results.get('alert_reason', '')}\n")

    # Exit with error if alert triggered
    if results["alert"]:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
