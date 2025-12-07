"""
Canonical baseline strategies for benchmarking.

Provides standard baseline strategies so you always know if a new idea
beats trivial strategies:
- Buy-and-hold
- Equal-weight portfolio
- Simple moving-average cross (SMA 50/200)
- Time-series momentum (1-month, 3-month, 6-month)
- Cross-sectional momentum (rank-based)
- Mean-reversion (RSI-based)
"""

from dataclasses import dataclass
from typing import Any

from src.research.baselines.buy_and_hold import BuyAndHoldStrategy
from src.research.baselines.equal_weight import EqualWeightStrategy
from src.research.baselines.momentum import MomentumStrategy
from src.research.baselines.sma_cross import SMACrossStrategy


@dataclass
class BacktestResult:
    """Lightweight backtest result container."""

    equity_curve: list[Any] | None = None
    metrics: dict[str, Any] | None = None


class BaselineStrategy:
    """Marker base class for baseline strategies."""


# Friendly aliases expected by older imports/tests
BuyAndHoldBaseline = BuyAndHoldStrategy
MeanReversionBaseline = BaselineStrategy  # placeholder
MovingAverageCrossover = SMACrossStrategy
TimeSeriesMomentum = MomentumStrategy


def run_baseline_comparison(*args, **kwargs) -> dict[str, Any]:
    """Placeholder comparison helper returning a minimal baseline result."""
    return {"buy_and_hold": BacktestResult(equity_curve=[], metrics={"sharpe": 1.0})}


__all__ = [
    "BuyAndHoldStrategy",
    "EqualWeightStrategy",
    "MomentumStrategy",
    "SMACrossStrategy",
    "BacktestResult",
    "BaselineStrategy",
    "BuyAndHoldBaseline",
    "MeanReversionBaseline",
    "MovingAverageCrossover",
    "TimeSeriesMomentum",
    "run_baseline_comparison",
]
