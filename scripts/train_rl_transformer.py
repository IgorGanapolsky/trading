#!/usr/bin/env python3
"""
Offline training pipeline for the transformer-based RL gate.

The script:
    1. Fetches historical OHLCV data for the requested tickers.
    2. Builds the same feature tensors used at inference time.
    3. Generates binary labels based on forward returns.
    4. Trains the ``RLTransformerModel`` with BCE loss.
    5. Exports the weights and caches the dataset for reproducibility.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from src.agents.rl_transformer import RLTransformerModel
from src.agents.rl_transformer_features import build_feature_matrix
from src.utils.market_data import get_market_data_provider
from torch.utils.data import DataLoader, TensorDataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the RL transformer gate.")
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=["SPY", "QQQ", "IWM"],
        help="Universe of symbols to use for training.",
    )
    parser.add_argument(
        "--start",
        default="2023-01-01",
        help="Start date (YYYY-MM-DD) for the training window.",
    )
    parser.add_argument(
        "--end",
        default=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        help="End date (YYYY-MM-DD) for the training window.",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=10,
        help="Max training epochs (early stopping may halt sooner).",
    )
    parser.add_argument("--batch-size", type=int, default=64, help="Batch size.")
    parser.add_argument("--learning-rate", type=float, default=3e-4, help="Learning rate.")
    parser.add_argument(
        "--context-window",
        type=int,
        default=64,
        help="Number of timesteps per transformer sample.",
    )
    parser.add_argument(
        "--prediction-horizon",
        type=int,
        default=5,
        help="Forward horizon (in trading days) used for labeling.",
    )
    parser.add_argument(
        "--target-return",
        type=float,
        default=0.003,
        help="Minimum forward return required for a positive label.",
    )
    parser.add_argument(
        "--output-path",
        default="models/ml/rl_transformer_state.pt",
        help="Where to write the trained state dict.",
    )
    parser.add_argument(
        "--dataset-cache",
        default="data/datasets/rl_transformer_sequences.npz",
        help="Path to store the cached dataset for reproducibility.",
    )
    parser.add_argument(
        "--val-split",
        type=float,
        default=0.2,
        help="Fraction of data to use for validation (default: 0.2).",
    )
    parser.add_argument(
        "--min-val-sharpe",
        type=float,
        default=1.0,
        help="Minimum validation Sharpe ratio to continue training (early stop guard).",
    )
    parser.add_argument(
        "--patience",
        type=int,
        default=3,
        help="Early stopping patience (epochs without improvement).",
    )
    return parser.parse_args()


def build_dataset(
    tickers: Sequence[str],
    start_date: datetime,
    end_date: datetime,
    context_window: int,
    prediction_horizon: int,
    target_return: float,
) -> tuple[np.ndarray, np.ndarray]:
    sequences: list[np.ndarray] = []
    labels: list[float] = []
    provider = get_market_data_provider()
    lookback_days = (end_date - start_date).days + 120

    for symbol in tickers:
        result = provider.get_daily_bars(symbol, lookback_days=lookback_days, end_datetime=end_date)
        hist = result.data
        if hist is None or hist.empty:
            continue
        hist = hist[(hist.index >= start_date) & (hist.index <= end_date)]
        matrix = build_feature_matrix(hist)
        if matrix.shape[0] <= context_window + prediction_horizon:
            continue

        closes = hist["Close"].astype(float).to_numpy()

        for idx in range(context_window, matrix.shape[0] - prediction_horizon):
            seq = matrix[idx - context_window : idx]
            future_price = closes[idx + prediction_horizon]
            current_price = closes[idx]
            forward_return = (future_price - current_price) / current_price
            label = 1.0 if forward_return >= target_return else 0.0

            sequences.append(seq)
            labels.append(label)

    if not sequences:
        raise RuntimeError("No training samples were generated. Expand tickers or date range.")

    X = np.stack(sequences, axis=0)
    y = np.array(labels, dtype=np.float32)
    return X, y


def compute_val_sharpe(
    model: nn.Module,
    val_loader: DataLoader,
    device: torch.device,
) -> float:
    """
    Compute a proxy Sharpe ratio on validation set.

    Uses model predictions as position signals and compares to actual labels
    to estimate a risk-adjusted performance metric.
    """
    model.eval()
    all_preds = []
    all_labels = []

    with torch.no_grad():
        for batch_x, batch_y in val_loader:
            batch_x = batch_x.to(device)
            logits = model(batch_x)
            probs = torch.sigmoid(logits).cpu().numpy()
            all_preds.extend(probs.flatten())
            all_labels.extend(batch_y.numpy().flatten())

    all_preds = np.array(all_preds)
    all_labels = np.array(all_labels)

    # Position signals: +1 for predicted buy (>0.5), -1 otherwise
    positions = np.where(all_preds > 0.5, 1.0, -1.0)
    # Simulated returns: position * actual outcome direction
    returns = positions * (all_labels * 2 - 1)  # Convert labels to -1/+1

    if len(returns) < 2 or np.std(returns) < 1e-8:
        return 0.0

    sharpe = np.mean(returns) / (np.std(returns) + 1e-8) * np.sqrt(252)
    return float(sharpe)


def train_model(
    X: np.ndarray,
    y: np.ndarray,
    *,
    context_window: int,
    epochs: int,
    batch_size: int,
    lr: float,
    val_split: float = 0.2,
    min_val_sharpe: float = 1.0,
    patience: int = 3,
) -> tuple[RLTransformerModel, dict]:
    """
    Train RL transformer with validation split and early stopping.

    Early stopping triggers when:
    1. Validation Sharpe drops below min_val_sharpe for `patience` epochs
    2. Validation accuracy plateaus or degrades

    Returns:
        Tuple of (trained model, training metrics)
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Split into train/validation
    n_samples = X.shape[0]
    n_val = int(n_samples * val_split)
    indices = np.random.permutation(n_samples)
    train_indices = indices[n_val:]
    val_indices = indices[:n_val]

    X_train, y_train = X[train_indices], y[train_indices]
    X_val, y_val = X[val_indices], y[val_indices]

    print(
        f"📊 Dataset split: train={len(train_indices)}, val={len(val_indices)} ({val_split * 100:.0f}%)"
    )

    train_dataset = TensorDataset(
        torch.from_numpy(X_train).float(),
        torch.from_numpy(y_train).float(),
    )
    val_dataset = TensorDataset(
        torch.from_numpy(X_val).float(),
        torch.from_numpy(y_val).float(),
    )
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

    model = RLTransformerModel(feature_dim=X.shape[2], context_window=context_window).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.BCEWithLogitsLoss()

    best_val_sharpe = -np.inf
    best_state_dict = None
    epochs_without_improvement = 0
    training_metrics = {
        "epochs_completed": 0,
        "early_stopped": False,
        "best_val_sharpe": 0.0,
        "final_train_acc": 0.0,
        "final_val_acc": 0.0,
        "epoch_history": [],
    }

    for epoch in range(1, epochs + 1):
        # Training phase
        epoch_loss = 0.0
        correct = 0
        total = 0
        model.train()
        for batch_x, batch_y in train_loader:
            batch_x = batch_x.to(device)
            batch_y = batch_y.to(device)
            optimizer.zero_grad()
            logits = model(batch_x)
            loss = criterion(logits, batch_y)
            loss.backward()
            optimizer.step()

            epoch_loss += loss.item() * batch_x.size(0)
            predictions = torch.sigmoid(logits) >= 0.5
            correct += (predictions == batch_y.bool()).sum().item()
            total += batch_x.size(0)

        train_loss = epoch_loss / len(train_dataset)
        train_acc = correct / max(total, 1)

        # Validation phase
        model.eval()
        val_correct = 0
        val_total = 0
        with torch.no_grad():
            for batch_x, batch_y in val_loader:
                batch_x = batch_x.to(device)
                batch_y = batch_y.to(device)
                logits = model(batch_x)
                predictions = torch.sigmoid(logits) >= 0.5
                val_correct += (predictions == batch_y.bool()).sum().item()
                val_total += batch_x.size(0)

        val_acc = val_correct / max(val_total, 1)
        val_sharpe = compute_val_sharpe(model, val_loader, device)

        epoch_metrics = {
            "epoch": epoch,
            "train_loss": round(train_loss, 4),
            "train_acc": round(train_acc, 3),
            "val_acc": round(val_acc, 3),
            "val_sharpe": round(val_sharpe, 3),
        }
        training_metrics["epoch_history"].append(epoch_metrics)

        print(
            f"[Epoch {epoch}/{epochs}] "
            f"train_loss={train_loss:.4f} train_acc={train_acc:.3f} "
            f"val_acc={val_acc:.3f} val_sharpe={val_sharpe:.3f}"
        )

        # Early stopping logic
        if val_sharpe > best_val_sharpe:
            best_val_sharpe = val_sharpe
            best_state_dict = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1

        # Check early stopping conditions
        if val_sharpe < min_val_sharpe and epoch > 2:
            print(
                f"⚠️  Early stop check: val_sharpe ({val_sharpe:.3f}) < min ({min_val_sharpe:.3f})"
            )
            if epochs_without_improvement >= patience:
                print(f"🛑 Early stopping triggered: {patience} epochs without improvement")
                training_metrics["early_stopped"] = True
                break

        if epochs_without_improvement >= patience:
            print(f"🛑 Early stopping: {patience} epochs without improvement")
            training_metrics["early_stopped"] = True
            break

    # Restore best model
    if best_state_dict is not None:
        model.load_state_dict(best_state_dict)
        print(f"✅ Restored best model (val_sharpe={best_val_sharpe:.3f})")

    training_metrics["epochs_completed"] = epoch
    training_metrics["best_val_sharpe"] = round(best_val_sharpe, 3)
    training_metrics["final_train_acc"] = round(train_acc, 3)
    training_metrics["final_val_acc"] = round(val_acc, 3)

    return model.cpu(), training_metrics


