"""
Shared feature engineering helpers for the RL transformer gate.

Centralising these functions ensures that both inference and training use the exact
same transformation pipeline (returns, volatility, volume z-score, RSI normalization,
price z-score, and drawdown). This prevents subtle drift when generating datasets for
offline training or verification.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def build_feature_matrix(frame: pd.DataFrame) -> np.ndarray:
    """
    Convert a price/volume frame into the stacked feature matrix expected by the
    transformer model.

    Args:
        frame: DataFrame with at least ``Close`` and ``Volume`` columns.

    Returns:
        np.ndarray of shape (len(frame), feature_dim). Returns an empty array if
        insufficient data is available.
    """
    if frame is None or frame.empty:
        return np.empty((0, 6))

    subset = frame[["Close", "Volume"]].dropna().copy()
    if subset.empty:
        return np.empty((0, 6))

    closes = subset["Close"].astype(float)
    volumes = subset["Volume"].astype(float)

    returns = closes.pct_change().fillna(0.0)
    rolling_vol = returns.rolling(5).std().fillna(0.0)
    price_z = (closes - closes.rolling(20).mean()) / (closes.rolling(20).std() + 1e-6)
    drawdown = (closes / closes.cummax()) - 1.0

    log_volume = np.log1p(volumes)
    volume_z = (log_volume - log_volume.rolling(20).mean()) / (log_volume.rolling(20).std() + 1e-6)
    volume_z = volume_z.fillna(0.0)

    rsi_series = _compute_rsi_series(closes)
    rsi_norm = (rsi_series / 100.0).fillna(0.5)

    stacked = np.stack(
        [
            returns.to_numpy(),
            rolling_vol.to_numpy(),
            volume_z.to_numpy(),
            rsi_norm.to_numpy(),
            price_z.to_numpy(),
            drawdown.to_numpy(),
        ],
        axis=1,
    )
    stacked = np.nan_to_num(stacked).astype(np.float32)
    if stacked.ndim == 3:
        stacked = np.squeeze(stacked, axis=-1)
    return stacked


def _compute_rsi_series(prices: pd.Series, period: int = 14) -> pd.Series:
    if len(prices) < period + 2:
        return prices.copy() * 0 + 50.0
    delta = prices.diff().fillna(0.0)
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.bfill().fillna(50.0)
    return rsi
