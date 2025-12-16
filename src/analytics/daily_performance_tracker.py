"""
Daily Performance Tracker - Tracks P/L and performance metrics.

This module:
1. Tracks daily P/L from trades
2. Updates system_state.json with current metrics
3. Calculates progress toward North Star ($100/day)
4. Creates lessons learned when performance drops

Created: Dec 16, 2025
Purpose: Ensure RAG/ML can learn from daily performance
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# North Star configuration
NORTH_STAR_DAILY_TARGET = 100.0  # $100/day net income
SYSTEM_STATE_PATH = Path(os.getenv("SYSTEM_STATE_PATH", "data/system_state.json"))
TRADE_LOG_PATH = Path("data/trades")


@dataclass
class DailyPerformance:
    """Daily performance summary."""

    date: str
    total_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    trades_count: int
    win_count: int
    loss_count: int
    win_rate: float
    largest_win: float
    largest_loss: float
    north_star_progress: float  # Percentage toward $100/day

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "total_pnl": round(self.total_pnl, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "trades_count": self.trades_count,
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "win_rate": round(self.win_rate, 4),
            "largest_win": round(self.largest_win, 2),
            "largest_loss": round(self.largest_loss, 2),
            "north_star_progress": round(self.north_star_progress, 2),
        }


class DailyPerformanceTracker:
    """
    Tracks and logs daily trading performance.

    Integrates with:
    - system_state.json for real-time metrics
    - RAG for lessons learned from performance
    - ML for anomaly detection
    """

    def __init__(self):
        self.today = datetime.now().strftime("%Y-%m-%d")
        self.state_path = SYSTEM_STATE_PATH
        self.trades_dir = TRADE_LOG_PATH
        self.trades_dir.mkdir(parents=True, exist_ok=True)

    def _load_system_state(self) -> dict[str, Any]:
        """Load current system state."""
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text())
            except Exception as e:
                logger.error(f"Failed to load system state: {e}")
        return {}

    def _save_system_state(self, state: dict[str, Any]) -> None:
        """Save system state."""
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps(state, indent=2))
            logger.info(f"System state updated: {self.state_path}")
        except Exception as e:
            logger.error(f"Failed to save system state: {e}")

    def _load_todays_trades(self) -> list[dict[str, Any]]:
        """Load trades from today's trade file."""
        trades_file = self.trades_dir / f"trades_{self.today}.json"
        if trades_file.exists():
            try:
                return json.loads(trades_file.read_text())
            except Exception as e:
                logger.error(f"Failed to load trades: {e}")
        return []

    def record_trade(self, trade: dict[str, Any]) -> None:
        """
        Record a trade and update daily metrics.

        Args:
            trade: Trade record with fields like:
                - symbol, side, qty, price, pnl, timestamp
        """
        trades_file = self.trades_dir / f"trades_{self.today}.json"

        # Load existing trades
        trades = self._load_todays_trades()

        # Add timestamp if not present
        if "timestamp" not in trade:
            trade["timestamp"] = datetime.now().isoformat()

        trades.append(trade)

        # Save trades
        try:
            trades_file.write_text(json.dumps(trades, indent=2))
            logger.info(f"Trade recorded: {trade.get('symbol')} {trade.get('side')} ${trade.get('pnl', 0):.2f}")
        except Exception as e:
            logger.error(f"Failed to save trade: {e}")

        # Update system state with new metrics
        self.update_daily_metrics()

    def calculate_daily_performance(self) -> DailyPerformance:
        """Calculate today's performance metrics."""
        trades = self._load_todays_trades()

        if not trades:
            return DailyPerformance(
                date=self.today,
                total_pnl=0.0,
                realized_pnl=0.0,
                unrealized_pnl=0.0,
                trades_count=0,
                win_count=0,
                loss_count=0,
                win_rate=0.0,
                largest_win=0.0,
                largest_loss=0.0,
                north_star_progress=0.0,
            )

        # Calculate metrics
        total_pnl = sum(t.get("pnl", 0) for t in trades)
        realized_pnl = sum(t.get("realized_pnl", t.get("pnl", 0)) for t in trades if t.get("status") == "closed")
        unrealized_pnl = total_pnl - realized_pnl

        wins = [t for t in trades if t.get("pnl", 0) > 0]
        losses = [t for t in trades if t.get("pnl", 0) < 0]

        win_count = len(wins)
        loss_count = len(losses)
        win_rate = win_count / len(trades) if trades else 0.0

        largest_win = max((t.get("pnl", 0) for t in trades), default=0.0)
        largest_loss = min((t.get("pnl", 0) for t in trades), default=0.0)

        north_star_progress = (total_pnl / NORTH_STAR_DAILY_TARGET) * 100 if NORTH_STAR_DAILY_TARGET > 0 else 0.0

        return DailyPerformance(
            date=self.today,
            total_pnl=total_pnl,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            trades_count=len(trades),
            win_count=win_count,
            loss_count=loss_count,
            win_rate=win_rate,
            largest_win=largest_win,
            largest_loss=largest_loss,
            north_star_progress=north_star_progress,
        )

    def update_daily_metrics(self) -> DailyPerformance:
        """Update system_state.json with current daily metrics."""
        perf = self.calculate_daily_performance()
        state = self._load_system_state()

        # Update daily performance section
        state.setdefault("daily_performance", {})
        state["daily_performance"] = perf.to_dict()

        # Update North Star tracking
        state.setdefault("north_star", {})
        state["north_star"]["target"] = NORTH_STAR_DAILY_TARGET
        state["north_star"]["today_pnl"] = perf.total_pnl
        state["north_star"]["progress_pct"] = perf.north_star_progress
        state["north_star"]["on_track"] = perf.total_pnl >= NORTH_STAR_DAILY_TARGET

        # Update timestamp
        state.setdefault("meta", {})
        state["meta"]["last_updated"] = datetime.now().isoformat()
        state["meta"]["last_performance_update"] = datetime.now().isoformat()

        self._save_system_state(state)

        # Log North Star progress
        if perf.north_star_progress >= 100:
            logger.info(f"🎯 NORTH STAR ACHIEVED! ${perf.total_pnl:.2f} ({perf.north_star_progress:.1f}%)")
        else:
            logger.info(f"📈 North Star Progress: ${perf.total_pnl:.2f} / ${NORTH_STAR_DAILY_TARGET:.2f} ({perf.north_star_progress:.1f}%)")

        return perf

    def check_performance_anomalies(self) -> list[str]:
        """
        Check for performance anomalies that should trigger lessons learned.

        Returns:
            List of anomaly descriptions
        """
        anomalies = []
        perf = self.calculate_daily_performance()
        self._load_system_state()

        # Check for significant losses
        if perf.total_pnl < -50:
            anomalies.append(f"CRITICAL: Daily loss exceeds $50 (${perf.total_pnl:.2f})")

        # Check for low win rate
        if perf.trades_count >= 5 and perf.win_rate < 0.4:
            anomalies.append(f"WARNING: Win rate below 40% ({perf.win_rate:.1%})")

        # Check for consecutive losses
        trades = self._load_todays_trades()
        consecutive_losses = 0
        for t in reversed(trades):
            if t.get("pnl", 0) < 0:
                consecutive_losses += 1
            else:
                break
        if consecutive_losses >= 3:
            anomalies.append(f"WARNING: {consecutive_losses} consecutive losses")

        # Log anomalies
        for a in anomalies:
            logger.warning(f"📉 Performance anomaly: {a}")

        return anomalies

    def get_north_star_status(self) -> dict[str, Any]:
        """Get current North Star ($100/day) status."""
        perf = self.calculate_daily_performance()

        return {
            "target": NORTH_STAR_DAILY_TARGET,
            "today_pnl": perf.total_pnl,
            "progress_pct": perf.north_star_progress,
            "on_track": perf.total_pnl >= NORTH_STAR_DAILY_TARGET,
            "trades_count": perf.trades_count,
            "win_rate": perf.win_rate,
            "remaining": max(0, NORTH_STAR_DAILY_TARGET - perf.total_pnl),
        }


# Global singleton
_tracker_instance: DailyPerformanceTracker | None = None


def get_performance_tracker() -> DailyPerformanceTracker:
    """Get the global performance tracker instance."""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = DailyPerformanceTracker()
    return _tracker_instance


def record_trade_pnl(trade: dict[str, Any]) -> None:
    """Record a trade and update daily metrics."""
    tracker = get_performance_tracker()
    tracker.record_trade(trade)


def get_north_star_status() -> dict[str, Any]:
    """Get current North Star status."""
    tracker = get_performance_tracker()
    return tracker.get_north_star_status()


def update_daily_metrics() -> DailyPerformance:
    """Force update of daily metrics in system_state.json."""
    tracker = get_performance_tracker()
    return tracker.update_daily_metrics()
