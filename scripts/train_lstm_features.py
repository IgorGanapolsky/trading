#!/usr/bin/env python3
"""
Train LSTM Feature Extractor for Deep Learning Trading Models

This script trains the LSTM feature extractor on historical market data
to learn temporal patterns for the PPO reinforcement learning agent.

Usage:
    python scripts/train_lstm_features.py --symbols SPY,QQQ,VOO --epochs 50

Based on:
- RL_TRADING_STRATEGY_GUIDE.md (LSTM-PPO ensemble architecture)
- Elite AI Trader Gap Analysis (Phase 1)
"""

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.lstm_feature_extractor import (
    LSTMPPOWrapper,
    LSTMTradingFeatureExtractor,
    MarketDataDataset,
)
from src.utils.data_collector import DataCollector
from src.utils.technical_indicators import calculate_all_features

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def prepare_training_data(
    hist_data: pd.DataFrame,
    seq_length: int = 60,
    prediction_horizon: int = 5,
    min_window_size: int = 200,  # Minimum data needed for feature calculation
) -> tuple:
    """
    Prepare sequences for LSTM training with proper sliding windows.

    Creates sequences where each sequence contains multiple timesteps,
    each timestep having a feature vector. This is the correct format for LSTM.

    Args:
        hist_data: Historical OHLCV DataFrame
        seq_length: Length of input sequences (number of timesteps)
        prediction_horizon: Days ahead to predict (for supervised learning)
        min_window_size: Minimum data needed for technical indicators

    Returns:
        Tuple of (sequences, labels) where:
        - sequences: (n_samples, seq_length, n_features) - proper 3D array
        - labels: (n_samples,) - future returns
    """
    sequences = []
    labels = []

    close_prices = hist_data["Close"].values

    # Need enough data to calculate features for each timestep in sequence
    # Each timestep needs min_window_size bars to calculate indicators
    start_idx = min_window_size
    end_idx = len(hist_data) - prediction_horizon

    logger.info(
        f"Preparing sequences: {end_idx - start_idx - seq_length} samples from {len(hist_data)} bars"
    )

    # Create sliding window sequences
    for i in range(start_idx, end_idx - seq_length + 1):
        # Extract sequence: seq_length timesteps
        sequence_features = []

        # For each timestep in the sequence, calculate features using a rolling window
        for t in range(i - seq_length, i):
            # Use a window ending at timestep t for feature calculation
            # Need at least min_window_size bars before t
            window_start = max(0, t - min_window_size)
            window_data = hist_data.iloc[window_start : t + 1]

            if len(window_data) < 50:  # Minimum for basic indicators
                # Skip this sequence if not enough data
                break

            # Calculate features for this timestep
            features = calculate_all_features(window_data)
            feature_array = _features_to_array(features)
            sequence_features.append(feature_array)

        # Only add sequence if we got all timesteps
        if len(sequence_features) == seq_length:
            sequences.append(sequence_features)

            # Label: future return (for supervised learning)
            future_return = (close_prices[i + prediction_horizon] - close_prices[i]) / close_prices[
                i
            ]
            labels.append(future_return)

    if not sequences:
        logger.warning("No sequences created from historical data")
        return np.array([]), np.array([])

    # Convert to numpy array: (n_samples, seq_length, n_features)
    sequences = np.array(sequences)
    labels = np.array(labels)

    logger.info(f"Created {len(sequences)} sequences")
    logger.info(f"Sequence shape: {sequences.shape} (samples, timesteps, features)")
    logger.info(f"Labels shape: {labels.shape}")

    return sequences, labels


def _features_to_array(features: dict[str, float]) -> np.ndarray:
    """Convert features dict to array in consistent order."""
    feature_order = [
        "close",
        "open",
        "high",
        "low",
        "return_1d",
        "return_5d",
        "return_20d",
        "volatility_20d",
        "ma_20",
        "ma_50",
        "ma_200",
        "price_vs_ma20",
        "price_vs_ma50",
        "price_vs_ma200",
        "macd",
        "macd_signal",
        "macd_histogram",
        "adx",
        "plus_di",
        "minus_di",
        "rsi",
        "roc_10",
        "roc_20",
        "bb_upper",
        "bb_middle",
        "bb_lower",
        "bb_width",
        "bb_position",
        "atr",
        "atr_pct",
        "volume",
        "volume_ratio",
        "obv",
        "obv_ma",
        "volume_roc",
    ]

    array = np.array([features.get(key, 0.0) for key in feature_order])

    # Normalize
    array = (array - array.mean()) / (array.std() + 1e-8)

    return array


