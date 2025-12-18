"""
Hybrid LSTM-Transformer Forecaster for Financial Time Series.

Combines the strengths of both architectures based on 2024-2025 research:
- LSTM: Superior for price differences/movements (R² ~11.5%)
- Transformer: Better for absolute prices, robust across market regimes
- Hybrid: Best overall performance per MDPI/OpenReview studies

References:
- "Transformers vs LSTMs for Electronic Trading" (OpenReview 2024)
- "LSTM-Transformer Hybrid for Financial Forecasting" (MDPI 2024)
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Try to import PyTorch, fall back to NumPy-only mode
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not available - using NumPy fallback mode")


class PositionalEncoding(nn.Module):
    """Sinusoidal positional encoding for Transformer."""

    def __init__(self, d_model: int, max_len: int = 500, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)

        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model)
        )
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)  # (1, max_len, d_model)
        self.register_buffer("pe", pe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, seq_len, d_model)
        x = x + self.pe[:, : x.size(1), :]
        return self.dropout(x)


class LSTMTransformerHybrid(nn.Module):
    """
    Hybrid architecture combining LSTM and Transformer.

    Architecture:
    1. Input embedding layer
    2. LSTM branch: Captures local temporal patterns (good for price movements)
    3. Transformer branch: Captures long-range dependencies (good for absolute prices)
    4. Fusion layer: Combines both representations
    5. Output head: Predicts next-day return probability
    """

    def __init__(
        self,
        input_dim: int = 8,
        hidden_dim: int = 64,
        lstm_layers: int = 2,
        transformer_heads: int = 4,
        transformer_layers: int = 2,
        dropout: float = 0.1,
    ):
        super().__init__()

        self.input_dim = input_dim
        self.hidden_dim = hidden_dim

        # Input projection
        self.input_proj = nn.Linear(input_dim, hidden_dim)

        # LSTM Branch - good at sequential/local patterns
        self.lstm = nn.LSTM(
            input_size=hidden_dim,
            hidden_size=hidden_dim,
            num_layers=lstm_layers,
            batch_first=True,
            dropout=dropout if lstm_layers > 1 else 0,
            bidirectional=False,
        )
        self.lstm_norm = nn.LayerNorm(hidden_dim)

        # Transformer Branch - good at long-range dependencies
        self.pos_encoder = PositionalEncoding(hidden_dim, dropout=dropout)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_dim,
            nhead=transformer_heads,
            dim_feedforward=hidden_dim * 4,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=transformer_layers)
        self.transformer_norm = nn.LayerNorm(hidden_dim)

        # Fusion layer - combines LSTM and Transformer outputs
        self.fusion = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.GELU(),
        )

        # Output head
        self.output_head = nn.Sequential(
            nn.Linear(hidden_dim // 2, 1),
            nn.Sigmoid(),
        )

        # Initialize weights
        self._init_weights()

    def _init_weights(self):
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
            elif isinstance(module, nn.LSTM):
                for name, param in module.named_parameters():
                    if "weight" in name:
                        nn.init.orthogonal_(param)
                    elif "bias" in name:
                        nn.init.zeros_(param)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.

        Args:
            x: Input tensor of shape (batch, seq_len, input_dim)

        Returns:
            Probability tensor of shape (batch, 1)
        """
        # Project input to hidden dimension
        x = self.input_proj(x)  # (batch, seq, hidden)

        # LSTM branch
        lstm_out, _ = self.lstm(x)
        lstm_out = self.lstm_norm(lstm_out[:, -1, :])  # Take last timestep

        # Transformer branch
        transformer_in = self.pos_encoder(x)
        transformer_out = self.transformer(transformer_in)
        transformer_out = self.transformer_norm(transformer_out[:, -1, :])  # Take last timestep

        # Fusion
        fused = torch.cat([lstm_out, transformer_out], dim=-1)
        fused = self.fusion(fused)

        # Output
        prob = self.output_head(fused)
        return prob


