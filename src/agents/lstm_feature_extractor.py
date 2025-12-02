"""
LSTM Feature Extractor for Deep Learning Trading Models

This module implements the LSTM feature extraction layer as specified in
the Elite AI Trader roadmap (Phase 1). The LSTM processes time-series
market data to extract temporal patterns for the PPO reinforcement learning agent.

Architecture:
- Input: Historical OHLCV data (60+ timesteps)
- LSTM Layer: Extracts temporal features
- Output: Feature vector (50 dimensions) for RL state space

Based on:
- RL_TRADING_STRATEGY_GUIDE.md (LSTM-PPO ensemble)
- Elite AI Trader Gap Analysis (Phase 1)
"""

import logging
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from src.utils.technical_indicators import calculate_all_features
from torch.utils.data import Dataset

logger = logging.getLogger(__name__)


class MarketDataDataset(Dataset):
    """PyTorch Dataset for market data sequences."""

    def __init__(self, sequences: np.ndarray, labels: Optional[np.ndarray] = None):
        """
        Initialize dataset.

        Args:
            sequences: Array of shape (n_samples, seq_length, n_features)
            labels: Optional labels for supervised learning
        """
        self.sequences = torch.FloatTensor(sequences)
        self.labels = torch.FloatTensor(labels) if labels is not None else None

    def __len__(self):
        return len(self.sequences)

    def __getitem__(self, idx):
        if self.labels is not None:
            return self.sequences[idx], self.labels[idx]
        return self.sequences[idx]


