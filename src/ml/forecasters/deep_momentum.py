"""
Lightweight deep momentum forecaster (2-layer MLP implemented in NumPy).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class DeepMomentumForecaster:
    """
    Tiny neural net that learns to predict next-day positive return probability.

    Implemented directly in NumPy to avoid heavyweight dependencies while still
    satisfying the "deep learning" requirement (two dense layers + non-linearity).
    """

    def __init__(
        self,
        lookback: int = 60,
        hidden_dim: int = 16,
        learning_rate: float = 0.01,
        epochs: int = 40,
        model_path: Path = Path("models/deep_momentum_forecaster.npz"),
    ) -> None:
        self.lookback = lookback
        self.hidden_dim = hidden_dim
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.model_path = model_path
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        self._rng = np.random.default_rng(42)
        self._initialized = False
        self._trained_once = False
        self._init_weights()

    def predict_probability(self, symbol: str, hist: pd.DataFrame) -> float:
        """Return probability (0-1) of positive next-day return."""
        X, y = self._build_dataset(hist)
        if X.size == 0:
            return 0.5

        if not self._trained_once and len(X) >= max(20, self.hidden_dim):
            self._train(X, y)
            self._save_weights()
            self._trained_once = True

        probs = self._forward(X[-1:])
        prob_value = float(probs.squeeze())
        logger.debug("Deep momentum %s prob=%.3f", symbol, prob_value)
        return prob_value

    # Internal helpers -------------------------------------------------

    def _build_dataset(self, hist: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        if hist is None or hist.empty:
            return np.array([]), np.array([])

        closes = hist["Close"].astype(float)
        volume = hist.get("Volume", pd.Series(index=hist.index, data=np.nan)).astype(
            float
        )

        df = pd.DataFrame(
            {
                "ret_1d": closes.pct_change(),
                "ret_5d": closes.pct_change(5),
                "ret_21d": closes.pct_change(21),
                "vol_ratio": volume / volume.rolling(20).mean(),
            }
        ).dropna()

        target = (closes.shift(-1) > closes).astype(float).reindex(df.index)
        df = df.join(target.rename("future_up")).dropna()

        if df.empty:
            return np.array([]), np.array([])

        X = df[["ret_1d", "ret_5d", "ret_21d", "vol_ratio"]].to_numpy(dtype=float)
        y = df["future_up"].to_numpy(dtype=float)

        # Keep the last N samples for responsiveness
        if len(X) > self.lookback:
            X = X[-self.lookback :]
            y = y[-self.lookback :]

        # Replace inf/nan with zeros
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        return X, y

    def _init_weights(self) -> None:
        if self.model_path.exists():
            try:
                data = np.load(self.model_path)
                self.W1 = data["W1"]
                self.b1 = data["b1"]
                self.W2 = data["W2"]
                self.b2 = data["b2"]
                self._initialized = True
                logger.info("Loaded deep momentum weights from %s", self.model_path)
                return
            except Exception as exc:  # pragma: no cover - corruption
                logger.warning("Failed to load deep momentum weights: %s", exc)

        input_dim = 4
        self.W1 = self._rng.normal(0, 0.1, size=(input_dim, self.hidden_dim))
        self.b1 = np.zeros((1, self.hidden_dim))
        self.W2 = self._rng.normal(0, 0.1, size=(self.hidden_dim, 1))
        self.b2 = np.zeros((1, 1))
        self._initialized = True

    def _forward(self, X: np.ndarray) -> np.ndarray:
        z1 = np.matmul(X, self.W1) + self.b1
        a1 = np.tanh(z1)
        z2 = np.matmul(a1, self.W2) + self.b2
        probs = 1 / (1 + np.exp(-z2))
        self._cache = (X, z1, a1, z2, probs)
        return probs

    def _train(self, X: np.ndarray, y: np.ndarray) -> None:
        if X.size == 0:
            return
        for _ in range(self.epochs):
            probs = self._forward(X)
            loss_grad = probs - y.reshape(-1, 1)
            self._step(loss_grad)

    def _step(self, grad_output: np.ndarray) -> None:
        X, z1, a1, _, probs = self._cache
        m = len(X)
        dz2 = grad_output / max(m, 1)
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

    def _save_weights(self) -> None:
        np.savez(
            self.model_path,
            W1=self.W1,
            b1=self.b1,
            W2=self.W2,
            b2=self.b2,
        )
