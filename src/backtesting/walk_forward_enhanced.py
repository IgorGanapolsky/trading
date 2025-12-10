"""
Enhanced Walk-Forward Analysis Module.

This module extends the base walk-forward validation with additional features
for production-grade strategy validation including:
    - Optimization within training windows
    - Efficiency ratio calculation (OOS/IS performance)
    - Overfitting detection
    - Parameter stability analysis
    - Rolling window statistics

Author: Trading System
Created: 2025-12-04
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.backtesting.backtest_results import BacktestResults
from src.backtesting.walk_forward import (
    WalkForwardFold,
    WalkForwardResults,
    WalkForwardValidator,
)

logger = logging.getLogger(__name__)


@dataclass
class EnhancedFoldResult:
    """Extended fold result with additional metrics."""

    fold: WalkForwardFold
    in_sample_result: BacktestResults
    out_of_sample_result: BacktestResults
    efficiency_ratio: float  # OOS Sharpe / IS Sharpe
    optimal_params: dict[str, Any]
    param_stability_score: float  # How similar to previous fold


@dataclass
class EnhancedWalkForwardResults:
    """Enhanced results with overfitting analysis."""

    base_results: WalkForwardResults
    fold_details: list[EnhancedFoldResult]

    # Efficiency metrics
    mean_efficiency_ratio: float
    efficiency_ratios: list[float]

    # Overfitting indicators
    overfitting_score: float  # 0 = no overfitting, 1 = severe overfitting
    degradation_pct: float  # IS vs OOS performance degradation

    # Parameter stability
    param_stability_scores: list[float]
    mean_param_stability: float

    # Statistical tests
    is_statistically_valid: bool
    validation_failures: list[str]


class EnhancedWalkForwardValidator:
    """
    Enhanced walk-forward validation with overfitting detection.

    This validator extends the base WalkForwardValidator with:
    1. In-sample optimization within each training window
    2. Out-of-sample validation to detect overfitting
    3. Efficiency ratio calculation (OOS/IS performance)
    4. Parameter stability analysis across folds
    5. Statistical significance testing
    """

    def __init__(
        self,
        train_window: int = 252,
        test_window: int = 63,
        step: int = 21,
        method: str = "anchored",  # 'anchored' (expanding) or 'rolling'
        min_efficiency_ratio: float = 0.5,  # OOS must be at least 50% of IS
        max_degradation: float = 0.4,  # Max 40% performance drop
    ):
        """
        Initialize enhanced walk-forward validator.

        Args:
            train_window: Training window size in trading days
            test_window: Test window size in trading days
            step: Step size between folds
            method: 'anchored' (expanding) or 'rolling' (fixed window)
            min_efficiency_ratio: Minimum acceptable OOS/IS ratio
            max_degradation: Maximum acceptable performance degradation
        """
        self.train_window = train_window
        self.test_window = test_window
        self.step = step
        self.method = "expanding" if method == "anchored" else method
        self.min_efficiency_ratio = min_efficiency_ratio
        self.max_degradation = max_degradation

        self.base_validator = WalkForwardValidator(
            train_window=train_window,
            test_window=test_window,
            step=step,
            method=self.method,
        )

        logger.info(
            f"Initialized enhanced walk-forward validator: "
            f"train={train_window}d, test={test_window}d, step={step}d"
        )

    def run_with_optimization(
        self,
        data: pd.DataFrame,
        strategy_factory: Callable,
        param_grid: dict[str, list[Any]],
        optimization_metric: str = "sharpe_ratio",
        **strategy_kwargs,
    ) -> EnhancedWalkForwardResults:
        """
        Run walk-forward analysis with parameter optimization.

        Args:
            data: DataFrame with datetime index and OHLCV data
            strategy_factory: Function that creates strategy given parameters
            param_grid: Dictionary of parameter names to value lists
            optimization_metric: Metric to optimize ('sharpe_ratio', 'total_return')
            **strategy_kwargs: Additional kwargs to pass to strategy

        Returns:
            EnhancedWalkForwardResults with comprehensive analysis
        """
        folds = self.base_validator.create_folds(data)

        if not folds:
            raise ValueError("No folds created - check data length")

        fold_details = []
        efficiency_ratios = []
        param_stability_scores = []
        previous_params: dict | None = None

        for fold in folds:
            logger.info(
                f"Processing fold {fold.fold_number + 1}/{len(folds)}: "
                f"Train {fold.train_start.date()} to {fold.train_end.date()}"
            )

            # Optimize on in-sample data
            best_params, is_result = self._optimize_in_sample(
                train_data=fold.train_data,
                strategy_factory=strategy_factory,
                param_grid=param_grid,
                optimization_metric=optimization_metric,
                **strategy_kwargs,
            )

            # Test on out-of-sample data
            oos_result = self._run_out_of_sample(
                test_data=fold.test_data,
                strategy_factory=strategy_factory,
                params=best_params,
                **strategy_kwargs,
            )

            # Calculate efficiency ratio
            is_metric = getattr(is_result, optimization_metric, 0.0)
            oos_metric = getattr(oos_result, optimization_metric, 0.0)

            if is_metric != 0:
                efficiency = oos_metric / is_metric
            else:
                efficiency = 0.0 if oos_metric <= 0 else 1.0

            efficiency_ratios.append(efficiency)

            # Calculate parameter stability
            if previous_params is not None:
                stability = self._calculate_param_stability(previous_params, best_params)
            else:
                stability = 1.0  # First fold has perfect stability

            param_stability_scores.append(stability)
            previous_params = best_params

            fold_detail = EnhancedFoldResult(
                fold=fold,
                in_sample_result=is_result,
                out_of_sample_result=oos_result,
                efficiency_ratio=efficiency,
                optimal_params=best_params,
                param_stability_score=stability,
            )
            fold_details.append(fold_detail)

        # Calculate aggregate metrics
        mean_efficiency = np.mean(efficiency_ratios) if efficiency_ratios else 0.0
        mean_param_stability = np.mean(param_stability_scores) if param_stability_scores else 0.0

        # Calculate overfitting score (higher = more overfitting)
        overfitting_score = self._calculate_overfitting_score(fold_details)

        # Calculate average degradation
        is_returns = [fd.in_sample_result.total_return for fd in fold_details]
        oos_returns = [fd.out_of_sample_result.total_return for fd in fold_details]

        if np.mean(is_returns) != 0:
            degradation = 1 - (np.mean(oos_returns) / np.mean(is_returns))
        else:
            degradation = 0.0

        # Validate results
        is_valid, failures = self._validate_results(
            mean_efficiency=mean_efficiency,
            degradation=degradation,
            overfitting_score=overfitting_score,
            fold_details=fold_details,
        )

        # Create base results for compatibility
        base_results = WalkForwardResults(
            folds=folds,
            fold_results=[fd.out_of_sample_result for fd in fold_details],
            summary_metrics=self._calculate_summary(fold_details),
            equity_curves=[[fd.out_of_sample_result.equity_curve[0]] for fd in fold_details],
            dates=[[fd.fold.test_start.strftime("%Y-%m-%d")] for fd in fold_details],
        )

        return EnhancedWalkForwardResults(
            base_results=base_results,
            fold_details=fold_details,
            mean_efficiency_ratio=mean_efficiency,
            efficiency_ratios=efficiency_ratios,
            overfitting_score=overfitting_score,
            degradation_pct=degradation,
            param_stability_scores=param_stability_scores,
            mean_param_stability=mean_param_stability,
            is_statistically_valid=is_valid,
            validation_failures=failures,
        )

    def _optimize_in_sample(
        self,
        train_data: pd.DataFrame,
        strategy_factory: Callable,
        param_grid: dict[str, list[Any]],
        optimization_metric: str,
        **strategy_kwargs,
    ) -> tuple[dict[str, Any], BacktestResults]:
        """
        Optimize strategy parameters on in-sample data.

        Returns:
            Tuple of (best_params, best_result)
        """
        from itertools import product

        # Generate all parameter combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        combinations = list(product(*param_values))

        best_metric = float("-inf")
        best_params = {}
        best_result = None

        for combo in combinations:
            params = dict(zip(param_names, combo, strict=False))

            try:
                strategy = strategy_factory(**params, **strategy_kwargs)

                # Run backtest on training data
                from src.backtesting.backtest_engine import BacktestEngine

                engine = BacktestEngine(
                    strategy=strategy,
                    start_date=train_data.index.min().strftime("%Y-%m-%d"),
                    end_date=train_data.index.max().strftime("%Y-%m-%d"),
                )
                result = engine.run()

                metric_value = getattr(result, optimization_metric, 0.0)

                if metric_value > best_metric:
                    best_metric = metric_value
                    best_params = params
                    best_result = result

            except Exception as e:
                logger.warning(f"Failed to evaluate params {params}: {e}")
                continue

        if best_result is None:
            # Return default params and empty result
            best_params = {name: values[0] for name, values in param_grid.items()}
            best_result = self._create_empty_result(train_data)

        return best_params, best_result

    def _run_out_of_sample(
        self,
        test_data: pd.DataFrame,
        strategy_factory: Callable,
        params: dict[str, Any],
        **strategy_kwargs,
    ) -> BacktestResults:
        """Run strategy with fixed parameters on out-of-sample data."""
        try:
            strategy = strategy_factory(**params, **strategy_kwargs)

            from src.backtesting.backtest_engine import BacktestEngine

            engine = BacktestEngine(
                strategy=strategy,
                start_date=test_data.index.min().strftime("%Y-%m-%d"),
                end_date=test_data.index.max().strftime("%Y-%m-%d"),
            )
            return engine.run()

        except Exception as e:
            logger.warning(f"OOS backtest failed: {e}")
            return self._create_empty_result(test_data)

    def _create_empty_result(self, data: pd.DataFrame) -> BacktestResults:
        """Create empty backtest result."""
        return BacktestResults(
            trades=[],
            equity_curve=[100000.0],
            dates=[data.index.min().strftime("%Y-%m-%d")],
            total_return=0.0,
            sharpe_ratio=0.0,
            max_drawdown=0.0,
            win_rate=0.0,
            total_trades=0,
            profitable_trades=0,
            average_trade_return=0.0,
            initial_capital=100000.0,
            final_capital=100000.0,
            start_date=data.index.min().strftime("%Y-%m-%d"),
            end_date=data.index.max().strftime("%Y-%m-%d"),
            trading_days=0,
        )

    def _calculate_param_stability(
        self,
        prev_params: dict[str, Any],
        curr_params: dict[str, Any],
    ) -> float:
        """
        Calculate parameter stability score between folds.

        Returns value between 0 (completely different) and 1 (identical).
        """
        if not prev_params or not curr_params:
            return 1.0

        matching = 0
        total = 0

        for key in prev_params:
            if key in curr_params:
                total += 1
                prev_val = prev_params[key]
                curr_val = curr_params[key]

                # Handle numeric comparison
                if isinstance(prev_val, int | float) and isinstance(curr_val, int | float):
                    if prev_val != 0:
                        diff = abs(curr_val - prev_val) / abs(prev_val)
                        matching += max(0, 1 - diff)  # 0% diff = 1, 100% diff = 0
                    else:
                        matching += 1.0 if curr_val == 0 else 0.0
                else:
                    matching += 1.0 if prev_val == curr_val else 0.0

        return matching / total if total > 0 else 1.0

    def _calculate_overfitting_score(self, fold_details: list[EnhancedFoldResult]) -> float:
        """
        Calculate overfitting score (0 = no overfitting, 1 = severe).

        Uses multiple indicators:
        - Efficiency ratio degradation across folds
        - Parameter instability
        - IS vs OOS performance gap
        """
        if not fold_details:
            return 0.0

        indicators = []

        # 1. Average efficiency ratio (lower = more overfitting)
        efficiencies = [fd.efficiency_ratio for fd in fold_details]
        avg_efficiency = np.mean(efficiencies)
        efficiency_indicator = max(0, 1 - avg_efficiency)  # Invert so higher = worse
        indicators.append(efficiency_indicator)

        # 2. Efficiency trend (declining = overfitting)
        if len(efficiencies) >= 3:
            # Check if efficiency is declining over time
            x = np.arange(len(efficiencies))
            slope = np.polyfit(x, efficiencies, 1)[0]
            trend_indicator = max(0, -slope)  # Negative slope = overfitting
            indicators.append(min(1, trend_indicator * 5))  # Scale to 0-1

        # 3. IS vs OOS gap
        is_returns = [fd.in_sample_result.total_return for fd in fold_details]
        oos_returns = [fd.out_of_sample_result.total_return for fd in fold_details]

        if np.mean(is_returns) != 0:
            gap = (np.mean(is_returns) - np.mean(oos_returns)) / abs(np.mean(is_returns))
            gap_indicator = max(0, min(1, gap))  # Clamp to 0-1
            indicators.append(gap_indicator)

        # 4. Parameter instability
        stabilities = [fd.param_stability_score for fd in fold_details]
        instability = 1 - np.mean(stabilities)
        indicators.append(instability)

        return float(np.mean(indicators))

    def _calculate_summary(self, fold_details: list[EnhancedFoldResult]) -> dict[str, Any]:
        """Calculate summary metrics from fold details."""
        oos_results = [fd.out_of_sample_result for fd in fold_details]

        returns = [r.total_return for r in oos_results]
        sharpes = [r.sharpe_ratio for r in oos_results]
        drawdowns = [r.max_drawdown for r in oos_results]

        return {
            "num_folds": len(fold_details),
            "avg_oos_return": float(np.mean(returns)),
            "std_oos_return": float(np.std(returns)),
            "avg_oos_sharpe": float(np.mean(sharpes)),
            "avg_oos_drawdown": float(np.mean(drawdowns)),
            "positive_folds": sum(1 for r in returns if r > 0),
            "consistency": sum(1 for r in returns if r > 0) / len(returns) if returns else 0.0,
        }

    def _validate_results(
        self,
        mean_efficiency: float,
        degradation: float,
        overfitting_score: float,
        fold_details: list[EnhancedFoldResult],
    ) -> tuple[bool, list[str]]:
        """
        Validate walk-forward results against quality thresholds.

        Returns:
            Tuple of (is_valid, list of failures)
        """
        failures = []

        # Check efficiency ratio
        if mean_efficiency < self.min_efficiency_ratio:
            failures.append(
                f"Low efficiency ratio: {mean_efficiency:.2f} < {self.min_efficiency_ratio:.2f}"
            )

        # Check degradation
        if degradation > self.max_degradation:
            failures.append(
                f"High IS→OOS degradation: {degradation:.1%} > {self.max_degradation:.0%}"
            )

        # Check overfitting
        if overfitting_score > 0.5:
            failures.append(f"High overfitting score: {overfitting_score:.2f} > 0.5")

        # Check consistency (should have >50% profitable folds)
        profitable_folds = sum(1 for fd in fold_details if fd.out_of_sample_result.total_return > 0)
        if len(fold_details) > 0 and profitable_folds / len(fold_details) < 0.5:
            failures.append(
                f"Low fold consistency: {profitable_folds}/{len(fold_details)} profitable"
            )

        return len(failures) == 0, failures

    def generate_report(self, results: EnhancedWalkForwardResults) -> str:
        """Generate comprehensive walk-forward validation report."""
        report = []
        report.append("=" * 80)
        report.append("ENHANCED WALK-FORWARD VALIDATION REPORT")
        report.append("=" * 80)

        report.append("\nConfiguration:")
        report.append(f"  Method: {self.method}")
        report.append(f"  Train Window: {self.train_window} days")
        report.append(f"  Test Window: {self.test_window} days")
        report.append(f"  Step Size: {self.step} days")
        report.append(f"  Total Folds: {len(results.fold_details)}")

        report.append("\nOverfitting Analysis:")
        report.append(f"  Overfitting Score: {results.overfitting_score:.2f} (0=none, 1=severe)")
        report.append(f"  Mean Efficiency Ratio: {results.mean_efficiency_ratio:.2f}")
        report.append(f"  IS→OOS Degradation: {results.degradation_pct:.1%}")
        report.append(f"  Parameter Stability: {results.mean_param_stability:.2f}")

        report.append("\nValidation Status:")
        if results.is_statistically_valid:
            report.append("  [PASS] Strategy passed validation")
        else:
            report.append("  [FAIL] Strategy failed validation:")
            for failure in results.validation_failures:
                report.append(f"    - {failure}")

        report.append("\nFold-by-Fold Results:")
        for i, fd in enumerate(results.fold_details):
            report.append(f"\n  Fold {i + 1}:")
            report.append(f"    Period: {fd.fold.test_start.date()} to {fd.fold.test_end.date()}")
            report.append(f"    IS Return: {fd.in_sample_result.total_return:.2f}%")
            report.append(f"    OOS Return: {fd.out_of_sample_result.total_return:.2f}%")
            report.append(f"    Efficiency: {fd.efficiency_ratio:.2f}")
            report.append(f"    Param Stability: {fd.param_stability_score:.2f}")

        # Recommendations
        report.append("\nRecommendations:")
        if results.overfitting_score > 0.3:
            report.append("  - Consider simplifying strategy (fewer parameters)")
            report.append("  - Use longer training windows")
            report.append("  - Add regularization to optimization")

        if results.mean_efficiency_ratio < 0.7:
            report.append("  - In-sample may be too optimistic")
            report.append("  - Review feature selection for data snooping")

        if results.mean_param_stability < 0.6:
            report.append("  - Parameters are unstable across time")
            report.append("  - Consider more robust parameter selection")

        report.append("\n" + "=" * 80)

        return "\n".join(report)
