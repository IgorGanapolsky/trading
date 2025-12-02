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
    parser.add_argument("--epochs", type=int, default=5, help="Number of training epochs.")
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


def train_model(
    X: np.ndarray,
    y: np.ndarray,
    *,
    context_window: int,
    epochs: int,
    batch_size: int,
    lr: float,
) -> RLTransformerModel:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    dataset = TensorDataset(
        torch.from_numpy(X).float(),
        torch.from_numpy(y).float(),
    )
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    model = RLTransformerModel(feature_dim=X.shape[2], context_window=context_window).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.BCEWithLogitsLoss()

    for epoch in range(1, epochs + 1):
        epoch_loss = 0.0
        correct = 0
        total = 0
        model.train()
        for batch_x, batch_y in loader:
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

        avg_loss = epoch_loss / len(dataset)
        accuracy = correct / max(total, 1)
        print(f"[Epoch {epoch}/{epochs}] loss={avg_loss:.4f} acc={accuracy:.3f}")

    return model.cpu()


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

    model = train_model(
        X,
        y,
        context_window=args.context_window,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.learning_rate,
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
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    dataset_path = Path(args.dataset_cache)
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(dataset_path, sequences=X, labels=y, metadata=json.dumps(metadata))
    print(f"📦 Cached dataset to {dataset_path}")


if __name__ == "__main__":
    main()
