"""
Backtesting Module

Lightweight backtesting engine for validating trading strategies on historical data.

Modules:
    - backtest_engine: Main backtesting engine
    - backtest_results: Results data structure and reporting
    - walk_forward_matrix: Walk-forward validation with rolling OOS evaluation
    - target_integration: $100/day target evaluation for backtests
    - benchmark_comparison: Compare strategy vs SPY, buy-and-hold, and other benchmarks
    - data_cache: OHLCV data caching with medallion architecture

Author: Trading System
Created: 2025-11-02
Updated: 2025-12-09 - Added benchmark comparison and data caching
"""

from src.backtesting.backtest_engine import BacktestEngine
from src.backtesting.backtest_results import BacktestResults
from src.backtesting.benchmark_comparison import (
    BenchmarkComparator,
    BenchmarkComparisonResult,
    BenchmarkMetrics,
    compare_to_benchmark,
    compare_to_buy_and_hold,
)
from src.backtesting.data_cache import (
    CacheMetadata,
    OHLCVDataCache,
    cached_fetch,
    get_data_cache,
)
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
    # Core backtest engine
    "BacktestEngine",
    "BacktestResults",
    # Performance reporting
    "PerformanceReport",
    "PerformanceReporter",
    # Walk-forward validation
    "WalkForwardValidator",
    "WalkForwardResults",
    "WalkForwardFold",
    "create_time_aware_split",
    # Matrix backtesting
    "BacktestMatrixResults",
    "WalkForwardMatrixValidator",
    "LiveVsBacktestTracker",
    "run_walk_forward_matrix",
    # Target integration
    "evaluate_backtest_with_target",
    "add_target_section_to_report",
    "save_target_evaluation",
    "BacktestTargetValidator",
    "TargetBacktestReport",
    # Monte Carlo simulation
    "MonteCarloResult",
    "MonteCarloSimulator",
    "run_monte_carlo_validation",
    # Benchmark comparison (new)
    "BenchmarkComparator",
    "BenchmarkComparisonResult",
    "BenchmarkMetrics",
    "compare_to_benchmark",
    "compare_to_buy_and_hold",
    # Data caching (new)
    "OHLCVDataCache",
    "CacheMetadata",
    "get_data_cache",
    "cached_fetch",
]
