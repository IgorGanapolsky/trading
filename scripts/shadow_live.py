#!/usr/bin/env python3
"""
Live Shadowing Script - Compare Paper vs Live Trading

Runs parallel paper/live comparison to quantify slippage gap.
Use weekly: python scripts/shadow_live.py --duration 1d

Dec 12, 2025: Added EV Drift Alert (CEO directive)
- Rolling 14-day paper EV tracking
- Auto-halt if EV < 0 (edge fade detection)

Author: Trading System CTO
Created: 2025-12-11
"""

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# EV Drift Alert configuration (CEO directive Dec 12, 2025)
EV_ROLLING_WINDOW_DAYS = 14
EV_HALT_THRESHOLD = 0.0  # Halt if rolling EV drops below 0


@dataclass
class ShadowResult:
    """Result of shadow comparison."""

    timestamp: str
    paper_pnl: float
    live_pnl: float
    paper_trades: int
    live_trades: int
    slippage_total: float
    deviation_pct: float
    passed: bool


@dataclass
class EVDriftAlert:
    """
    EV Drift Alert - Catches edge fade in real-time.

    CEO Directive (Dec 12, 2025):
    - Track rolling 14-day paper EV
    - Halt trading if EV < 0 (edge has faded)
    """

    timestamp: str
    rolling_ev: float
    rolling_window_days: int
    daily_evs: list[float] = field(default_factory=list)
    trades_in_window: int = 0
    should_halt: bool = False
    halt_reason: str | None = None


