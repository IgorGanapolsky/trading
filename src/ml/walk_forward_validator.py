"""
Walk-Forward Validation for Trading ML Models

WARNING: This module is DEPRECATED and BROKEN.
The LSTM-PPO networks it depends on have been removed from production.

Production system uses:
- RLFilter (Gate 2) with TransformerRLPolicy
- RLPolicyLearner (simple Q-learning)

This module implements proper time-series cross-validation using the walk-forward
methodology - essential for any trading system to prevent look-ahead bias and
ensure models generalize to unseen market regimes.

Walk-Forward Approach:
1. Train on initial window (e.g., 252 trading days)
2. Test on next window (e.g., 63 trading days)
3. Roll forward by step size (e.g., 21 trading days)
4. Repeat until all data is used
5. Aggregate out-of-sample performance across all folds

This prevents:
- Look-ahead bias (training on future data)
- Regime overfitting (model only works in one market condition)
- Overly optimistic backtest results

Author: Trading System
Created: 2025-12-01
DEPRECATED: 2025-12-04
"""

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim

logger = logging.getLogger(__name__)


@dataclass
class WalkForwardFold:
    """Results from a single walk-forward fold."""

    fold_number: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    train_size: int
    test_size: int

    # Performance metrics
    train_loss: float = 0.0
    test_loss: float = 0.0
    test_accuracy: float = 0.0
    test_sharpe: float = 0.0
    test_return: float = 0.0
    test_max_drawdown: float = 0.0
    test_win_rate: float = 0.0

    # Predictions for analysis
    predictions: list[int] = field(default_factory=list)
    actuals: list[int] = field(default_factory=list)
    returns: list[float] = field(default_factory=list)