class LSTMTradingFeatureExtractor(nn.Module):
    """
    LSTM-based feature extractor for trading signals.

    Architecture:
    - Input: (batch_size, seq_length, n_features)
    - LSTM: Hidden size 128, 2 layers
    - Output: (batch_size, feature_dim) - 50-dimensional feature vector
    """

    def __init__(
        self,
        input_dim: int = 50,  # Number of features per timestep
        hidden_dim: int = 128,
        num_layers: int = 2,
        output_dim: int = 50,  # Output feature dimension for RL
        dropout: float = 0.2,
    ):
        """
        Initialize LSTM feature extractor.

        Args:
            input_dim: Number of input features per timestep
            hidden_dim: LSTM hidden dimension
            num_layers: Number of LSTM layers
            output_dim: Output feature dimension
            dropout: Dropout rate
        """
        super().__init__()

        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.output_dim = output_dim

        # LSTM layers
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0,
            batch_first=True,
        )

        # Output projection layer
        self.fc = nn.Linear(hidden_dim, output_dim)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass through LSTM.

        Args:
            x: Input tensor of shape (batch_size, seq_length, input_dim)

        Returns:
            Feature vector of shape (batch_size, output_dim)
        """
        # LSTM forward pass
        lstm_out, (hidden, cell) = self.lstm(x)

        # Use last hidden state (from final timestep)
        last_hidden = hidden[-1]  # Shape: (batch_size, hidden_dim)

        # Project to output dimension
        features = self.fc(self.dropout(last_hidden))

        return features

    def extract_features(self, hist_data: pd.DataFrame, seq_length: int = 60) -> np.ndarray:
        """
        Extract features from historical data.

        Args:
            hist_data: Historical OHLCV DataFrame
            seq_length: Sequence length for LSTM (default: 60)

        Returns:
            Feature vector (output_dim,)
        """
        self.eval()  # Set to evaluation mode

        # Calculate features for each timestep
        sequences = []
        for i in range(seq_length, len(hist_data)):
            window = hist_data.iloc[i - seq_length : i]
            features = calculate_all_features(window)

            # Convert to array (ensure consistent feature order)
            feature_array = self._features_to_array(features)
            sequences.append(feature_array)

        if not sequences:
            logger.warning("No sequences extracted from historical data")
            return np.zeros(self.output_dim)

        # Use most recent sequence
        sequence = np.array(sequences[-1:])  # Shape: (1, seq_length, input_dim)

        # Convert to tensor and extract features
        with torch.no_grad():
            x = torch.FloatTensor(sequence)
            features = self.forward(x)
            return features.numpy().flatten()

    def _features_to_array(self, features: dict[str, float]) -> np.ndarray:
        """Convert features dict to array in consistent order."""
        # Define feature order (must match input_dim)
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

        # Pad with zeros if features missing
        array = np.array([features.get(key, 0.0) for key in feature_order])

        # Normalize features (simple min-max normalization)
        # In production, use pre-computed normalization parameters
        array = (array - array.mean()) / (array.std() + 1e-8)

        return array


class LSTMPPOWrapper:
    """
    Wrapper that integrates LSTM feature extractor with existing PPO RL framework.

    This allows the OptimizedRLPolicyLearner to use deep learning features
    instead of discrete state keys.
    """

    def __init__(self, model_path: Optional[str] = None, device: str = "cpu"):
        """
        Initialize LSTM-PPO wrapper.

        Args:
            model_path: Path to saved LSTM model (optional)
            device: Device to run on ('cpu' or 'cuda')
        """
        self.device = torch.device(device)
        self.feature_extractor = LSTMTradingFeatureExtractor().to(self.device)

        if model_path and Path(model_path).exists():
            self.load_model(model_path)
        else:
            logger.info("LSTM feature extractor initialized with random weights")
            logger.info("Train the model before using for production")

    def extract_state_features(self, hist_data: pd.DataFrame, symbol: str = "") -> dict[str, Any]:
        """
        Extract deep learning features from historical data.

        Args:
            hist_data: Historical OHLCV DataFrame
            symbol: Symbol name (for logging)

        Returns:
            Dictionary with 'features' array and metadata
        """
        try:
            features = self.feature_extractor.extract_features(hist_data)

            return {
                "features": features.tolist(),
                "feature_dim": len(features),
                "extraction_method": "lstm",
                "symbol": symbol,
            }
        except Exception as e:
            logger.error(f"Error extracting LSTM features for {symbol}: {e}")
            # Fallback to basic features
            basic_features = calculate_all_features(hist_data, symbol)
            return {
                "features": list(basic_features.values()),
                "feature_dim": len(basic_features),
                "extraction_method": "basic",
                "symbol": symbol,
                "error": str(e),
            }

    def save_model(self, path: str):
        """Save LSTM model to disk."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "model_state_dict": self.feature_extractor.state_dict(),
                "input_dim": self.feature_extractor.input_dim,
                "hidden_dim": self.feature_extractor.hidden_dim,
                "num_layers": self.feature_extractor.num_layers,
                "output_dim": self.feature_extractor.output_dim,
            },
            path,
        )
        logger.info(f"LSTM model saved to {path}")

    def load_model(self, path: str):
        """Load LSTM model from disk."""
        checkpoint = torch.load(path, map_location=self.device)
        self.feature_extractor.load_state_dict(checkpoint["model_state_dict"])
        self.feature_extractor.eval()
        logger.info(f"LSTM model loaded from {path}")


def create_lstm_ppo_integration(
    rl_learner, hist_data: pd.DataFrame, symbol: str = ""
) -> dict[str, Any]:
    """
    Integrate LSTM features with existing RL learner.

    This function bridges the gap between the new LSTM feature extractor
    and the existing OptimizedRLPolicyLearner.

    Args:
        rl_learner: OptimizedRLPolicyLearner instance
        hist_data: Historical OHLCV DataFrame
        symbol: Symbol name

    Returns:
        Enhanced market state with LSTM features
    """
    # Initialize LSTM wrapper
    lstm_wrapper = LSTMPPOWrapper()

    # Extract deep learning features
    lstm_features = lstm_wrapper.extract_state_features(hist_data, symbol)

    # Create enhanced market state
    # Note: This requires modifying OptimizedRLPolicyLearner to accept
    # continuous features instead of discrete state keys
    enhanced_state = {
        "lstm_features": lstm_features["features"],
        "feature_extraction_method": lstm_features["extraction_method"],
        "symbol": symbol,
        "timestamp": pd.Timestamp.now().isoformat(),
    }

    return enhanced_state