class EVDriftTracker:
    """
    Track rolling Expected Value from paper trading.

    Catches edge fade before it destroys capital.
    """

    def __init__(
        self,
        window_days: int = EV_ROLLING_WINDOW_DAYS,
        halt_threshold: float = EV_HALT_THRESHOLD,
        data_dir: Path | None = None,
    ):
        self.window_days = window_days
        self.halt_threshold = halt_threshold
        self.data_dir = data_dir or Path("data/ev_tracking")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.ev_log_path = self.data_dir / "ev_drift_log.jsonl"
        self.halt_file = self.data_dir / "TRADING_HALTED"

    def compute_rolling_ev(self) -> EVDriftAlert:
        """
        Compute rolling EV from paper trade history.

        Returns:
            EVDriftAlert with current status
        """
        # Load daily P/L data
        daily_evs = self._load_daily_pnl(days=self.window_days)

        if not daily_evs:
            logger.warning("No paper trade data for EV calculation")
            return EVDriftAlert(
                timestamp=datetime.now().isoformat(),
                rolling_ev=0.0,
                rolling_window_days=self.window_days,
                daily_evs=[],
                trades_in_window=0,
                should_halt=False,
                halt_reason=None,
            )

        # Compute rolling EV (mean of daily P/L)
        rolling_ev = sum(daily_evs) / len(daily_evs)
        trades = self._count_trades_in_window(days=self.window_days)

        # Check halt condition
        should_halt = rolling_ev < self.halt_threshold
        halt_reason = None

        if should_halt:
            halt_reason = (
                f"Rolling {self.window_days}d EV = ${rolling_ev:.2f} < "
                f"threshold ${self.halt_threshold:.2f}"
            )
            logger.critical("EV DRIFT ALERT: %s", halt_reason)
            self._create_halt_file(halt_reason)

        alert = EVDriftAlert(
            timestamp=datetime.now().isoformat(),
            rolling_ev=round(rolling_ev, 2),
            rolling_window_days=self.window_days,
            daily_evs=[round(ev, 2) for ev in daily_evs],
            trades_in_window=trades,
            should_halt=should_halt,
            halt_reason=halt_reason,
        )

        # Log the alert
        self._log_alert(alert)

        return alert

    def _load_daily_pnl(self, days: int) -> list[float]:
        """Load daily P/L from paper trade logs."""
        daily_pnl: dict[str, float] = {}
        cutoff = datetime.now() - timedelta(days=days)

        # Try to read from paper trades log
        paper_log = Path("data/paper_trades.jsonl")
        if paper_log.exists():
            try:
                with open(paper_log) as f:
                    for line in f:
                        trade = json.loads(line)
                        ts = trade.get("timestamp", "")
                        try:
                            trade_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        except (ValueError, TypeError):
                            continue

                        if trade_time >= cutoff:
                            date_key = trade_time.strftime("%Y-%m-%d")
                            pnl = float(trade.get("pnl", 0) or 0)
                            daily_pnl[date_key] = daily_pnl.get(date_key, 0) + pnl
            except Exception as e:
                logger.warning("Error reading paper trades: %s", e)

        # Also check system state for recent performance
        system_state_path = Path("data/system_state.json")
        if system_state_path.exists() and not daily_pnl:
            try:
                with open(system_state_path) as f:
                    state = json.load(f)
                    closed = state.get("performance", {}).get("closed_trades", [])
                    for trade in closed:
                        exit_date = trade.get("exit_date", "")
                        try:
                            trade_time = datetime.fromisoformat(exit_date.replace("Z", "+00:00"))
                        except (ValueError, TypeError):
                            continue

                        if trade_time >= cutoff:
                            date_key = trade_time.strftime("%Y-%m-%d")
                            pnl = float(trade.get("pl", 0) or 0)
                            daily_pnl[date_key] = daily_pnl.get(date_key, 0) + pnl
            except Exception as e:
                logger.warning("Error reading system state: %s", e)

        # Sort by date and return values
        sorted_dates = sorted(daily_pnl.keys())
        return [daily_pnl[d] for d in sorted_dates]

    def _count_trades_in_window(self, days: int) -> int:
        """Count trades executed in rolling window."""
        count = 0
        cutoff = datetime.now() - timedelta(days=days)

        paper_log = Path("data/paper_trades.jsonl")
        if paper_log.exists():
            try:
                with open(paper_log) as f:
                    for line in f:
                        trade = json.loads(line)
                        ts = trade.get("timestamp", "")
                        try:
                            trade_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                            if trade_time >= cutoff:
                                count += 1
                        except (ValueError, TypeError):
                            continue
            except Exception:
                pass

        return count

    def _create_halt_file(self, reason: str) -> None:
        """Create halt file to signal trading should stop."""
        with open(self.halt_file, "w") as f:
            json.dump(
                {
                    "halted_at": datetime.now().isoformat(),
                    "reason": reason,
                    "action": "Manual review required before resuming",
                },
                f,
                indent=2,
            )
        logger.critical("TRADING HALTED - Created halt file at %s", self.halt_file)

    def _log_alert(self, alert: EVDriftAlert) -> None:
        """Append alert to log file."""
        with open(self.ev_log_path, "a") as f:
            f.write(
                json.dumps(
                    {
                        "timestamp": alert.timestamp,
                        "rolling_ev": alert.rolling_ev,
                        "rolling_window_days": alert.rolling_window_days,
                        "trades_in_window": alert.trades_in_window,
                        "should_halt": alert.should_halt,
                        "halt_reason": alert.halt_reason,
                    }
                )
                + "\n"
            )

    def is_halted(self) -> bool:
        """Check if trading is currently halted."""
        return self.halt_file.exists()

    def clear_halt(self) -> bool:
        """Clear halt status (manual intervention)."""
        if self.halt_file.exists():
            self.halt_file.unlink()
            logger.info("Trading halt cleared")
            return True
        return False