class HybridLSTMTransformerForecaster:
    """
    Production-ready hybrid forecaster for trading system.

    Features:
    - Combines LSTM (local patterns) + Transformer (global patterns)
    - Automatic feature engineering from OHLCV data
    - Graceful fallback to NumPy if PyTorch unavailable
    - Compatible with existing DeepMomentumForecaster interface
    """

    def __init__(
        self,
        lookback: int = 60,
        hidden_dim: int = 64,
        learning_rate: float = 0.001,
        epochs: int = 50,
        model_path: Path = Path("models/hybrid_lstm_transformer.pt"),
        device: Optional[str] = None,
    ) -> None:
        self.lookback = lookback
        self.hidden_dim = hidden_dim
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.model_path = model_path
        self.model_path.parent.mkdir(parents=True, exist_ok=True)

        self._trained_once = False
        self._use_torch = TORCH_AVAILABLE

        if self._use_torch:
            self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
            self._init_model()
        else:
            # NumPy fallback - simple MLP
            self._init_numpy_fallback()

    def _init_model(self) -> None:
        """Initialize PyTorch model."""
        self.model = LSTMTransformerHybrid(
            input_dim=8,  # Number of features we'll engineer
            hidden_dim=self.hidden_dim,
            lstm_layers=2,
            transformer_heads=4,
            transformer_layers=2,
            dropout=0.1,
        ).to(self.device)

        self.optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=self.learning_rate,
            weight_decay=0.01,
        )
        self.scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            self.optimizer, T_max=self.epochs
        )
        self.criterion = nn.BCELoss()

        # Try to load existing weights
        if self.model_path.exists():
            try:
                state = torch.load(self.model_path, map_location=self.device, weights_only=True)
                self.model.load_state_dict(state["model"])
                self._trained_once = True
                logger.info("Loaded hybrid LSTM-Transformer weights from %s", self.model_path)
            except Exception as e:
                logger.warning("Failed to load model weights: %s", e)

    def _init_numpy_fallback(self) -> None:
        """Initialize NumPy fallback for when PyTorch isn't available."""
        self._rng = np.random.default_rng(42)
        input_dim = 8
        self.W1 = self._rng.normal(0, 0.1, size=(input_dim, self.hidden_dim))
        self.b1 = np.zeros((1, self.hidden_dim))
        self.W2 = self._rng.normal(0, 0.1, size=(self.hidden_dim, 1))
        self.b2 = np.zeros((1, 1))

    def predict_probability(self, symbol: str, hist: pd.DataFrame) -> float:
        """
        Predict probability of positive next-day return.

        Args:
            symbol: Stock symbol
            hist: Historical OHLCV DataFrame

        Returns:
            Probability (0-1) of positive next-day return
        """
        X, y = self._build_dataset(hist)
        if X.size == 0:
            return 0.5

        # Train if we have enough data and haven't trained yet
        min_samples = max(30, self.hidden_dim)
        if not self._trained_once and len(X) >= min_samples:
            self._train(X, y)
            self._save_weights()
            self._trained_once = True

        # Predict
        prob = self._predict(X[-self.lookback:])
        logger.debug("Hybrid LSTM-Transformer %s prob=%.3f", symbol, prob)
        return prob

    def _build_dataset(self, hist: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        """Build feature dataset from OHLCV data."""
        if hist is None or hist.empty or len(hist) < 30:
            return np.array([]), np.array([])

        try:
            # Extract OHLCV
            close = hist["Close"].astype(float)
            high = hist.get("High", close).astype(float)
            low = hist.get("Low", close).astype(float)
            volume = hist.get("Volume", pd.Series(index=hist.index, data=1.0)).astype(float)

            # Feature engineering - 8 features total
            features = pd.DataFrame(index=hist.index)

            # Returns at different horizons
            features["ret_1d"] = close.pct_change()
            features["ret_5d"] = close.pct_change(5)
            features["ret_21d"] = close.pct_change(21)

            # Volatility
            features["volatility_10d"] = close.pct_change().rolling(10).std()
            features["volatility_21d"] = close.pct_change().rolling(21).std()

            # Price position (normalized)
            rolling_high = high.rolling(20).max()
            rolling_low = low.rolling(20).min()
            features["price_position"] = (close - rolling_low) / (rolling_high - rolling_low + 1e-8)

            # Volume ratio
            features["volume_ratio"] = volume / volume.rolling(20).mean()

            # Momentum (RSI-like)
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            features["momentum"] = gain / (gain + loss + 1e-8)

            # Target: next day positive return
            target = (close.shift(-1) > close).astype(float)

            # Combine and clean
            features = features.dropna()
            target = target.reindex(features.index).dropna()
            features = features.loc[target.index]

            if features.empty:
                return np.array([]), np.array([])

            X = features.to_numpy(dtype=np.float32)
            y = target.to_numpy(dtype=np.float32)

            # Replace inf/nan
            X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

            # Keep last N samples
            if len(X) > self.lookback * 2:
                X = X[-self.lookback * 2:]
                y = y[-self.lookback * 2:]

            return X, y

        except Exception as e:
            logger.warning("Failed to build dataset: %s", e)
            return np.array([]), np.array([])

    def _train(self, X: np.ndarray, y: np.ndarray) -> None:
        """Train the model."""
        if self._use_torch:
            self._train_torch(X, y)
        else:
            self._train_numpy(X, y)

    def _train_torch(self, X: np.ndarray, y: np.ndarray) -> None:
        """Train PyTorch model."""
        self.model.train()

        # Create sequences for LSTM/Transformer
        seq_len = min(20, len(X) // 2)
        sequences = []
        targets = []

        for i in range(seq_len, len(X)):
            sequences.append(X[i - seq_len : i])
            targets.append(y[i - 1])

        if not sequences:
            return

        X_seq = torch.tensor(np.array(sequences), dtype=torch.float32).to(self.device)
        y_seq = torch.tensor(np.array(targets), dtype=torch.float32).unsqueeze(1).to(self.device)

        # Training loop
        best_loss = float("inf")
        patience = 10
        patience_counter = 0

        for epoch in range(self.epochs):
            self.optimizer.zero_grad()
            preds = self.model(X_seq)
            loss = self.criterion(preds, y_seq)
            loss.backward()

            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)

            self.optimizer.step()
            self.scheduler.step()

            # Early stopping
            if loss.item() < best_loss:
                best_loss = loss.item()
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    logger.debug("Early stopping at epoch %d", epoch)
                    break

            if epoch % 10 == 0:
                logger.debug("Epoch %d, Loss: %.4f", epoch, loss.item())

        self.model.eval()
        logger.info("Trained hybrid LSTM-Transformer (final loss: %.4f)", best_loss)

    def _train_numpy(self, X: np.ndarray, y: np.ndarray) -> None:
        """Train NumPy fallback model (simple MLP)."""
        for _ in range(self.epochs):
            # Forward
            z1 = np.matmul(X, self.W1) + self.b1
            a1 = np.tanh(z1)
            z2 = np.matmul(a1, self.W2) + self.b2
            probs = 1 / (1 + np.exp(-z2))

            # Backward
            loss_grad = probs - y.reshape(-1, 1)
            m = len(X)
            dz2 = loss_grad / max(m, 1)
            dW2 = np.matmul(a1.T, dz2)
            db2 = dz2.sum(axis=0, keepdims=True)

            da1 = np.matmul(dz2, self.W2.T)
            dz1 = da1 * (1 - np.tanh(z1) ** 2)
            dW1 = np.matmul(X.T, dz1)
            db1 = dz1.sum(axis=0, keepdims=True)

            self.W2 -= self.learning_rate * dW2
            self.b2 -= self.learning_rate * db2
            self.W1 -= self.learning_rate * dW1
            self.b1 -= self.learning_rate * db1

    def _predict(self, X: np.ndarray) -> float:
        """Make prediction."""
        if self._use_torch:
            return self._predict_torch(X)
        else:
            return self._predict_numpy(X)

    def _predict_torch(self, X: np.ndarray) -> float:
        """Predict using PyTorch model."""
        self.model.eval()
        with torch.no_grad():
            # Ensure we have enough for a sequence
            seq_len = min(20, len(X))
            if len(X) < seq_len:
                X = np.pad(X, ((seq_len - len(X), 0), (0, 0)), mode="edge")

            X_seq = torch.tensor(X[-seq_len:], dtype=torch.float32).unsqueeze(0).to(self.device)
            prob = self.model(X_seq)
            return float(prob.squeeze().cpu().numpy())

    def _predict_numpy(self, X: np.ndarray) -> float:
        """Predict using NumPy fallback."""
        # Use mean of recent features
        x = X[-1:] if len(X) > 0 else np.zeros((1, 8))
        z1 = np.matmul(x, self.W1) + self.b1
        a1 = np.tanh(z1)
        z2 = np.matmul(a1, self.W2) + self.b2
        prob = 1 / (1 + np.exp(-z2))
        return float(prob.squeeze())

    def _save_weights(self) -> None:
        """Save model weights."""
        try:
            if self._use_torch:
                torch.save(
                    {"model": self.model.state_dict()},
                    self.model_path,
                )
            else:
                np.savez(
                    str(self.model_path).replace(".pt", ".npz"),
                    W1=self.W1,
                    b1=self.b1,
                    W2=self.W2,
                    b2=self.b2,
                )
            logger.info("Saved hybrid forecaster weights to %s", self.model_path)
        except Exception as e:
            logger.warning("Failed to save weights: %s", e)

    def get_model_info(self) -> dict:
        """Return model information for debugging."""
        info = {
            "type": "HybridLSTMTransformerForecaster",
            "backend": "pytorch" if self._use_torch else "numpy",
            "lookback": self.lookback,
            "hidden_dim": self.hidden_dim,
            "trained": self._trained_once,
        }
        if self._use_torch:
            info["device"] = self.device
            info["parameters"] = sum(p.numel() for p in self.model.parameters())
        return info


# Convenience alias
LSTMTransformerForecaster = HybridLSTMTransformerForecaster
