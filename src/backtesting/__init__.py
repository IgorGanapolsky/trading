"""
Backtesting Module

Lightweight backtesting engine for validating trading strategies on historical data.

Modules:
    - backtest_engine: Main backtesting engine
    - backtest_results: Results data structure and reporting
    - walk_forward_matrix: Walk-forward validation with rolling OOS evaluation

Author: Trading System
Created: 2025-11-02
"""

from src.backtesting.backtest_engine import BacktestEngine
from src.backtesting.backtest_results import BacktestResults
from src.backtesting.walk_forward_matrix import (
    BacktestMatrixResults,
    LiveVsBacktestTracker,
    WalkForwardMatrixValidator,
    run_walk_forward_matrix,
)

__all__ = [
    "BacktestEngine",
    "BacktestResults",
    "BacktestMatrixResults",
    "WalkForwardMatrixValidator",
    "LiveVsBacktestTracker",
    "run_walk_forward_matrix",
]
