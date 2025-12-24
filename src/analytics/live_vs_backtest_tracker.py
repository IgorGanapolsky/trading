"""
Live vs Backtest Performance Tracker

Compares paper trading results with backtest predictions to detect
model drift and execution discrepancies.

Created: December 2025
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class PerformanceComparison:
    """Comparison between live and backtest results."""

    timestamp: datetime
    ticker: str
    backtest_pnl: float
    live_pnl: float
    deviation_pct: float
    slippage_bps: float

    @property
    def is_acceptable(self) -> bool:
        """Check if deviation is within acceptable threshold."""
        return abs(self.deviation_pct) < 0.25  # 25% max deviation


class LiveVsBacktestTracker:
    """Track and compare live trading vs backtest performance."""

    def __init__(self) -> None:
        self.comparisons: list[PerformanceComparison] = []

    def record_comparison(
        self,
        ticker: str,
        backtest_pnl: float,
        live_pnl: float,
        slippage_bps: float = 0.0,
    ) -> PerformanceComparison:
        """Record a performance comparison."""
        deviation = abs(backtest_pnl - live_pnl) / max(abs(backtest_pnl), 1) * 100

        comparison = PerformanceComparison(
            timestamp=datetime.now(),
            ticker=ticker,
            backtest_pnl=backtest_pnl,
            live_pnl=live_pnl,
            deviation_pct=deviation,
            slippage_bps=slippage_bps,
        )

        self.comparisons.append(comparison)
        return comparison

    def get_average_deviation(self) -> float:
        """Get average deviation across all comparisons."""
        if not self.comparisons:
            return 0.0
        return sum(c.deviation_pct for c in self.comparisons) / len(self.comparisons)

    def get_drift_alert(self) -> Optional[str]:
        """Return alert if drift exceeds threshold."""
        avg_dev = self.get_average_deviation()
        if avg_dev > 25:
            return f"DRIFT ALERT: Average deviation {avg_dev:.1f}% exceeds 25% threshold"
        return None
