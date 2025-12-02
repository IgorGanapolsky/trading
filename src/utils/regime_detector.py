"""
Multi-layer regime detection with HMM and VIX/Skew integration.

Layers:
1. Heuristic detection (fast, always available)
2. HMM-based regime classification (4 states: calm, trend, vol, spike)
3. VIX/VVIX skew analysis for regime confirmation
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Regime labels mapped to numeric IDs for HMM
REGIME_LABELS = {
    0: "calm",        # Low vol, range-bound
    1: "trending",    # Directional movement
    2: "volatile",    # High vol, choppy
    3: "spike",       # Crisis/tail event
}

REGIME_ALLOCATIONS = {
    "calm": {"equities": 0.8, "treasuries": 0.2, "pause_trading": False},
    "trending": {"equities": 0.7, "treasuries": 0.3, "pause_trading": False},
    "volatile": {"equities": 0.4, "treasuries": 0.5, "pause_trading": False},
    "spike": {"equities": 0.0, "treasuries": 0.6, "pause_trading": True},
}


@dataclass
class RegimeSnapshot:
    """Immutable snapshot of current regime state."""

    label: str
    regime_id: int
    confidence: float
    vix_level: float
    vvix_level: float
    skew_percentile: float
    risk_bias: str
    allocation_override: dict[str, float] | None
    detected_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class RegimeDetector:
    """
    Multi-layer regime detection with HMM and VIX/Skew integration.

    Layer 1 (Heuristic): Fast, always-available detection based on features
    Layer 2 (HMM): Probabilistic 4-state regime classification
    Layer 3 (VIX/Skew): Confirmation via options market signals
    """

    high_vol_threshold: float = 0.4
    trend_threshold: float = 0.03
    vix_spike_threshold: float = 30.0
    vix_calm_threshold: float = 15.0
    hmm_enabled: bool = field(default_factory=lambda: os.getenv("HMM_REGIME_ENABLED", "true").lower() == "true")
    _hmm_model: Any = field(default=None, repr=False)
    _last_hmm_fit: datetime | None = field(default=None, repr=False)
    _hmm_fit_interval_hours: int = 24

    def detect(self, features: dict[str, Any]) -> dict[str, Any]:
        """
        Layer 1: Heuristic detection (backward compatible).
        """
        volatility = float(features.get("volatility", 0.0) or 0.0)
        trend = float(features.get("trend_strength", 0.0) or 0.0)
        order_flow = float(features.get("order_flow_imbalance", 0.0) or 0.0)
        momentum = float(features.get("short_term_momentum", 0.0) or 0.0)
        downside = float(features.get("downside_volatility", 0.0) or 0.0)

        label = "range"
        confidence = 0.5

        if volatility >= self.high_vol_threshold and abs(trend) < self.trend_threshold:
            label = "volatile"
            confidence = min(0.95, volatility / (self.high_vol_threshold * 1.5))
        elif trend >= self.trend_threshold:
            label = "trending_bull"
            confidence = min(0.9, trend / (self.trend_threshold * 2))
        elif trend <= -self.trend_threshold:
            label = "trending_bear"
            confidence = min(0.9, abs(trend) / (self.trend_threshold * 2))
        elif abs(order_flow) > 0.3 or abs(momentum) > 1.0:
            label = "microstructure_impulse"
            confidence = 0.6 + min(0.3, abs(order_flow))

        risk_bias = "neutral"
        if label == "volatile" or downside > volatility * 0.7:
            risk_bias = "de_risk"
        elif label == "trending_bull" and order_flow > 0 and momentum > 0:
            risk_bias = "lean_in"
        elif label == "trending_bear":
            risk_bias = "hedge"

        return {
            "label": label,
            "confidence": round(confidence, 3),
            "volatility": round(volatility, 4),
            "trend": round(trend, 4),
            "order_flow": round(order_flow, 4),
            "risk_bias": risk_bias,
        }

    def detect_live_regime(self, lookback_days: int = 90) -> RegimeSnapshot:
        """
        Layer 2+3: Live regime detection using VIX, VVIX, and optional HMM.

        Fetches current market data and classifies into 4 regimes:
        - calm: VIX < 15, low skew
        - trending: Directional VIX movement
        - volatile: VIX 20-30, elevated skew
        - spike: VIX > 30, extreme skew (pause equities)

        Returns:
            RegimeSnapshot with allocation recommendations
        """
        try:
            import yfinance as yf
        except ImportError:
            logger.warning("yfinance not available for live regime detection")
            return self._fallback_snapshot()

        try:
            # Fetch VIX, VVIX, and TLT (treasury proxy for flight-to-safety)
            tickers = ["^VIX", "^VVIX", "TLT"]
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=lookback_days)

            data = yf.download(
                tickers,
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                progress=False,
            )

            if data.empty:
                logger.warning("No VIX/VVIX data available")
                return self._fallback_snapshot()

            # Extract close prices
            closes = data["Close"] if "Close" in data else data
            if closes.empty:
                return self._fallback_snapshot()

            # Current levels
            vix = float(closes["^VIX"].iloc[-1]) if "^VIX" in closes else 20.0
            vvix = float(closes["^VVIX"].iloc[-1]) if "^VVIX" in closes else 100.0

            # Calculate skew percentile (VVIX relative to VIX)
            if vix > 0:
                skew_ratio = vvix / vix
                # Historical percentile of skew ratio
                hist_skew = (closes["^VVIX"] / closes["^VIX"]).dropna()
                if len(hist_skew) > 10:
                    skew_percentile = (hist_skew < skew_ratio).mean() * 100
                else:
                    skew_percentile = 50.0
            else:
                skew_percentile = 50.0

            # Classify regime based on VIX levels
            if vix >= self.vix_spike_threshold:
                regime_id = 3  # spike
                confidence = min(0.95, vix / 40.0)
            elif vix >= 20.0:
                regime_id = 2  # volatile
                confidence = 0.7 + (vix - 20) / 30
            elif skew_percentile > 80 or (closes["^VIX"].iloc[-5:].mean() > closes["^VIX"].iloc[-20:].mean()):
                regime_id = 1  # trending (VIX rising = bear trend)
                confidence = 0.6 + skew_percentile / 200
            else:
                regime_id = 0  # calm
                confidence = 0.8 - (vix / 30)

            label = REGIME_LABELS.get(regime_id, "unknown")
            allocation = REGIME_ALLOCATIONS.get(label, {"equities": 0.5, "treasuries": 0.5})

            # Risk bias based on regime
            if regime_id == 3:
                risk_bias = "pause"
            elif regime_id == 2:
                risk_bias = "de_risk"
            elif regime_id == 1:
                risk_bias = "hedge"
            else:
                risk_bias = "neutral"

            # Optional: Run HMM for more nuanced classification
            hmm_regime = None
            if self.hmm_enabled:
                hmm_regime = self._run_hmm_classification(closes)
                if hmm_regime is not None and hmm_regime != regime_id:
                    # Blend HMM and heuristic (HMM gets 40% weight)
                    confidence = 0.6 * confidence + 0.4 * 0.7
                    if hmm_regime > regime_id:
                        regime_id = hmm_regime
                        label = REGIME_LABELS.get(regime_id, label)

            return RegimeSnapshot(
                label=label,
                regime_id=regime_id,
                confidence=min(0.95, confidence),
                vix_level=round(vix, 2),
                vvix_level=round(vvix, 2),
                skew_percentile=round(skew_percentile, 1),
                risk_bias=risk_bias,
                allocation_override=allocation if regime_id >= 2 else None,
            )

        except Exception as exc:
            logger.error("Live regime detection failed: %s", exc)
            return self._fallback_snapshot()

    def _run_hmm_classification(self, closes) -> int | None:
        """
        Run HMM classification on VIX/VVIX/TLT features.

        Uses a 4-state Gaussian HMM to identify hidden market regimes.
        """
        try:
            from hmmlearn.hmm import GaussianHMM
        except ImportError:
            logger.debug("hmmlearn not available, skipping HMM classification")
            return None

        try:
            # Build feature matrix
            features = []
            if "^VIX" in closes:
                features.append(closes["^VIX"].pct_change().fillna(0).values)
            if "^VVIX" in closes:
                features.append(closes["^VVIX"].pct_change().fillna(0).values)
            if "TLT" in closes:
                features.append(np.log(closes["TLT"]).diff().fillna(0).values)

            if len(features) < 2:
                return None

            X = np.column_stack(features)

            # Check if we need to refit the model
            now = datetime.utcnow()
            should_refit = (
                self._hmm_model is None
                or self._last_hmm_fit is None
                or (now - self._last_hmm_fit).total_seconds() > self._hmm_fit_interval_hours * 3600
            )

            if should_refit:
                model = GaussianHMM(
                    n_components=4,
                    covariance_type="full",
                    n_iter=100,
                    random_state=42,
                )
                model.fit(X)
                self._hmm_model = model
                self._last_hmm_fit = now
                logger.info("HMM regime model fitted with %d observations", len(X))

            # Predict current regime
            regime_id = int(self._hmm_model.predict(X)[-1])
            return regime_id

        except Exception as exc:
            logger.warning("HMM classification failed: %s", exc)
            return None

    def _fallback_snapshot(self) -> RegimeSnapshot:
        """Return a neutral regime snapshot when detection fails."""
        return RegimeSnapshot(
            label="unknown",
            regime_id=-1,
            confidence=0.0,
            vix_level=0.0,
            vvix_level=0.0,
            skew_percentile=50.0,
            risk_bias="neutral",
            allocation_override=None,
        )

    def get_allocation_override(self, regime_id: int) -> dict[str, float] | None:
        """
        Get allocation override for a given regime.

        McMillan Rule: In spike regime (VIX > 30), shift 60% to treasuries
        and pause equity trading.
        """
        label = REGIME_LABELS.get(regime_id, "unknown")
        return REGIME_ALLOCATIONS.get(label)
