"""
Progress Tracker - Track P&L Progress Toward $100/Day

This module provides persistent tracking of daily P&L progress,
trend analysis, and reporting for the $100/day goal.

Author: Trading System
Created: 2025-12-03
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DailyProgress:
    """A single day's progress record."""

    date: str
    pnl: float
    equity: float
    target: float = 100.0
    hit_target: bool = False
    cumulative_pnl: float = 0.0
    strategy: str = "unknown"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "pnl": round(self.pnl, 2),
            "equity": round(self.equity, 2),
            "target": self.target,
            "hit_target": self.hit_target,
            "cumulative_pnl": round(self.cumulative_pnl, 2),
            "strategy": self.strategy,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DailyProgress:
        return cls(
            date=data.get("date", ""),
            pnl=data.get("pnl", 0.0),
            equity=data.get("equity", 0.0),
            target=data.get("target", 100.0),
            hit_target=data.get("hit_target", False),
            cumulative_pnl=data.get("cumulative_pnl", 0.0),
            strategy=data.get("strategy", "unknown"),
            notes=data.get("notes", ""),
        )


@dataclass
class ProgressTracker:
    """
    Persistent tracker for $100/day goal progress.

    This class:
    - Records daily P&L history
    - Tracks trends and streaks
    - Generates progress reports
    - Persists to disk for continuity
    """

    target_daily: float = 100.0
    storage_path: Path = field(default_factory=lambda: Path("data/progress_tracker.json"))
    history: list[DailyProgress] = field(default_factory=list)
    initial_capital: float = 10000.0

    def __post_init__(self) -> None:
        self.storage_path = Path(self.storage_path)
        self._load()

    def _load(self) -> None:
        """Load history from disk."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path) as f:
                    data = json.load(f)
                self.history = [DailyProgress.from_dict(d) for d in data.get("history", [])]
                self.target_daily = data.get("target_daily", 100.0)
                self.initial_capital = data.get("initial_capital", 10000.0)
                logger.info(f"Loaded {len(self.history)} days of progress history")
            except Exception as e:
                logger.warning(f"Failed to load progress history: {e}")
                self.history = []

    def _save(self) -> None:
        """Persist history to disk."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "target_daily": self.target_daily,
            "initial_capital": self.initial_capital,
            "last_updated": datetime.now().isoformat(),
            "history": [d.to_dict() for d in self.history],
        }
        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2)
        logger.debug(f"Saved progress to {self.storage_path}")

    def record_day(
        self,
        date: str | datetime,
        pnl: float,
        equity: float,
        strategy: str = "unknown",
        notes: str = "",
    ) -> DailyProgress:
        """
        Record a day's trading results.

        Args:
            date: Trading date
            pnl: Day's profit/loss
            equity: End-of-day equity
            strategy: Strategy used
            notes: Optional notes

        Returns:
            DailyProgress record
        """
        if isinstance(date, datetime):
            date_str = date.strftime("%Y-%m-%d")
        else:
            date_str = date

        # Calculate cumulative P&L
        cumulative = sum(d.pnl for d in self.history) + pnl

        progress = DailyProgress(
            date=date_str,
            pnl=pnl,
            equity=equity,
            target=self.target_daily,
            hit_target=pnl >= self.target_daily,
            cumulative_pnl=cumulative,
            strategy=strategy,
            notes=notes,
        )

        # Remove existing entry for same date if exists
        self.history = [d for d in self.history if d.date != date_str]
        self.history.append(progress)

        # Sort by date
        self.history.sort(key=lambda d: d.date)

        self._save()

        logger.info(f"Recorded {date_str}: P&L=${pnl:.2f} (Target: ${self.target_daily})")

        return progress

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics."""
        if not self.history:
            return {
                "total_days": 0,
                "days_above_target": 0,
                "hit_rate_pct": 0.0,
                "average_daily_pnl": 0.0,
                "cumulative_pnl": 0.0,
                "best_day": 0.0,
                "worst_day": 0.0,
                "current_streak": 0,
                "best_streak": 0,
                "progress_to_target_pct": 0.0,
            }

        pnls = [d.pnl for d in self.history]
        days_above = sum(1 for d in self.history if d.hit_target)
        avg_daily = sum(pnls) / len(pnls)

        # Streak calculation
        current_streak = 0
        for d in reversed(self.history):
            if d.hit_target:
                current_streak += 1
            else:
                break

        best_streak = 0
        streak = 0
        for d in self.history:
            if d.hit_target:
                streak += 1
                best_streak = max(best_streak, streak)
            else:
                streak = 0

        return {
            "total_days": len(self.history),
            "days_above_target": days_above,
            "hit_rate_pct": (days_above / len(self.history)) * 100,
            "average_daily_pnl": avg_daily,
            "cumulative_pnl": sum(pnls),
            "best_day": max(pnls),
            "worst_day": min(pnls),
            "current_streak": current_streak,
            "best_streak": best_streak,
            "progress_to_target_pct": (avg_daily / self.target_daily) * 100
            if self.target_daily > 0
            else 0,
        }

    def get_recent_days(self, n: int = 10) -> list[DailyProgress]:
        """Get the most recent N days of history."""
        return self.history[-n:] if len(self.history) >= n else self.history[:]

    def get_trend(self, window: int = 5) -> str:
        """Analyze recent trend."""
        if len(self.history) < window * 2:
            return "insufficient_data"

        recent = self.history[-window:]
        prior = self.history[-window * 2 : -window]

        recent_avg = sum(d.pnl for d in recent) / len(recent)
        prior_avg = sum(d.pnl for d in prior) / len(prior)

        if recent_avg > prior_avg * 1.10:
            return "strongly_improving"
        elif recent_avg > prior_avg * 1.02:
            return "improving"
        elif recent_avg < prior_avg * 0.90:
            return "strongly_declining"
        elif recent_avg < prior_avg * 0.98:
            return "declining"
        else:
            return "stable"

    def generate_progress_report(self) -> str:
        """Generate a comprehensive progress report."""
        summary = self.get_summary()
        trend = self.get_trend()
        recent = self.get_recent_days(10)

        report = []
        report.append("=" * 70)
        report.append("$100/DAY GOAL - PROGRESS TRACKER")
        report.append("=" * 70)
        report.append("")

        # Progress bar
        progress = min(100, max(0, summary["progress_to_target_pct"]))
        bar_filled = int(progress / 5)
        bar = "█" * bar_filled + "░" * (20 - bar_filled)
        report.append(f"Progress: [{bar}] {progress:.1f}% of target")
        report.append("")

        # Summary stats
        report.append("SUMMARY STATISTICS")
        report.append("-" * 50)
        report.append(f"  Total Trading Days:      {summary['total_days']:>12}")
        report.append(f"  Days Above Target:       {summary['days_above_target']:>12}")
        report.append(f"  Hit Rate:                {summary['hit_rate_pct']:>11.1f}%")
        report.append(f"  Average Daily P&L:       ${summary['average_daily_pnl']:>10.2f}")
        report.append(f"  Target Daily P&L:        ${self.target_daily:>10.2f}")
        report.append(
            f"  Gap to Target:           ${(self.target_daily - summary['average_daily_pnl']):>10.2f}"
        )
        report.append("")

        report.append("CUMULATIVE PERFORMANCE")
        report.append("-" * 50)
        report.append(f"  Cumulative P&L:          ${summary['cumulative_pnl']:>10.2f}")
        report.append(f"  Best Single Day:         ${summary['best_day']:>10.2f}")
        report.append(f"  Worst Single Day:        ${summary['worst_day']:>10.2f}")
        report.append("")

        report.append("STREAKS")
        report.append("-" * 50)
        report.append(f"  Current Streak:          {summary['current_streak']:>12} days")
        report.append(f"  Best Streak:             {summary['best_streak']:>12} days")
        report.append("")

        # Trend indicator
        trend_indicators = {
            "strongly_improving": "🚀 STRONGLY IMPROVING",
            "improving": "📈 Improving",
            "stable": "➡️  Stable",
            "declining": "📉 Declining",
            "strongly_declining": "⚠️  STRONGLY DECLINING",
            "insufficient_data": "❓ Insufficient data",
        }
        report.append("TREND ANALYSIS")
        report.append("-" * 50)
        report.append(f"  Current Trend:           {trend_indicators.get(trend, trend)}")
        report.append("")

        # Recent history
        if recent:
            report.append("RECENT TRADING DAYS")
            report.append("-" * 50)
            report.append("  Date           P&L        Hit    Strategy")
            report.append("  " + "-" * 46)
            for d in reversed(recent):
                hit_emoji = "✅" if d.hit_target else "❌"
                report.append(f"  {d.date}   ${d.pnl:>8.2f}    {hit_emoji}     {d.strategy[:15]}")
            report.append("")

        report.append("=" * 70)

        return "\n".join(report)

    def export_for_dashboard(self) -> dict[str, Any]:
        """Export data formatted for dashboard display."""
        summary = self.get_summary()
        trend = self.get_trend()

        # Prepare chart data
        dates = [d.date for d in self.history]
        pnls = [d.pnl for d in self.history]
        equities = [d.equity for d in self.history]
        cumulative = [d.cumulative_pnl for d in self.history]
        targets = [self.target_daily] * len(self.history)

        return {
            "summary": summary,
            "trend": trend,
            "chart_data": {
                "dates": dates,
                "daily_pnl": pnls,
                "equity": equities,
                "cumulative_pnl": cumulative,
                "target_line": targets,
            },
            "recent_days": [d.to_dict() for d in self.get_recent_days(10)],
            "target_daily": self.target_daily,
            "initial_capital": self.initial_capital,
        }


# Global tracker instance
_tracker: ProgressTracker | None = None


def get_tracker() -> ProgressTracker:
    """Get or create the global progress tracker."""
    global _tracker
    if _tracker is None:
        _tracker = ProgressTracker()
    return _tracker


def record_daily_pnl(
    date: str | datetime,
    pnl: float,
    equity: float,
    strategy: str = "unknown",
) -> DailyProgress:
    """Convenience function to record daily P&L."""
    return get_tracker().record_day(date, pnl, equity, strategy)


def get_progress_report() -> str:
    """Convenience function to get progress report."""
    return get_tracker().generate_progress_report()
