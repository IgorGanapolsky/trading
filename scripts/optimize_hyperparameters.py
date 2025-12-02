#!/usr/bin/env python3
"""
Hyperparameter Optimization Script for RL Trading Models
Finds optimal hyperparameters for LSTM-PPO models using grid/random search.
"""

import argparse
import logging
import sys
from pathlib import Path

import torch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from src.ml.data_processor import DataProcessor
from src.ml.hyperparameter_optimizer import HyperparameterOptimizer
from src.ml.networks import LSTMPPO
from src.ml.trainer import ModelTrainer

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def train_model_with_params(params: dict, symbol: str) -> LSTMPPO:
    """
    Train model with given hyperparameters.

    Args:
        params: Hyperparameter dictionary
        symbol: Symbol to train on

    Returns:
        Trained model
    """
    # Create trainer with custom hyperparameters
    trainer = ModelTrainer(device="cpu")

    # Override hyperparameters
    trainer.hidden_dim = params.get("hidden_dim", 128)
    trainer.num_layers = params.get("num_layers", 2)
    trainer.learning_rate = params.get("learning_rate", 0.001)
    trainer.batch_size = params.get("batch_size", 32)

    # Train model
    result = trainer.train_supervised(symbol, use_cloud_rl=False)

    if not result.get("success"):
        raise ValueError(f"Training failed: {result.get('error')}")

    # Load trained model
    model = trainer.load_model(symbol)
    return model


def evaluate_model(model: LSTMPPO, symbol: str) -> dict:
    """
    Evaluate model and return metrics.

    Args:
        model: Trained model
        symbol: Symbol to evaluate on

    Returns:
        Dictionary with metrics (sharpe_ratio, win_rate, total_return)
    """
    # For now, use simple evaluation based on validation loss
    # In production, this would use backtesting or walk-forward analysis

    ModelTrainer(device="cpu")
    data_processor = DataProcessor()

    # Fetch and prepare data
    df = data_processor.fetch_data(symbol, period="2y")
    if df.empty:
        return {"sharpe_ratio": -1.0, "win_rate": 0.0, "total_return": -1.0}

    df = data_processor.add_technical_indicators(df)
    df = data_processor.normalize_data(df)

    # Create sequences
    X_tensor = data_processor.create_sequences(df)
    targets = (df["Returns"].shift(-1) > 0).astype(int).values
    y_tensor = torch.LongTensor(
        targets[data_processor.sequence_length : data_processor.sequence_length + len(X_tensor)]
    )

    # Split for validation
    val_size = int(0.2 * len(X_tensor))
    X_val = X_tensor[-val_size:]
    y_val = y_tensor[-val_size:]

    # Evaluate
    model.eval()
    with torch.no_grad():
        action_probs, _, _ = model(X_val)
        predictions = torch.argmax(action_probs, dim=-1)

        # Calculate metrics
        correct = (predictions == y_val).float()
        win_rate = correct.mean().item()

        # Simple Sharpe approximation (would need actual returns for real Sharpe)
        # For now, use win rate as proxy
        sharpe_ratio = (win_rate - 0.5) * 2.0  # Normalize to [-1, 1] range, then scale

    return {
        "sharpe_ratio": sharpe_ratio,
        "win_rate": win_rate,
        "total_return": win_rate - 0.5,  # Simple proxy
    }


def main():
    parser = argparse.ArgumentParser(description="Optimize hyperparameters for RL trading models")
    parser.add_argument(
        "--symbol",
        type=str,
        default="SPY",
        help="Symbol to optimize for (default: SPY)",
    )
    parser.add_argument("--n-trials", type=int, default=20, help="Number of trials (default: 20)")
    parser.add_argument(
        "--metric",
        type=str,
        default="sharpe_ratio",
        choices=["sharpe_ratio", "win_rate", "total_return"],
        help="Metric to optimize (default: sharpe_ratio)",
    )
    parser.add_argument(
        "--method",
        type=str,
        default="random",
        choices=["random", "grid"],
        help="Search method (default: random)",
    )

    args = parser.parse_args()

    print("=" * 70)
    print("HYPERPARAMETER OPTIMIZATION")
    print("=" * 70)
    print(f"Symbol: {args.symbol}")
    print(f"Trials: {args.n_trials}")
    print(f"Metric: {args.metric}")
    print(f"Method: {args.method}")
    print("=" * 70)
    print()

    # Initialize optimizer
    optimizer = HyperparameterOptimizer(optimization_metric=args.metric, n_trials=args.n_trials)

    # Run optimization
    if args.method == "random":
        results = optimizer.random_search(
            train_fn=lambda params: train_model_with_params(params, args.symbol),
            evaluate_fn=evaluate_model,
            symbol=args.symbol,
        )
    else:
        results = optimizer.grid_search(
            train_fn=lambda params: train_model_with_params(params, args.symbol),
            evaluate_fn=evaluate_model,
            symbol=args.symbol,
        )

    # Print results
    print("\n" + "=" * 70)
    print("OPTIMIZATION RESULTS")
    print("=" * 70)
    print(f"Best {args.metric}: {results['best_score']:.4f}")
    print("\nBest Hyperparameters:")
    for key, value in results["best_params"].items():
        print(f"  {key}: {value}")
    print(f"\nTotal trials: {results['total_trials']}")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
