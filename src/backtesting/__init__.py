"""
Backtesting Module

Lightweight backtesting engine for validating trading strategies on historical data.

Modules:
    - backtest_engine: Main backtesting engine
    - backtest_results: Results data structure and reporting
    - walk_forward_matrix: Walk-forward validation with rolling OOS evaluation
    - target_integration: $100/day target evaluation for backtests

Author: Trading System
Created: 2025-11-02
"""

from src.backtesting.backtest_engine import BacktestEngine
from src.backtesting.backtest_results import BacktestResults
from src.backtesting.monte_carlo import (
    MonteCarloResult,
    MonteCarloSimulator,
    run_monte_carlo_validation,
)
from src.backtesting.performance_report import PerformanceReport, PerformanceReporter
from src.backtesting.target_integration import (
    BacktestTargetValidator,
    TargetBacktestReport,
    add_target_section_to_report,
    evaluate_backtest_with_target,
    save_target_evaluation,
)
from src.backtesting.walk_forward import (
    WalkForwardFold,
    WalkForwardResults,
    WalkForwardValidator,
    create_time_aware_split,
)
from src.backtesting.walk_forward_matrix import (
    BacktestMatrixResults,
    LiveVsBacktestTracker,
    WalkForwardMatrixValidator,
    run_walk_forward_matrix,
)

__all__ = [
    "BacktestEngine",
    "BacktestResults",
    "PerformanceReport",
    "PerformanceReporter",
    "WalkForwardValidator",
    "WalkForwardResults",
    "WalkForwardFold",
    "create_time_aware_split",
    "BacktestMatrixResults",
    "WalkForwardMatrixValidator",
    "LiveVsBacktestTracker",
    "run_walk_forward_matrix",
    "evaluate_backtest_with_target",
    "add_target_section_to_report",
    "save_target_evaluation",
    "BacktestTargetValidator",
    "TargetBacktestReport",
    "MonteCarloResult",
    "MonteCarloSimulator",
    "run_monte_carlo_validation",
]
