"""Advanced ML Feature Extractor for Options & Market Regime Analysis.

Extracts a 14-dimensional normalized feature vector incorporating:
1. Volatility Regime: VIX Level, VIX Percentile, VIX Term Structure (VIX/VXV), IV Rank
2. Market Sentiment: Put-Call Ratio, Volume Premium, RSI Gap
3. Momentum & Trend: SPY 20d/5d Returns, ATR Normalized, ADX Normalized, DI Difference
4. Temporal Dynamics: Hour of Day, Day of Week
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MarketFeatures:
    vix_level: float = 20.0
    vix_percentile: float = 0.5
    vix_term_structure: float = 0.95
    iv_rank: float = 50.0
    put_call_ratio: float = 1.0
    spy_20d_return: float = 0.01
    spy_5d_return: float = 0.002
    atr_normalized: float = 0.015
    adx_normalized: float = 0.25
    di_difference: float = 0.05
    rsi_gap: float = 0.0
    volume_premium: float = 1.0
    hour_of_day: float = 0.5
    day_of_week: float = 0.4

    def to_vector(self) -> np.ndarray:
        """Convert features to normalized 14-D numpy array."""
        return np.array(
            [
                min(max(self.vix_level / 50.0, 0.0), 2.0),
                min(max(self.vix_percentile, 0.0), 1.0),
                min(max(self.vix_term_structure, 0.5), 1.5),
                min(max(self.iv_rank / 100.0, 0.0), 1.0),
                min(max(self.put_call_ratio / 2.0, 0.0), 2.0),
                min(max(self.spy_20d_return * 10.0, -2.0), 2.0),
                min(max(self.spy_5d_return * 10.0, -2.0), 2.0),
                min(max(self.atr_normalized * 20.0, 0.0), 2.0),
                min(max(self.adx_normalized, 0.0), 1.0),
                min(max(self.di_difference, -1.0), 1.0),
                min(max(self.rsi_gap / 50.0, -1.0), 1.0),
                min(max(self.volume_premium / 2.0, 0.0), 2.0),
                min(max(self.hour_of_day, 0.0), 1.0),
                min(max(self.day_of_week, 0.0), 1.0),
            ],
            dtype=np.float32,
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class FeatureExtractor:
    """Extracts and normalizes features from raw market snapshots."""

    def extract_from_snapshot(self, snapshot: dict[str, Any]) -> MarketFeatures:
        """Extract MarketFeatures from market snapshot dictionary."""
        try:
            return MarketFeatures(
                vix_level=float(snapshot.get("vix_level", snapshot.get("vix", 20.0))),
                vix_percentile=float(snapshot.get("vix_percentile", 0.5)),
                vix_term_structure=float(snapshot.get("vix_term_structure", 0.95)),
                iv_rank=float(snapshot.get("iv_rank", 50.0)),
                put_call_ratio=float(snapshot.get("put_call_ratio", 1.0)),
                spy_20d_return=float(snapshot.get("spy_20d_return", 0.01)),
                spy_5d_return=float(snapshot.get("spy_5d_return", 0.002)),
                atr_normalized=float(snapshot.get("atr_normalized", 0.015)),
                adx_normalized=float(snapshot.get("adx_normalized", 0.25)),
                di_difference=float(snapshot.get("di_difference", 0.05)),
                rsi_gap=float(snapshot.get("rsi_gap", 0.0)),
                volume_premium=float(snapshot.get("volume_premium", 1.0)),
                hour_of_day=float(snapshot.get("hour_of_day", 0.5)),
                day_of_week=float(snapshot.get("day_of_week", 0.4)),
            )
        except Exception as e:
            logger.warning("Feature extraction failed, using defaults: %s", e)
            return MarketFeatures()

    def batch_extract(self, snapshots: list[dict[str, Any]]) -> np.ndarray:
        """Extract feature matrix (N x 14) from batch of snapshots."""
        features = [self.extract_from_snapshot(s).to_vector() for s in snapshots]
        if not features:
            return np.empty((0, 14), dtype=np.float32)
        return np.vstack(features)
