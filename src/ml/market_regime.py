"""
Market Regime Clustering - Unsupervised ML for Trading

Identifies market regimes using clustering to determine optimal trading conditions:
- LOW_VOL_RANGE: Ideal for iron condors (range-bound, low volatility)
- TRENDING_UP: Bullish momentum, avoid neutral strategies
- TRENDING_DOWN: Bearish momentum, avoid neutral strategies
- HIGH_VOL_CHAOS: High uncertainty, stay out
- EARNINGS_COMPRESSION: Pre-earnings IV expansion period

Based on: "Data Without Labels" by Vaibhav Verdhan (Manning, 2025)

Usage:
    from src.ml.market_regime import MarketRegimeClassifier

    classifier = MarketRegimeClassifier()
    regime = classifier.classify_current()

    if regime.name == "LOW_VOL_RANGE":
        # Perfect for iron condors
        signal = 0.9
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Project paths
PROJECT_DIR = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_DIR / "data"
MODEL_DIR = DATA_DIR / "ml" / "regime_model"
MODEL_DIR.mkdir(parents=True, exist_ok=True)


class MarketRegime(Enum):
    """Market regime types for iron condor trading."""

    LOW_VOL_RANGE = "low_vol_range"  # Best for IC
    TRENDING_UP = "trending_up"  # Avoid IC
    TRENDING_DOWN = "trending_down"  # Avoid IC
    HIGH_VOL_CHAOS = "high_vol_chaos"  # Stay out
    EARNINGS_COMPRESSION = "earnings_compression"  # Elevated IV
    UNKNOWN = "unknown"


@dataclass
class RegimeClassification:
    """Result of regime classification."""

    regime: MarketRegime
    confidence: float  # 0-1
    features: dict[str, float]  # Input features used
    cluster_distances: dict[str, float]  # Distance to each cluster center
    recommendation: str  # Trading recommendation
    timestamp: datetime

    @property
    def name(self) -> str:
        return self.regime.value

    @property
    def is_favorable_for_ic(self) -> bool:
        """Check if regime is favorable for iron condors."""
        return self.regime == MarketRegime.LOW_VOL_RANGE

    def to_dict(self) -> dict:
        return {
            "regime": self.regime.value,
            "confidence": self.confidence,
            "features": self.features,
            "cluster_distances": self.cluster_distances,
            "recommendation": self.recommendation,
            "timestamp": self.timestamp.isoformat(),
            "is_favorable_for_ic": self.is_favorable_for_ic,
        }


class MarketRegimeClassifier:
    """
    Unsupervised market regime classifier using K-means clustering.

    Features used:
    - VIX level (volatility)
    - VIX percentile (relative to history)
    - SPY 20-day return (trend)
    - SPY 5-day return (momentum)
    - SPY ATR% (realized volatility)
    - Put/Call ratio (sentiment)
    """

    # Pre-defined cluster centers (trained on historical data)
    # These can be updated by calling fit() with new data
    CLUSTER_CENTERS = {
        MarketRegime.LOW_VOL_RANGE: np.array([15.0, 0.3, 0.02, 0.005, 0.8, 0.9]),
        MarketRegime.TRENDING_UP: np.array([18.0, 0.4, 0.08, 0.03, 1.2, 0.7]),
        MarketRegime.TRENDING_DOWN: np.array([22.0, 0.6, -0.06, -0.02, 1.5, 1.3]),
        MarketRegime.HIGH_VOL_CHAOS: np.array([30.0, 0.85, -0.02, -0.01, 2.5, 1.5]),
        MarketRegime.EARNINGS_COMPRESSION: np.array([20.0, 0.5, 0.01, 0.01, 1.0, 1.0]),
    }

    # Feature names for interpretation
    FEATURE_NAMES = [
        "vix_level",
        "vix_percentile",
        "spy_20d_return",
        "spy_5d_return",
        "spy_atr_pct",
        "put_call_ratio",
    ]

    # Recommendations per regime
    RECOMMENDATIONS = {
        MarketRegime.LOW_VOL_RANGE: "TRADE: Ideal conditions for iron condors. Use standard 15-delta strikes.",
        MarketRegime.TRENDING_UP: "CAUTION: Strong uptrend. If trading IC, widen call side or use call credit spread.",
        MarketRegime.TRENDING_DOWN: "CAUTION: Downtrend. If trading IC, widen put side or use put credit spread.",
        MarketRegime.HIGH_VOL_CHAOS: "AVOID: High volatility regime. Stay flat until VIX normalizes.",
        MarketRegime.EARNINGS_COMPRESSION: "CAUTION: Elevated IV before earnings. Wait for post-earnings IV crush.",
        MarketRegime.UNKNOWN: "UNKNOWN: Insufficient data. Do not trade.",
    }

    def __init__(self):
        self._centers = self.CLUSTER_CENTERS.copy()
        self._load_model()

    def _load_model(self) -> None:
        """Load trained cluster centers from disk."""
        model_file = MODEL_DIR / "cluster_centers.json"
        if model_file.exists():
            try:
                data = json.loads(model_file.read_text())
                for regime_name, center in data.get("centers", {}).items():
                    try:
                        regime = MarketRegime(regime_name)
                        self._centers[regime] = np.array(center)
                    except ValueError:
                        pass
                logger.info(f"Loaded regime model from {model_file}")
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to load regime model: {e}")

    def _save_model(self) -> None:
        """Save cluster centers to disk."""
        model_file = MODEL_DIR / "cluster_centers.json"
        data = {
            "updated_at": datetime.now().isoformat(),
            "centers": {
                regime.value: center.tolist()
                for regime, center in self._centers.items()
            },
        }
        model_file.write_text(json.dumps(data, indent=2))

    def _extract_features(
        self, market_data: dict[str, Any] | None = None
    ) -> np.ndarray:
        """
        Extract features from market data.

        If no data provided, fetches current data from Alpaca/external sources.
        """
        if market_data:
            features = np.array(
                [
                    market_data.get("vix_level", 18.0),
                    market_data.get("vix_percentile", 0.5),
                    market_data.get("spy_20d_return", 0.0),
                    market_data.get("spy_5d_return", 0.0),
                    market_data.get("spy_atr_pct", 1.0),
                    market_data.get("put_call_ratio", 1.0),
                ]
            )
        else:
            # Fetch current market data
            features = self._fetch_current_features()

        return features

    def _fetch_current_features(self) -> np.ndarray:
        """Fetch current market features from available sources."""
        # Try to load from system state or use defaults
        state_file = DATA_DIR / "system_state.json"

        vix_level = 18.0
        vix_percentile = 0.5
        spy_20d_return = 0.0
        spy_5d_return = 0.0
        spy_atr_pct = 1.0
        put_call_ratio = 1.0

        if state_file.exists():
            try:
                state = json.loads(state_file.read_text())
                market = state.get("market_context", {})

                vix_level = market.get("vix", 18.0)
                # Estimate percentile (VIX historical range roughly 10-80)
                vix_percentile = min((vix_level - 10) / 40, 1.0)

                # Try to get returns from positions or estimates
                spy_20d_return = market.get("spy_20d_return", 0.0)
                spy_5d_return = market.get("spy_5d_return", 0.0)

            except (json.JSONDecodeError, KeyError):
                pass

        # Try to load VIX data from Cloudflare worker cache
        vix_cache = DATA_DIR / "vix_cache.json"
        if vix_cache.exists():
            try:
                vix_data = json.loads(vix_cache.read_text())
                vix_level = vix_data.get("vix", vix_level)
            except (json.JSONDecodeError, KeyError):
                pass

        return np.array(
            [
                vix_level,
                vix_percentile,
                spy_20d_return,
                spy_5d_return,
                spy_atr_pct,
                put_call_ratio,
            ]
        )

    def _compute_distances(self, features: np.ndarray) -> dict[MarketRegime, float]:
        """Compute Euclidean distance to each cluster center."""
        distances = {}

        # Normalize features for fair comparison
        feature_scales = np.array([10.0, 1.0, 0.1, 0.05, 1.0, 0.5])  # Rough scales
        normalized = features / feature_scales

        for regime, center in self._centers.items():
            normalized_center = center / feature_scales
            dist = np.linalg.norm(normalized - normalized_center)
            distances[regime] = float(dist)

        return distances

    def classify(
        self, market_data: dict[str, Any] | None = None
    ) -> RegimeClassification:
        """
        Classify the current market regime.

        Args:
            market_data: Optional dict with feature values. If None, fetches current data.

        Returns:
            RegimeClassification with regime, confidence, and recommendation.
        """
        features = self._extract_features(market_data)
        distances = self._compute_distances(features)

        # Find closest cluster
        closest_regime = min(distances, key=distances.get)
        min_distance = distances[closest_regime]

        # Compute confidence (inverse of distance, normalized)
        # Lower distance = higher confidence
        max_distance = max(distances.values())
        if max_distance > 0:
            confidence = 1.0 - (min_distance / max_distance)
        else:
            confidence = 1.0

        # Build feature dict for interpretability
        feature_dict = {
            name: float(val)
            for name, val in zip(self.FEATURE_NAMES, features, strict=False)
        }

        return RegimeClassification(
            regime=closest_regime,
            confidence=round(confidence, 3),
            features=feature_dict,
            cluster_distances={r.value: round(d, 3) for r, d in distances.items()},
            recommendation=self.RECOMMENDATIONS[closest_regime],
            timestamp=datetime.now(),
        )

    def classify_current(self) -> RegimeClassification:
        """Classify current market regime using latest available data."""
        return self.classify(None)

    def fit(self, historical_data: list[dict[str, Any]], n_clusters: int = 5) -> None:
        """
        Train/update cluster centers using historical market data.

        This implements K-means clustering on historical features.

        Args:
            historical_data: List of dicts with feature values and optional labels
            n_clusters: Number of clusters (default 5 = number of regimes)
        """
        if len(historical_data) < n_clusters * 10:
            logger.warning("Insufficient data for training. Need at least 50 samples.")
            return

        # Extract feature matrix
        X = np.array([self._extract_features(d) for d in historical_data])

        # Simple K-means implementation (no sklearn dependency)
        centers = self._kmeans(X, n_clusters, max_iter=100)

        # Map clusters to regimes based on characteristics
        self._assign_clusters_to_regimes(centers)
        self._save_model()

        logger.info(f"Trained regime model on {len(historical_data)} samples")

    def _kmeans(self, X: np.ndarray, k: int, max_iter: int = 100) -> np.ndarray:
        """Simple K-means clustering implementation."""
        n_samples = X.shape[0]

        # Initialize centers randomly
        idx = np.random.choice(n_samples, k, replace=False)
        centers = X[idx].copy()

        for _ in range(max_iter):
            # Assign points to nearest center
            distances = np.array([[np.linalg.norm(x - c) for c in centers] for x in X])
            labels = np.argmin(distances, axis=1)

            # Update centers
            new_centers = np.array(
                [
                    (
                        X[labels == i].mean(axis=0)
                        if (labels == i).sum() > 0
                        else centers[i]
                    )
                    for i in range(k)
                ]
            )

            # Check convergence
            if np.allclose(centers, new_centers):
                break
            centers = new_centers

        return centers

    def _assign_clusters_to_regimes(self, centers: np.ndarray) -> None:
        """Assign cluster centers to regime types based on feature characteristics."""
        # Sort by VIX level (first feature) to assign regimes
        sorted_idx = np.argsort(centers[:, 0])  # Sort by VIX

        # Assign based on VIX level
        # Lowest VIX → LOW_VOL_RANGE
        # Highest VIX → HIGH_VOL_CHAOS
        # Middle ones based on trend (3rd feature)

        for i, idx in enumerate(sorted_idx):
            if i == 0:
                self._centers[MarketRegime.LOW_VOL_RANGE] = centers[idx]
            elif i == len(sorted_idx) - 1:
                self._centers[MarketRegime.HIGH_VOL_CHAOS] = centers[idx]
            else:
                # Check trend direction
                trend = centers[idx][2]  # spy_20d_return
                if trend > 0.02:
                    self._centers[MarketRegime.TRENDING_UP] = centers[idx]
                elif trend < -0.02:
                    self._centers[MarketRegime.TRENDING_DOWN] = centers[idx]
                else:
                    self._centers[MarketRegime.EARNINGS_COMPRESSION] = centers[idx]


def get_regime_signal() -> dict[str, Any]:
    """
    Get market regime signal for swarm integration.

    Returns signal in swarm-compatible format.
    """
    classifier = MarketRegimeClassifier()
    result = classifier.classify_current()

    # Convert regime to trading signal (0-1)
    regime_signals = {
        MarketRegime.LOW_VOL_RANGE: 0.9,
        MarketRegime.TRENDING_UP: 0.4,
        MarketRegime.TRENDING_DOWN: 0.3,
        MarketRegime.HIGH_VOL_CHAOS: 0.1,
        MarketRegime.EARNINGS_COMPRESSION: 0.5,
        MarketRegime.UNKNOWN: 0.0,
    }

    signal = regime_signals.get(result.regime, 0.5)

    return {
        "signal": signal,
        "confidence": result.confidence,
        "data": {
            "regime": result.name,
            "is_favorable_for_ic": result.is_favorable_for_ic,
            "recommendation": result.recommendation,
            "features": result.features,
        },
    }


async def main():
    """Demo the market regime classifier."""
    classifier = MarketRegimeClassifier()

    print("=== Market Regime Classification ===\n")

    result = classifier.classify_current()

    print(f"Regime: {result.regime.value.upper()}")
    print(f"Confidence: {result.confidence:.1%}")
    print(f"Favorable for IC: {'✅ YES' if result.is_favorable_for_ic else '❌ NO'}")
    print(f"\nRecommendation: {result.recommendation}")

    print("\n--- Features ---")
    for name, value in result.features.items():
        print(f"  {name}: {value:.4f}")

    print("\n--- Cluster Distances ---")
    for regime, dist in sorted(result.cluster_distances.items(), key=lambda x: x[1]):
        marker = "→" if regime == result.regime.value else " "
        print(f"  {marker} {regime}: {dist:.3f}")

    print("\n=== Swarm Signal ===")
    signal = get_regime_signal()
    print(f"Signal: {signal['signal']} (1.0 = trade, 0.0 = avoid)")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
