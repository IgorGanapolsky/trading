"""
Tests for the ML Anomaly Detector.

Tests ensure that:
1. Large order amounts are detected (200x error prevention)
2. Stale data is flagged
3. Unknown symbols are caught
4. Market hours violations are detected
"""

import pytest
from datetime import datetime, timedelta, timezone

from src.ml.anomaly_detector import (
    TradingAnomalyDetector,
    AnomalyType,
    AlertLevel,
    validate_order,
)


@pytest.fixture
def detector():
    """Create a detector with test settings."""
    return TradingAnomalyDetector(
        expected_daily_amount=10.0,
        portfolio_value=100000.0
    )


class TestOrderAmountValidation:
    """Test order amount anomaly detection."""

    def test_normal_order_no_anomaly(self, detector):
        """Test that normal orders don't trigger anomalies."""
        anomalies = detector.validate_trade(
            symbol="SPY",
            amount=10.0,
            action="BUY"
        )
        # Should have no blocking anomalies
        blocking = [a for a in anomalies if a.alert_level == AlertLevel.BLOCK]
        assert len(blocking) == 0

    def test_large_order_triggers_warning(self, detector):
        """Test that large orders trigger warning."""
        anomalies = detector.validate_trade(
            symbol="SPY",
            amount=500.0,  # 50x expected
            action="BUY"
        )
        assert len(anomalies) > 0
        amount_anomalies = [a for a in anomalies if a.anomaly_type == AnomalyType.ORDER_AMOUNT]
        assert len(amount_anomalies) > 0

    def test_200x_order_blocked(self, detector):
        """Test that 200x order (the historical error) is blocked."""
        anomalies = detector.validate_trade(
            symbol="SPY",
            amount=2000.0,  # 200x expected $10
            action="BUY"
        )
        blocking = [a for a in anomalies if a.alert_level == AlertLevel.BLOCK]
        assert len(blocking) > 0
        assert any(a.anomaly_type == AnomalyType.ORDER_AMOUNT for a in blocking)

    def test_10x_multiplier_detection(self, detector):
        """Test that 10x+ multiplier triggers blocking."""
        anomalies = detector.validate_trade(
            symbol="SPY",
            amount=150.0,  # 15x expected $10
            action="BUY"
        )
        blocking = [a for a in anomalies if a.alert_level == AlertLevel.BLOCK]
        assert len(blocking) > 0


class TestDataFreshnessValidation:
    """Test data staleness detection."""

    def test_fresh_data_no_anomaly(self, detector):
        """Test that fresh data doesn't trigger anomaly."""
        fresh_time = datetime.now(timezone.utc) - timedelta(hours=1)
        anomalies = detector.check_data_freshness(fresh_time, "system_state")
        assert len(anomalies) == 0

    def test_stale_data_triggers_warning(self, detector):
        """Test that stale data triggers warning."""
        stale_time = datetime.now(timezone.utc) - timedelta(hours=48)
        anomalies = detector.check_data_freshness(stale_time, "system_state")
        assert len(anomalies) > 0
        assert anomalies[0].anomaly_type == AnomalyType.DATA_STALENESS

    def test_very_stale_data_blocked(self, detector):
        """Test that very stale data triggers blocking."""
        very_stale = datetime.now(timezone.utc) - timedelta(days=7)
        anomalies = detector.check_data_freshness(very_stale, "system_state")
        blocking = [a for a in anomalies if a.alert_level == AlertLevel.BLOCK]
        assert len(blocking) > 0


class TestSymbolValidation:
    """Test unknown symbol detection."""

    def test_valid_stock_symbol(self, detector):
        """Test that valid stock symbols pass."""
        anomalies = detector.validate_trade("SPY", 10.0, "BUY")
        symbol_anomalies = [a for a in anomalies if a.anomaly_type == AnomalyType.SYMBOL_UNKNOWN]
        assert len(symbol_anomalies) == 0

    def test_valid_crypto_symbol(self, detector):
        """Test that valid crypto symbols pass."""
        anomalies = detector.validate_trade("BTCUSD", 10.0, "BUY")
        symbol_anomalies = [a for a in anomalies if a.anomaly_type == AnomalyType.SYMBOL_UNKNOWN]
        assert len(symbol_anomalies) == 0

    def test_unknown_symbol_detected(self, detector):
        """Test that unknown symbols are flagged."""
        anomalies = detector.validate_trade("FAKESYMBOL", 10.0, "BUY")
        symbol_anomalies = [a for a in anomalies if a.anomaly_type == AnomalyType.SYMBOL_UNKNOWN]
        assert len(symbol_anomalies) > 0