class LiveShadowTracker:
    """
    Track and compare paper vs live trading performance.

    This helps quantify the real-world gap between backtests/paper
    and actual live execution, including:
    - Fill price slippage
    - Execution timing differences
    - Volume impact
    """

    def __init__(self, output_dir: Path | None = None):
        self.output_dir = output_dir or Path("data/shadow_results")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results: list[ShadowResult] = []

    def fetch_paper_data(self, start_time: datetime, end_time: datetime) -> dict[str, Any]:
        """Fetch paper trading data for comparison period."""
        paper_data = {
            "pnl": 0.0,
            "trades": [],
            "fills": [],
        }

        # Try to read from paper account logs
        paper_log = Path("data/paper_trades.jsonl")
        if paper_log.exists():
            with open(paper_log) as f:
                for line in f:
                    trade = json.loads(line)
                    trade_time = datetime.fromisoformat(trade.get("timestamp", "2000-01-01"))
                    if start_time <= trade_time <= end_time:
                        paper_data["trades"].append(trade)
                        paper_data["pnl"] += trade.get("pnl", 0)

        return paper_data

    def fetch_live_data(self, start_time: datetime, end_time: datetime) -> dict[str, Any]:
        """Fetch live trading data for comparison period."""
        live_data = {
            "pnl": 0.0,
            "trades": [],
            "fills": [],
        }

        # Check if we have Alpaca access
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")

        if not api_key or not secret_key:
            logger.warning("No Alpaca credentials - using mock data for shadow comparison")
            return live_data

        try:
            from alpaca.trading.client import TradingClient

            # Initialize client
            paper = os.getenv("PAPER_TRADING", "true").lower() == "true"
            client = TradingClient(api_key, secret_key, paper=paper)

            # Fetch orders in date range
            orders = client.get_orders(
                status="filled",
                after=start_time.isoformat(),
                until=end_time.isoformat(),
            )

            for order in orders:
                live_data["trades"].append(
                    {
                        "id": str(order.id),
                        "symbol": order.symbol,
                        "side": order.side.value,
                        "qty": float(order.qty),
                        "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price else 0,
                        "timestamp": order.filled_at.isoformat() if order.filled_at else None,
                    }
                )

        except ImportError:
            logger.warning("Alpaca SDK not available - using mock data")
        except Exception as e:
            logger.error(f"Error fetching live data: {e}")

        return live_data

    def compute_slippage(
        self, paper_data: dict[str, Any], live_data: dict[str, Any]
    ) -> tuple[float, list[dict]]:
        """Compute slippage between paper and live fills."""
        slippage_details = []
        total_slippage = 0.0

        # Match trades by symbol and approximate time
        for paper_trade in paper_data.get("trades", []):
            symbol = paper_trade.get("symbol") or paper_trade.get("ticker")
            paper_price = paper_trade.get("price", 0) or paper_trade.get("filled_price", 0)

            # Find matching live trade
            for live_trade in live_data.get("trades", []):
                if live_trade.get("symbol") == symbol:
                    live_price = live_trade.get("filled_avg_price", 0)

                    if paper_price > 0 and live_price > 0:
                        slip = abs(live_price - paper_price)
                        slip_pct = slip / paper_price
                        total_slippage += slip

                        slippage_details.append(
                            {
                                "symbol": symbol,
                                "paper_price": paper_price,
                                "live_price": live_price,
                                "slippage": slip,
                                "slippage_pct": slip_pct,
                            }
                        )
                    break

        return total_slippage, slippage_details

    def run_comparison(self, duration_hours: int = 24) -> ShadowResult:
        """Run shadow comparison for specified duration."""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=duration_hours)

        logger.info(f"Running shadow comparison: {start_time} to {end_time}")

        # Fetch data
        paper_data = self.fetch_paper_data(start_time, end_time)
        live_data = self.fetch_live_data(start_time, end_time)

        # Compute metrics
        paper_pnl = paper_data.get("pnl", 0)
        live_pnl = live_data.get("pnl", 0)
        paper_trades = len(paper_data.get("trades", []))
        live_trades = len(live_data.get("trades", []))

        slippage_total, slippage_details = self.compute_slippage(paper_data, live_data)

        # Compute deviation
        if paper_pnl != 0:
            deviation_pct = abs(paper_pnl - live_pnl) / abs(paper_pnl)
        else:
            deviation_pct = 0.0 if live_pnl == 0 else 1.0

        # Pass if deviation < 5% (threshold for acceptable gap)
        passed = deviation_pct < 0.05 and slippage_total < 10.0

        result = ShadowResult(
            timestamp=datetime.now().isoformat(),
            paper_pnl=paper_pnl,
            live_pnl=live_pnl,
            paper_trades=paper_trades,
            live_trades=live_trades,
            slippage_total=slippage_total,
            deviation_pct=deviation_pct,
            passed=passed,
        )

        self.results.append(result)

        # Save result
        self._save_result(result, slippage_details)

        return result

    def _save_result(self, result: ShadowResult, slippage_details: list[dict]):
        """Save comparison result to file."""
        output_file = self.output_dir / f"shadow_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(output_file, "w") as f:
            json.dump(
                {
                    "result": {
                        "timestamp": result.timestamp,
                        "paper_pnl": result.paper_pnl,
                        "live_pnl": result.live_pnl,
                        "paper_trades": result.paper_trades,
                        "live_trades": result.live_trades,
                        "slippage_total": result.slippage_total,
                        "deviation_pct": result.deviation_pct,
                        "passed": result.passed,
                    },
                    "slippage_details": slippage_details,
                },
                f,
                indent=2,
            )

        logger.info(f"Shadow result saved to {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Run live shadowing comparison")
    parser.add_argument(
        "--duration",
        type=str,
        default="1d",
        help="Duration for comparison (e.g., 1d, 6h, 1w)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/shadow_results",
        help="Output directory for results",
    )
    parser.add_argument(
        "--ev-check",
        action="store_true",
        help="Run EV drift check (14-day rolling, halt if <0)",
    )
    parser.add_argument(
        "--ev-window",
        type=int,
        default=EV_ROLLING_WINDOW_DAYS,
        help=f"EV rolling window in days (default: {EV_ROLLING_WINDOW_DAYS})",
    )
    parser.add_argument(
        "--clear-halt",
        action="store_true",
        help="Clear trading halt status (manual intervention)",
    )
    args = parser.parse_args()

    # Handle halt clearing
    if args.clear_halt:
        tracker = EVDriftTracker()
        if tracker.clear_halt():
            print("Trading halt CLEARED - trading can resume")
            return 0
        else:
            print("No halt to clear")
            return 0

    # EV Drift Check (CEO directive Dec 12, 2025)
    if args.ev_check:
        ev_tracker = EVDriftTracker(window_days=args.ev_window)

        # Check if already halted
        if ev_tracker.is_halted():
            print("\n" + "=" * 60)
            print("⚠️  TRADING IS HALTED")
            print("=" * 60)
            print("Run with --clear-halt to resume after manual review")
            print("=" * 60)
            return 1

        alert = ev_tracker.compute_rolling_ev()

        print("\n" + "=" * 60)
        print("EV DRIFT ALERT - ROLLING PERFORMANCE")
        print("=" * 60)
        print(f"Timestamp:       {alert.timestamp}")
        print(f"Rolling Window:  {alert.rolling_window_days} days")
        print(f"Rolling EV:      ${alert.rolling_ev:.2f}")
        print(f"Trades in Window: {alert.trades_in_window}")
        print(f"Daily EVs:       {alert.daily_evs}")
        print(f"Should Halt:     {'YES ⛔' if alert.should_halt else 'NO ✅'}")
        if alert.halt_reason:
            print(f"Halt Reason:     {alert.halt_reason}")
        print("=" * 60)

        if alert.should_halt:
            print("\n⚠️  TRADING HALTED - Edge has faded. Manual review required.")
            return 1
        return 0

    # Parse duration for shadow comparison
    duration_str = args.duration.lower()
    if duration_str.endswith("d"):
        hours = int(duration_str[:-1]) * 24
    elif duration_str.endswith("h"):
        hours = int(duration_str[:-1])
    elif duration_str.endswith("w"):
        hours = int(duration_str[:-1]) * 24 * 7
    else:
        hours = 24

    tracker = LiveShadowTracker(output_dir=Path(args.output_dir))
    result = tracker.run_comparison(duration_hours=hours)

    # Print results
    print("\n" + "=" * 60)
    print("LIVE SHADOWING COMPARISON RESULTS")
    print("=" * 60)
    print(f"Timestamp:       {result.timestamp}")
    print(f"Paper P/L:       ${result.paper_pnl:.2f}")
    print(f"Live P/L:        ${result.live_pnl:.2f}")
    print(f"Paper Trades:    {result.paper_trades}")
    print(f"Live Trades:     {result.live_trades}")
    print(f"Total Slippage:  ${result.slippage_total:.2f}")
    print(f"Deviation:       {result.deviation_pct:.2%}")
    print(f"Status:          {'PASS' if result.passed else 'FAIL'}")
    print("=" * 60)

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
