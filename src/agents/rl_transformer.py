"""
Transformer-based reinforcement learning policy used by the RL gate prototype.

The goal of this module is to provide a flexible, torch-based inference stack that
can consume multi-horizon price/volume features and output a confidence score plus
lightweight explainability metadata (feature importances, volatility regime tags).

The model is intentionally lightweight (few Transformer encoder blocks) so it can run
inside GitHub Actions or inexpensive cloud runners without GPU access. If a trained
state dict is available under ``models/ml/rl_transformer_state.pt`` it will be loaded;
otherwise the module falls back to randomly initialised weights but still produces
deterministic outputs thanks to a fixed seed.
"""

from __future__ import annotations

import logging
import math
import os
from pathlib import Path
from typing import Any

import numpy as np
from src.agents.rl_transformer_features import build_feature_matrix
from src.utils.market_data import get_market_data_provider

logger = logging.getLogger(__name__)

try:  # Optional dependency - torch is already in requirements.in
    import torch
    import torch.nn as nn
except Exception:  # pragma: no cover - handled by fallback
    torch = None  # type: ignore
    nn = None  # type: ignore


class TransformerUnavailableError(RuntimeError):
    """Raised when torch is missing or the transformer cannot be constructed."""


if torch is not None and nn is not None:

    class PositionalEncoding(nn.Module):  # type: ignore[misc]
        """Standard sinusoidal positional encoding."""

        def __init__(self, dim: int, max_len: int = 512) -> None:
            super().__init__()
            position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
            div_term = torch.exp(torch.arange(0, dim, 2).float() * (-math.log(10000.0) / dim))
            pe = torch.zeros(max_len, dim)
            pe[:, 0::2] = torch.sin(position * div_term)
            pe[:, 1::2] = torch.cos(position * div_term)
            pe = pe.unsqueeze(0)
            self.register_buffer("pe", pe)

        def forward(self, x: torch.Tensor) -> torch.Tensor:  # pragma: no cover - tiny wrapper
            return x + self.pe[:, : x.size(1), :]

    class RLTransformerModel(nn.Module):  # type: ignore[misc]
        """Encoder-only transformer tailored for univariate time-series features."""

        def __init__(
            self,
            feature_dim: int,
            context_window: int = 64,
            hidden_dim: int = 64,
            num_layers: int = 2,
            num_heads: int = 4,
        ) -> None:
            super().__init__()
            self.context_window = context_window
            self.input_projection = nn.Linear(feature_dim, hidden_dim)
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=hidden_dim,
                nhead=num_heads,
                dim_feedforward=hidden_dim * 2,
                batch_first=True,
                dropout=0.05,
            )
            self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
            self.positional_encoding = PositionalEncoding(hidden_dim, max_len=context_window)
            self.head = nn.Sequential(
                nn.LayerNorm(hidden_dim),
                nn.Linear(hidden_dim, hidden_dim // 2),
                nn.GELU(),
                nn.Linear(hidden_dim // 2, 1),
            )

        def forward(self, x: torch.Tensor) -> torch.Tensor:  # pragma: no cover - simple wrapper
            # x shape: (batch, seq_len, feature_dim)
            embedding = self.input_projection(x)
            embedding = self.positional_encoding(embedding)
            encoded = self.encoder(embedding)
            pooled = encoded[:, -1, :]  # Use last timestep representation
            logits = self.head(pooled).squeeze(-1)
            return logits


else:

    class TransformerRLPolicy:  # type: ignore[too-few-public-methods]
        """Fallback stub that raises when PyTorch is unavailable."""

        def __init__(self, *args, **kwargs) -> None:  # pragma: no cover - simple guard
            raise TransformerUnavailableError("PyTorch is not available in this runtime.")


if torch is not None and nn is not None:

    class TransformerRLPolicy:
        """Encapsulates the transformer model + feature engineering pipeline."""

        FEATURE_NAMES = [
            "pct_return",
            "rolling_vol",
            "volume_zscore",
            "rsi_norm",
            "price_zscore",
            "drawdown",
        ]

        def __init__(
            self,
            *,
            context_window: int = 64,
            feature_dim: int = 6,
            state_path: str | Path | None = None,
            lookback_days: int = 160,
            confidence_threshold: float = 0.55,
        ) -> None:
            self.context_window = context_window
            self.feature_dim = feature_dim
            self.confidence_threshold = confidence_threshold
            self.lookback_days = lookback_days
            self.state_path = Path(state_path or "models/ml/rl_transformer_state.pt")
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.model = RLTransformerModel(
                feature_dim=feature_dim,
                context_window=context_window,
            ).to(self.device)

            torch.manual_seed(42)
            if self.state_path.exists():
                try:
                    state = torch.load(self.state_path, map_location=self.device)
                    self.model.load_state_dict(state)
                    logger.info("Loaded transformer RL weights from %s", self.state_path)
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning(
                        "Failed to load transformer weights (%s). Using random init.", exc
                    )
            else:
                logger.warning(
                    "Transformer state file missing (%s). Using random init.", self.state_path
                )

            self.model.eval()
            self._provider = get_market_data_provider()
            self.model_version = os.getenv("RL_TRANSFORMER_VERSION", "transformer-v0.1")

        def predict(self, symbol: str, base_state: dict[str, Any]) -> dict[str, Any]:
            """
            Run transformer inference for a given symbol and indicator bundle.

            Args:
                symbol: Equity ticker (upper/lower case accepted)
                base_state: Indicator dict from Gate 1 (momentum agent)

            Returns:
                Dict payload used by the RL gate.
            """
            sequence, engineered = self._build_feature_tensor(symbol)
            if sequence is None:
                raise ValueError(f"Insufficient history to evaluate transformer for {symbol}")

            with torch.no_grad():
                logits = self.model(sequence)
                probability = torch.sigmoid(logits).item()

            regime_label = self._classify_regime(engineered)
            attribution = self._compute_attribution(engineered)
            multiplier = 0.6 + probability * 0.8  # 0.6-1.4 range

            action = "long" if probability >= self.confidence_threshold else "neutral"
            output = {
                "action": action,
                "confidence": round(probability, 4),
                "suggested_multiplier": round(multiplier, 3),
                "attribution": attribution,
                "regime": regime_label,
                "model_version": self.model_version,
                "features": {**base_state, "transformer_regime": regime_label},
            }
            return output

        # ------------------------------------------------------------------
        # Feature engineering helpers
        # ------------------------------------------------------------------
        def _build_feature_tensor(
            self, symbol: str
        ) -> tuple[torch.Tensor | None, np.ndarray | None]:
            result = self._provider.get_daily_bars(symbol, lookback_days=self.lookback_days)
            hist = result.data
            if hist is None or hist.empty or len(hist) < 40:
                return None, None

            frame = hist[["Close", "Volume"]].dropna().copy()
            stacked = build_feature_matrix(frame)
            if stacked.size == 0:
                return None, None

            if stacked.shape[0] >= self.context_window:
                sliced = stacked[-self.context_window :]
            else:
                pad = np.zeros((self.context_window - stacked.shape[0], stacked.shape[1]))
                sliced = np.concatenate([pad, stacked], axis=0)

            tensor = torch.from_numpy(sliced).float().unsqueeze(0).to(self.device)
            return tensor, sliced

        def _compute_attribution(self, engineered: np.ndarray | None) -> dict[str, float]:
            if engineered is None:
                return {}
            avg_vector = np.abs(engineered).mean(axis=0)
            total = np.sum(avg_vector) + 1e-8
            scores = avg_vector / total
            return {
                name: round(float(score), 4)
                for name, score in zip(self.FEATURE_NAMES, scores.tolist(), strict=False)
            }

        def _classify_regime(self, engineered: np.ndarray | None) -> str:
            if engineered is None or len(engineered) == 0:
                return "unknown"
            # Use the latest row for quick heuristics
            latest = engineered[-1]
            pct_return = latest[0]
            vol = latest[1]
            drawdown_val = latest[5]

            if drawdown_val < -0.08:
                return "bear_trend"
            if vol > 0.02 and abs(pct_return) < 0.005:
                return "sideways_high_vol"
            if pct_return > 0.01 and drawdown_val > -0.02:
                return "bull_accel"
            if pct_return < -0.01:
                return "pullback"
            return "neutral"
