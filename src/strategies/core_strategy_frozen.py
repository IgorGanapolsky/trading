"""
Frozen Core Strategy - Productized Version

This is the frozen, tested, and productized version of CoreStrategy.
Any changes to this module must pass CI checks that compare metrics
against the reference backtest.

DO NOT modify this file without:
1. Running the reference backtest
2. Comparing metrics against baseline
3. Explicitly accepting any metric degradation in PR description

Author: Trading System
Created: 2025-12-02
"""

import logging
from typing import Any

from src.strategies.core_strategy import CoreStrategy

logger = logging.getLogger(__name__)

# Reference backtest metrics (baseline)
REFERENCE_BACKTEST_METRICS = {
    "sharpe_ratio": 1.5,  # Minimum acceptable Sharpe
    "avg_daily_pnl": 50.0,  # Minimum acceptable daily P&L
    "pct_days_above_target": 40.0,  # Minimum % days hitting $100
    "max_drawdown": 10.0,  # Maximum acceptable drawdown %
    "worst_5day_drawdown": 2000.0,  # Maximum acceptable 5-day drawdown $
    "worst_20day_drawdown": 10000.0,  # Maximum acceptable 20-day drawdown $
}

# Tolerance for metric changes (5% degradation allowed without explicit acceptance)
METRIC_TOLERANCE_PCT = 5.0


class CoreStrategyFrozen(CoreStrategy):
    """
    Frozen, productized version of CoreStrategy.

    This class wraps CoreStrategy with frozen rules and reference metrics.
    All changes must be validated against the reference backtest.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize frozen strategy."""
        super().__init__(*args, **kwargs)
        logger.info("Initializing Frozen Core Strategy (productized version)")

    @classmethod
    def get_reference_metrics(cls) -> dict[str, Any]:
        """Get reference backtest metrics (baseline)."""
        return REFERENCE_BACKTEST_METRICS.copy()

    @classmethod
    def validate_metrics(cls, new_metrics: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validate new metrics against reference baseline.

        Args:
            new_metrics: New backtest metrics to validate

        Returns:
            Tuple of (is_valid, list_of_warnings)
        """
        warnings = []
        is_valid = True

        ref = REFERENCE_BACKTEST_METRICS

        # Check Sharpe ratio
        new_sharpe = new_metrics.get("sharpe_ratio", 0.0)
        if new_sharpe < ref["sharpe_ratio"] * (1 - METRIC_TOLERANCE_PCT / 100):
            warnings.append(
                f"Sharpe ratio degraded: {new_sharpe:.2f} < {ref['sharpe_ratio']:.2f} "
                f"(tolerance: {METRIC_TOLERANCE_PCT}%)"
            )
            if new_sharpe < ref["sharpe_ratio"] * 0.9:  # More than 10% degradation
                is_valid = False

        # Check average daily P&L
        new_avg_pnl = new_metrics.get("avg_daily_pnl", 0.0)
        if new_avg_pnl < ref["avg_daily_pnl"] * (1 - METRIC_TOLERANCE_PCT / 100):
            warnings.append(
                f"Avg daily P&L degraded: ${new_avg_pnl:.2f} < ${ref['avg_daily_pnl']:.2f} "
                f"(tolerance: {METRIC_TOLERANCE_PCT}%)"
            )
            if new_avg_pnl < ref["avg_daily_pnl"] * 0.9:
                is_valid = False

        # Check % days above target
        new_pct = new_metrics.get("pct_days_above_target", 0.0)
        if new_pct < ref["pct_days_above_target"] * (1 - METRIC_TOLERANCE_PCT / 100):
            warnings.append(
                f"% days ≥ $100 degraded: {new_pct:.1f}% < {ref['pct_days_above_target']:.1f}% "
                f"(tolerance: {METRIC_TOLERANCE_PCT}%)"
            )

        # Check max drawdown (should not exceed)
        new_dd = new_metrics.get("max_drawdown", 100.0)
        if new_dd > ref["max_drawdown"] * (1 + METRIC_TOLERANCE_PCT / 100):
            warnings.append(
                f"Max drawdown increased: {new_dd:.2f}% > {ref['max_drawdown']:.2f}% "
                f"(tolerance: {METRIC_TOLERANCE_PCT}%)"
            )
            if new_dd > ref["max_drawdown"] * 1.1:
                is_valid = False

        # Check worst drawdowns
        new_5dd = new_metrics.get("worst_5day_drawdown", 0.0)
        if new_5dd > ref["worst_5day_drawdown"] * (1 + METRIC_TOLERANCE_PCT / 100):
            warnings.append(
                f"Worst 5-day drawdown increased: ${new_5dd:.2f} > ${ref['worst_5day_drawdown']:.2f} "
                f"(tolerance: {METRIC_TOLERANCE_PCT}%)"
            )

        new_20dd = new_metrics.get("worst_20day_drawdown", 0.0)
        if new_20dd > ref["worst_20day_drawdown"] * (1 + METRIC_TOLERANCE_PCT / 100):
            warnings.append(
                f"Worst 20-day drawdown increased: ${new_20dd:.2f} > ${ref['worst_20day_drawdown']:.2f} "
                f"(tolerance: {METRIC_TOLERANCE_PCT}%)"
            )

        return is_valid, warnings
