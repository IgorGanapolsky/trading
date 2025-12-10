"""
Alpha research and signal generation.

Provides tools for alpha signal development:
- Feature library with common features
- Signal generation and ranking
- Information Coefficient analysis
- Alpha combination methods
"""

from typing import Optional

from src.research.alpha.features import (
    FeatureConfig,
    FeatureLibrary,
    compute_momentum_features,
    compute_technical_features,
    compute_volatility_features,
    compute_volume_features,
)
from src.research.alpha.signals import (
    AlphaSignal,
    SignalGenerator,
    combine_signals,
    rank_signals_by_ic,
)


class AlphaResearcher:
    """Lightweight facade for feature generation and signal ranking."""

    def __init__(self, feature_library: Optional[FeatureLibrary] = None) -> None:
        self.feature_library = feature_library or FeatureLibrary()

    def build_features(self, ohlcv) -> dict:
        """Generate a basic feature bundle from OHLCV data."""
        return {
            "momentum": compute_momentum_features(ohlcv),
            "volatility": compute_volatility_features(ohlcv),
            "volume": compute_volume_features(ohlcv),
            "technical": compute_technical_features(ohlcv),
        }

    def generate_signals(self, features, categories=None):
        """Simple placeholder signal generator using average of selected features."""
        import pandas as pd

        if categories is None:
            categories = ["momentum"]

        if isinstance(features, dict):
            selected = [features[c] for c in categories if c in features]
            combined = pd.concat(selected, axis=1)
        else:
            combined = features

        signal = combined.mean(axis=1)
        return pd.DataFrame({"alpha_momentum": signal})


__all__ = [
    "AlphaResearcher",
    "FeatureLibrary",
    "FeatureConfig",
    "compute_momentum_features",
    "compute_volatility_features",
    "compute_volume_features",
    "compute_technical_features",
    "AlphaSignal",
    "SignalGenerator",
    "combine_signals",
    "rank_signals_by_ic",
]
