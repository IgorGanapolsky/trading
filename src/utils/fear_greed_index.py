"""
Crypto Fear & Greed Index Integration

This module fetches the Fear & Greed Index from Alternative.me API
and provides trading signals based on backtested strategies.

BACKTEST RESULTS (Source: Nasdaq, Bitcoin Magazine):
- Fear & Greed Strategy: 1,145% ROI
- Buy & Hold: 1,046% ROI
- Strategy: Buy when index < 25 (extreme fear), sell when > 75 (extreme greed)

Usage:
    from src.utils.fear_greed_index import FearGreedIndex

    fgi = FearGreedIndex()
    signal = fgi.get_trading_signal()
    # Returns: {"value": 25, "classification": "Extreme Fear", "action": "BUY", "size_multiplier": 1.5}
"""

import logging
from datetime import datetime
from typing import Any

import requests

logger = logging.getLogger(__name__)


class FearGreedIndex:
    """
    Crypto Fear & Greed Index from Alternative.me

    The index analyzes emotions and sentiments from different sources:
    - Volatility (25%)
    - Market Momentum/Volume (25%)
    - Social Media (15%)
    - Surveys (15%)
    - Dominance (10%)
    - Trends (10%)

    Scale:
    - 0-24: Extreme Fear (BUY signal)
    - 25-44: Fear (Accumulate)
    - 45-55: Neutral (Hold)
    - 56-75: Greed (Reduce)
    - 76-100: Extreme Greed (SELL signal)
    """

    API_URL = "https://api.alternative.me/fng/"

    # Thresholds based on backtested strategies
    EXTREME_FEAR_THRESHOLD = 25  # Strong buy signal
    FEAR_THRESHOLD = 40  # Mild buy signal
    GREED_THRESHOLD = 60  # Mild sell signal
    EXTREME_GREED_THRESHOLD = 75  # Strong sell signal

    def __init__(self):
        """Initialize Fear & Greed Index fetcher."""
        self.last_value: int | None = None
        self.last_classification: str | None = None
        self.last_update: datetime | None = None
        self.cache_duration_minutes = 60  # Cache for 1 hour

    def fetch_current(self) -> dict[str, Any]:
        """
        Fetch current Fear & Greed Index value.

        Returns:
            Dict with value, classification, and timestamp
        """
        try:
            response = requests.get(self.API_URL, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("data"):
                fng_data = data["data"][0]
                self.last_value = int(fng_data["value"])
                self.last_classification = fng_data["value_classification"]
                self.last_update = datetime.now()

                logger.info(f"Fear & Greed Index: {self.last_value} ({self.last_classification})")

                return {
                    "value": self.last_value,
                    "classification": self.last_classification,
                    "timestamp": fng_data.get("timestamp"),
                    "time_until_update": fng_data.get("time_until_update"),
                    "success": True,
                }
            else:
                logger.warning("No data in Fear & Greed API response")
                return {"success": False, "error": "No data in response"}

        except requests.RequestException as e:
            logger.error(f"Failed to fetch Fear & Greed Index: {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Error processing Fear & Greed data: {e}")
            return {"success": False, "error": str(e)}

    def get_trading_signal(self) -> dict[str, Any]:
        """
        Get trading signal based on Fear & Greed Index.

        Based on backtested strategy from Nasdaq/Bitcoin Magazine:
        - Buy 1% of capital when index <= 20
        - Sell 1% of holdings when index >= 80

        Enhanced with size multipliers for DCA adjustment.

        Returns:
            Dict with action, size_multiplier, and reasoning
        """
        data = self.fetch_current()

        if not data.get("success"):
            # Fallback to neutral if API fails
            return {
                "action": "HOLD",
                "size_multiplier": 1.0,
                "value": None,
                "classification": "Unknown",
                "reasoning": f"API unavailable: {data.get('error', 'Unknown error')}",
                "confidence": 0.0,
            }

        value = data["value"]
        classification = data["classification"]

        # Determine action and size based on thresholds
        if value <= self.EXTREME_FEAR_THRESHOLD:
            # EXTREME FEAR = Strong buy signal
            # Backtested: This is when you want maximum exposure
            action = "BUY"
            size_multiplier = 1.5  # Buy 50% more than normal
            confidence = 0.9
            reasoning = f"Extreme Fear ({value}) - Historical buying opportunity. Backtest shows 1,145% ROI."

        elif value <= self.FEAR_THRESHOLD:
            # FEAR = Mild buy signal
            action = "BUY"
            size_multiplier = 1.25  # Buy 25% more than normal
            confidence = 0.7
            reasoning = f"Fear ({value}) - Good accumulation zone."

        elif value <= self.GREED_THRESHOLD:
            # NEUTRAL = Hold, normal DCA
            action = "HOLD"
            size_multiplier = 1.0
            confidence = 0.5
            reasoning = f"Neutral ({value}) - Continue normal DCA."

        elif value <= self.EXTREME_GREED_THRESHOLD:
            # GREED = Reduce buying
            action = "REDUCE"
            size_multiplier = 0.5  # Buy 50% less than normal
            confidence = 0.7
            reasoning = f"Greed ({value}) - Consider reducing exposure."

        else:
            # EXTREME GREED = Sell signal
            action = "SELL"
            size_multiplier = 0.0  # Don't buy, consider selling
            confidence = 0.9
            reasoning = f"Extreme Greed ({value}) - Historical selling opportunity. Take profits."

        return {
            "action": action,
            "size_multiplier": size_multiplier,
            "value": value,
            "classification": classification,
            "reasoning": reasoning,
            "confidence": confidence,
        }

    def get_historical(self, days: int = 30) -> list[dict]:
        """
        Fetch historical Fear & Greed Index values.

        Args:
            days: Number of days of history to fetch (max 100)

        Returns:
            List of historical values
        """
        try:
            response = requests.get(f"{self.API_URL}?limit={min(days, 100)}", timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("data"):
                return [
                    {
                        "value": int(d["value"]),
                        "classification": d["value_classification"],
                        "timestamp": d["timestamp"],
                    }
                    for d in data["data"]
                ]
            return []

        except Exception as e:
            logger.error(f"Failed to fetch historical Fear & Greed data: {e}")
            return []

    def calculate_trend(self, days: int = 7) -> dict[str, Any]:
        """
        Calculate Fear & Greed Index trend over specified days.

        Returns:
            Dict with trend direction, average, and extremes
        """
        history = self.get_historical(days)

        if not history:
            return {"trend": "unknown", "error": "No historical data"}

        values = [h["value"] for h in history]

        avg_value = sum(values) / len(values)
        current = values[0] if values else 50
        oldest = values[-1] if values else 50

        change = current - oldest

        if change > 10:
            trend = "improving"  # Moving from fear to greed
        elif change < -10:
            trend = "deteriorating"  # Moving from greed to fear (buying opportunity forming)
        else:
            trend = "stable"

        return {
            "trend": trend,
            "current": current,
            "average": avg_value,
            "change": change,
            "min": min(values),
            "max": max(values),
            "days_analyzed": len(values),
        }


# Singleton instance for easy import
_fear_greed_instance: FearGreedIndex | None = None


def get_fear_greed_signal() -> dict[str, Any]:
    """
    Convenience function to get current Fear & Greed trading signal.

    Usage:
        from src.utils.fear_greed_index import get_fear_greed_signal
        signal = get_fear_greed_signal()
    """
    global _fear_greed_instance
    if _fear_greed_instance is None:
        _fear_greed_instance = FearGreedIndex()
    return _fear_greed_instance.get_trading_signal()


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)

    fgi = FearGreedIndex()

    print("=== Fear & Greed Index ===")
    signal = fgi.get_trading_signal()
    print(f"Value: {signal['value']}")
    print(f"Classification: {signal['classification']}")
    print(f"Action: {signal['action']}")
    print(f"Size Multiplier: {signal['size_multiplier']}")
    print(f"Reasoning: {signal['reasoning']}")

    print("\n=== 7-Day Trend ===")
    trend = fgi.calculate_trend(7)
    print(f"Trend: {trend['trend']}")
    print(f"Change: {trend.get('change', 'N/A')}")