def train_lstm_model(
    sequences: np.ndarray,
    labels: np.ndarray,
    epochs: int = 50,
    batch_size: int = 32,
    learning_rate: float = 0.001,
    device: str = "cpu",
) -> LSTMTradingFeatureExtractor:
    """
    Train LSTM feature extractor.

    Args:
        sequences: Training sequences (n_samples, seq_length, n_features)
        labels: Training labels (n_samples,)
        epochs: Number of training epochs
        batch_size: Batch size
        learning_rate: Learning rate
        device: Device to train on

    Returns:
        Trained LSTM model
    """
    if len(sequences) == 0:
        raise ValueError("No training sequences provided")

    device = torch.device(device)

    # Verify sequence shape: should be (n_samples, seq_length, n_features)
    if len(sequences.shape) != 3:
        raise ValueError(
            f"Expected 3D sequences (n_samples, seq_length, n_features), "
            f"got shape {sequences.shape}"
        )

    n_samples, seq_length, input_dim = sequences.shape

    logger.info(f"Training LSTM on {n_samples} sequences")
    logger.info(f"Sequence length: {seq_length} timesteps")
    logger.info(f"Features per timestep: {input_dim}")

    logger.info(f"Training LSTM: input_dim={input_dim}, seq_length={seq_length}")

    # Create dataset
    dataset = MarketDataDataset(sequences, labels)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    # Initialize model
    model = LSTMTradingFeatureExtractor(
        input_dim=input_dim, hidden_dim=128, num_layers=2, output_dim=50, dropout=0.2
    ).to(device)

    # Loss and optimizer
    criterion = nn.MSELoss()  # Predict future returns
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)

    # Training loop
    model.train()
    for epoch in range(epochs):
        total_loss = 0.0
        n_batches = 0

        for batch_sequences, batch_labels in dataloader:
            batch_sequences = batch_sequences.to(device)
            batch_labels = batch_labels.to(device)

            # Forward pass
            features = model(batch_sequences)

            # Predict future return (simple linear projection)
            predictions = features.mean(dim=1)  # Average features as prediction

            # Calculate loss
            loss = criterion(predictions, batch_labels)

            # Backward pass
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            total_loss += loss.item()
            n_batches += 1

        avg_loss = total_loss / n_batches if n_batches > 0 else 0.0

        if (epoch + 1) % 10 == 0:
            logger.info(f"Epoch {epoch + 1}/{epochs}, Loss: {avg_loss:.6f}")

    model.eval()
    logger.info("Training complete")

    return model


def main():
    """Main training script."""
    parser = argparse.ArgumentParser(description="Train LSTM feature extractor")
    parser.add_argument(
        "--symbols",
        type=str,
        default="SPY,QQQ,VOO",
        help="Comma-separated list of symbols (default: SPY,QQQ,VOO)",
    )
    parser.add_argument(
        "--epochs", type=int, default=50, help="Number of training epochs (default: 50)"
    )
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size (default: 32)")
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=0.001,
        help="Learning rate (default: 0.001)",
    )
    parser.add_argument("--seq-length", type=int, default=60, help="Sequence length (default: 60)")
    parser.add_argument(
        "--output",
        type=str,
        default="data/models/lstm_feature_extractor.pt",
        help="Output model path",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        choices=["cpu", "cuda"],
        help="Device to train on (default: cpu)",
    )

    args = parser.parse_args()

    print("=" * 70)
    print("LSTM Feature Extractor Training")
    print("=" * 70)
    print(f"Symbols: {args.symbols}")
    print(f"Epochs: {args.epochs}")
    print(f"Device: {args.device}")
    print("=" * 70)

    # Load historical data
    symbols = [s.strip() for s in args.symbols.split(",")]
    collector = DataCollector(data_dir="data/historical")

    all_sequences = []
    all_labels = []

    for symbol in symbols:
        logger.info(f"Loading data for {symbol}...")
        hist_data = collector.load_historical_data(symbol)

        if hist_data.empty:
            logger.warning(f"No historical data for {symbol}, skipping")
            continue

        if len(hist_data) < args.seq_length + 10:
            logger.warning(f"Insufficient data for {symbol} ({len(hist_data)} bars), skipping")
            continue

        # Prepare training data
        sequences, labels = prepare_training_data(
            hist_data, seq_length=args.seq_length, prediction_horizon=5
        )

        if len(sequences) > 0:
            all_sequences.append(sequences)
            all_labels.append(labels)
            logger.info(f"{symbol}: {len(sequences)} sequences")

    if not all_sequences:
        logger.error("No training data available. Run populate_historical_data.py first.")
        sys.exit(1)

    # Combine all symbols
    combined_sequences = np.concatenate(all_sequences, axis=0)
    combined_labels = np.concatenate(all_labels, axis=0)

    logger.info(f"Total training samples: {len(combined_sequences)}")

    # Train model
    logger.info("Starting training...")
    model = train_lstm_model(
        combined_sequences,
        combined_labels,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        device=args.device,
    )

    # Save model
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    wrapper = LSTMPPOWrapper()
    wrapper.feature_extractor = model
    wrapper.save_model(args.output)

    print(f"\n✅ Model saved to: {args.output}")
    print("Next steps:")
    print("1. Integrate with OptimizedRLPolicyLearner")
    print("2. Test on live market data")
    print("3. A/B test against current strategy")


if __name__ == "__main__":
    main()
