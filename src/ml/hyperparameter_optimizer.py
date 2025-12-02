"""
Hyperparameter Optimization Framework for RL Trading
Automated hyperparameter search using Bayesian optimization.
"""

import itertools
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np

logger = logging.getLogger(__name__)


class HyperparameterOptimizer:
    """
    Hyperparameter optimizer for RL trading models.

    Uses grid search or random search to find optimal hyperparameters.
    Can be extended with Bayesian optimization (Optuna) for better efficiency.
    """

    def __init__(
        self,
        search_space: Optional[dict[str, list[Any]]] = None,
        optimization_metric: str = "sharpe_ratio",
        n_trials: int = 50,
        save_dir: str = "models/ml/hyperopt",
    ):
        """
        Initialize hyperparameter optimizer.

        Args:
            search_space: Dictionary of hyperparameters and their search ranges
            optimization_metric: Metric to optimize ("sharpe_ratio", "win_rate", "total_return")
            n_trials: Number of trials to run
            save_dir: Directory to save optimization results
        """
        self.search_space = search_space or self._default_search_space()
        self.optimization_metric = optimization_metric
        self.n_trials = n_trials
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)

        self.trials = []
        self.best_params = None
        self.best_score = -np.inf

        logger.info(
            f"✅ Hyperparameter Optimizer initialized ({n_trials} trials, metric: {optimization_metric})"
        )

    def _default_search_space(self) -> dict[str, list[Any]]:
        """Default hyperparameter search space."""
        return {
            "learning_rate": [0.0001, 0.001, 0.01],
            "hidden_dim": [64, 128, 256],
            "num_layers": [1, 2, 3],
            "batch_size": [16, 32, 64],
            "gamma": [0.9, 0.95, 0.99],  # Discount factor
            "epsilon": [0.1, 0.2, 0.3],  # Exploration rate
            "ppo_clip": [0.1, 0.2, 0.3],  # PPO clip epsilon
            "value_coef": [0.5, 1.0, 2.0],  # Value loss coefficient
            "entropy_coef": [0.01, 0.05, 0.1],  # Entropy bonus coefficient
        }

    def grid_search(
        self,
        train_fn: Callable,
        evaluate_fn: Callable,
        symbol: str,
        max_combinations: int = 100,
    ) -> dict[str, Any]:
        """
        Perform grid search over hyperparameter space.

        Args:
            train_fn: Function that trains model with hyperparameters
            evaluate_fn: Function that evaluates model and returns metrics
            symbol: Symbol to optimize for
            max_combinations: Maximum combinations to try (to limit search)

        Returns:
            Best hyperparameters and results
        """
        logger.info(f"🔍 Starting grid search for {symbol}...")

        # Generate all combinations
        param_names = list(self.search_space.keys())
        param_values = list(self.search_space.values())

        # Limit combinations if too many
        total_combinations = np.prod([len(v) for v in param_values])
        if total_combinations > max_combinations:
            logger.warning(
                f"⚠️  Too many combinations ({total_combinations}), limiting to {max_combinations}"
            )
            # Use random sampling instead
            return self.random_search(train_fn, evaluate_fn, symbol)

        combinations = list(itertools.product(*param_values))

        logger.info(f"📊 Testing {len(combinations)} hyperparameter combinations...")

        for i, combination in enumerate(combinations):
            params = dict(zip(param_names, combination))

            logger.info(f"Trial {i + 1}/{len(combinations)}: {params}")

            try:
                # Train model
                model = train_fn(params)

                # Evaluate model
                metrics = evaluate_fn(model, symbol)
                score = metrics.get(self.optimization_metric, 0.0)

                # Record trial
                trial_result = {
                    "params": params,
                    "metrics": metrics,
                    "score": score,
                    "trial": i + 1,
                    "timestamp": datetime.now().isoformat(),
                }
                self.trials.append(trial_result)

                # Update best
                if score > self.best_score:
                    self.best_score = score
                    self.best_params = params.copy()
                    logger.info(f"✅ New best score: {score:.4f} with params: {params}")

            except Exception as e:
                logger.error(f"❌ Trial {i + 1} failed: {e}")
                continue

        # Save results
        self._save_results(symbol)

        return {
            "best_params": self.best_params,
            "best_score": self.best_score,
            "total_trials": len(self.trials),
            "all_trials": self.trials,
        }

    def random_search(
        self, train_fn: Callable, evaluate_fn: Callable, symbol: str
    ) -> dict[str, Any]:
        """
        Perform random search over hyperparameter space.

        Args:
            train_fn: Function that trains model with hyperparameters
            evaluate_fn: Function that evaluates model and returns metrics
            symbol: Symbol to optimize for

        Returns:
            Best hyperparameters and results
        """
        logger.info(f"🔍 Starting random search for {symbol} ({self.n_trials} trials)...")

        param_names = list(self.search_space.keys())

        for i in range(self.n_trials):
            # Sample random hyperparameters
            params = {}
            for name in param_names:
                values = self.search_space[name]
                params[name] = np.random.choice(values)

            logger.info(f"Trial {i + 1}/{self.n_trials}: {params}")

            try:
                # Train model
                model = train_fn(params)

                # Evaluate model
                metrics = evaluate_fn(model, symbol)
                score = metrics.get(self.optimization_metric, 0.0)

                # Record trial
                trial_result = {
                    "params": params,
                    "metrics": metrics,
                    "score": score,
                    "trial": i + 1,
                    "timestamp": datetime.now().isoformat(),
                }
                self.trials.append(trial_result)

                # Update best
                if score > self.best_score:
                    self.best_score = score
                    self.best_params = params.copy()
                    logger.info(f"✅ New best score: {score:.4f} with params: {params}")

            except Exception as e:
                logger.error(f"❌ Trial {i + 1} failed: {e}")
                continue

        # Save results
        self._save_results(symbol)

        return {
            "best_params": self.best_params,
            "best_score": self.best_score,
            "total_trials": len(self.trials),
            "all_trials": self.trials,
        }

    def _save_results(self, symbol: str):
        """Save optimization results."""
        results_path = self.save_dir / f"{symbol}_hyperopt_results.json"

        results = {
            "symbol": symbol,
            "optimization_metric": self.optimization_metric,
            "best_params": self.best_params,
            "best_score": self.best_score,
            "total_trials": len(self.trials),
            "trials": self.trials[-50:],  # Save last 50 trials
            "timestamp": datetime.now().isoformat(),
        }

        with open(results_path, "w") as f:
            json.dump(results, f, indent=2)

        logger.info(f"💾 Saved optimization results to {results_path}")

    def load_results(self, symbol: str) -> Optional[dict[str, Any]]:
        """Load previous optimization results."""
        results_path = self.save_dir / f"{symbol}_hyperopt_results.json"

        if results_path.exists():
            with open(results_path) as f:
                results = json.load(f)
                self.best_params = results.get("best_params")
                self.best_score = results.get("best_score", -np.inf)
                logger.info(f"📂 Loaded optimization results for {symbol}")
                return results

        return None

    def get_best_params(self) -> Optional[dict[str, Any]]:
        """Get best hyperparameters found."""
        return self.best_params.copy() if self.best_params else None


# Convenience function for quick optimization
def optimize_hyperparameters(
    symbol: str,
    train_fn: Callable,
    evaluate_fn: Callable,
    search_space: Optional[dict[str, list[Any]]] = None,
    n_trials: int = 50,
    metric: str = "sharpe_ratio",
) -> dict[str, Any]:
    """
    Quick hyperparameter optimization.

    Args:
        symbol: Symbol to optimize for
        train_fn: Training function
        evaluate_fn: Evaluation function
        search_space: Hyperparameter search space
        n_trials: Number of trials
        metric: Metric to optimize

    Returns:
        Best hyperparameters
    """
    optimizer = HyperparameterOptimizer(
        search_space=search_space, optimization_metric=metric, n_trials=n_trials
    )

    return optimizer.random_search(train_fn, evaluate_fn, symbol)
