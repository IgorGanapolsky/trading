"""
Live vs Backtest Performance Tracker

Tracks and compares live trading performance against backtest predictions
to detect strategy decay, overfitting, and execution issues.

Key Metrics Tracked:
- Win rate divergence (live vs backtest)
- Sharpe ratio divergence
- Average profit per trade divergence
- Slippage variance
- Signal accuracy

Author: Trading System
Created: 2025-12-04
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    """Record of a single trade for comparison."""

    trade_id: str
    symbol: str
    side: str  # "buy" or "sell"
    entry_price: float
    exit_price: Optional[float] = None
    entry_time: str = ""
    exit_time: Optional[str] = None
    pnl: float = 0.0
    pnl_pct: float = 0.0
    signal_strength: float = 0.0
    is_winner: bool = False
    slippage_pct: float = 0.0
    source: str = "live"  # "live" or "backtest"

    def to_dict(self) -> dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "side": self.side,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "entry_time": self.entry_time,
            "exit_time": self.exit_time,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "signal_strength": self.signal_strength,
            "is_winner": self.is_winner,
            "slippage_pct": self.slippage_pct,
            "source": self.source,
        }


@dataclass
class PerformanceMetrics:
    """Performance metrics for comparison."""

    win_rate: float = 0.0
    avg_profit_per_trade: float = 0.0
    total_pnl: float = 0.0
    trade_count: int = 0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    avg_slippage: float = 0.0
    winners: int = 0
    losers: int = 0
    period_start: str = ""
    period_end: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "win_rate": round(self.win_rate, 4),
            "avg_profit_per_trade": round(self.avg_profit_per_trade, 2),
            "total_pnl": round(self.total_pnl, 2),
            "trade_count": self.trade_count,
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "max_drawdown": round(self.max_drawdown, 4),
            "avg_slippage": round(self.avg_slippage, 4),
            "winners": self.winners,
            "losers": self.losers,
            "period_start": self.period_start,
            "period_end": self.period_end,
        }


@dataclass
class DivergenceReport:
    """Report comparing live vs backtest performance."""

    timestamp: str = ""
    live_metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    backtest_metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    win_rate_divergence: float = 0.0  # live - backtest
    sharpe_divergence: float = 0.0
    pnl_divergence_pct: float = 0.0
    slippage_divergence: float = 0.0
    alert_level: str = "NORMAL"  # NORMAL, WARNING, CRITICAL
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "live_metrics": self.live_metrics.to_dict(),
            "backtest_metrics": self.backtest_metrics.to_dict(),
            "divergence": {
                "win_rate": round(self.win_rate_divergence, 4),
                "sharpe": round(self.sharpe_divergence, 4),
                "pnl_pct": round(self.pnl_divergence_pct, 4),
                "slippage": round(self.slippage_divergence, 4),
            },
            "alert_level": self.alert_level,
            "recommendations": self.recommendations,
        }


class LiveVsBacktestTracker:
    """
    Tracks live trading performance and compares against backtest predictions.

    Uses rolling window comparison to detect strategy decay.
    """

    # Alert thresholds
    WIN_RATE_WARNING_THRESHOLD = 0.10  # 10% divergence
    WIN_RATE_CRITICAL_THRESHOLD = 0.20  # 20% divergence
    SHARPE_WARNING_THRESHOLD = 0.5  # 0.5 Sharpe points
    SHARPE_CRITICAL_THRESHOLD = 1.0  # 1.0 Sharpe points
    SLIPPAGE_WARNING_THRESHOLD = 0.005  # 0.5% extra slippage

    def __init__(
        self,
        data_dir: str = "data/performance_tracking",
        comparison_window_days: int = 30,
    ):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.comparison_window_days = comparison_window_days

        self.live_trades: list[TradeRecord] = []
        self.backtest_trades: list[TradeRecord] = []

        self._load_historical_data()

        logger.info(
            f"LiveVsBacktestTracker initialized: "
            f"{len(self.live_trades)} live trades, {len(self.backtest_trades)} backtest trades"
        )

    def record_live_trade(self, trade: TradeRecord) -> None:
        """Record a live trade."""
        trade.source = "live"
        self.live_trades.append(trade)
        self._save_trade(trade)
        logger.debug(f"Recorded live trade: {trade.trade_id}")

    def record_backtest_trade(self, trade: TradeRecord) -> None:
        """Record a backtest trade for comparison."""
        trade.source = "backtest"
        self.backtest_trades.append(trade)
        self._save_trade(trade)

    def calculate_metrics(
        self,
        trades: list[TradeRecord],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> PerformanceMetrics:
        """Calculate performance metrics for a set of trades."""
        if not trades:
            return PerformanceMetrics()

        # Filter by date if specified
        if start_date or end_date:
            filtered = []
            for t in trades:
                if t.entry_time:
                    try:
                        trade_date = datetime.fromisoformat(t.entry_time).date()
                        if start_date and trade_date < start_date:
                            continue
                        if end_date and trade_date > end_date:
                            continue
                        filtered.append(t)
                    except (ValueError, TypeError):
                        continue
            trades = filtered

        if not trades:
            return PerformanceMetrics()

        winners = sum(1 for t in trades if t.is_winner)
        losers = len(trades) - winners
        total_pnl = sum(t.pnl for t in trades)
        avg_pnl = total_pnl / len(trades)
        avg_slippage = sum(t.slippage_pct for t in trades) / len(trades)

        # Calculate Sharpe ratio (simplified)
        if len(trades) > 1:
            returns = [t.pnl_pct for t in trades]
            import statistics

            mean_return = statistics.mean(returns)
            std_return = statistics.stdev(returns) if len(returns) > 1 else 1
            sharpe = (mean_return * 252**0.5) / std_return if std_return > 0 else 0
        else:
            sharpe = 0

        # Get date range
        dates = []
        for t in trades:
            if t.entry_time:
                try:
                    dates.append(datetime.fromisoformat(t.entry_time).date())
                except (ValueError, TypeError):
                    pass

        return PerformanceMetrics(
            win_rate=winners / len(trades),
            avg_profit_per_trade=avg_pnl,
            total_pnl=total_pnl,
            trade_count=len(trades),
            sharpe_ratio=sharpe,
            max_drawdown=0.0,  # Simplified
            avg_slippage=avg_slippage,
            winners=winners,
            losers=losers,
            period_start=str(min(dates)) if dates else "",
            period_end=str(max(dates)) if dates else "",
        )

    def generate_divergence_report(
        self,
        window_days: Optional[int] = None,
    ) -> DivergenceReport:
        """
        Generate a comparison report between live and backtest performance.

        Args:
            window_days: Number of days to compare (default: comparison_window_days)

        Returns:
            DivergenceReport with comparison and recommendations
        """
        window = window_days or self.comparison_window_days
        end_date = date.today()
        start_date = end_date - timedelta(days=window)

        live_metrics = self.calculate_metrics(self.live_trades, start_date, end_date)
        backtest_metrics = self.calculate_metrics(self.backtest_trades, start_date, end_date)

        # Calculate divergences
        win_rate_div = live_metrics.win_rate - backtest_metrics.win_rate
        sharpe_div = live_metrics.sharpe_ratio - backtest_metrics.sharpe_ratio
        slippage_div = live_metrics.avg_slippage - backtest_metrics.avg_slippage

        # Calculate PnL divergence
        if backtest_metrics.total_pnl != 0:
            pnl_div = (live_metrics.total_pnl - backtest_metrics.total_pnl) / abs(
                backtest_metrics.total_pnl
            )
        else:
            pnl_div = 0 if live_metrics.total_pnl == 0 else 1.0

        # Determine alert level and recommendations
        alert_level = "NORMAL"
        recommendations = []

        # Win rate checks
        if abs(win_rate_div) >= self.WIN_RATE_CRITICAL_THRESHOLD:
            alert_level = "CRITICAL"
            recommendations.append(
                f"Win rate diverged {win_rate_div:.1%} from backtest - strategy may be overfit"
            )
        elif abs(win_rate_div) >= self.WIN_RATE_WARNING_THRESHOLD:
            alert_level = "WARNING"
            recommendations.append(
                f"Win rate diverging {win_rate_div:.1%} from backtest - monitor closely"
            )

        # Sharpe ratio checks
        if sharpe_div <= -self.SHARPE_CRITICAL_THRESHOLD:
            alert_level = "CRITICAL"
            recommendations.append(
                f"Sharpe ratio dropped {abs(sharpe_div):.2f} below backtest - consider pausing"
            )
        elif sharpe_div <= -self.SHARPE_WARNING_THRESHOLD:
            if alert_level != "CRITICAL":
                alert_level = "WARNING"
            recommendations.append(
                f"Sharpe ratio declining {abs(sharpe_div):.2f} vs backtest"
            )

        # Slippage checks
        if slippage_div >= self.SLIPPAGE_WARNING_THRESHOLD:
            if alert_level == "NORMAL":
                alert_level = "WARNING"
            recommendations.append(
                f"Slippage {slippage_div:.2%} higher than backtest - review execution"
            )

        # No issues
        if not recommendations:
            recommendations.append("Performance tracking within acceptable ranges")

        return DivergenceReport(
            timestamp=datetime.now().isoformat(),
            live_metrics=live_metrics,
            backtest_metrics=backtest_metrics,
            win_rate_divergence=win_rate_div,
            sharpe_divergence=sharpe_div,
            pnl_divergence_pct=pnl_div,
            slippage_divergence=slippage_div,
            alert_level=alert_level,
            recommendations=recommendations,
        )

    def _save_trade(self, trade: TradeRecord) -> None:
        """Save trade to disk."""
        filename = f"{trade.source}_trades_{date.today().isoformat()}.jsonl"
        filepath = self.data_dir / filename
        try:
            with open(filepath, "a") as f:
                f.write(json.dumps(trade.to_dict()) + "\n")
        except Exception as e:
            logger.error(f"Error saving trade: {e}")

    def _load_historical_data(self) -> None:
        """Load historical trade data from disk."""
        for file in self.data_dir.glob("live_trades_*.jsonl"):
            self._load_trades_from_file(file, self.live_trades)
        for file in self.data_dir.glob("backtest_trades_*.jsonl"):
            self._load_trades_from_file(file, self.backtest_trades)

    def _load_trades_from_file(self, filepath: Path, trades_list: list) -> None:
        """Load trades from a JSONL file."""
        try:
            with open(filepath) as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        trades_list.append(
                            TradeRecord(
                                trade_id=data.get("trade_id", ""),
                                symbol=data.get("symbol", ""),
                                side=data.get("side", ""),
                                entry_price=data.get("entry_price", 0),
                                exit_price=data.get("exit_price"),
                                entry_time=data.get("entry_time", ""),
                                exit_time=data.get("exit_time"),
                                pnl=data.get("pnl", 0),
                                pnl_pct=data.get("pnl_pct", 0),
                                signal_strength=data.get("signal_strength", 0),
                                is_winner=data.get("is_winner", False),
                                slippage_pct=data.get("slippage_pct", 0),
                                source=data.get("source", "live"),
                            )
                        )
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Error loading trades from {filepath}: {e}")

    def get_summary(self) -> dict[str, Any]:
        """Get current tracking summary."""
        report = self.generate_divergence_report()
        return {
            "status": report.alert_level,
            "live_trades_tracked": len(self.live_trades),
            "backtest_trades_tracked": len(self.backtest_trades),
            "divergence_report": report.to_dict(),
            "comparison_window_days": self.comparison_window_days,
        }


# Convenience function for integration
def check_performance_divergence() -> dict[str, Any]:
    """Quick check of live vs backtest divergence."""
    tracker = LiveVsBacktestTracker()
    return tracker.get_summary()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("LIVE VS BACKTEST PERFORMANCE TRACKER")
    print("=" * 80)

    tracker = LiveVsBacktestTracker()

    # Add some sample data for testing
    import random

    for i in range(20):
        # Simulated live trades (slightly worse than backtest)
        tracker.record_live_trade(
            TradeRecord(
                trade_id=f"live_{i}",
                symbol="SPY",
                side="buy",
                entry_price=450.0,
                exit_price=450.0 * (1 + random.uniform(-0.02, 0.03)),
                entry_time=datetime.now().isoformat(),
                pnl=random.uniform(-50, 80),
                pnl_pct=random.uniform(-0.02, 0.03),
                is_winner=random.random() > 0.45,  # 55% win rate
                slippage_pct=random.uniform(0.001, 0.003),
            )
        )

        # Simulated backtest trades (better)
        tracker.record_backtest_trade(
            TradeRecord(
                trade_id=f"bt_{i}",
                symbol="SPY",
                side="buy",
                entry_price=450.0,
                exit_price=450.0 * (1 + random.uniform(-0.015, 0.035)),
                entry_time=datetime.now().isoformat(),
                pnl=random.uniform(-40, 100),
                pnl_pct=random.uniform(-0.015, 0.035),
                is_winner=random.random() > 0.38,  # 62% win rate
                slippage_pct=random.uniform(0.0005, 0.001),
            )
        )

    # Generate report
    summary = tracker.get_summary()

    print(f"\n📊 Status: {summary['status']}")
    print(f"   Live trades tracked: {summary['live_trades_tracked']}")
    print(f"   Backtest trades tracked: {summary['backtest_trades_tracked']}")

    report = summary["divergence_report"]
    print("\n📈 Divergence Analysis:")
    print(f"   Win Rate: Live={report['live_metrics']['win_rate']:.1%}, "
          f"Backtest={report['backtest_metrics']['win_rate']:.1%}, "
          f"Δ={report['divergence']['win_rate']:.1%}")
    print(f"   Sharpe: Live={report['live_metrics']['sharpe_ratio']:.2f}, "
          f"Backtest={report['backtest_metrics']['sharpe_ratio']:.2f}, "
          f"Δ={report['divergence']['sharpe']:.2f}")
    print(f"   Slippage: Live={report['live_metrics']['avg_slippage']:.3%}, "
          f"Backtest={report['backtest_metrics']['avg_slippage']:.3%}")

    print("\n💡 Recommendations:")
    for rec in report["recommendations"]:
        print(f"   • {rec}")
