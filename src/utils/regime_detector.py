"""
Simple regime detection heuristics for routing strategies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RegimeDetector:
    """
    Maps microstructure features to coarse market regimes.
    """

    high_vol_threshold: float = 0.4
    trend_threshold: float = 0.03

    def detect(self, features: dict[str, Any]) -> dict[str, Any]:
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
