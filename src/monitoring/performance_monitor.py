"""
Live Performance Monitor Module.

This module tracks live trading performance and compares it against
backtest expectations to detect strategy degradation early.

Features:
    - Real-time performance tracking
    - Backtest vs live comparison
    - Performance degradation alerts
    - Statistical significance testing
    - Rolling performance metrics

Author: Trading System
Created: 2025-12-04
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of performance alerts."""

    PERFORMANCE_DEGRADATION = "performance_degradation"
    SHARPE_BELOW_THRESHOLD = "sharpe_below_threshold"
    DRAWDOWN_EXCEEDED = "drawdown_exceeded"
    WIN_RATE_DECLINE = "win_rate_decline"
    VOLATILITY_SPIKE = "volatility_spike"
    REGIME_CHANGE = "regime_change"
    CORRELATION_BREAK = "correlation_break"


@dataclass
class PerformanceAlert:
    """Performance monitoring alert."""

    alert_type: AlertType
    severity: AlertSeverity
    message: str
    timestamp: datetime
    metric_name: str
    expected_value: float
    actual_value: float
    threshold: float
    recommended_action: str


@dataclass
class PerformanceComparison:
    """Comparison between backtest and live performance."""

    # Return metrics
    backtest_return: float
    live_return: float
    return_ratio: float  # live / backtest

    # Risk metrics
    backtest_sharpe: float
    live_sharpe: float
    sharpe_ratio: float

    # Win rate
    backtest_win_rate: float
    live_win_rate: float
    win_rate_ratio: float

    # Drawdown
    backtest_max_dd: float
    live_max_dd: float
    drawdown_ratio: float

    # Statistical tests
    is_significantly_different: bool
    p_value: float

    # Overall assessment
    performance_score: float  # 0-100
    status: str  # "healthy", "warning", "critical"
    alerts: list[PerformanceAlert]


@dataclass
class LiveMetrics:
    """Container for live trading metrics."""

    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    profitable_trades: int = 0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    volatility: float = 0.0
    current_drawdown: float = 0.0
    peak_equity: float = 0.0
    current_equity: float = 0.0
    daily_returns: list[float] = field(default_factory=list)
    trade_returns: list[float] = field(default_factory=list)


