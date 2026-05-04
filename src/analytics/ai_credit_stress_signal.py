"""AI Credit Stress Signal Module"""

from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd


@dataclass
class AICreditStressSignal:
    """AI-driven credit stress signal analyzer"""

    def __init__(self, lookback_days: int = 252):
        self.lookback_days = lookback_days
        self.stress_threshold = 0.7  # Threshold for stress signal

    def calculate_signal(self, credit_data: pd.DataFrame) -> dict:
        """Calculate credit stress signal"""
        try:
            # Basic implementation - can be enhanced with ML models
            spreads = credit_data.get("spread", pd.Series())
            volumes = credit_data.get("volume", pd.Series())

            if spreads.empty or volumes.empty:
                return {
                    "signal": 0.0,
                    "stress_level": "LOW",
                    "confidence": 0.0,
                    "timestamp": datetime.now().isoformat(),
                }

            # Calculate stress indicators
            spread_zscore = (spreads - spreads.mean()) / spreads.std()
            volume_ratio = volumes / volumes.rolling(window=20).mean()

            # Combine indicators
            stress_signal = np.tanh(spread_zscore.iloc[-1] + (1 - volume_ratio.iloc[-1]))

            # Determine stress level
            if stress_signal > self.stress_threshold:
                stress_level = "HIGH"
            elif stress_signal > 0.3:
                stress_level = "MEDIUM"
            else:
                stress_level = "LOW"

            return {
                "signal": float(stress_signal),
                "stress_level": stress_level,
                "confidence": min(1.0, abs(stress_signal)),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            return {
                "signal": 0.0,
                "stress_level": "UNKNOWN",
                "confidence": 0.0,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def get_stress_factors(self, credit_data: pd.DataFrame) -> list[str]:
        """Identify key stress factors"""
        factors = []

        try:
            spreads = credit_data.get("spread", pd.Series())
            if not spreads.empty:
                recent_spread = spreads.iloc[-1]
                avg_spread = spreads.mean()

                if recent_spread > avg_spread * 1.5:
                    factors.append("Elevated credit spreads")

            volumes = credit_data.get("volume", pd.Series())
            if not volumes.empty:
                recent_volume = volumes.iloc[-1]
                avg_volume = volumes.mean()

                if recent_volume < avg_volume * 0.5:
                    factors.append("Reduced trading volume")

        except Exception:
            factors.append("Unable to analyze stress factors")

        return factors