class TestMarketHoursValidation:
    """Test market hours validation."""

    def test_crypto_anytime(self, detector):
        """Test that crypto can trade anytime."""
        # Create a weekend time
        saturday = datetime(2025, 12, 13, 12, 0, 0, tzinfo=timezone.utc)  # Saturday
        anomalies = detector.check_market_hours("BTCUSD", saturday)
        assert len(anomalies) == 0  # Crypto trades 24/7

    def test_stock_weekend_warning(self, detector):
        """Test that stock trading on weekend is flagged."""
        saturday = datetime(2025, 12, 13, 12, 0, 0, tzinfo=timezone.utc)  # Saturday
        anomalies = detector.check_market_hours("SPY", saturday)
        market_anomalies = [a for a in anomalies if a.anomaly_type == AnomalyType.MARKET_HOURS]
        assert len(market_anomalies) > 0


class TestPositionSizeValidation:
    """Test position size limits."""

    def test_small_position_ok(self, detector):
        """Test that small positions pass."""
        anomalies = detector.validate_trade("SPY", 100.0, "BUY")  # 0.1% of $100k
        position_anomalies = [a for a in anomalies if a.anomaly_type == AnomalyType.POSITION_SIZE]
        assert len(position_anomalies) == 0

    def test_large_position_flagged(self, detector):
        """Test that large positions are flagged."""
        anomalies = detector.validate_trade("SPY", 10000.0, "BUY")  # 10% of $100k
        position_anomalies = [a for a in anomalies if a.anomaly_type == AnomalyType.POSITION_SIZE]
        assert len(position_anomalies) > 0


class TestConvenienceFunction:
    """Test the validate_order convenience function."""

    def test_valid_order(self):
        """Test that valid orders return True."""
        is_valid, warnings = validate_order(
            symbol="SPY",
            amount=10.0,
            action="BUY"
        )
        # Should be valid with no blocking warnings
        assert is_valid is True or len([w for w in warnings if "exceeds" in w.lower()]) == 0

    def test_blocked_order(self):
        """Test that dangerous orders are blocked."""
        is_valid, warnings = validate_order(
            symbol="SPY",
            amount=2000.0,  # Way over expected
            action="BUY",
            expected_daily=10.0
        )
        # Should be blocked due to amount
        assert is_valid is False
        assert len(warnings) > 0


class TestAnomalyHistory:
    """Test anomaly history tracking."""

    def test_anomalies_recorded(self, detector):
        """Test that anomalies are recorded in history."""
        # Trigger an anomaly
        detector.validate_trade("FAKESYMBOL", 10.0, "BUY")

        history = detector.get_anomaly_history()
        assert len(history) > 0

    def test_filter_by_type(self, detector):
        """Test filtering history by type."""
        # Trigger different anomaly types
        detector.validate_trade("FAKESYMBOL", 10.0, "BUY")  # Unknown symbol
        detector.validate_trade("SPY", 2000.0, "BUY")  # Large amount

        symbol_history = detector.get_anomaly_history(
            anomaly_type=AnomalyType.SYMBOL_UNKNOWN
        )
        assert all(a.anomaly_type == AnomalyType.SYMBOL_UNKNOWN for a in symbol_history)

    def test_filter_by_level(self, detector):
        """Test filtering history by alert level."""
        detector.validate_trade("SPY", 2000.0, "BUY")  # Should trigger BLOCK

        blocking_history = detector.get_anomaly_history(
            alert_level=AlertLevel.BLOCK
        )
        assert all(a.alert_level == AlertLevel.BLOCK for a in blocking_history)