class LivePerformanceMonitor:
    """
    Monitors live trading performance against backtest expectations.

    This class tracks live trades and compares performance against
    historical backtest results to detect strategy degradation.
    """

    def __init__(
        self,
        backtest_sharpe: float = 1.0,
        backtest_win_rate: float = 0.55,
        backtest_max_dd: float = 0.10,
        backtest_return: float = 0.10,
        initial_capital: float = 100000.0,
        alert_threshold: float = 0.7,  # Alert if live < 70% of backtest
        data_dir: str = "data/monitoring",
    ):
        """
        Initialize performance monitor.

        Args:
            backtest_sharpe: Expected Sharpe ratio from backtesting
            backtest_win_rate: Expected win rate from backtesting
            backtest_max_dd: Expected max drawdown from backtesting
            backtest_return: Expected annualized return from backtesting
            initial_capital: Starting capital
            alert_threshold: Threshold for performance alerts (live/backtest ratio)
            data_dir: Directory for storing monitoring data
        """
        self.backtest_sharpe = backtest_sharpe
        self.backtest_win_rate = backtest_win_rate
        self.backtest_max_dd = backtest_max_dd
        self.backtest_return = backtest_return
        self.initial_capital = initial_capital
        self.alert_threshold = alert_threshold
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Initialize live metrics
        self.metrics = LiveMetrics(
            peak_equity=initial_capital,
            current_equity=initial_capital,
        )

        self.alerts: list[PerformanceAlert] = []
        self.trade_history: list[dict] = []
        self.daily_equity: list[tuple[datetime, float]] = []

        logger.info(
            f"Initialized performance monitor: "
            f"Backtest Sharpe={backtest_sharpe:.2f}, "
            f"Win Rate={backtest_win_rate:.1%}"
        )

    def record_trade(
        self,
        symbol: str,
        entry_price: float,
        exit_price: float,
        quantity: float,
        entry_time: datetime,
        exit_time: datetime,
        side: str = "long",
    ) -> None:
        """
        Record a completed trade.

        Args:
            symbol: Trading symbol
            entry_price: Entry price
            exit_price: Exit price
            quantity: Position size
            entry_time: Entry timestamp
            exit_time: Exit timestamp
            side: "long" or "short"
        """
        # Calculate P&L
        if side == "long":
            pnl = (exit_price - entry_price) * quantity
            return_pct = (exit_price - entry_price) / entry_price * 100
        else:
            pnl = (entry_price - exit_price) * quantity
            return_pct = (entry_price - exit_price) / entry_price * 100

        trade = {
            "symbol": symbol,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "quantity": quantity,
            "entry_time": entry_time.isoformat(),
            "exit_time": exit_time.isoformat(),
            "side": side,
            "pnl": pnl,
            "return_pct": return_pct,
        }

        self.trade_history.append(trade)
        self.metrics.trade_returns.append(return_pct)

        # Update metrics
        self._update_metrics(pnl, return_pct > 0)

        # Check for alerts
        self._check_alerts()

        logger.info(f"Recorded trade: {symbol} {side} P&L=${pnl:.2f} ({return_pct:+.2f}%)")

    def record_daily_equity(self, equity: float, date: datetime | None = None) -> None:
        """
        Record end-of-day equity value.

        Args:
            equity: Current portfolio equity
            date: Date of recording (defaults to today)
        """
        if date is None:
            date = datetime.now()

        self.daily_equity.append((date, equity))
        self.metrics.current_equity = equity

        # Update peak and drawdown
        if equity > self.metrics.peak_equity:
            self.metrics.peak_equity = equity

        self.metrics.current_drawdown = (
            self.metrics.peak_equity - equity
        ) / self.metrics.peak_equity

        if self.metrics.current_drawdown > self.metrics.max_drawdown:
            self.metrics.max_drawdown = self.metrics.current_drawdown

        # Calculate daily return
        if len(self.daily_equity) >= 2:
            prev_equity = self.daily_equity[-2][1]
            daily_return = (equity - prev_equity) / prev_equity
            self.metrics.daily_returns.append(daily_return)

            # Update Sharpe ratio
            self._update_sharpe()

        # Update total return
        self.metrics.total_return = (equity - self.initial_capital) / self.initial_capital

        self._check_alerts()

    def _update_metrics(self, pnl: float, is_win: bool) -> None:
        """Update running metrics after a trade."""
        self.metrics.total_trades += 1

        if is_win:
            self.metrics.profitable_trades += 1

        # Update win rate
        self.metrics.win_rate = (
            self.metrics.profitable_trades / self.metrics.total_trades
            if self.metrics.total_trades > 0
            else 0.0
        )

        # Update equity
        self.metrics.current_equity += pnl

        # Update peak
        if self.metrics.current_equity > self.metrics.peak_equity:
            self.metrics.peak_equity = self.metrics.current_equity

        # Update drawdown
        self.metrics.current_drawdown = (
            (self.metrics.peak_equity - self.metrics.current_equity) / self.metrics.peak_equity
            if self.metrics.peak_equity > 0
            else 0.0
        )

        if self.metrics.current_drawdown > self.metrics.max_drawdown:
            self.metrics.max_drawdown = self.metrics.current_drawdown

        # Update average win/loss
        wins = [r for r in self.metrics.trade_returns if r > 0]
        losses = [r for r in self.metrics.trade_returns if r < 0]

        self.metrics.avg_win = np.mean(wins) if wins else 0.0
        self.metrics.avg_loss = np.mean(losses) if losses else 0.0

        # Update profit factor
        total_wins = sum(wins) if wins else 0
        total_losses = abs(sum(losses)) if losses else 0
        self.metrics.profit_factor = total_wins / total_losses if total_losses > 0 else float("inf")

    def _update_sharpe(self) -> None:
        """Update Sharpe ratio from daily returns."""
        if len(self.metrics.daily_returns) < 5:
            return

        returns = np.array(self.metrics.daily_returns)
        if np.std(returns) > 0:
            self.metrics.sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252)
            self.metrics.volatility = np.std(returns) * np.sqrt(252)

    def _check_alerts(self) -> None:
        """Check for performance degradation and generate alerts."""
        now = datetime.now()

        # Check Sharpe ratio
        if self.metrics.sharpe_ratio < self.backtest_sharpe * self.alert_threshold:
            if self.metrics.total_trades >= 10:  # Minimum trades for validity
                alert = PerformanceAlert(
                    alert_type=AlertType.SHARPE_BELOW_THRESHOLD,
                    severity=AlertSeverity.WARNING,
                    message=f"Sharpe ratio {self.metrics.sharpe_ratio:.2f} below threshold",
                    timestamp=now,
                    metric_name="sharpe_ratio",
                    expected_value=self.backtest_sharpe,
                    actual_value=self.metrics.sharpe_ratio,
                    threshold=self.backtest_sharpe * self.alert_threshold,
                    recommended_action="Review recent trades and market conditions",
                )
                self._add_alert(alert)

        # Check drawdown
        if self.metrics.max_drawdown > self.backtest_max_dd * 1.5:
            severity = (
                AlertSeverity.CRITICAL
                if self.metrics.max_drawdown > self.backtest_max_dd * 2
                else AlertSeverity.WARNING
            )
            alert = PerformanceAlert(
                alert_type=AlertType.DRAWDOWN_EXCEEDED,
                severity=severity,
                message=f"Drawdown {self.metrics.max_drawdown:.1%} exceeds expected",
                timestamp=now,
                metric_name="max_drawdown",
                expected_value=self.backtest_max_dd,
                actual_value=self.metrics.max_drawdown,
                threshold=self.backtest_max_dd * 1.5,
                recommended_action="Consider reducing position sizes",
            )
            self._add_alert(alert)

        # Check win rate
        if self.metrics.total_trades >= 20:
            if self.metrics.win_rate < self.backtest_win_rate * self.alert_threshold:
                alert = PerformanceAlert(
                    alert_type=AlertType.WIN_RATE_DECLINE,
                    severity=AlertSeverity.WARNING,
                    message=f"Win rate {self.metrics.win_rate:.1%} below expected",
                    timestamp=now,
                    metric_name="win_rate",
                    expected_value=self.backtest_win_rate,
                    actual_value=self.metrics.win_rate,
                    threshold=self.backtest_win_rate * self.alert_threshold,
                    recommended_action="Review signal quality and entry criteria",
                )
                self._add_alert(alert)

    def _add_alert(self, alert: PerformanceAlert) -> None:
        """Add alert if not duplicate of recent alert."""
        # Check for duplicate in last hour
        recent_cutoff = alert.timestamp - timedelta(hours=1)

        for existing in self.alerts:
            if existing.alert_type == alert.alert_type and existing.timestamp > recent_cutoff:
                return  # Don't add duplicate

        self.alerts.append(alert)
        logger.warning(f"Alert: {alert.message}")

    def compare_to_backtest(self) -> PerformanceComparison:
        """
        Compare current live performance to backtest expectations.

        Returns:
            PerformanceComparison with detailed analysis
        """
        # Calculate ratios (handle division by zero)
        return_ratio = (
            self.metrics.total_return / self.backtest_return if self.backtest_return != 0 else 0.0
        )

        sharpe_ratio = (
            self.metrics.sharpe_ratio / self.backtest_sharpe if self.backtest_sharpe != 0 else 0.0
        )

        win_rate_ratio = (
            self.metrics.win_rate / self.backtest_win_rate if self.backtest_win_rate != 0 else 0.0
        )

        drawdown_ratio = (
            self.metrics.max_drawdown / self.backtest_max_dd if self.backtest_max_dd != 0 else 0.0
        )

        # Statistical test (if enough data)
        is_different, p_value = self._statistical_test()

        # Calculate overall score (0-100)
        score = self._calculate_score(return_ratio, sharpe_ratio, win_rate_ratio, drawdown_ratio)

        # Determine status
        if score >= 70:
            status = "healthy"
        elif score >= 50:
            status = "warning"
        else:
            status = "critical"

        return PerformanceComparison(
            backtest_return=self.backtest_return,
            live_return=self.metrics.total_return,
            return_ratio=return_ratio,
            backtest_sharpe=self.backtest_sharpe,
            live_sharpe=self.metrics.sharpe_ratio,
            sharpe_ratio=sharpe_ratio,
            backtest_win_rate=self.backtest_win_rate,
            live_win_rate=self.metrics.win_rate,
            win_rate_ratio=win_rate_ratio,
            backtest_max_dd=self.backtest_max_dd,
            live_max_dd=self.metrics.max_drawdown,
            drawdown_ratio=drawdown_ratio,
            is_significantly_different=is_different,
            p_value=p_value,
            performance_score=score,
            status=status,
            alerts=self.alerts.copy(),
        )

    def _statistical_test(self) -> tuple[bool, float]:
        """
        Test if live performance is statistically different from backtest.

        Uses a simple z-test for now. Returns (is_different, p_value).
        """
        if len(self.metrics.trade_returns) < 30:
            return False, 1.0  # Not enough data

        # Simple z-test comparing mean returns
        # Assuming backtest had similar number of trades
        sample_mean = np.mean(self.metrics.trade_returns)
        sample_std = np.std(self.metrics.trade_returns)
        n = len(self.metrics.trade_returns)

        # Estimate backtest mean from win rate and avg win/loss
        # This is a rough approximation
        expected_mean = self.backtest_win_rate * abs(self.metrics.avg_win) - (
            1 - self.backtest_win_rate
        ) * abs(self.metrics.avg_loss)

        if sample_std > 0:
            z_stat = (sample_mean - expected_mean) / (sample_std / np.sqrt(n))
            # Two-tailed p-value approximation
            p_value = 2 * (1 - min(0.9999, abs(z_stat) / 4))
        else:
            p_value = 1.0

        return p_value < 0.05, p_value

    def _calculate_score(
        self,
        return_ratio: float,
        sharpe_ratio: float,
        win_rate_ratio: float,
        drawdown_ratio: float,
    ) -> float:
        """Calculate overall performance score (0-100)."""
        # Weight different metrics
        weights = {
            "sharpe": 0.35,
            "return": 0.25,
            "win_rate": 0.20,
            "drawdown": 0.20,
        }

        # Score each metric (capped at 1.0 for over-performance)
        sharpe_score = min(1.0, max(0, sharpe_ratio)) * 100
        return_score = min(1.0, max(0, return_ratio)) * 100
        win_rate_score = min(1.0, max(0, win_rate_ratio)) * 100

        # Drawdown: lower is better, so invert
        drawdown_score = max(0, 100 - (drawdown_ratio - 1) * 50)

        score = (
            weights["sharpe"] * sharpe_score
            + weights["return"] * return_score
            + weights["win_rate"] * win_rate_score
            + weights["drawdown"] * drawdown_score
        )

        return min(100, max(0, score))

    def generate_report(self) -> str:
        """Generate performance monitoring report."""
        comparison = self.compare_to_backtest()

        report = []
        report.append("=" * 70)
        report.append("LIVE PERFORMANCE MONITORING REPORT")
        report.append("=" * 70)

        report.append(f"\nReport Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        report.append(f"Total Trades: {self.metrics.total_trades}")
        report.append(f"Trading Days: {len(self.daily_equity)}")

        report.append("\n" + "-" * 70)
        report.append("PERFORMANCE COMPARISON (Live vs Backtest)")
        report.append("-" * 70)

        report.append(f"\n{'Metric':<20} {'Backtest':<15} {'Live':<15} {'Ratio':<10}")
        report.append("-" * 60)

        report.append(
            f"{'Total Return':<20} {self.backtest_return:>14.1%} "
            f"{self.metrics.total_return:>14.1%} {comparison.return_ratio:>9.2f}"
        )
        report.append(
            f"{'Sharpe Ratio':<20} {self.backtest_sharpe:>14.2f} "
            f"{self.metrics.sharpe_ratio:>14.2f} {comparison.sharpe_ratio:>9.2f}"
        )
        report.append(
            f"{'Win Rate':<20} {self.backtest_win_rate:>14.1%} "
            f"{self.metrics.win_rate:>14.1%} {comparison.win_rate_ratio:>9.2f}"
        )
        report.append(
            f"{'Max Drawdown':<20} {self.backtest_max_dd:>14.1%} "
            f"{self.metrics.max_drawdown:>14.1%} {comparison.drawdown_ratio:>9.2f}"
        )

        report.append("\n" + "-" * 70)
        report.append("OVERALL ASSESSMENT")
        report.append("-" * 70)

        status_emoji = {"healthy": "[OK]", "warning": "[WARN]", "critical": "[FAIL]"}
        report.append(f"\nPerformance Score: {comparison.performance_score:.0f}/100")
        report.append(
            f"Status: {status_emoji.get(comparison.status, '')} {comparison.status.upper()}"
        )

        if comparison.is_significantly_different:
            report.append(f"Statistical Significance: Yes (p={comparison.p_value:.3f})")
        else:
            report.append(f"Statistical Significance: No (p={comparison.p_value:.3f})")

        if self.alerts:
            report.append("\n" + "-" * 70)
            report.append("ACTIVE ALERTS")
            report.append("-" * 70)

            for alert in self.alerts[-5:]:  # Last 5 alerts
                report.append(f"\n  [{alert.severity.value.upper()}] {alert.alert_type.value}")
                report.append(f"    {alert.message}")
                report.append(f"    Action: {alert.recommended_action}")

        report.append("\n" + "=" * 70)

        return "\n".join(report)

    def save_state(self) -> None:
        """Save monitoring state to disk."""
        state = {
            "metrics": {
                "total_return": self.metrics.total_return,
                "sharpe_ratio": self.metrics.sharpe_ratio,
                "max_drawdown": self.metrics.max_drawdown,
                "win_rate": self.metrics.win_rate,
                "total_trades": self.metrics.total_trades,
                "profitable_trades": self.metrics.profitable_trades,
                "current_equity": self.metrics.current_equity,
                "peak_equity": self.metrics.peak_equity,
            },
            "trade_history": self.trade_history,
            "daily_equity": [(dt.isoformat(), eq) for dt, eq in self.daily_equity],
            "alerts": [
                {
                    "type": a.alert_type.value,
                    "severity": a.severity.value,
                    "message": a.message,
                    "timestamp": a.timestamp.isoformat(),
                }
                for a in self.alerts
            ],
        }

        state_file = self.data_dir / "monitor_state.json"
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)

        logger.info(f"Saved monitoring state to {state_file}")

    def load_state(self) -> bool:
        """Load monitoring state from disk."""
        state_file = self.data_dir / "monitor_state.json"

        if not state_file.exists():
            return False

        try:
            with open(state_file) as f:
                state = json.load(f)

            # Restore metrics
            m = state.get("metrics", {})
            self.metrics.total_return = m.get("total_return", 0.0)
            self.metrics.sharpe_ratio = m.get("sharpe_ratio", 0.0)
            self.metrics.max_drawdown = m.get("max_drawdown", 0.0)
            self.metrics.win_rate = m.get("win_rate", 0.0)
            self.metrics.total_trades = m.get("total_trades", 0)
            self.metrics.profitable_trades = m.get("profitable_trades", 0)
            self.metrics.current_equity = m.get("current_equity", self.initial_capital)
            self.metrics.peak_equity = m.get("peak_equity", self.initial_capital)

            self.trade_history = state.get("trade_history", [])

            # Restore daily equity
            self.daily_equity = [
                (datetime.fromisoformat(dt), eq) for dt, eq in state.get("daily_equity", [])
            ]

            logger.info("Loaded monitoring state")
            return True

        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            return False
