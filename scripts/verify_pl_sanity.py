#!/usr/bin/env python3
"""
P/L Sanity Check - Catch silent trading failures early

This script verifies that the trading system is actually active and making changes.
It detects "zombie mode" where the system appears to run but doesn't execute trades.

Checks:
1. Equity unchanged for 3+ trading days → ALERT
2. No trades executed for 3+ trading days → ALERT
3. P/L exactly 0.00 for 3+ days → ALERT
4. Daily P/L change > 5% → ALERT (unusual volatility)
5. Equity dropped > 10% from peak → ALERT (drawdown warning)

Exit codes:
- 0: System healthy
- 1: Alert condition detected (silent failure, anomaly, or drawdown)
- 2: Script error (missing credentials, API failure, etc.)

This would have caught our 30-day silent failure within 3 days.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Third-party imports
try:
    from alpaca.trading.client import TradingClient
except ImportError:
    print("ERROR: alpaca-py not installed. Run: pip install alpaca-py")
    sys.exit(2)

# Paths
DATA_DIR = Path("data")
PERFORMANCE_LOG_FILE = DATA_DIR / "performance_log.json"
SYSTEM_STATE_FILE = DATA_DIR / "system_state.json"
TRADES_DIR = DATA_DIR

# Alert thresholds
STALE_DAYS_THRESHOLD = 3  # Alert if no change for 3+ trading days
ANOMALY_PCT_THRESHOLD = 5.0  # Alert if daily P/L change > 5%
DRAWDOWN_PCT_THRESHOLD = 10.0  # Alert if equity drops > 10% from peak


class PLSanityChecker:
    """Monitors P/L health and detects silent trading failures."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.alerts: list[dict[str, Any]] = []
        self.metrics: dict[str, Any] = {}
        self.api = None

    def log(self, message: str):
        """Print verbose logging if enabled."""
        if self.verbose:
            print(f"[DEBUG] {message}")

    def initialize_alpaca_api(self) -> bool:
        """Initialize Alpaca API connection."""
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")

        if not api_key or not secret_key:
            self.log("WARNING: Alpaca credentials not found in environment")
            return False

        try:
            self.api = TradingClient(
                api_key=api_key,
                secret_key=secret_key,
                paper=True,  # Use paper trading
            )
            # Test connection
            self.api.get_account()
            self.log("Alpaca API initialized successfully")
            return True
        except Exception as e:
            self.log(f"WARNING: Failed to initialize Alpaca API: {e}")
            return False

    def get_current_equity(self) -> float | None:
        """Get current equity from Alpaca API or system_state.json fallback."""
        # Try Alpaca API first
        if self.api:
            try:
                account = self.api.get_account()
                # In alpaca-py, account attributes are accessed directly
                equity = (
                    float(account.equity)
                    if hasattr(account, "equity")
                    else float(account.portfolio_value)
                )
                self.log(f"Current equity from Alpaca API: ${equity:,.2f}")
                return equity
            except Exception as e:
                self.log(f"WARNING: Failed to get equity from Alpaca: {e}")

        # Fallback to system_state.json
        if SYSTEM_STATE_FILE.exists():
            try:
                with open(SYSTEM_STATE_FILE) as f:
                    state = json.load(f)
                equity = state.get("account", {}).get("current_equity")
                if equity is not None:
                    self.log(f"Current equity from system_state.json: ${equity:,.2f}")
                    return float(equity)
            except Exception as e:
                self.log(f"WARNING: Failed to read system_state.json: {e}")

        return None

    def is_market_open(self) -> bool:
        """Check if market is currently open (uses Alpaca clock API)."""
        if not self.api:
            return False

        try:
            clock = self.api.get_clock()
            # In alpaca-py, clock.is_open is a boolean attribute
            return bool(clock.is_open)
        except Exception as e:
            self.log(f"WARNING: Failed to check market status: {e}")
            return False

    def is_trading_day(self, date_obj: datetime) -> bool:
        """Check if a given date is a trading day (not weekend)."""
        # Simple check: weekdays only (Monday=0, Sunday=6)
        # Note: This doesn't account for market holidays, but good enough for our purposes
        return date_obj.weekday() < 5

    def load_performance_log(self) -> list[dict[str, Any]]:
        """Load historical performance log."""
        if not PERFORMANCE_LOG_FILE.exists():
            self.log("Performance log doesn't exist yet - creating empty log")
            return []

        try:
            with open(PERFORMANCE_LOG_FILE) as f:
                data = json.load(f)
            self.log(f"Loaded {len(data)} entries from performance log")
            return data
        except Exception as e:
            self.log(f"WARNING: Failed to read performance log: {e}")
            return []

    def save_performance_log(self, log_data: list[dict[str, Any]]):
        """Save performance log to disk."""
        DATA_DIR.mkdir(exist_ok=True)
        with open(PERFORMANCE_LOG_FILE, "w") as f:
            json.dump(log_data, f, indent=2)
        self.log(f"Saved {len(log_data)} entries to performance log")

    def update_performance_log(self, current_equity: float) -> list[dict[str, Any]]:
        """Update performance log with current equity snapshot."""
        log_data = self.load_performance_log()

        # Add new entry
        new_entry = {
            "date": datetime.now().date().isoformat(),
            "timestamp": datetime.now().isoformat(),
            "equity": current_equity,
            "pl": current_equity - 100000.0,  # Assuming $100k starting balance
        }

        # Check if we already have an entry for today
        today = datetime.now().date().isoformat()
        existing_index = next(
            (i for i, entry in enumerate(log_data) if entry.get("date") == today),
            None,
        )

        if existing_index is not None:
            # Update existing entry
            log_data[existing_index] = new_entry
            self.log(f"Updated existing entry for {today}")
        else:
            # Append new entry
            log_data.append(new_entry)
            self.log(f"Added new entry for {today}")

        self.save_performance_log(log_data)
        return log_data

    def count_recent_trades(self, days: int = 3) -> int:
        """Count trades executed in last N trading days."""
        trade_count = 0
        cutoff_date = datetime.now() - timedelta(days=days)

        # Check all trades_*.json files
        for trade_file in TRADES_DIR.glob("trades_*.json"):
            try:
                with open(trade_file) as f:
                    trades = json.load(f)

                # Filter trades by date
                for trade in trades:
                    trade_date_str = trade.get("timestamp", "")
                    if not trade_date_str:
                        continue

                    try:
                        trade_date = datetime.fromisoformat(trade_date_str.replace("Z", "+00:00"))
                        if trade_date >= cutoff_date:
                            trade_count += 1
                    except ValueError:
                        continue
            except Exception as e:
                self.log(f"WARNING: Failed to read {trade_file}: {e}")
                continue

        self.log(f"Found {trade_count} trades in last {days} days")
        return trade_count

    def check_stuck_equity(self, log_data: list[dict[str, Any]]) -> bool:
        """Check if equity has been stuck at same value for 3+ trading days."""
        if len(log_data) < STALE_DAYS_THRESHOLD + 1:  # +1 for today's entry
            self.log("Not enough history to check stuck equity")
            return False

        # Get last N trading day entries (excluding today's new entry)
        # We look at log_data[:-1] to ignore today's freshly added entry
        historical_data = log_data[:-1] if len(log_data) > 1 else log_data

        recent_entries = []
        for entry in reversed(historical_data):
            try:
                entry_date = datetime.fromisoformat(entry["date"])
                if self.is_trading_day(entry_date):
                    recent_entries.append(entry)
                    if len(recent_entries) >= STALE_DAYS_THRESHOLD:
                        break
            except (ValueError, KeyError):
                continue

        if len(recent_entries) < STALE_DAYS_THRESHOLD:
            self.log("Not enough trading day entries to check stuck equity")
            return False

        # Check if all equities are identical (within $0.01)
        equities = [entry["equity"] for entry in recent_entries]
        if max(equities) - min(equities) < 0.01:
            days_stuck = len(recent_entries)
            self.alerts.append(
                {
                    "level": "CRITICAL",
                    "type": "STUCK_EQUITY",
                    "message": f"Equity unchanged for {days_stuck} trading days (${equities[0]:,.2f})",
                    "days_stuck": days_stuck,
                    "equity": equities[0],
                }
            )
            return True

        return False

    def check_no_trades(self) -> bool:
        """Check if no trades executed for 3+ trading days."""
        trade_count = self.count_recent_trades(days=STALE_DAYS_THRESHOLD)

        if trade_count == 0:
            self.alerts.append(
                {
                    "level": "CRITICAL",
                    "type": "NO_TRADES",
                    "message": f"No trades executed in last {STALE_DAYS_THRESHOLD} days",
                    "days_without_trades": STALE_DAYS_THRESHOLD,
                }
            )
            return True

        self.metrics["recent_trades"] = trade_count
        return False

    def check_zero_pl(self, log_data: list[dict[str, Any]]) -> bool:
        """Check if P/L has been exactly 0.00 for 3+ days."""
        if len(log_data) < STALE_DAYS_THRESHOLD + 1:
            return False

        # Check historical entries (excluding today's new entry)
        historical_data = log_data[:-1] if len(log_data) > 1 else log_data
        if len(historical_data) < STALE_DAYS_THRESHOLD:
            return False

        recent_entries = historical_data[-STALE_DAYS_THRESHOLD:]
        pls = [abs(entry.get("pl", 0)) for entry in recent_entries]

        # Check if all P/Ls are exactly 0 (within $0.01)
        if max(pls) < 0.01:
            self.alerts.append(
                {
                    "level": "WARNING",
                    "type": "ZERO_PL",
                    "message": f"P/L exactly $0.00 for {len(recent_entries)} days",
                    "days_zero": len(recent_entries),
                }
            )
            return True

        return False

    def check_anomalous_pl_change(self, log_data: list[dict[str, Any]]) -> bool:
        """Check if daily P/L change > 5% (unusual volatility)."""
        if len(log_data) < 3:  # Need at least 3 entries: 2 historical + today
            return False

        # Compare most recent historical entry vs the one before it
        # (This avoids flagging today's normal update as anomalous)
        log_data[-1]
        yesterday = log_data[-2]
        day_before = log_data[-3] if len(log_data) >= 3 else yesterday

        # Check yesterday vs day before for historical anomaly
        yesterday_equity = yesterday["equity"]
        day_before_equity = day_before["equity"]

        if day_before_equity == 0:
            return False

        pct_change = abs((yesterday_equity - day_before_equity) / day_before_equity * 100)

        if pct_change > ANOMALY_PCT_THRESHOLD:
            self.alerts.append(
                {
                    "level": "WARNING",
                    "type": "ANOMALOUS_CHANGE",
                    "message": f"Daily equity change {pct_change:.2f}% exceeds {ANOMALY_PCT_THRESHOLD}% threshold",
                    "pct_change": pct_change,
                    "yesterday_equity": day_before_equity,
                    "today_equity": yesterday_equity,
                }
            )
            return True

        return False

    def check_drawdown(self, log_data: list[dict[str, Any]]) -> bool:
        """Check if equity dropped > 10% from peak."""
        if len(log_data) < 2:
            return False

        equities = [entry["equity"] for entry in log_data]
        peak_equity = max(equities)
        current_equity = log_data[-1]["equity"]

        if peak_equity == 0:
            return False

        drawdown_pct = (peak_equity - current_equity) / peak_equity * 100

        if drawdown_pct > DRAWDOWN_PCT_THRESHOLD:
            self.alerts.append(
                {
                    "level": "WARNING",
                    "type": "DRAWDOWN",
                    "message": f"Equity down {drawdown_pct:.2f}% from peak (${peak_equity:,.2f} → ${current_equity:,.2f})",
                    "drawdown_pct": drawdown_pct,
                    "peak_equity": peak_equity,
                    "current_equity": current_equity,
                }
            )
            return True

        self.metrics["drawdown_pct"] = drawdown_pct
        return False

    def write_github_output(self):
        """Write results to GITHUB_OUTPUT for CI workflows."""
        github_output = os.getenv("GITHUB_OUTPUT")
        if not github_output:
            self.log("Not running in GitHub Actions - skipping GITHUB_OUTPUT")
            return

        # Determine health status
        has_critical = any(a["level"] == "CRITICAL" for a in self.alerts)
        pl_healthy = "false" if has_critical else "true"

        # Calculate days since change/trade
        days_since_change = 0
        days_since_trade = 0

        for alert in self.alerts:
            if alert["type"] == "STUCK_EQUITY":
                days_since_change = alert.get("days_stuck", 0)
            elif alert["type"] == "NO_TRADES":
                days_since_trade = alert.get("days_without_trades", 0)

        # Alert reason (first critical or warning)
        alert_reason = ""
        if self.alerts:
            alert_reason = self.alerts[0]["message"]

        # Write to GITHUB_OUTPUT
        try:
            with open(github_output, "a") as f:
                f.write(f"pl_healthy={pl_healthy}\n")
                f.write(f"days_since_change={days_since_change}\n")
                f.write(f"days_since_trade={days_since_trade}\n")
                f.write(f"alert_reason={alert_reason}\n")
            self.log(f"Wrote results to GITHUB_OUTPUT: healthy={pl_healthy}")
        except Exception as e:
            self.log(f"WARNING: Failed to write GITHUB_OUTPUT: {e}")

    def print_report(self):
        """Print formatted sanity check report."""
        print("\n" + "=" * 70)
        print("P/L SANITY CHECK REPORT")
        print("=" * 70)
        print(f"Timestamp: {datetime.now().isoformat()}")
        print()

        # Metrics
        if self.metrics:
            print("📊 METRICS:")
            for key, value in self.metrics.items():
                if isinstance(value, float):
                    print(f"   {key}: {value:.2f}")
                else:
                    print(f"   {key}: {value}")
            print()

        # Alerts
        if not self.alerts:
            print("✅ No alerts - P/L system appears healthy")
        else:
            critical = [a for a in self.alerts if a["level"] == "CRITICAL"]
            warnings = [a for a in self.alerts if a["level"] == "WARNING"]

            if critical:
                print("🚨 CRITICAL ALERTS (Silent Failure Detected):")
                for alert in critical:
                    print(f"   [{alert['type']}] {alert['message']}")
                print()

            if warnings:
                print("⚠️  WARNINGS:")
                for alert in warnings:
                    print(f"   [{alert['type']}] {alert['message']}")
                print()

        print("=" * 70)

    def run_all_checks(self) -> bool:
        """Run all P/L sanity checks. Returns True if healthy, False if alerts."""
        self.log("Starting P/L sanity checks...")

        # Initialize Alpaca API
        self.initialize_alpaca_api()

        # Get current equity
        current_equity = self.get_current_equity()
        if current_equity is None:
            print("ERROR: Could not retrieve current equity from Alpaca or system_state.json")
            return False

        self.metrics["current_equity"] = current_equity

        # Update performance log
        log_data = self.update_performance_log(current_equity)

        # Run all checks
        self.check_stuck_equity(log_data)
        self.check_no_trades()
        self.check_zero_pl(log_data)
        self.check_anomalous_pl_change(log_data)
        self.check_drawdown(log_data)

        # Write GitHub output if in CI
        self.write_github_output()

        # Return health status - any alert (critical or warning) means unhealthy
        return len(self.alerts) == 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="P/L sanity check - detect silent trading failures"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging",
    )
    args = parser.parse_args()

    checker = PLSanityChecker(verbose=args.verbose)

    try:
        is_healthy = checker.run_all_checks()
        checker.print_report()

        # Exit codes:
        # 0 = healthy
        # 1 = alerts detected
        sys.exit(0 if is_healthy else 1)

    except Exception as e:
        print(f"ERROR: Sanity check failed with exception: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()
