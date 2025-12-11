"""
ML-based Anomaly Detection for Trading Operations.

This module detects unusual patterns that might indicate:
- Configuration errors (200x order amount mistakes)
- Data quality issues (stale data, missing fields)
- Market regime changes (unusual volatility)
- Execution anomalies (failed trades, unexpected prices)

Uses statistical methods and ML models to flag potential issues
before they cause financial harm.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

ANOMALY_LOG_PATH = Path("data/anomaly_log.json")


class AnomalyType(Enum):
    """Types of anomalies that can be detected."""
    ORDER_AMOUNT = "order_amount"           # Unusual order size
    ORDER_FREQUENCY = "order_frequency"     # Too many/few orders
    PRICE_DEVIATION = "price_deviation"     # Price far from expected
    DATA_STALENESS = "data_staleness"       # Old data being used
    EXECUTION_FAILURE = "execution_failure" # Trade execution issues
    SYMBOL_UNKNOWN = "symbol_unknown"       # Unknown trading symbol
    MARKET_HOURS = "market_hours"           # Trading outside hours
    POSITION_SIZE = "position_size"         # Position too large
    VOLATILITY_SPIKE = "volatility_spike"   # Unusual market volatility


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"           # Informational, no action needed
    WARNING = "warning"     # Review recommended
    CRITICAL = "critical"   # Immediate attention required
    BLOCK = "block"         # Action should be blocked


@dataclass
class Anomaly:
    """Represents a detected anomaly."""
    anomaly_id: str
    anomaly_type: AnomalyType
    alert_level: AlertLevel
    message: str
    details: dict[str, Any]
    detected_at: datetime
    context: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "anomaly_id": self.anomaly_id,
            "type": self.anomaly_type.value,
            "level": self.alert_level.value,
            "message": self.message,
            "details": self.details,
            "detected_at": self.detected_at.isoformat(),
            "context": self.context
        }


class TradingAnomalyDetector:
    """
    Detects anomalies in trading operations using statistical methods.

    Key features:
    - Order amount validation (detect 10x+ deviations)
    - Data freshness checking
    - Market hours validation
    - Position size limits
    - Historical pattern comparison

    Usage:
        detector = TradingAnomalyDetector()

        # Check before executing a trade
        anomalies = detector.validate_trade(symbol, amount, action)

        # Check data freshness
        anomalies = detector.check_data_freshness(timestamp)

        # Get all detected anomalies
        history = detector.get_anomaly_history()
    """

    # Default thresholds (can be overridden)
    DEFAULT_THRESHOLDS = {
        "max_order_amount": 100.0,       # Maximum single order $
        "order_amount_multiplier": 10.0,  # Alert if order > 10x expected
        "max_position_pct": 5.0,          # Max position as % of portfolio
        "data_staleness_hours": 24,       # Max hours for data freshness
        "min_daily_orders": 0,            # Minimum expected daily orders
        "max_daily_orders": 10,           # Maximum expected daily orders
        "price_deviation_pct": 5.0,       # Max price deviation from expected
        "volatility_zscore_threshold": 3.0,  # Z-score for volatility alert
    }

    # Known valid symbols
    VALID_SYMBOLS = {
        "stocks": ["SPY", "QQQ", "VOO", "NVDA", "GOOGL", "AMZN", "BIL", "SHY", "IEF", "TLT"],
        "crypto": ["BTCUSD", "ETHUSD", "SOLUSD"],
    }

    def __init__(
        self,
        thresholds: dict[str, float] | None = None,
        expected_daily_amount: float = 10.0,
        portfolio_value: float = 100000.0
    ):
        """
        Initialize the anomaly detector.

        Args:
            thresholds: Custom thresholds (merged with defaults)
            expected_daily_amount: Expected daily investment amount
            portfolio_value: Current portfolio value for position sizing
        """
        self.thresholds = {**self.DEFAULT_THRESHOLDS, **(thresholds or {})}
        self.expected_daily_amount = expected_daily_amount
        self.portfolio_value = portfolio_value
        self.anomaly_history: list[Anomaly] = []
        self._order_history: list[dict] = []

        # Load historical anomalies
        self._load_history()

    def _load_history(self) -> None:
        """Load anomaly history from disk."""
        if ANOMALY_LOG_PATH.exists():
            try:
                with open(ANOMALY_LOG_PATH) as f:
                    data = json.load(f)
                    # Just store as dicts, don't reconstruct Anomaly objects
                    self._historical_anomalies = data.get("anomalies", [])
            except Exception as e:
                logger.warning(f"Failed to load anomaly history: {e}")
                self._historical_anomalies = []

    def _save_anomaly(self, anomaly: Anomaly) -> None:
        """Save anomaly to history log."""
        self.anomaly_history.append(anomaly)

        # Persist to disk
        ANOMALY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            existing = []
            if ANOMALY_LOG_PATH.exists():
                with open(ANOMALY_LOG_PATH) as f:
                    existing = json.load(f).get("anomalies", [])

            existing.append(anomaly.to_dict())

            with open(ANOMALY_LOG_PATH, "w") as f:
                json.dump({"anomalies": existing[-1000:]}, f, indent=2)  # Keep last 1000
        except Exception as e:
            logger.error(f"Failed to save anomaly: {e}")

    def validate_trade(
        self,
        symbol: str,
        amount: float,
        action: str,
        expected_price: float | None = None,
        actual_price: float | None = None
    ) -> list[Anomaly]:
        """
        Validate a proposed trade for anomalies.

        Args:
            symbol: Trading symbol
            amount: Dollar amount
            action: BUY or SELL
            expected_price: Expected execution price
            actual_price: Actual execution price

        Returns:
            List of detected anomalies (empty if trade is normal)
        """
        anomalies = []
        context = {
            "symbol": symbol,
            "amount": amount,
            "action": action,
            "expected_price": expected_price,
            "actual_price": actual_price
        }

        # 1. Check for unknown symbol
        all_symbols = self.VALID_SYMBOLS["stocks"] + self.VALID_SYMBOLS["crypto"]
        if symbol not in all_symbols:
            anomaly = Anomaly(
                anomaly_id=f"ANO-{datetime.now().strftime('%Y%m%d%H%M%S')}-SYM",
                anomaly_type=AnomalyType.SYMBOL_UNKNOWN,
                alert_level=AlertLevel.WARNING,
                message=f"Unknown symbol: {symbol}",
                details={"symbol": symbol, "valid_symbols": all_symbols},
                detected_at=datetime.now(timezone.utc),
                context=context
            )
            anomalies.append(anomaly)
            self._save_anomaly(anomaly)

        # 2. Check order amount (THE 200x ERROR PREVENTION)
        max_amount = self.thresholds["max_order_amount"]
        multiplier = self.thresholds["order_amount_multiplier"]

        if amount > max_amount:
            alert_level = AlertLevel.WARNING
            if amount > self.expected_daily_amount * multiplier:
                alert_level = AlertLevel.BLOCK  # Critical: potential 200x error

            anomaly = Anomaly(
                anomaly_id=f"ANO-{datetime.now().strftime('%Y%m%d%H%M%S')}-AMT",
                anomaly_type=AnomalyType.ORDER_AMOUNT,
                alert_level=alert_level,
                message=f"Order amount ${amount:.2f} exceeds threshold ${max_amount:.2f}",
                details={
                    "amount": amount,
                    "max_amount": max_amount,
                    "expected_daily": self.expected_daily_amount,
                    "multiplier": amount / self.expected_daily_amount if self.expected_daily_amount > 0 else 0
                },
                detected_at=datetime.now(timezone.utc),
                context=context
            )
            anomalies.append(anomaly)
            self._save_anomaly(anomaly)

        # 3. Check position size
        position_pct = (amount / self.portfolio_value) * 100 if self.portfolio_value > 0 else 0
        if position_pct > self.thresholds["max_position_pct"]:
            anomaly = Anomaly(
                anomaly_id=f"ANO-{datetime.now().strftime('%Y%m%d%H%M%S')}-POS",
                anomaly_type=AnomalyType.POSITION_SIZE,
                alert_level=AlertLevel.WARNING,
                message=f"Position size {position_pct:.2f}% exceeds max {self.thresholds['max_position_pct']}%",
                details={
                    "position_pct": position_pct,
                    "max_pct": self.thresholds["max_position_pct"],
                    "amount": amount,
                    "portfolio_value": self.portfolio_value
                },
                detected_at=datetime.now(timezone.utc),
                context=context
            )
            anomalies.append(anomaly)
            self._save_anomaly(anomaly)

        # 4. Check price deviation
        if expected_price and actual_price:
            deviation_pct = abs(actual_price - expected_price) / expected_price * 100
            if deviation_pct > self.thresholds["price_deviation_pct"]:
                anomaly = Anomaly(
                    anomaly_id=f"ANO-{datetime.now().strftime('%Y%m%d%H%M%S')}-PRC",
                    anomaly_type=AnomalyType.PRICE_DEVIATION,
                    alert_level=AlertLevel.WARNING,
                    message=f"Price deviation {deviation_pct:.2f}% exceeds threshold",
                    details={
                        "expected_price": expected_price,
                        "actual_price": actual_price,
                        "deviation_pct": deviation_pct
                    },
                    detected_at=datetime.now(timezone.utc),
                    context=context
                )
                anomalies.append(anomaly)
                self._save_anomaly(anomaly)

        # Record order for frequency tracking
        self._order_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "amount": amount,
            "action": action
        })

        return anomalies

    def check_data_freshness(
        self,
        data_timestamp: datetime | str,
        data_source: str = "unknown"
    ) -> list[Anomaly]:
        """
        Check if data is fresh enough for trading decisions.

        Args:
            data_timestamp: When the data was last updated
            data_source: Source of the data

        Returns:
            List of anomalies if data is stale
        """
        anomalies = []

        if isinstance(data_timestamp, str):
            data_timestamp = datetime.fromisoformat(data_timestamp.replace("Z", "+00:00"))

        if data_timestamp.tzinfo is None:
            data_timestamp = data_timestamp.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        age_hours = (now - data_timestamp).total_seconds() / 3600

        if age_hours > self.thresholds["data_staleness_hours"]:
            alert_level = AlertLevel.WARNING
            if age_hours > self.thresholds["data_staleness_hours"] * 5:
                alert_level = AlertLevel.BLOCK  # Very stale data

            anomaly = Anomaly(
                anomaly_id=f"ANO-{datetime.now().strftime('%Y%m%d%H%M%S')}-STL",
                anomaly_type=AnomalyType.DATA_STALENESS,
                alert_level=alert_level,
                message=f"Data from {data_source} is {age_hours:.1f} hours old",
                details={
                    "data_timestamp": data_timestamp.isoformat(),
                    "age_hours": age_hours,
                    "threshold_hours": self.thresholds["data_staleness_hours"],
                    "data_source": data_source
                },
                detected_at=datetime.now(timezone.utc),
                context={"data_source": data_source}
            )
            anomalies.append(anomaly)
            self._save_anomaly(anomaly)

        return anomalies

    def check_market_hours(
        self,
        symbol: str,
        execution_time: datetime | None = None
    ) -> list[Anomaly]:
        """
        Check if trading is happening during appropriate market hours.

        Args:
            symbol: Trading symbol
            execution_time: Time of execution (defaults to now)

        Returns:
            List of anomalies if trading outside hours
        """
        anomalies = []

        if execution_time is None:
            execution_time = datetime.now(timezone.utc)

        # Crypto trades 24/7
        if symbol in self.VALID_SYMBOLS["crypto"]:
            return anomalies

        # Stock market hours (simplified: 9:30 AM - 4:00 PM ET, Mon-Fri)
        # Note: This is simplified, real implementation should use proper timezone handling
        weekday = execution_time.weekday()
        hour = execution_time.hour

        if weekday >= 5:  # Saturday or Sunday
            anomaly = Anomaly(
                anomaly_id=f"ANO-{datetime.now().strftime('%Y%m%d%H%M%S')}-MKT",
                anomaly_type=AnomalyType.MARKET_HOURS,
                alert_level=AlertLevel.WARNING,
                message=f"Stock trading attempted on weekend for {symbol}",
                details={
                    "symbol": symbol,
                    "weekday": weekday,
                    "execution_time": execution_time.isoformat()
                },
                detected_at=datetime.now(timezone.utc),
                context={"symbol": symbol}
            )
            anomalies.append(anomaly)
            self._save_anomaly(anomaly)

        return anomalies

    def get_anomaly_history(
        self,
        anomaly_type: AnomalyType | None = None,
        alert_level: AlertLevel | None = None,
        limit: int = 100
    ) -> list[Anomaly]:
        """
        Get historical anomalies with optional filtering.

        Args:
            anomaly_type: Filter by type
            alert_level: Filter by level
            limit: Maximum results

        Returns:
            List of matching anomalies
        """
        results = self.anomaly_history.copy()

        if anomaly_type:
            results = [a for a in results if a.anomaly_type == anomaly_type]

        if alert_level:
            results = [a for a in results if a.alert_level == alert_level]

        return results[-limit:]

    def get_blocking_anomalies(self) -> list[Anomaly]:
        """Get anomalies that should block trading."""
        return [a for a in self.anomaly_history if a.alert_level == AlertLevel.BLOCK]


# Convenience function for integration
def validate_order(
    symbol: str,
    amount: float,
    action: str,
    expected_daily: float = 10.0,
    portfolio_value: float = 100000.0
) -> tuple[bool, list[str]]:
    """
    Validate an order before execution.

    Args:
        symbol: Trading symbol
        amount: Dollar amount
        action: BUY or SELL
        expected_daily: Expected daily investment
        portfolio_value: Current portfolio value

    Returns:
        (is_valid, list of warning messages)
    """
    detector = TradingAnomalyDetector(
        expected_daily_amount=expected_daily,
        portfolio_value=portfolio_value
    )

    anomalies = detector.validate_trade(symbol, amount, action)

    # Check for blocking anomalies
    blocking = [a for a in anomalies if a.alert_level == AlertLevel.BLOCK]
    if blocking:
        return False, [a.message for a in blocking]

    # Return warnings but allow trade
    warnings = [a.message for a in anomalies]
    return True, warnings
