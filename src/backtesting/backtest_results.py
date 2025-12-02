"""
Backtest Results Module

This module provides a data structure for storing and analyzing backtesting results,
including trades, performance metrics, and reporting capabilities.

Author: Trading System
Created: 2025-11-02
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
from datetime import datetime
import numpy as np
import json


@dataclass
class BacktestResults:
    """
    Data class for storing comprehensive backtesting results.

    Attributes:
        trades: List of all executed trades with details
        equity_curve: Daily portfolio values throughout backtest
        dates: Trading dates corresponding to equity curve
        total_return: Overall return percentage
        sharpe_ratio: Risk-adjusted return metric
        max_drawdown: Maximum peak-to-trough decline percentage
        win_rate: Percentage of profitable days
        total_trades: Total number of trades executed
        profitable_trades: Number of profitable trades
        average_trade_return: Average return per trade
        initial_capital: Starting capital amount
        final_capital: Ending capital amount
        start_date: Backtest start date
        end_date: Backtest end date
        trading_days: Number of trading days
    """

    trades: List[Dict[str, Any]] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    dates: List[str] = field(default_factory=list)
    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    profitable_trades: int = 0
    average_trade_return: float = 0.0
    initial_capital: float = 0.0
    final_capital: float = 0.0
    start_date: str = ""
    end_date: str = ""
    trading_days: int = 0
    # Slippage tracking for realistic cost analysis
    total_slippage_cost: float = 0.0
    slippage_enabled: bool = False

    def generate_report(self) -> str:
        """
        Generate a comprehensive human-readable text report of backtest results.

        Returns:
            Formatted string containing backtest summary and metrics
        """
        report_lines = [
            "=" * 80,
            "BACKTEST RESULTS SUMMARY",
            "=" * 80,
            "",
            "PERIOD INFORMATION",
            "-" * 80,
            f"Start Date:        {self.start_date}",
            f"End Date:          {self.end_date}",
            f"Trading Days:      {self.trading_days}",
            "",
            "CAPITAL & RETURNS",
            "-" * 80,
            f"Initial Capital:   ${self.initial_capital:,.2f}",
            f"Final Capital:     ${self.final_capital:,.2f}",
            f"Total Return:      ${self.final_capital - self.initial_capital:,.2f} ({self.total_return:.2f}%)",
            f"Annualized Return: {self._calculate_annualized_return():.2f}%",
            "",
            "RISK METRICS",
            "-" * 80,
            f"Sharpe Ratio:      {self.sharpe_ratio:.2f}",
            f"Max Drawdown:      {self.max_drawdown:.2f}%",
            f"Volatility:        {self._calculate_volatility():.2f}%",
            "",
            "EXECUTION COSTS",
            "-" * 80,
            f"Slippage Model:    {'Enabled' if self.slippage_enabled else 'Disabled (results may be optimistic)'}",
            f"Total Slippage:    ${self.total_slippage_cost:.2f}",
            f"Slippage % of PnL: {self._calculate_slippage_impact():.2f}%",
            "",
            "TRADE STATISTICS",
            "-" * 80,
            f"Total Trades:      {self.total_trades}",
            f"Profitable Trades: {self.profitable_trades}",
            f"Losing Trades:     {self.total_trades - self.profitable_trades}",
            f"Win Rate:          {self.win_rate:.2f}%",
            f"Avg Trade Return:  {self.average_trade_return:.2f}%",
            "",
            "PERFORMANCE SUMMARY",
            "-" * 80,
        ]

        # Add performance rating
        rating = self._get_performance_rating()
        report_lines.append(f"Overall Rating:    {rating}")
        report_lines.append("")

        # Add trade details if available
        if self.trades:
            report_lines.append("RECENT TRADES (Last 5)")
            report_lines.append("-" * 80)
            for trade in self.trades[-5:]:
                symbol = trade.get("symbol", "N/A")
                date = trade.get("date", "N/A")
                amount = trade.get("amount", 0.0)
                price = trade.get("price", 0.0)
                report_lines.append(
                    f"  {date}: BUY {symbol} @ ${price:.2f} (${amount:.2f})"
                )
            report_lines.append("")

        report_lines.append("=" * 80)

        return "\n".join(report_lines)

    def _calculate_annualized_return(self) -> float:
        """
        Calculate annualized return based on total return and holding period.

        Returns:
            Annualized return percentage
        """
        if self.trading_days == 0:
            return 0.0

        years = self.trading_days / 252  # Assuming 252 trading days per year
        if years == 0:
            return 0.0

        # Annualized return formula: (1 + total_return)^(1/years) - 1
        annualized = (pow(1 + self.total_return / 100, 1 / years) - 1) * 100
        return annualized

    def _calculate_volatility(self) -> float:
        """
        Calculate annualized volatility of returns.

        Returns:
            Annualized volatility percentage
        """
        if len(self.equity_curve) < 2:
            return 0.0

        # Calculate daily returns
        daily_returns = np.diff(self.equity_curve) / self.equity_curve[:-1]

        # Annualized volatility
        volatility = np.std(daily_returns) * np.sqrt(252) * 100
        return volatility

    def _calculate_slippage_impact(self) -> float:
        """
        Calculate slippage as percentage of P&L.

        Returns:
            Slippage impact percentage (higher = more of your gains eaten by slippage)
        """
        pnl = self.final_capital - self.initial_capital
        if pnl <= 0:
            return 0.0
        return (self.total_slippage_cost / pnl) * 100 if pnl > 0 else 0.0

    def _get_performance_rating(self) -> str:
        """
        Get an overall performance rating based on key metrics.

        Returns:
            Performance rating string
        """
        # Simple rating system based on multiple metrics
        score = 0

        # Total return scoring
        if self.total_return > 20:
            score += 3
        elif self.total_return > 10:
            score += 2
        elif self.total_return > 5:
            score += 1

        # Sharpe ratio scoring
        if self.sharpe_ratio > 2.0:
            score += 3
        elif self.sharpe_ratio > 1.5:
            score += 2
        elif self.sharpe_ratio > 1.0:
            score += 1

        # Win rate scoring
        if self.win_rate > 65:
            score += 3
        elif self.win_rate > 55:
            score += 2
        elif self.win_rate > 50:
            score += 1

        # Max drawdown scoring (lower is better)
        if self.max_drawdown < 5:
            score += 3
        elif self.max_drawdown < 10:
            score += 2
        elif self.max_drawdown < 15:
            score += 1

        # Convert score to rating
        if score >= 10:
            return "EXCELLENT"
        elif score >= 7:
            return "GOOD"
        elif score >= 4:
            return "FAIR"
        else:
            return "NEEDS IMPROVEMENT"

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert results to dictionary format for serialization.

        Returns:
            Dictionary containing all results data
        """
        return {
            "trades": self.trades,
            "equity_curve": self.equity_curve,
            "dates": self.dates,
            "total_return": self.total_return,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
            "total_trades": self.total_trades,
            "profitable_trades": self.profitable_trades,
            "average_trade_return": self.average_trade_return,
            "initial_capital": self.initial_capital,
            "final_capital": self.final_capital,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "trading_days": self.trading_days,
            "annualized_return": self._calculate_annualized_return(),
            "volatility": self._calculate_volatility(),
            "performance_rating": self._get_performance_rating(),
            "total_slippage_cost": self.total_slippage_cost,
            "slippage_enabled": self.slippage_enabled,
            "slippage_impact_pct": self._calculate_slippage_impact(),
        }

    def save_to_json(self, filepath: str) -> None:
        """
        Save backtest results to a JSON file.

        Args:
            filepath: Path to save the JSON file
        """
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