@dataclass
class WalkForwardResults:
    """Aggregated results from walk-forward validation."""

    symbol: str
    total_folds: int
    folds: list[WalkForwardFold]

    # Aggregated metrics (out-of-sample)
    mean_test_accuracy: float = 0.0
    std_test_accuracy: float = 0.0
    mean_test_sharpe: float = 0.0
    std_test_sharpe: float = 0.0
    mean_test_return: float = 0.0
    total_test_return: float = 0.0
    mean_max_drawdown: float = 0.0
    worst_drawdown: float = 0.0
    mean_win_rate: float = 0.0

    # Regime analysis
    regime_performance: dict[str, dict[str, float]] = field(default_factory=dict)

    # Validation status
    passed_validation: bool = False
    validation_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert results to dictionary for JSON serialization."""
        return {
            "symbol": self.symbol,
            "total_folds": self.total_folds,
            "mean_test_accuracy": self.mean_test_accuracy,
            "std_test_accuracy": self.std_test_accuracy,
            "mean_test_sharpe": self.mean_test_sharpe,
            "std_test_sharpe": self.std_test_sharpe,
            "mean_test_return": self.mean_test_return,
            "total_test_return": self.total_test_return,
            "mean_max_drawdown": self.mean_max_drawdown,
            "worst_drawdown": self.worst_drawdown,
            "mean_win_rate": self.mean_win_rate,
            "passed_validation": self.passed_validation,
            "validation_message": self.validation_message,
            "regime_performance": self.regime_performance,
            "folds": [
                {
                    "fold_number": f.fold_number,
                    "train_period": f"{f.train_start} to {f.train_end}",
                    "test_period": f"{f.test_start} to {f.test_end}",
                    "test_accuracy": f.test_accuracy,
                    "test_sharpe": f.test_sharpe,
                    "test_return": f.test_return,
                    "test_max_drawdown": f.test_max_drawdown,
                }
                for f in self.folds
            ],
        }


class WalkForwardValidator:
    """
    Walk-Forward Validator for LSTM-PPO trading models.

    Implements proper time-series cross-validation to ensure models
    generalize beyond the training period.

    Args:
        train_window: Number of trading days for training (default: 252 = 1 year)
        test_window: Number of trading days for testing (default: 63 = 1 quarter)
        step_size: Number of days to roll forward (default: 21 = 1 month)
        min_train_samples: Minimum samples required for training (default: 200)
        device: PyTorch device (default: "cpu")
    """

    def __init__(
        self,
        train_window: int = 252,
        test_window: int = 63,
        step_size: int = 21,
        min_train_samples: int = 200,
        embargo_pct: float = 0.01,  # AFML Ch. 7: Embargo period as % of data
        device: str = "cpu",
    ):
        self.train_window = train_window
        self.test_window = test_window
        self.step_size = step_size
        self.min_train_samples = min_train_samples
        self.embargo_pct = embargo_pct  # López de Prado recommends 1% embargo
        self.device = torch.device(device)

        # Validation thresholds (from CLAUDE.md: 60% win rate, 1.5 Sharpe, <10% drawdown)
        self.min_win_rate = 0.55  # Slightly below promotion threshold
        self.min_sharpe = 1.0  # Below promotion but still positive
        self.max_drawdown = 0.15  # 15% max drawdown tolerance

        logger.info(
            f"WalkForwardValidator initialized: "
            f"train={train_window}d, test={test_window}d, step={step_size}d, "
            f"embargo={embargo_pct:.1%}"
        )

    def generate_folds(
        self, data_length: int, sequence_length: int = 60
    ) -> list[tuple[tuple[int, int], tuple[int, int], int]]:
        """
        Generate train/test indices for walk-forward validation with embargo.

        Per López de Prado (AFML Ch. 7): Add embargo period between train and test
        to prevent information leakage from labels near the boundary.

        Args:
            data_length: Total number of data points
            sequence_length: LSTM sequence length (need this many points before first prediction)

        Returns:
            List of ((train_start, train_end), (test_start, test_end), embargo_size) tuples
        """
        folds = []

        # Calculate embargo period (typically 1% of total data)
        # Per AFML: T_embargo = pct_embargo * (max(t) - min(t))
        embargo_size = max(1, int(data_length * self.embargo_pct))

        # Account for sequence length in usable data
        usable_start = sequence_length
        usable_length = data_length - sequence_length

        # Need room for train + embargo + test
        min_required = self.train_window + embargo_size + self.test_window
        if usable_length < min_required:
            logger.warning(
                f"Insufficient data for walk-forward with embargo: "
                f"{usable_length} < {min_required} (train={self.train_window}, "
                f"embargo={embargo_size}, test={self.test_window})"
            )
            return folds

        current_start = usable_start

        while current_start + min_required <= data_length:
            train_start = current_start
            train_end = current_start + self.train_window

            # EMBARGO: Gap between train_end and test_start (AFML Ch. 7)
            # This prevents information leakage from overlapping labels
            test_start = train_end + embargo_size
            test_end = min(test_start + self.test_window, data_length)

            folds.append(((train_start, train_end), (test_start, test_end), embargo_size))

            current_start += self.step_size

        logger.info(
            f"Generated {len(folds)} walk-forward folds with {embargo_size}-sample embargo "
            f"(AFML Ch. 7: prevents info leakage at fold boundaries)"
        )
        return folds

    def validate(
        self,
        symbol: str,
        model_class: type,
        model_kwargs: dict[str, Any],
        data_processor,
        epochs: int = 30,
        learning_rate: float = 0.001,
    ) -> WalkForwardResults:
        """
        Run full walk-forward validation for a symbol.

        Args:
            symbol: Stock symbol to validate
            model_class: Model class to instantiate (e.g., LSTMPPO)
            model_kwargs: Kwargs for model initialization
            data_processor: DataProcessor instance for data preparation
            epochs: Training epochs per fold
            learning_rate: Learning rate for optimizer

        Returns:
            WalkForwardResults with aggregated out-of-sample performance
        """
        logger.info(f"Starting walk-forward validation for {symbol}")

        # Fetch and prepare data
        df = data_processor.fetch_data(symbol, period="5y")
        if df.empty:
            return self._empty_results(symbol, "No data available")

        df = data_processor.add_technical_indicators(df)

        # Ensure all feature columns exist
        for col in data_processor.feature_columns:
            if col not in df.columns:
                df[col] = 0.0

        df = data_processor.normalize_data(df)

        # Create targets (1 if next day up, 0 otherwise)
        targets = (df["Close"].shift(-1) > df["Close"]).astype(int).values

        # Store returns for Sharpe calculation
        returns = df["Close"].pct_change().shift(-1).values

        # Create sequences
        X_tensor = data_processor.create_sequences(df)
        if len(X_tensor) == 0:
            return self._empty_results(symbol, "Insufficient data for sequences")

        # Align targets with sequences
        seq_len = data_processor.sequence_length
        valid_len = len(X_tensor)
        y_tensor = torch.LongTensor(targets[seq_len : seq_len + valid_len])
        returns_aligned = returns[seq_len : seq_len + valid_len]

        # Generate folds
        folds_indices = self.generate_folds(len(X_tensor) + seq_len, seq_len)
        if not folds_indices:
            return self._empty_results(symbol, "Insufficient data for validation folds")

        # Run validation for each fold
        fold_results = []

        for fold_num, ((train_start, train_end), (test_start, test_end), embargo_size) in enumerate(
            folds_indices, 1
        ):
            logger.info(
                f"Processing fold {fold_num}/{len(folds_indices)} "
                f"(embargo gap: {embargo_size} samples between train and test)"
            )

            # Adjust indices for sequence offset
            adj_train_start = train_start - seq_len
            adj_train_end = train_end - seq_len
            adj_test_start = test_start - seq_len
            adj_test_end = min(test_end - seq_len, len(X_tensor))

            if adj_train_end <= adj_train_start or adj_test_end <= adj_test_start:
                continue

            # Split data
            X_train = X_tensor[adj_train_start:adj_train_end]
            y_train = y_tensor[adj_train_start:adj_train_end]
            X_test = X_tensor[adj_test_start:adj_test_end]
            y_test = y_tensor[adj_test_start:adj_test_end]
            test_returns = returns_aligned[adj_test_start:adj_test_end]

            if len(X_train) < self.min_train_samples:
                logger.warning(f"Fold {fold_num}: Insufficient training samples")
                continue

            # Train model for this fold
            fold_result = self._train_and_evaluate_fold(
                fold_num=fold_num,
                model_class=model_class,
                model_kwargs=model_kwargs,
                X_train=X_train,
                y_train=y_train,
                X_test=X_test,
                y_test=y_test,
                test_returns=test_returns,
                epochs=epochs,
                learning_rate=learning_rate,
                df=df,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
            )

            fold_results.append(fold_result)

        # Aggregate results
        return self._aggregate_results(symbol, fold_results)

    def _train_and_evaluate_fold(
        self,
        fold_num: int,
        model_class: type,
        model_kwargs: dict[str, Any],
        X_train: torch.Tensor,
        y_train: torch.Tensor,
        X_test: torch.Tensor,
        y_test: torch.Tensor,
        test_returns: np.ndarray,
        epochs: int,
        learning_rate: float,
        df: pd.DataFrame,
        train_start: int,
        train_end: int,
        test_start: int,
        test_end: int,
    ) -> WalkForwardFold:
        """Train model and evaluate on test fold."""

        # Initialize fresh model for this fold (no data leakage)
        model = model_class(**model_kwargs).to(self.device)
        optimizer = optim.Adam(model.parameters(), lr=learning_rate)
        criterion = nn.CrossEntropyLoss()

        # Map binary targets to action indices (0=Hold, 1=Buy, 2=Sell)
        # Up (1) -> Buy (1), Down (0) -> Sell (2)
        y_train_mapped = torch.where(y_train == 1, torch.tensor(1), torch.tensor(2)).to(self.device)

        # Training loop
        best_train_loss = float("inf")
        for _epoch in range(epochs):
            model.train()
            optimizer.zero_grad()

            action_probs, _, _ = model(X_train.to(self.device))
            loss = criterion(action_probs, y_train_mapped)

            loss.backward()
            optimizer.step()

            if loss.item() < best_train_loss:
                best_train_loss = loss.item()

        # Evaluate on test set (OUT OF SAMPLE)
        model.eval()
        with torch.no_grad():
            test_action_probs, _, _ = model(X_test.to(self.device))
            predictions = test_action_probs.argmax(dim=1).cpu().numpy()

            # Map predictions back to binary (Buy=1 -> Up, Sell=2 -> Down, Hold=0 -> Neutral)
            pred_direction = np.where(predictions == 1, 1, np.where(predictions == 2, 0, 0))
            actual_direction = y_test.numpy()

            # Calculate metrics
            accuracy = (pred_direction == actual_direction).mean()

            # Strategy returns: long when predicting up, flat otherwise
            strategy_returns = np.where(pred_direction == 1, test_returns, 0)
            strategy_returns = np.nan_to_num(strategy_returns, nan=0.0)

            # Sharpe ratio (annualized)
            if len(strategy_returns) > 1 and np.std(strategy_returns) > 0:
                sharpe = (np.mean(strategy_returns) / np.std(strategy_returns)) * np.sqrt(252)
            else:
                sharpe = 0.0

            # Total return
            total_return = (1 + strategy_returns).prod() - 1

            # Max drawdown
            cumulative = (1 + strategy_returns).cumprod()
            running_max = np.maximum.accumulate(cumulative)
            drawdown = (cumulative - running_max) / running_max
            max_drawdown = abs(np.min(drawdown)) if len(drawdown) > 0 else 0.0

            # Win rate (profitable predictions)
            profitable = (pred_direction == 1) & (test_returns > 0)
            profitable = profitable | ((pred_direction == 0) & (test_returns <= 0))
            win_rate = profitable.mean()

        # Get date strings
        train_start_date = (
            df.index[train_start].strftime("%Y-%m-%d")
            if hasattr(df.index[train_start], "strftime")
            else str(df.index[train_start])[:10]
        )
        train_end_date = (
            df.index[train_end - 1].strftime("%Y-%m-%d")
            if hasattr(df.index[train_end - 1], "strftime")
            else str(df.index[train_end - 1])[:10]
        )
        test_start_date = (
            df.index[test_start].strftime("%Y-%m-%d")
            if hasattr(df.index[test_start], "strftime")
            else str(df.index[test_start])[:10]
        )
        test_end_date = (
            df.index[min(test_end - 1, len(df) - 1)].strftime("%Y-%m-%d")
            if hasattr(df.index[min(test_end - 1, len(df) - 1)], "strftime")
            else str(df.index[min(test_end - 1, len(df) - 1)])[:10]
        )

        return WalkForwardFold(
            fold_number=fold_num,
            train_start=train_start_date,
            train_end=train_end_date,
            test_start=test_start_date,
            test_end=test_end_date,
            train_size=len(X_train),
            test_size=len(X_test),
            train_loss=best_train_loss,
            test_loss=0.0,  # Not computing test loss for efficiency
            test_accuracy=float(accuracy),
            test_sharpe=float(sharpe),
            test_return=float(total_return),
            test_max_drawdown=float(max_drawdown),
            test_win_rate=float(win_rate),
            predictions=pred_direction.tolist(),
            actuals=actual_direction.tolist(),
            returns=strategy_returns.tolist(),
        )

    def _aggregate_results(
        self, symbol: str, fold_results: list[WalkForwardFold]
    ) -> WalkForwardResults:
        """Aggregate results across all folds."""

        if not fold_results:
            return self._empty_results(symbol, "No valid folds completed")

        # Extract metrics
        accuracies = [f.test_accuracy for f in fold_results]
        sharpes = [f.test_sharpe for f in fold_results]
        returns = [f.test_return for f in fold_results]
        drawdowns = [f.test_max_drawdown for f in fold_results]
        win_rates = [f.test_win_rate for f in fold_results]

        # Calculate aggregates
        mean_accuracy = np.mean(accuracies)
        std_accuracy = np.std(accuracies)
        mean_sharpe = np.mean(sharpes)
        std_sharpe = np.std(sharpes)
        mean_return = np.mean(returns)
        total_return = (np.array(returns) + 1).prod() - 1
        mean_drawdown = np.mean(drawdowns)
        worst_drawdown = np.max(drawdowns)
        mean_win_rate = np.mean(win_rates)

        # Validation check
        passed = (
            mean_win_rate >= self.min_win_rate
            and mean_sharpe >= self.min_sharpe
            and worst_drawdown <= self.max_drawdown
        )

        if passed:
            message = (
                f"PASSED: Win rate {mean_win_rate:.1%} >= {self.min_win_rate:.1%}, "
                f"Sharpe {mean_sharpe:.2f} >= {self.min_sharpe:.2f}, "
                f"Max DD {worst_drawdown:.1%} <= {self.max_drawdown:.1%}"
            )
        else:
            failures = []
            if mean_win_rate < self.min_win_rate:
                failures.append(f"Win rate {mean_win_rate:.1%} < {self.min_win_rate:.1%}")
            if mean_sharpe < self.min_sharpe:
                failures.append(f"Sharpe {mean_sharpe:.2f} < {self.min_sharpe:.2f}")
            if worst_drawdown > self.max_drawdown:
                failures.append(f"Max DD {worst_drawdown:.1%} > {self.max_drawdown:.1%}")
            message = f"FAILED: {'; '.join(failures)}"

        logger.info(f"Walk-forward validation for {symbol}: {message}")

        return WalkForwardResults(
            symbol=symbol,
            total_folds=len(fold_results),
            folds=fold_results,
            mean_test_accuracy=float(mean_accuracy),
            std_test_accuracy=float(std_accuracy),
            mean_test_sharpe=float(mean_sharpe),
            std_test_sharpe=float(std_sharpe),
            mean_test_return=float(mean_return),
            total_test_return=float(total_return),
            mean_max_drawdown=float(mean_drawdown),
            worst_drawdown=float(worst_drawdown),
            mean_win_rate=float(mean_win_rate),
            passed_validation=passed,
            validation_message=message,
        )

    def _empty_results(self, symbol: str, message: str) -> WalkForwardResults:
        """Return empty results with error message."""
        logger.error(f"Walk-forward validation failed for {symbol}: {message}")
        return WalkForwardResults(
            symbol=symbol,
            total_folds=0,
            folds=[],
            passed_validation=False,
            validation_message=f"FAILED: {message}",
        )


def run_walk_forward_validation(
    symbol: str = "SPY",
    train_window: int = 252,
    test_window: int = 63,
    step_size: int = 21,
) -> WalkForwardResults:
    """
    Convenience function to run walk-forward validation.

    Args:
        symbol: Stock symbol to validate
        train_window: Training window in days
        test_window: Test window in days
        step_size: Step size in days

    Returns:
        WalkForwardResults with validation outcomes
    """
    from src.ml.data_processor import DataProcessor
    from src.ml.networks import LSTMPPO

    processor = DataProcessor()
    validator = WalkForwardValidator(
        train_window=train_window,
        test_window=test_window,
        step_size=step_size,
    )

    model_kwargs = {
        "input_dim": len(processor.feature_columns),
        "hidden_dim": 128,
        "num_layers": 2,
    }

    return validator.validate(
        symbol=symbol,
        model_class=LSTMPPO,
        model_kwargs=model_kwargs,
        data_processor=processor,
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("=" * 80)
    print("WALK-FORWARD VALIDATION")
    print("=" * 80)

    results = run_walk_forward_validation("SPY")

    print(f"\nSymbol: {results.symbol}")
    print(f"Total Folds: {results.total_folds}")
    print("\nOut-of-Sample Performance:")
    print(f"  Mean Accuracy: {results.mean_test_accuracy:.1%} (±{results.std_test_accuracy:.1%})")
    print(f"  Mean Sharpe: {results.mean_test_sharpe:.2f} (±{results.std_test_sharpe:.2f})")
    print(f"  Mean Win Rate: {results.mean_win_rate:.1%}")
    print(f"  Total Return: {results.total_test_return:.1%}")
    print(f"  Worst Drawdown: {results.worst_drawdown:.1%}")
    print(f"\nValidation: {results.validation_message}")
