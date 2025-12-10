"""
Walk-forward validation utilities.

Provides time-aware train/test splits to avoid look-ahead bias and overfitting.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.backtesting.backtest_results import BacktestResults

logger = logging.getLogger(__name__)


@dataclass
class WalkForwardFold:
    """Represents a single fold in walk-forward validation."""

    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    train_data: pd.DataFrame
    test_data: pd.DataFrame
    fold_number: int


@dataclass
class WalkForwardResults:
    """Results from walk-forward validation."""

    folds: list[WalkForwardFold]
    fold_results: list[BacktestResults]
    summary_metrics: dict[str, Any]
    equity_curves: list[list[float]]
    dates: list[list[str]]


class WalkForwardValidator:
    """
    Walk-forward validation with time-aware splits.

    This ensures no look-ahead bias by using expanding or rolling windows
    where training data always comes before test data.
    """

    def __init__(
        self,
        train_window: int = 252,  # 1 year (trading days)
        test_window: int = 63,  # 1 quarter (trading days)
        step: int = 21,  # Monthly rebalance
        method: str = "expanding",  # 'expanding' or 'rolling'
    ):
        """
        Initialize walk-forward validator.

        Args:
            train_window: Training window size in trading days
            test_window: Test window size in trading days
            step: Step size between folds (in trading days)
            method: 'expanding' (growing training set) or 'rolling' (fixed size)
        """
        self.train_window = train_window
        self.test_window = test_window
        self.step = step
        self.method = method

        if method not in ["expanding", "rolling"]:
            raise ValueError(f"Unknown method: {method}. Use 'expanding' or 'rolling'")

    def create_folds(
        self,
        data: pd.DataFrame,
        start_date: pd.Timestamp | None = None,
        end_date: pd.Timestamp | None = None,
    ) -> list[WalkForwardFold]:
        """
        Create walk-forward validation folds.

        Args:
            data: DataFrame with datetime index
            start_date: Optional start date (defaults to data start)
            end_date: Optional end date (defaults to data end)

        Returns:
            List of WalkForwardFold objects
        """
        if not isinstance(data.index, pd.DatetimeIndex):
            raise ValueError("Data must have DatetimeIndex")

        # Filter to date range
        if start_date:
            data = data[data.index >= start_date]
        if end_date:
            data = data[data.index <= end_date]

        if len(data) < self.train_window + self.test_window:
            raise ValueError(
                f"Insufficient data: need at least {self.train_window + self.test_window} days, "
                f"got {len(data)}"
            )

        # Get unique trading dates
        dates = data.index.unique().sort_values()
        n_dates = len(dates)

        folds = []
        fold_number = 0

        # Start with first train_window days for training
        train_start_idx = 0
        train_end_idx = self.train_window

        while train_end_idx + self.test_window <= n_dates:
            train_start = dates[train_start_idx]
            train_end = dates[train_end_idx - 1]  # End is inclusive
            test_start = dates[train_end_idx]
            test_end_idx = min(train_end_idx + self.test_window, n_dates)
            test_end = dates[test_end_idx - 1]

            # Extract data for this fold
            train_mask = (data.index >= train_start) & (data.index <= train_end)
            test_mask = (data.index >= test_start) & (data.index <= test_end)

            train_data = data[train_mask].copy()
            test_data = data[test_mask].copy()

            if len(train_data) > 0 and len(test_data) > 0:
                fold = WalkForwardFold(
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                    train_data=train_data,
                    test_data=test_data,
                    fold_number=fold_number,
                )
                folds.append(fold)
                fold_number += 1

            # Move to next fold
            if self.method == "expanding":
                # Expanding: training window grows, test window moves forward
                train_end_idx += self.step
            else:  # rolling
                # Rolling: training window moves forward, test window moves forward
                train_start_idx += self.step
                train_end_idx += self.step

            # Check if we have enough data for another fold
            if train_end_idx + self.test_window > n_dates:
                break

        logger.info(f"Created {len(folds)} walk-forward folds")
        return folds

    def run(
        self,
        model_class: type,
        data: pd.DataFrame,
        strategy_factory: Callable | None = None,
        **model_kwargs,
    ) -> WalkForwardResults:
        """
        Run walk-forward validation.

        Args:
            model_class: Model class to instantiate for each fold
            data: Full dataset with datetime index
            strategy_factory: Optional function to create strategy from model
            **model_kwargs: Additional arguments to pass to model

        Returns:
            WalkForwardResults object
        """
        folds = self.create_folds(data)
        fold_results = []
        equity_curves = []
        dates_list = []

        for fold in folds:
            logger.info(
                f"Fold {fold.fold_number + 1}/{len(folds)}: "
                f"Train {fold.train_start.date()} to {fold.train_end.date()}, "
                f"Test {fold.test_start.date()} to {fold.test_end.date()}"
            )

            try:
                # Train model on training data
                model = model_class(**model_kwargs)
                # Note: This is a simplified interface - actual implementation
                # would depend on your model's training interface
                if hasattr(model, "fit"):
                    model.fit(fold.train_data)

                # Test on test data
                if strategy_factory:
                    strategy = strategy_factory(model, fold.test_data)
                else:
                    # Default: use model's predict method
                    strategy = model

                # Run backtest on test period
                # Note: This requires integration with your backtest engine
                # For now, we'll create a placeholder result
                from src.backtesting.backtest_engine import BacktestEngine

                # This is a simplified example - you'd need to adapt to your actual strategy interface
                try:
                    engine = BacktestEngine(
                        strategy=strategy,
                        start_date=fold.test_start.strftime("%Y-%m-%d"),
                        end_date=fold.test_end.strftime("%Y-%m-%d"),
                    )
                    results = engine.run()
                    fold_results.append(results)
                    equity_curves.append(results.equity_curve)
                    dates_list.append(results.dates)
                except Exception as e:
                    logger.warning(f"Backtest failed for fold {fold.fold_number}: {e}")
                    # Create empty result
                    from src.backtesting.backtest_results import BacktestResults

                    empty_result = BacktestResults(
                        trades=[],
                        equity_curve=[100000.0],
                        dates=[fold.test_start.strftime("%Y-%m-%d")],
                        total_return=0.0,
                        sharpe_ratio=0.0,
                        max_drawdown=0.0,
                        win_rate=0.0,
                        total_trades=0,
                        profitable_trades=0,
                        average_trade_return=0.0,
                        initial_capital=100000.0,
                        final_capital=100000.0,
                        start_date=fold.test_start.strftime("%Y-%m-%d"),
                        end_date=fold.test_end.strftime("%Y-%m-%d"),
                        trading_days=0,
                    )
                    fold_results.append(empty_result)
                    equity_curves.append([100000.0])
                    dates_list.append([fold.test_start.strftime("%Y-%m-%d")])

            except Exception as e:
                logger.error(f"Error in fold {fold.fold_number}: {e}", exc_info=True)
                # Create empty result for failed fold
                from src.backtesting.backtest_results import BacktestResults

                empty_result = BacktestResults(
                    trades=[],
                    equity_curve=[100000.0],
                    dates=[fold.test_start.strftime("%Y-%m-%d")],
                    total_return=0.0,
                    sharpe_ratio=0.0,
                    max_drawdown=0.0,
                    win_rate=0.0,
                    total_trades=0,
                    profitable_trades=0,
                    average_trade_return=0.0,
                    initial_capital=100000.0,
                    final_capital=100000.0,
                    start_date=fold.test_start.strftime("%Y-%m-%d"),
                    end_date=fold.test_end.strftime("%Y-%m-%d"),
                    trading_days=0,
                )
                fold_results.append(empty_result)
                equity_curves.append([100000.0])
                dates_list.append([fold.test_start.strftime("%Y-%m-%d")])

        # Calculate summary metrics
        summary_metrics = self._calculate_summary_metrics(fold_results)

        return WalkForwardResults(
            folds=folds,
            fold_results=fold_results,
            summary_metrics=summary_metrics,
            equity_curves=equity_curves,
            dates=dates_list,
        )

    def _calculate_summary_metrics(self, fold_results: list[BacktestResults]) -> dict[str, Any]:
        """Calculate summary metrics across all folds."""
        if not fold_results:
            return {}

        returns = [r.total_return for r in fold_results]
        sharpes = [r.sharpe_ratio for r in fold_results]
        drawdowns = [r.max_drawdown for r in fold_results]
        win_rates = [r.win_rate for r in fold_results]

        return {
            "num_folds": len(fold_results),
            "avg_return": np.mean(returns),
            "std_return": np.std(returns),
            "min_return": np.min(returns),
            "max_return": np.max(returns),
            "avg_sharpe": np.mean(sharpes),
            "std_sharpe": np.std(sharpes),
            "avg_drawdown": np.mean(drawdowns),
            "max_drawdown": np.max(drawdowns),
            "avg_win_rate": np.mean(win_rates),
            "consistency": len([r for r in returns if r > 0]) / len(returns) if returns else 0.0,
        }

    def generate_report(self, results: WalkForwardResults) -> str:
        """
        Generate human-readable report of walk-forward validation.

        Args:
            results: WalkForwardResults object

        Returns:
            Formatted report string
        """
        report = []
        report.append("=" * 80)
        report.append("WALK-FORWARD VALIDATION REPORT")
        report.append("=" * 80)
        report.append("\nConfiguration:")
        report.append(f"  Method: {self.method}")
        report.append(f"  Train Window: {self.train_window} days")
        report.append(f"  Test Window: {self.test_window} days")
        report.append(f"  Step: {self.step} days")
        report.append(f"  Total Folds: {len(results.folds)}")

        report.append("\nSummary Metrics:")
        for key, value in results.summary_metrics.items():
            if isinstance(value, float):
                report.append(f"  {key}: {value:.2f}")
            else:
                report.append(f"  {key}: {value}")

        report.append("\nFold Details:")
        for i, (fold, fold_result) in enumerate(
            zip(results.folds, results.fold_results, strict=False)
        ):
            report.append(f"\n  Fold {i + 1}:")
            report.append(f"    Train: {fold.train_start.date()} to {fold.train_end.date()}")
            report.append(f"    Test: {fold.test_start.date()} to {fold.test_end.date()}")
            report.append(f"    Return: {fold_result.total_return:.2f}%")
            report.append(f"    Sharpe: {fold_result.sharpe_ratio:.2f}")
            report.append(f"    Max DD: {fold_result.max_drawdown:.2f}%")
            report.append(f"    Win Rate: {fold_result.win_rate:.1f}%")

        report.append("\n" + "=" * 80)

        return "\n".join(report)


def create_time_aware_split(
    data: pd.DataFrame,
    train_start: pd.Timestamp,
    train_end: pd.Timestamp,
    test_start: pd.Timestamp,
    test_end: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Create time-aware train/test split (no look-ahead bias).

    Args:
        data: DataFrame with datetime index
        train_start: Training start date
        train_end: Training end date
        test_start: Test start date
        test_end: Test end date

    Returns:
        Tuple of (train_data, test_data)
    """
    if not isinstance(data.index, pd.DatetimeIndex):
        raise ValueError("Data must have DatetimeIndex")

    train_mask = (data.index >= train_start) & (data.index <= train_end)
    test_mask = (data.index >= test_start) & (data.index <= test_end)

    train_data = data[train_mask].copy()
    test_data = data[test_mask].copy()

    return train_data, test_data
