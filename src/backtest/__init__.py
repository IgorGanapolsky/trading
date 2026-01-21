"""Backtesting module for options trading strategies."""

from src.backtest.monte_carlo import (
    MonteCarloResults,
    generate_monte_carlo_report,
    run_monte_carlo,
    stress_test_strategy,
)
from src.backtest.risk_metrics import (
    RiskMetrics,
    calculate_max_drawdown,
    calculate_risk_metrics,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_var_cvar,
    generate_risk_report,
)

__all__ = [
    # Risk metrics
    "RiskMetrics",
    "calculate_risk_metrics",
    "calculate_sharpe_ratio",
    "calculate_sortino_ratio",
    "calculate_max_drawdown",
    "calculate_var_cvar",
    "generate_risk_report",
    # Monte Carlo
    "MonteCarloResults",
    "run_monte_carlo",
    "generate_monte_carlo_report",
    "stress_test_strategy",
]
