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
# NEW: File for bidirectional learning - live observations update backtest assumptions
SLIPPAGE_ASSUMPTIONS_FILE = DATA_DIR / "live_slippage_assumptions.json"


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

    def calculate_slippage_assumptions(self) -> dict[str, Any]:
        """
        Calculate slippage assumptions from live trading observations.

        This implements BIDIRECTIONAL LEARNING: live execution data
        updates the assumptions used in backtesting.

        Returns:
            Dictionary with per-symbol slippage estimates and overall stats
        """
        trades = self.data.get("trades", [])
        if not trades:
            return {"symbol_slippage": {}, "overall": {"avg_slippage_bps": 5.0}}

        # Group slippage by symbol
        symbol_slippages: dict[str, list[float]] = {}
        all_slippages: list[float] = []

        for trade in trades:
            symbol = trade.get("symbol", "UNKNOWN")
            slippage = trade.get("slippage_pct", 0.0)

            if symbol not in symbol_slippages:
                symbol_slippages[symbol] = []
            symbol_slippages[symbol].append(abs(slippage))
            all_slippages.append(abs(slippage))

        # Calculate per-symbol averages
        symbol_assumptions = {}
        for symbol, slippages in symbol_slippages.items():
            avg_slippage = sum(slippages) / len(slippages) if slippages else 0.0
            # Convert to basis points (1% = 100 bps)
            avg_slippage_bps = avg_slippage * 100
            symbol_assumptions[symbol] = {
                "avg_slippage_bps": round(avg_slippage_bps, 2),
                "sample_size": len(slippages),
                "max_slippage_bps": round(max(slippages) * 100, 2) if slippages else 0,
            }

        # Overall average
        overall_avg = sum(all_slippages) / len(all_slippages) if all_slippages else 0.0

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "symbol_slippage": symbol_assumptions,
            "overall": {
                "avg_slippage_bps": round(overall_avg * 100, 2),
                "sample_size": len(all_slippages),
            },
        }

    def sync_to_backtest_assumptions(self) -> bool:
        """
        Sync live slippage observations to backtest assumption file.

        This completes the bidirectional learning loop:
        Live trading → Observed slippage → Updated backtest assumptions

        Returns:
            True if sync successful, False otherwise
        """
        try:
            assumptions = self.calculate_slippage_assumptions()

            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(SLIPPAGE_ASSUMPTIONS_FILE, "w") as f:
                json.dump(assumptions, f, indent=2)

            logger.info(
                f"Synced live slippage assumptions: "
                f"overall={assumptions['overall']['avg_slippage_bps']}bps, "
                f"symbols={len(assumptions['symbol_slippage'])}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to sync slippage assumptions: {e}")
            return False


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


def sync_slippage_to_backtest() -> bool:
    """
    Convenience function to sync live slippage to backtest assumptions.

    Call this after trading sessions to update backtest assumptions
    with real-world slippage data (bidirectional learning).
    """
    return get_tracker().sync_to_backtest_assumptions()


def load_live_slippage_assumptions() -> dict[str, Any]:
    """
    Load slippage assumptions derived from live trading.

    Use this in backtests to apply realistic slippage based on
    actual execution data.

    Returns:
        Dictionary with symbol-level and overall slippage assumptions
    """
    if SLIPPAGE_ASSUMPTIONS_FILE.exists():
        try:
            with open(SLIPPAGE_ASSUMPTIONS_FILE) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load slippage assumptions: {e}")

    # Default assumptions if no live data available
    return {
        "symbol_slippage": {},
        "overall": {"avg_slippage_bps": 5.0, "sample_size": 0},
    }
