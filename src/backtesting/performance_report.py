"""
Comprehensive performance reporting for backtest results.

Provides detailed metrics, attribution analysis, and regime overlays.
"""

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.backtesting.backtest_results import BacktestResults

logger = logging.getLogger(__name__)


@dataclass
class PerformanceReport:
    """Comprehensive performance report."""

    # Returns
    total_return: float
    annualized_return: float
    cagr: float

    # Risk
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    volatility: float

    # Trade statistics
    total_trades: int
    profitable_trades: int
    win_rate: float
    average_win: float
    average_loss: float
    profit_factor: float

    # Exposure
    avg_exposure: float
    max_exposure: float
    turnover: float

    # Attribution (if available)
    factor_exposures: dict[str, float] | None = None
    sector_exposures: dict[str, float] | None = None

    # Regime analysis (if available)
    regime_performance: dict[str, dict[str, float]] | None = None


class PerformanceReporter:
    """Generate comprehensive performance reports."""

    def __init__(self, risk_free_rate: float = 0.04):
        """
        Initialize performance reporter.

        Args:
            risk_free_rate: Annual risk-free rate (default: 4%)
        """
        self.risk_free_rate = risk_free_rate

    def generate_report(
        self,
        results: BacktestResults,
        prices: pd.DataFrame | None = None,
        benchmark_returns: pd.Series | None = None,
    ) -> PerformanceReport:
        """
        Generate comprehensive performance report.

        Args:
            results: BacktestResults object
            prices: Optional price data for additional analysis
            benchmark_returns: Optional benchmark returns for comparison

        Returns:
            PerformanceReport object
        """
        # Calculate returns
        equity_curve = np.array(results.equity_curve)
        daily_returns = np.diff(equity_curve) / equity_curve[:-1]

        # Basic returns
        total_return = results.total_return
        trading_days = results.trading_days
        years = trading_days / 252.0
        annualized_return = (1 + total_return / 100) ** (1 / years) - 1 if years > 0 else 0.0
        cagr = annualized_return

        # Risk metrics
        sharpe_ratio = results.sharpe_ratio
        sortino_ratio = self._calculate_sortino(daily_returns)
        max_drawdown = results.max_drawdown
        volatility = np.std(daily_returns) * np.sqrt(252) if len(daily_returns) > 0 else 0.0

        # Trade statistics
        total_trades = results.total_trades
        profitable_trades = results.profitable_trades
        win_rate = results.win_rate

        # Calculate average win/loss
        avg_win, avg_loss, profit_factor = self._calculate_trade_statistics(results.trades)

        # Exposure
        avg_exposure, max_exposure, turnover = self._calculate_exposure(
            results.trades, equity_curve, trading_days
        )

        # Attribution (if prices available)
        factor_exposures = None
        sector_exposures = None
        if prices is not None:
            factor_exposures = self._calculate_factor_exposures(results.trades, prices)

        # Regime analysis (if benchmark available)
        regime_performance = None
        if benchmark_returns is not None:
            regime_performance = self._calculate_regime_performance(
                daily_returns, benchmark_returns
            )

        return PerformanceReport(
            total_return=total_return,
            annualized_return=annualized_return * 100,
            cagr=cagr * 100,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_drawdown,
            volatility=volatility * 100,
            total_trades=total_trades,
            profitable_trades=profitable_trades,
            win_rate=win_rate,
            average_win=avg_win,
            average_loss=avg_loss,
            profit_factor=profit_factor,
            avg_exposure=avg_exposure,
            max_exposure=max_exposure,
            turnover=turnover,
            factor_exposures=factor_exposures,
            sector_exposures=sector_exposures,
            regime_performance=regime_performance,
        )

    def _calculate_sortino(self, returns: np.ndarray) -> float:
        """Calculate Sortino ratio (downside deviation only)."""
        if len(returns) == 0:
            return 0.0

        downside_returns = returns[returns < 0]
        if len(downside_returns) == 0:
            return np.inf if np.mean(returns) > 0 else 0.0

        downside_std = np.std(downside_returns)
        if downside_std == 0:
            return 0.0

        mean_return = np.mean(returns)
        annualized_return = mean_return * 252
        annualized_downside = downside_std * np.sqrt(252)

        sortino = (annualized_return - self.risk_free_rate) / annualized_downside
        return sortino

    def _calculate_trade_statistics(
        self, trades: list[dict[str, Any]]
    ) -> tuple[float, float, float]:
        """Calculate average win, average loss, and profit factor."""
        if not trades:
            return 0.0, 0.0, 0.0

        # Simplified: assume we can calculate P&L from trades
        # In practice, you'd need to track entry/exit prices
        wins = []
        losses = []

        for trade in trades:
            # This is a simplified calculation
            # In practice, you'd track actual P&L
            if "pnl" in trade:
                pnl = trade["pnl"]
                if pnl > 0:
                    wins.append(pnl)
                else:
                    losses.append(abs(pnl))

        avg_win = np.mean(wins) if wins else 0.0
        avg_loss = np.mean(losses) if losses else 0.0

        total_wins = sum(wins) if wins else 0.0
        total_losses = sum(losses) if losses else 0.0
        profit_factor = total_wins / total_losses if total_losses > 0 else 0.0

        return avg_win, avg_loss, profit_factor

    def _calculate_exposure(
        self,
        trades: list[dict[str, Any]],
        equity_curve: np.ndarray,
        trading_days: int,
    ) -> tuple[float, float, float]:
        """Calculate average exposure, max exposure, and turnover."""
        if not trades or len(equity_curve) == 0:
            return 0.0, 0.0, 0.0

        # Simplified exposure calculation
        # In practice, you'd track positions over time
        total_notional = sum(trade.get("amount", 0) for trade in trades)
        avg_exposure = total_notional / trading_days if trading_days > 0 else 0.0
        max_exposure = max((trade.get("amount", 0) for trade in trades), default=0.0)

        # Turnover: total traded value / average equity
        avg_equity = np.mean(equity_curve)
        turnover = total_notional / avg_equity if avg_equity > 0 else 0.0

        return avg_exposure, max_exposure, turnover

    def _calculate_factor_exposures(
        self, trades: list[dict[str, Any]], prices: pd.DataFrame
    ) -> dict[str, float]:
        """Calculate factor exposures (simplified)."""
        # This is a placeholder - actual implementation would require
        # factor loadings data (e.g., from Fama-French factors)
        return {}

    def _calculate_regime_performance(
        self, strategy_returns: np.ndarray, benchmark_returns: pd.Series
    ) -> dict[str, dict[str, float]]:
        """Calculate performance by market regime."""
        # Simplified regime detection based on benchmark returns
        if len(strategy_returns) != len(benchmark_returns):
            return {}

        # Define regimes based on benchmark returns
        bull_mask = benchmark_returns > 0.01  # >1% daily return
        bear_mask = benchmark_returns < -0.01  # <-1% daily return
        choppy_mask = ~(bull_mask | bear_mask)

        regime_performance = {}

        # Volatility floor and risk-free rate for Sharpe calculations
        MIN_VOL_FLOOR = 0.0001
        rf_daily = 0.04 / 252

        def safe_sharpe(returns_arr):
            """Calculate Sharpe with floor and clamp."""
            std_val = max(float(np.std(returns_arr)), MIN_VOL_FLOOR)
            sharpe = (float(np.mean(returns_arr)) - rf_daily) / std_val * np.sqrt(252)
            return float(np.clip(sharpe, -10.0, 10.0))

        if np.any(bull_mask):
            bull_returns = strategy_returns[bull_mask]
            regime_performance["bull"] = {
                "return": np.mean(bull_returns) * 252 * 100,
                "sharpe": safe_sharpe(bull_returns),
                "days": int(np.sum(bull_mask)),
            }

        if np.any(bear_mask):
            bear_returns = strategy_returns[bear_mask]
            regime_performance["bear"] = {
                "return": np.mean(bear_returns) * 252 * 100,
                "sharpe": safe_sharpe(bear_returns),
                "days": int(np.sum(bear_mask)),
            }

        if np.any(choppy_mask):
            choppy_returns = strategy_returns[choppy_mask]
            regime_performance["choppy"] = {
                "return": np.mean(choppy_returns) * 252 * 100,
                "sharpe": safe_sharpe(choppy_returns),
                "days": int(np.sum(choppy_mask)),
            }

        return regime_performance

    def format_report(self, report: PerformanceReport) -> str:
        """
        Format performance report as human-readable string.

        Args:
            report: PerformanceReport object

        Returns:
            Formatted report string
        """
        lines = []
        lines.append("=" * 80)
        lines.append("PERFORMANCE REPORT")
        lines.append("=" * 80)

        lines.append("\nRETURNS:")
        lines.append(f"  Total Return: {report.total_return:.2f}%")
        lines.append(f"  Annualized Return: {report.annualized_return:.2f}%")
        lines.append(f"  CAGR: {report.cagr:.2f}%")

        lines.append("\nRISK:")
        lines.append(f"  Sharpe Ratio: {report.sharpe_ratio:.2f}")
        lines.append(f"  Sortino Ratio: {report.sortino_ratio:.2f}")
        lines.append(f"  Max Drawdown: {report.max_drawdown:.2f}%")
        lines.append(f"  Volatility: {report.volatility:.2f}%")

        lines.append("\nTRADE STATISTICS:")
        lines.append(f"  Total Trades: {report.total_trades}")
        lines.append(f"  Profitable Trades: {report.profitable_trades}")
        lines.append(f"  Win Rate: {report.win_rate:.1f}%")
        lines.append(f"  Average Win: ${report.average_win:.2f}")
        lines.append(f"  Average Loss: ${report.average_loss:.2f}")
        lines.append(f"  Profit Factor: {report.profit_factor:.2f}")

        lines.append("\nEXPOSURE:")
        lines.append(f"  Average Exposure: ${report.avg_exposure:.2f}")
        lines.append(f"  Max Exposure: ${report.max_exposure:.2f}")
        lines.append(f"  Turnover: {report.turnover:.2f}")

        if report.regime_performance:
            lines.append("\nREGIME PERFORMANCE:")
            for regime, metrics in report.regime_performance.items():
                lines.append(f"  {regime.upper()}:")
                lines.append(f"    Return: {metrics['return']:.2f}%")
                lines.append(f"    Sharpe: {metrics['sharpe']:.2f}")
                lines.append(f"    Days: {metrics['days']}")

        lines.append("\n" + "=" * 80)

        return "\n".join(lines)