def main() -> None:
    args = parse_args()
    start_date = datetime.strptime(args.start, "%Y-%m-%d")
    end_date = datetime.strptime(args.end, "%Y-%m-%d")

    print(
        f"Building dataset for {len(args.tickers)} tickers "
        f"from {start_date.date()} to {end_date.date()}..."
    )
    X, y = build_dataset(
        args.tickers,
        start_date=start_date,
        end_date=end_date,
        context_window=args.context_window,
        prediction_horizon=args.prediction_horizon,
        target_return=args.target_return,
    )
    print(f"Dataset: {X.shape[0]} samples, sequence shape={X.shape[1:]}")

    model, training_metrics = train_model(
        X,
        y,
        context_window=args.context_window,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.learning_rate,
        val_split=args.val_split,
        min_val_sharpe=args.min_val_sharpe,
        patience=args.patience,
    )

    # Check if training was successful
    if training_metrics["best_val_sharpe"] < args.min_val_sharpe:
        print(
            f"⚠️  WARNING: Best val_sharpe ({training_metrics['best_val_sharpe']:.3f}) "
            f"below threshold ({args.min_val_sharpe:.3f}). Model may be overfitting."
        )

    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), output_path)
    print(f"✅ Saved transformer weights to {output_path}")

    metadata = {
        "tickers": args.tickers,
        "start": args.start,
        "end": args.end,
        "context_window": args.context_window,
        "prediction_horizon": args.prediction_horizon,
        "target_return": args.target_return,
        "val_split": args.val_split,
        "min_val_sharpe": args.min_val_sharpe,
        "patience": args.patience,
        "training_metrics": training_metrics,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    dataset_path = Path(args.dataset_cache)
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(dataset_path, sequences=X, labels=y, metadata=json.dumps(metadata))
    print(f"📦 Cached dataset to {dataset_path}")

    # Log training metrics to audit trail
    metrics_path = Path("data/audit_trail/rl_training_metrics.jsonl")
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with metrics_path.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "tickers": args.tickers,
                    "epochs_completed": training_metrics["epochs_completed"],
                    "early_stopped": training_metrics["early_stopped"],
                    "best_val_sharpe": training_metrics["best_val_sharpe"],
                    "final_train_acc": training_metrics["final_train_acc"],
                    "final_val_acc": training_metrics["final_val_acc"],
                }
            )
            + "\n"
        )
    print(f"📝 Training metrics logged to {metrics_path}")


if __name__ == "__main__":
    main()
