"""
Backtest Results - Data class for backtest output.

Created: Dec 19, 2025 - Fix for AttributeError: 'dict' has no 'equity_curve'
"""

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class BacktestResults:
    """Results from a backtest run."""

    # Core metrics
    start_date: str = ""
    end_date: str = ""
    trading_days: int = 0
    initial_capital: float = 100000.0
    final_capital: float = 100000.0

    # Performance metrics
    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 50.0
    total_trades: int = 0

    # Equity curve (daily portfolio values)
    equity_curve: np.ndarray = field(default_factory=lambda: np.array([100000.0]))

    # Trade log
    trades: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert results to dictionary."""
        # Calculate annualized return
        if self.trading_days > 0:
            daily_return = (self.final_capital / self.initial_capital) ** (
                1 / self.trading_days
            ) - 1
            annualized_return = ((1 + daily_return) ** 252 - 1) * 100
        else:
            annualized_return = 0.0

        return {
            "start_date": self.start_date,
            "end_date": self.end_date,
            "trading_days": self.trading_days,
            "initial_capital": self.initial_capital,
            "final_capital": self.final_capital,
            "total_return": self.total_return,
            "annualized_return": annualized_return,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
            "total_trades": self.total_trades,
        }
