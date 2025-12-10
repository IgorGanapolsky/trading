"""
Backtest Results Module

This module provides a data structure for storing and analyzing backtesting results,
including trades, performance metrics, and reporting capabilities.

Dec 3, 2025 Enhancement:
- Added trade-based win rate metrics (vs daily-based)
- Added average win/loss amounts
- Added profit factor (total wins / total losses)
- Added consecutive win/loss streak tracking
- Added trade duration and holding period analysis

Author: Trading System
Created: 2025-11-02
Updated: 2025-12-03
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class TradeMetrics:
    """
    Trade-based performance metrics (Dec 3, 2025).

    These metrics are calculated per-trade rather than per-day,
    which is more accurate for evaluating strategy performance.
    """

    # Core trade metrics
    trade_win_rate: float = 0.0  # % of profitable trades (NOT days)
    total_winning_trades: int = 0
    total_losing_trades: int = 0
    breakeven_trades: int = 0

    # Win/Loss amounts
    avg_win_amount: float = 0.0  # Average profit on winning trades
    avg_loss_amount: float = 0.0  # Average loss on losing trades (positive number)
    largest_win: float = 0.0
    largest_loss: float = 0.0  # Positive number for readability

    # Profit factor and expectancy
    profit_factor: float = 0.0  # Total wins / Total losses
    expectancy: float = 0.0  # Average expected profit per trade
    risk_reward_ratio: float = 0.0  # Avg win / Avg loss

    # Streak analysis
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    current_streak: int = 0  # Positive = wins, negative = losses

    # Duration analysis
    avg_holding_period_days: float = 0.0
    avg_winning_hold_days: float = 0.0
    avg_losing_hold_days: float = 0.0

    @classmethod
    def from_trades(cls, trades: list[dict[str, Any]]) -> TradeMetrics:
        """
        Calculate trade metrics from a list of trade records.

        Each trade should have:
        - 'pnl' or 'profit': The profit/loss amount
        - 'entry_date' and 'exit_date': For duration calculation (optional)
        """
        if not trades:
            return cls()

        # Extract P&L values
        pnls = []
        for trade in trades:
            pnl = trade.get("pnl") or trade.get("profit") or trade.get("return_pct", 0)
            if isinstance(pnl, str):
                try:
                    pnl = float(pnl.replace("%", "").replace("$", "").replace(",", ""))
                except ValueError:
                    pnl = 0
            pnls.append(float(pnl))

        if not pnls:
            return cls()

        # Categorize trades
        wins = [p for p in pnls if p > 0]
        losses = [abs(p) for p in pnls if p < 0]
        breakevens = [p for p in pnls if p == 0]

        total_trades = len(pnls)
        winning_trades = len(wins)
        losing_trades = len(losses)

        # Core metrics
        trade_win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0

        largest_win = max(wins) if wins else 0
        largest_loss = max(losses) if losses else 0

        total_wins = sum(wins)
        total_losses = sum(losses)
        profit_factor = (
            (total_wins / total_losses)
            if total_losses > 0
            else float("inf")
            if total_wins > 0
            else 0
        )
        risk_reward_ratio = (
            (avg_win / avg_loss) if avg_loss > 0 else float("inf") if avg_win > 0 else 0
        )

        # Expectancy = (Win% * Avg Win) - (Loss% * Avg Loss)
        win_pct = winning_trades / total_trades if total_trades > 0 else 0
        loss_pct = losing_trades / total_trades if total_trades > 0 else 0
        expectancy = (win_pct * avg_win) - (loss_pct * avg_loss)

        # Calculate streaks
        max_wins, max_losses, current = cls._calculate_streaks(pnls)

        # Duration analysis (if dates available)
        avg_hold, avg_win_hold, avg_loss_hold = cls._calculate_durations(trades, pnls)

        return cls(
            trade_win_rate=round(trade_win_rate, 2),
            total_winning_trades=winning_trades,
            total_losing_trades=losing_trades,
            breakeven_trades=len(breakevens),
            avg_win_amount=round(avg_win, 2),
            avg_loss_amount=round(avg_loss, 2),
            largest_win=round(largest_win, 2),
            largest_loss=round(largest_loss, 2),
            profit_factor=round(profit_factor, 2) if profit_factor != float("inf") else 999.99,
            expectancy=round(expectancy, 2),
            risk_reward_ratio=round(risk_reward_ratio, 2)
            if risk_reward_ratio != float("inf")
            else 999.99,
            max_consecutive_wins=max_wins,
            max_consecutive_losses=max_losses,
            current_streak=current,
            avg_holding_period_days=round(avg_hold, 1),
            avg_winning_hold_days=round(avg_win_hold, 1),
            avg_losing_hold_days=round(avg_loss_hold, 1),
        )

    @staticmethod
    def _calculate_streaks(pnls: list[float]) -> tuple[int, int, int]:
        """Calculate max consecutive wins/losses and current streak."""
        if not pnls:
            return 0, 0, 0

        max_wins = 0
        max_losses = 0
        current_wins = 0
        current_losses = 0

        for pnl in pnls:
            if pnl > 0:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            elif pnl < 0:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)
            else:
                # Breakeven doesn't break streak but doesn't extend it
                pass

        # Current streak (positive = wins, negative = losses)
        current_streak = current_wins if current_wins > 0 else -current_losses

        return max_wins, max_losses, current_streak

    @staticmethod
    def _calculate_durations(
        trades: list[dict[str, Any]], pnls: list[float]
    ) -> tuple[float, float, float]:
        """Calculate average holding periods."""
        from datetime import datetime

        durations = []
        win_durations = []
        loss_durations = []

        for i, trade in enumerate(trades):
            entry = trade.get("entry_date") or trade.get("date")
            exit_date = trade.get("exit_date") or trade.get("close_date")

            if entry and exit_date:
                try:
                    if isinstance(entry, str):
                        entry = datetime.fromisoformat(entry.replace("Z", "+00:00"))
                    if isinstance(exit_date, str):
                        exit_date = datetime.fromisoformat(exit_date.replace("Z", "+00:00"))

                    duration = (exit_date - entry).days
                    if duration >= 0:
                        durations.append(duration)
                        if i < len(pnls):
                            if pnls[i] > 0:
                                win_durations.append(duration)
                            elif pnls[i] < 0:
                                loss_durations.append(duration)
                except (ValueError, TypeError):
                    pass

        avg_hold = sum(durations) / len(durations) if durations else 0
        avg_win_hold = sum(win_durations) / len(win_durations) if win_durations else 0
        avg_loss_hold = sum(loss_durations) / len(loss_durations) if loss_durations else 0

        return avg_hold, avg_win_hold, avg_loss_hold

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "trade_win_rate": self.trade_win_rate,
            "total_winning_trades": self.total_winning_trades,
            "total_losing_trades": self.total_losing_trades,
            "breakeven_trades": self.breakeven_trades,
            "avg_win_amount": self.avg_win_amount,
            "avg_loss_amount": self.avg_loss_amount,
            "largest_win": self.largest_win,
            "largest_loss": self.largest_loss,
            "profit_factor": self.profit_factor,
            "expectancy": self.expectancy,
            "risk_reward_ratio": self.risk_reward_ratio,
            "max_consecutive_wins": self.max_consecutive_wins,
            "max_consecutive_losses": self.max_consecutive_losses,
            "current_streak": self.current_streak,
            "avg_holding_period_days": self.avg_holding_period_days,
            "avg_winning_hold_days": self.avg_winning_hold_days,
            "avg_losing_hold_days": self.avg_losing_hold_days,
        }


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

    trades: list[dict[str, Any]] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)
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
    # $100/day target metrics
    avg_daily_pnl: float = 0.0
    pct_days_above_target: float = 0.0
    worst_5day_drawdown: float = 0.0
    worst_20day_drawdown: float = 0.0
    # Trade-based metrics (Dec 3, 2025 enhancement)
    trade_metrics: TradeMetrics | None = None

    def calculate_trade_metrics(self) -> TradeMetrics:
        """
        Calculate trade-based metrics from the trades list.

        This provides more accurate performance measurement than
        daily-based metrics (which is what win_rate currently is).
        """
        if self.trades:
            self.trade_metrics = TradeMetrics.from_trades(self.trades)
        else:
            self.trade_metrics = TradeMetrics()
        return self.trade_metrics

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
            "$100/DAY TARGET METRICS",
            "-" * 80,
            f"Avg Daily P&L:     ${self.avg_daily_pnl:.2f}",
            f"% Days ≥ $100:     {self.pct_days_above_target:.1f}%",
            f"Worst 5-Day DD:    ${self.worst_5day_drawdown:.2f}",
            f"Worst 20-Day DD:   ${self.worst_20day_drawdown:.2f}",
            "",
            "TRADE STATISTICS (Daily-Based)",
            "-" * 80,
            f"Total Trades:      {self.total_trades}",
            f"Profitable Trades: {self.profitable_trades}",
            f"Losing Trades:     {self.total_trades - self.profitable_trades}",
            f"Win Rate (Daily):  {self.win_rate:.2f}%",
            f"Avg Trade Return:  {self.average_trade_return:.2f}%",
            "",
        ]

        # Add trade-based metrics (Dec 3, 2025 enhancement)
        if self.trade_metrics is None and self.trades:
            self.calculate_trade_metrics()

        if self.trade_metrics:
            tm = self.trade_metrics
            report_lines.extend(
                [
                    "TRADE-BASED METRICS (More Accurate)",
                    "-" * 80,
                    f"Trade Win Rate:    {tm.trade_win_rate:.1f}% ({tm.total_winning_trades}W / {tm.total_losing_trades}L)",
                    f"Profit Factor:     {tm.profit_factor:.2f} (Total Wins / Total Losses)",
                    f"Expectancy:        ${tm.expectancy:.2f} per trade",
                    f"Risk/Reward Ratio: {tm.risk_reward_ratio:.2f}",
                    f"Avg Win Amount:    ${tm.avg_win_amount:.2f}",
                    f"Avg Loss Amount:   ${tm.avg_loss_amount:.2f}",
                    f"Largest Win:       ${tm.largest_win:.2f}",
                    f"Largest Loss:      ${tm.largest_loss:.2f}",
                    f"Max Win Streak:    {tm.max_consecutive_wins}",
                    f"Max Loss Streak:   {tm.max_consecutive_losses}",
                    f"Avg Holding Days:  {tm.avg_holding_period_days:.1f}",
                    "",
                ]
            )

        report_lines.extend(
            [
                "PERFORMANCE SUMMARY",
                "-" * 80,
            ]
        )

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
                report_lines.append(f"  {date}: BUY {symbol} @ ${price:.2f} (${amount:.2f})")
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

    def to_dict(self) -> dict[str, Any]:
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
            "avg_daily_pnl": self.avg_daily_pnl,
            "pct_days_above_target": self.pct_days_above_target,
            "worst_5day_drawdown": self.worst_5day_drawdown,
            "worst_20day_drawdown": self.worst_20day_drawdown,
            # Trade-based metrics (Dec 3, 2025)
            "trade_metrics": self.trade_metrics.to_dict() if self.trade_metrics else None,
        }

    def save_to_json(self, filepath: str) -> None:
        """
        Save backtest results to a JSON file.

        Args:
            filepath: Path to save the JSON file
        """
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
