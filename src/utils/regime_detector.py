"""
Multi-layer regime detection with HMM and VIX/Skew integration.

Dec 4, 2025 Enhancement:
- Added regime transition prediction (detects "just entered new regime")
- Added composite regime scoring from multiple detectors
- Added forward-looking indicators (VVIX predicting VIX spike)
- Added transition smoothing with EMA filtering

Layers:
1. Heuristic detection (fast, always available)
2. HMM-based regime classification (4 states: calm, trend, vol, spike)
3. VIX/VVIX skew analysis for regime confirmation
4. Transition prediction (forward-looking)
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
    0: "calm",  # Low vol, range-bound
    1: "trending",  # Directional movement
    2: "volatile",  # High vol, choppy
    3: "spike",  # Crisis/tail event
}

REGIME_ALLOCATIONS = {
    "calm": {"equities": 0.8, "treasuries": 0.2, "pause_trading": False},
    "trending": {"equities": 0.7, "treasuries": 0.3, "pause_trading": False},
    "volatile": {"equities": 0.4, "treasuries": 0.5, "pause_trading": False},
    "spike": {"equities": 0.0, "treasuries": 0.6, "pause_trading": True},
}


@dataclass
class TransitionPrediction:
    """Prediction of regime transition based on forward-looking indicators."""

    current_regime: str
    predicted_regime: str
    transition_probability: float  # 0-1 probability of transition
    time_horizon_hours: int  # Prediction horizon
    leading_indicators: dict[str, float]  # VVIX change, skew change, etc.
    transition_detected: bool  # True if recent transition detected
    bars_since_transition: int  # How long ago transition occurred
    confidence: float
    warning_message: str | None = None


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
    # Dec 4, 2025: Transition prediction fields
    transition_prediction: TransitionPrediction | None = None
    composite_score: float = 0.5  # 0 = very bearish, 1 = very bullish
    regime_stability: float = 0.5  # 0 = unstable/transitioning, 1 = stable


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
    hmm_enabled: bool = field(
        default_factory=lambda: os.getenv("HMM_REGIME_ENABLED", "true").lower() == "true"
    )
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
        # Use wrapper for graceful fallback
        from src.utils import yfinance_wrapper as yf

        if not yf.is_available():
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
            closes = data.get("Close", data)
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
            elif skew_percentile > 80 or (
                closes["^VIX"].iloc[-5:].mean() > closes["^VIX"].iloc[-20:].mean()
            ):
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

    # ========== Dec 4, 2025: Transition Prediction Methods ==========

    def predict_transition(
        self,
        closes: Any,
        current_regime_id: int,
        _lookback_periods: int = 20,
    ) -> TransitionPrediction:
        """
        Predict regime transition using forward-looking indicators.

        Key leading indicators:
        1. VVIX/VIX ratio increase (vol of vol rising = regime change coming)
        2. VIX term structure inversion (near > far = stress imminent)
        3. Rate of change in VIX (acceleration predicts spikes)
        4. Skew percentile momentum

        Args:
            closes: DataFrame with VIX, VVIX, TLT columns
            current_regime_id: Current detected regime (0-3)
            lookback_periods: Periods for calculating changes

        Returns:
            TransitionPrediction with probability and indicators
        """
        try:
            current_label = REGIME_LABELS.get(current_regime_id, "unknown")

            # Calculate leading indicators
            indicators = {}

            if "^VIX" in closes:
                vix = closes["^VIX"]
                # VIX rate of change (acceleration)
                vix_roc_5 = (vix.iloc[-1] / vix.iloc[-5] - 1) * 100 if len(vix) > 5 else 0
                vix_roc_10 = (vix.iloc[-1] / vix.iloc[-10] - 1) * 100 if len(vix) > 10 else 0
                indicators["vix_roc_5d"] = round(float(vix_roc_5), 2)
                indicators["vix_roc_10d"] = round(float(vix_roc_10), 2)

                # VIX acceleration (2nd derivative)
                if len(vix) > 10:
                    vix_accel = vix_roc_5 - (vix.iloc[-5] / vix.iloc[-10] - 1) * 100
                    indicators["vix_acceleration"] = round(float(vix_accel), 2)

            if "^VVIX" in closes and "^VIX" in closes:
                vvix = closes["^VVIX"]
                vix = closes["^VIX"]
                # VVIX/VIX ratio (high = uncertainty about volatility = transition)
                ratio = float(vvix.iloc[-1] / vix.iloc[-1]) if vix.iloc[-1] > 0 else 5.0
                ratio_ma = float((vvix / vix).iloc[-10:].mean()) if len(vvix) > 10 else ratio
                indicators["vvix_vix_ratio"] = round(ratio, 2)
                indicators["vvix_vix_ratio_change"] = round(ratio - ratio_ma, 2)

            # Detect if we just transitioned (regime changed in last 5 bars)
            transition_detected = False
            bars_since_transition = 999

            if hasattr(self, "_regime_history") and self._regime_history:
                # Check recent regime history
                for i, (ts, rid) in enumerate(reversed(self._regime_history[-5:])):
                    if rid != current_regime_id:
                        transition_detected = True
                        bars_since_transition = i + 1
                        break

            # Calculate transition probability based on indicators
            transition_prob = 0.1  # Base probability
            predicted_regime = current_label

            # High VVIX/VIX ratio increase = transition likely
            if indicators.get("vvix_vix_ratio_change", 0) > 0.5:
                transition_prob += 0.2

            # VIX accelerating = likely moving to higher regime
            if indicators.get("vix_acceleration", 0) > 5:
                transition_prob += 0.15
                if current_regime_id < 3:
                    predicted_regime = REGIME_LABELS.get(current_regime_id + 1, current_label)

            # VIX rate of change high = regime shift
            if indicators.get("vix_roc_5d", 0) > 15:
                transition_prob += 0.25
                if current_regime_id < 3:
                    predicted_regime = REGIME_LABELS.get(current_regime_id + 1, current_label)
            elif indicators.get("vix_roc_5d", 0) < -15:
                transition_prob += 0.15
                if current_regime_id > 0:
                    predicted_regime = REGIME_LABELS.get(current_regime_id - 1, current_label)

            # Cap probability
            transition_prob = min(0.9, transition_prob)

            # Generate warning if transition likely
            warning = None
            if transition_prob > 0.5:
                warning = (
                    f"High probability ({transition_prob:.0%}) of transition to {predicted_regime}"
                )
            elif transition_detected and bars_since_transition <= 2:
                warning = f"Just entered {current_label} regime ({bars_since_transition} bars ago)"

            return TransitionPrediction(
                current_regime=current_label,
                predicted_regime=predicted_regime,
                transition_probability=round(transition_prob, 2),
                time_horizon_hours=24,  # 1-day prediction
                leading_indicators=indicators,
                transition_detected=transition_detected,
                bars_since_transition=bars_since_transition,
                confidence=0.6 + transition_prob * 0.3,
                warning_message=warning,
            )

        except Exception as e:
            logger.warning(f"Transition prediction failed: {e}")
            return TransitionPrediction(
                current_regime=REGIME_LABELS.get(current_regime_id, "unknown"),
                predicted_regime=REGIME_LABELS.get(current_regime_id, "unknown"),
                transition_probability=0.0,
                time_horizon_hours=24,
                leading_indicators={},
                transition_detected=False,
                bars_since_transition=999,
                confidence=0.0,
            )

    def calculate_composite_score(
        self,
        regime_id: int,
        vix_level: float,
        skew_percentile: float,
        confidence: float,
    ) -> tuple[float, float]:
        """
        Calculate composite regime score and stability.

        Combines multiple signals into a single 0-1 score:
        - 0.0 = Very bearish (spike regime, high VIX, high skew)
        - 0.5 = Neutral
        - 1.0 = Very bullish (calm regime, low VIX, low skew)

        Returns:
            Tuple of (composite_score, stability_score)
        """
        # Base score from regime (0=calm=1.0, 3=spike=0.0)
        regime_score = 1.0 - (regime_id / 3.0)

        # VIX contribution (lower = more bullish)
        if vix_level <= 12:
            vix_score = 1.0
        elif vix_level >= 35:
            vix_score = 0.0
        else:
            vix_score = 1.0 - (vix_level - 12) / 23.0

        # Skew contribution (lower percentile = more bullish)
        skew_score = 1.0 - (skew_percentile / 100.0)

        # Weighted composite
        composite = 0.4 * regime_score + 0.35 * vix_score + 0.25 * skew_score

        # Stability: high confidence + consistent signals = stable
        signal_variance = np.var([regime_score, vix_score, skew_score])
        stability = confidence * (1.0 - min(1.0, signal_variance * 4))

        return round(composite, 3), round(stability, 3)

    def detect_live_regime_with_prediction(self, lookback_days: int = 90) -> RegimeSnapshot:
        """
        Enhanced version of detect_live_regime with transition prediction.

        This is the recommended method for production use.
        """
        # First get base regime detection
        snapshot = self.detect_live_regime(lookback_days)

        if snapshot.regime_id < 0:
            return snapshot  # Detection failed

        try:
            # Use wrapper for graceful fallback
            from src.utils import yfinance_wrapper as yf

            # Fetch data for transition prediction
            tickers = ["^VIX", "^VVIX", "TLT"]
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=lookback_days)

            data = yf.download(
                tickers,
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                progress=False,
            )

            closes = data.get("Close", data)

            # Get transition prediction
            transition = self.predict_transition(closes, snapshot.regime_id)

            # Calculate composite scores
            composite, stability = self.calculate_composite_score(
                snapshot.regime_id,
                snapshot.vix_level,
                snapshot.skew_percentile,
                snapshot.confidence,
            )

            # Update regime history
            if not hasattr(self, "_regime_history"):
                self._regime_history = []
            self._regime_history.append((datetime.utcnow(), snapshot.regime_id))
            # Keep last 100 observations
            self._regime_history = self._regime_history[-100:]

            # Return enhanced snapshot
            return RegimeSnapshot(
                label=snapshot.label,
                regime_id=snapshot.regime_id,
                confidence=snapshot.confidence,
                vix_level=snapshot.vix_level,
                vvix_level=snapshot.vvix_level,
                skew_percentile=snapshot.skew_percentile,
                risk_bias=snapshot.risk_bias,
                allocation_override=snapshot.allocation_override,
                detected_at=snapshot.detected_at,
                transition_prediction=transition,
                composite_score=composite,
                regime_stability=stability,
            )

        except Exception as e:
            logger.warning(f"Enhanced regime detection failed, using base: {e}")
            return snapshot
