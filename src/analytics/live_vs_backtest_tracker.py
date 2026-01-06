"""
Live vs Backtest Performance Tracker.

Tracks and compares live trading results against backtest predictions
to detect model drift, slippage, and execution quality issues.

Created: Jan 6, 2026 - Fix for missing file causing CI failure.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
TRACKER_FILE = DATA_DIR / "live_vs_backtest.json"


class LiveVsBacktestTracker:
    """
    Tracks discrepancies between live trading and backtest predictions.

    Key metrics tracked:
    - Slippage (expected vs actual execution price)
    - Fill rate (orders filled vs attempted)
    - P/L variance (backtest predicted vs actual)
    - Signal accuracy (signals that led to profitable trades)
    """

    def __init__(self):
        self.data = self._load_data()

    def _load_data(self) -> dict[str, Any]:
        """Load existing tracker data."""
        if TRACKER_FILE.exists():
            try:
                with open(TRACKER_FILE) as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"Could not load tracker data: {e}")

        return {
            "created": datetime.now(timezone.utc).isoformat(),
            "trades": [],
            "metrics": {
                "total_trades": 0,
                "avg_slippage_pct": 0.0,
                "fill_rate": 100.0,
                "pl_variance_pct": 0.0,
                "signal_accuracy": 0.0,
            },
            "alerts": [],
        }

    def _save_data(self):
        """Save tracker data."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(TRACKER_FILE, "w") as f:
            json.dump(self.data, f, indent=2)

    def record_trade(
        self,
        symbol: str,
        side: str,
        expected_price: float,
        actual_price: float,
        expected_qty: float,
        actual_qty: float,
        backtest_pnl: Optional[float] = None,
        actual_pnl: Optional[float] = None,
        signal_source: Optional[str] = None,
    ):
        """
        Record a trade for live vs backtest comparison.

        Args:
            symbol: Trading symbol
            side: "buy" or "sell"
            expected_price: Price predicted/expected from backtest
            actual_price: Actual execution price
            expected_qty: Quantity expected to fill
            actual_qty: Quantity actually filled
            backtest_pnl: P/L predicted by backtest (if available)
            actual_pnl: Actual realized P/L (if available)
            signal_source: Source of the trading signal
        """
        # Calculate slippage
        slippage_pct = 0.0
        if expected_price > 0:
            slippage_pct = ((actual_price - expected_price) / expected_price) * 100
            # Negative slippage is good for buys, bad for sells
            if side.lower() == "buy":
                slippage_pct = -slippage_pct

        # Calculate fill rate
        fill_rate = (actual_qty / expected_qty * 100) if expected_qty > 0 else 0

        # Calculate P/L variance
        pl_variance_pct = 0.0
        if backtest_pnl is not None and actual_pnl is not None and backtest_pnl != 0:
            pl_variance_pct = ((actual_pnl - backtest_pnl) / abs(backtest_pnl)) * 100

        trade_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "side": side,
            "expected_price": expected_price,
            "actual_price": actual_price,
            "expected_qty": expected_qty,
            "actual_qty": actual_qty,
            "slippage_pct": slippage_pct,
            "fill_rate": fill_rate,
            "backtest_pnl": backtest_pnl,
            "actual_pnl": actual_pnl,
            "pl_variance_pct": pl_variance_pct,
            "signal_source": signal_source,
        }

        self.data["trades"].append(trade_record)
        self._update_metrics()
        self._check_alerts(trade_record)
        self._save_data()

        logger.info(
            f"Tracked trade: {symbol} {side} | "
            f"Slippage: {slippage_pct:.2f}% | Fill: {fill_rate:.1f}%"
        )

    def _update_metrics(self):
        """Update aggregate metrics."""
        trades = self.data["trades"]
        if not trades:
            return

        self.data["metrics"]["total_trades"] = len(trades)

        # Average slippage
        slippages = [t["slippage_pct"] for t in trades if t.get("slippage_pct") is not None]
        self.data["metrics"]["avg_slippage_pct"] = (
            sum(slippages) / len(slippages) if slippages else 0.0
        )

        # Average fill rate
        fill_rates = [t["fill_rate"] for t in trades if t.get("fill_rate") is not None]
        self.data["metrics"]["fill_rate"] = (
            sum(fill_rates) / len(fill_rates) if fill_rates else 100.0
        )

        # P/L variance
        pl_variances = [
            t["pl_variance_pct"]
            for t in trades
            if t.get("pl_variance_pct") is not None and t["pl_variance_pct"] != 0
        ]
        self.data["metrics"]["pl_variance_pct"] = (
            sum(pl_variances) / len(pl_variances) if pl_variances else 0.0
        )

        # Signal accuracy (trades with positive actual P/L)
        profitable = [t for t in trades if t.get("actual_pnl") is not None and t["actual_pnl"] > 0]
        self.data["metrics"]["signal_accuracy"] = (
            len(profitable) / len(trades) * 100 if trades else 0.0
        )

    def _check_alerts(self, trade: dict[str, Any]):
        """Check for concerning patterns and create alerts."""
        alerts = []

        # High slippage alert
        if abs(trade.get("slippage_pct", 0)) > 1.0:
            alerts.append(
                {
                    "type": "HIGH_SLIPPAGE",
                    "message": f"Slippage of {trade['slippage_pct']:.2f}% on {trade['symbol']}",
                    "timestamp": trade["timestamp"],
                    "severity": "WARNING",
                }
            )

        # Low fill rate alert
        if trade.get("fill_rate", 100) < 90:
            alerts.append(
                {
                    "type": "LOW_FILL_RATE",
                    "message": f"Fill rate of {trade['fill_rate']:.1f}% on {trade['symbol']}",
                    "timestamp": trade["timestamp"],
                    "severity": "WARNING",
                }
            )

        # Large P/L variance alert
        if abs(trade.get("pl_variance_pct", 0)) > 20:
            alerts.append(
                {
                    "type": "PL_VARIANCE",
                    "message": f"P/L variance of {trade['pl_variance_pct']:.1f}% vs backtest",
                    "timestamp": trade["timestamp"],
                    "severity": "HIGH" if abs(trade["pl_variance_pct"]) > 50 else "WARNING",
                }
            )

        self.data["alerts"].extend(alerts)

        # Keep only last 100 alerts
        self.data["alerts"] = self.data["alerts"][-100:]

    def get_metrics(self) -> dict[str, Any]:
        """Get current tracking metrics."""
        return self.data["metrics"]

    def get_recent_trades(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get most recent tracked trades."""
        return self.data["trades"][-limit:]

    def get_alerts(self, severity: Optional[str] = None) -> list[dict[str, Any]]:
        """Get alerts, optionally filtered by severity."""
        alerts = self.data["alerts"]
        if severity:
            alerts = [a for a in alerts if a.get("severity") == severity]
        return alerts


# Singleton instance
_tracker: Optional[LiveVsBacktestTracker] = None


def get_tracker() -> LiveVsBacktestTracker:
    """Get singleton tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = LiveVsBacktestTracker()
    return _tracker


def record_trade(**kwargs) -> None:
    """Convenience function to record a trade."""
    get_tracker().record_trade(**kwargs)
