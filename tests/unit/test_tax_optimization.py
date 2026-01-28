"""Tests for tax_optimization.py - Tax compliance and optimization.

This module tests tax tracking including:
- Pattern Day Trader (PDT) rule compliance
- Wash sale rule detection
- Short-term vs long-term capital gains
- Tax-loss harvesting recommendations
- After-tax return calculations

CRITICAL for regulatory compliance and tax efficiency.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from src.utils.tax_optimization import (
    TaxLot,
    TaxEvent,
    TaxOptimizer,
    SHORT_TERM_TAX_RATE,
    LONG_TERM_TAX_RATE,
    LONG_TERM_THRESHOLD_DAYS,
    PDT_MINIMUM_EQUITY,
    PDT_DAY_TRADE_THRESHOLD,
    WASH_SALE_WINDOW_DAYS,
)


class TestTaxLot:
    """Tests for TaxLot dataclass."""

    def test_creates_tax_lot(self):
        """Should create a tax lot with all fields."""
        lot = TaxLot(
            symbol="SPY",
            quantity=10.0,
            cost_basis=6000.0,
            purchase_date=datetime(2026, 1, 1),
            trade_id="trade-123",
        )
        assert lot.symbol == "SPY"
        assert lot.quantity == 10.0
        assert lot.cost_basis == 6000.0


class TestTaxEvent:
    """Tests for TaxEvent dataclass."""

    def test_creates_short_term_gain(self):
        """Should create a short-term capital gain event."""
        event = TaxEvent(
            symbol="SPY",
            sale_date=datetime(2026, 1, 28),
            sale_price=650.0,
            quantity=10.0,
            cost_basis=6000.0,
            holding_period_days=30,
            gain_loss=500.0,
            is_long_term=False,
            is_wash_sale=False,
            wash_sale_adjustment=0.0,
            trade_id="trade-456",
        )
        assert event.gain_loss == 500.0
        assert event.is_long_term is False
        assert event.is_wash_sale is False

    def test_creates_long_term_gain(self):
        """Should create a long-term capital gain event."""
        event = TaxEvent(
            symbol="SPY",
            sale_date=datetime(2026, 1, 28),
            sale_price=700.0,
            quantity=10.0,
            cost_basis=6000.0,
            holding_period_days=400,
            gain_loss=1000.0,
            is_long_term=True,
            is_wash_sale=False,
            wash_sale_adjustment=0.0,
            trade_id="trade-789",
        )
        assert event.is_long_term is True
        assert event.holding_period_days >= LONG_TERM_THRESHOLD_DAYS


class TestTaxOptimizerBasics:
    """Tests for TaxOptimizer initialization and basic operations."""

    @pytest.fixture
    def optimizer(self):
        """Create a fresh TaxOptimizer."""
        return TaxOptimizer()

    def test_creates_optimizer(self, optimizer):
        """Should create an optimizer with empty state."""
        assert len(optimizer.tax_lots) == 0
        assert len(optimizer.tax_events) == 0
        assert len(optimizer.day_trades) == 0

    def test_record_trade_entry(self, optimizer):
        """Should record a trade entry as a tax lot."""
        optimizer.record_trade_entry(
            symbol="SPY",
            quantity=10.0,
            price=600.0,
            trade_date=datetime(2026, 1, 1),
            trade_id="trade-001",
        )
        assert len(optimizer.tax_lots["SPY"]) == 1
        assert optimizer.tax_lots["SPY"][0].cost_basis == 6000.0


class TestTradeExit:
    """Tests for record_trade_exit method."""

    @pytest.fixture
    def optimizer_with_lot(self):
        """Create optimizer with an existing tax lot."""
        optimizer = TaxOptimizer()
        optimizer.record_trade_entry(
            symbol="SPY",
            quantity=10.0,
            price=600.0,
            trade_date=datetime(2026, 1, 1),
            trade_id="trade-001",
        )
        return optimizer

    def test_short_term_gain(self, optimizer_with_lot):
        """Should calculate short-term gain correctly."""
        event = optimizer_with_lot.record_trade_exit(
            symbol="SPY",
            quantity=10.0,
            price=650.0,
            sale_date=datetime(2026, 2, 1),  # 31 days later
            trade_id="trade-002",
        )
        assert event.gain_loss == 500.0  # (650 - 600) * 10
        assert event.is_long_term is False
        assert event.holding_period_days == 31

    def test_long_term_gain(self, optimizer_with_lot):
        """Should calculate long-term gain for 365+ day hold."""
        event = optimizer_with_lot.record_trade_exit(
            symbol="SPY",
            quantity=10.0,
            price=700.0,
            sale_date=datetime(2027, 2, 1),  # 366+ days later
            trade_id="trade-002",
        )
        assert event.is_long_term is True
        assert event.holding_period_days >= 365

    def test_loss_event(self, optimizer_with_lot):
        """Should calculate loss correctly."""
        event = optimizer_with_lot.record_trade_exit(
            symbol="SPY",
            quantity=10.0,
            price=550.0,
            sale_date=datetime(2026, 2, 1),
            trade_id="trade-002",
        )
        assert event.gain_loss == -500.0  # (550 - 600) * 10

    def test_handles_missing_tax_lot(self):
        """Should handle exit for symbol with no tax lots."""
        optimizer = TaxOptimizer()
        event = optimizer.record_trade_exit(
            symbol="QQQ",
            quantity=10.0,
            price=500.0,
            sale_date=datetime(2026, 1, 28),
            trade_id="trade-001",
        )
        assert event.cost_basis == 0.0
        assert event.gain_loss == 0.0


class TestWashSaleRule:
    """Tests for wash sale detection."""

    @pytest.fixture
    def optimizer(self):
        return TaxOptimizer()

    def test_detects_wash_sale_within_30_days(self, optimizer):
        """Should detect wash sale when selling within 30 days of previous sale."""
        # First trade
        optimizer.record_trade_entry(
            symbol="SPY",
            quantity=10.0,
            price=600.0,
            trade_date=datetime(2026, 1, 1),
            trade_id="trade-001",
        )
        # First sale
        optimizer.record_trade_exit(
            symbol="SPY",
            quantity=10.0,
            price=550.0,
            sale_date=datetime(2026, 1, 15),
            trade_id="trade-002",
        )

        # Re-purchase
        optimizer.record_trade_entry(
            symbol="SPY",
            quantity=10.0,
            price=555.0,
            trade_date=datetime(2026, 1, 20),
            trade_id="trade-003",
        )

        # Second sale within 30 days of first
        event = optimizer.record_trade_exit(
            symbol="SPY",
            quantity=10.0,
            price=560.0,
            sale_date=datetime(2026, 1, 25),  # 10 days after first sale
            trade_id="trade-004",
        )
        assert event.is_wash_sale is True

    def test_no_wash_sale_after_30_days(self, optimizer):
        """Should not flag wash sale after 30 day window."""
        # First trade
        optimizer.record_trade_entry(
            symbol="SPY",
            quantity=10.0,
            price=600.0,
            trade_date=datetime(2026, 1, 1),
            trade_id="trade-001",
        )
        # First sale
        optimizer.record_trade_exit(
            symbol="SPY",
            quantity=10.0,
            price=550.0,
            sale_date=datetime(2026, 1, 15),
            trade_id="trade-002",
        )

        # Re-purchase after 30 days
        optimizer.record_trade_entry(
            symbol="SPY",
            quantity=10.0,
            price=560.0,
            trade_date=datetime(2026, 2, 20),
            trade_id="trade-003",
        )

        # Second sale - 45 days after first sale
        event = optimizer.record_trade_exit(
            symbol="SPY",
            quantity=10.0,
            price=580.0,
            sale_date=datetime(2026, 3, 1),
            trade_id="trade-004",
        )
        assert event.is_wash_sale is False


class TestPDTRule:
    """Tests for Pattern Day Trader rule compliance."""

    @pytest.fixture
    def optimizer(self):
        return TaxOptimizer()

    def test_no_pdt_with_zero_day_trades(self, optimizer):
        """Should not be PDT with no day trades."""
        status = optimizer.check_pdt_status(current_equity=30000.0)
        assert status["is_pdt"] is False
        assert status["day_trades_count"] == 0
        assert "Compliant" in status["status"]

    def test_pdt_triggered_at_4_day_trades(self, optimizer):
        """Should trigger PDT at 4+ day trades in 5 days."""
        # Simulate 4 day trades
        for i in range(4):
            optimizer.day_trades.append({
                "symbol": f"SPY{i}",
                "date": datetime.now().date(),
                "trade_id": f"trade-{i}",
            })

        # With low equity
        status = optimizer.check_pdt_status(current_equity=10000.0)
        assert status["is_pdt"] is True
        assert status["day_trades_count"] >= PDT_DAY_TRADE_THRESHOLD
        assert status["meets_equity_requirement"] is False
        assert "VIOLATION" in status["status"]

    def test_pdt_compliant_with_25k_equity(self, optimizer):
        """Should be compliant with $25k+ equity even with day trades."""
        # Simulate 4 day trades
        for i in range(4):
            optimizer.day_trades.append({
                "symbol": f"SPY{i}",
                "date": datetime.now().date(),
                "trade_id": f"trade-{i}",
            })

        status = optimizer.check_pdt_status(current_equity=30000.0)
        assert status["is_pdt"] is True
        assert status["meets_equity_requirement"] is True
        assert "VIOLATION" not in status["status"]


class TestAfterTaxReturns:
    """Tests for after-tax return calculations."""

    @pytest.fixture
    def optimizer(self):
        return TaxOptimizer()

    def test_empty_events_returns_zeros(self, optimizer):
        """Should return zeros for no tax events."""
        result = optimizer.calculate_after_tax_returns([])
        assert result["gross_return"] == 0.0
        assert result["tax_liability"] == 0.0
        assert result["tax_efficiency"] == 1.0

    def test_calculates_short_term_tax(self, optimizer):
        """Should calculate short-term tax at 37% rate."""
        # Add a short-term gain
        event = TaxEvent(
            symbol="SPY",
            sale_date=datetime.now(),
            sale_price=650.0,
            quantity=10.0,
            cost_basis=6000.0,
            holding_period_days=30,
            gain_loss=500.0,
            is_long_term=False,
            is_wash_sale=False,
            wash_sale_adjustment=0.0,
            trade_id="test",
        )
        optimizer.tax_events.append(event)

        result = optimizer.calculate_after_tax_returns([])
        assert result["short_term_gains"] == 500.0
        assert result["short_term_tax"] > 0
        # Tax should be approximately 37% of $500 = $185
        expected_tax = 500.0 * SHORT_TERM_TAX_RATE
        assert abs(result["short_term_tax"] - expected_tax) < 1.0

    def test_calculates_long_term_tax(self, optimizer):
        """Should calculate long-term tax at 20% rate."""
        event = TaxEvent(
            symbol="SPY",
            sale_date=datetime.now(),
            sale_price=700.0,
            quantity=10.0,
            cost_basis=6000.0,
            holding_period_days=400,
            gain_loss=1000.0,
            is_long_term=True,
            is_wash_sale=False,
            wash_sale_adjustment=0.0,
            trade_id="test",
        )
        optimizer.tax_events.append(event)

        result = optimizer.calculate_after_tax_returns([])
        assert result["long_term_gains"] == 1000.0
        # Tax should be 20% of $1000 = $200
        expected_tax = 1000.0 * LONG_TERM_TAX_RATE
        assert abs(result["long_term_tax"] - expected_tax) < 1.0


class TestTaxRecommendations:
    """Tests for tax optimization recommendations."""

    @pytest.fixture
    def optimizer(self):
        return TaxOptimizer()

    def test_pdt_warning_in_recommendations(self, optimizer):
        """Should include PDT warnings in recommendations."""
        # Trigger PDT status
        for i in range(4):
            optimizer.day_trades.append({
                "symbol": f"SPY{i}",
                "date": datetime.now().date(),
                "trade_id": f"trade-{i}",
            })

        recommendations = optimizer.get_tax_optimization_recommendations(
            current_equity=10000.0,
            open_positions=[],
        )
        assert any("PDT" in r for r in recommendations)

    def test_wash_sale_warning(self, optimizer):
        """Should warn about recent losses for wash sale avoidance."""
        # Add a recent loss
        event = TaxEvent(
            symbol="SPY",
            sale_date=datetime.now(),
            sale_price=550.0,
            quantity=10.0,
            cost_basis=6000.0,
            holding_period_days=30,
            gain_loss=-500.0,
            is_long_term=False,
            is_wash_sale=False,
            wash_sale_adjustment=0.0,
            trade_id="test",
        )
        optimizer.tax_events.append(event)

        recommendations = optimizer.get_tax_optimization_recommendations(
            current_equity=30000.0,
            open_positions=[],
        )
        assert any("WASH SALE" in r for r in recommendations)


class TestTaxAwareRewardAdjustment:
    """Tests for RL reward adjustment based on tax implications."""

    @pytest.fixture
    def optimizer(self):
        return TaxOptimizer()

    def test_penalizes_short_term_gains(self, optimizer):
        """Should reduce reward for short-term gains (higher tax)."""
        event = TaxEvent(
            symbol="SPY",
            sale_date=datetime.now(),
            sale_price=650.0,
            quantity=10.0,
            cost_basis=6000.0,
            holding_period_days=30,
            gain_loss=500.0,
            is_long_term=False,
            is_wash_sale=False,
            wash_sale_adjustment=0.0,
            trade_id="test",
        )

        base_reward = 100.0
        adjusted = optimizer.calculate_tax_aware_reward_adjustment(event, base_reward)
        assert adjusted < base_reward  # Should be penalized

    def test_rewards_long_term_gains(self, optimizer):
        """Should increase reward for long-term gains (lower tax)."""
        event = TaxEvent(
            symbol="SPY",
            sale_date=datetime.now(),
            sale_price=700.0,
            quantity=10.0,
            cost_basis=6000.0,
            holding_period_days=400,
            gain_loss=1000.0,
            is_long_term=True,
            is_wash_sale=False,
            wash_sale_adjustment=0.0,
            trade_id="test",
        )

        base_reward = 100.0
        adjusted = optimizer.calculate_tax_aware_reward_adjustment(event, base_reward)
        assert adjusted > base_reward  # Should be rewarded

    def test_penalizes_wash_sales(self, optimizer):
        """Should reduce reward for wash sale violations."""
        event = TaxEvent(
            symbol="SPY",
            sale_date=datetime.now(),
            sale_price=550.0,
            quantity=10.0,
            cost_basis=6000.0,
            holding_period_days=30,
            gain_loss=-500.0,
            is_long_term=False,
            is_wash_sale=True,
            wash_sale_adjustment=500.0,
            trade_id="test",
        )

        base_reward = 100.0
        adjusted = optimizer.calculate_tax_aware_reward_adjustment(event, base_reward)
        assert adjusted < base_reward  # Should be penalized


class TestTaxSummary:
    """Tests for tax summary generation."""

    @pytest.fixture
    def optimizer(self):
        return TaxOptimizer()

    def test_empty_summary(self, optimizer):
        """Should return zeros for empty tax history."""
        summary = optimizer.get_tax_summary()
        assert summary["total_trades"] == 0
        assert summary["net_gain_loss"] == 0.0
        assert summary["estimated_tax"] == 0.0

    def test_summary_with_events(self, optimizer):
        """Should summarize tax events correctly."""
        # Add some events
        optimizer.tax_events.append(TaxEvent(
            symbol="SPY",
            sale_date=datetime.now(),
            sale_price=650.0,
            quantity=10.0,
            cost_basis=6000.0,
            holding_period_days=30,
            gain_loss=500.0,
            is_long_term=False,
            is_wash_sale=False,
            wash_sale_adjustment=0.0,
            trade_id="test-1",
        ))
        optimizer.tax_events.append(TaxEvent(
            symbol="QQQ",
            sale_date=datetime.now(),
            sale_price=400.0,
            quantity=10.0,
            cost_basis=5000.0,
            holding_period_days=400,
            gain_loss=-1000.0,
            is_long_term=True,
            is_wash_sale=False,
            wash_sale_adjustment=0.0,
            trade_id="test-2",
        ))

        summary = optimizer.get_tax_summary()
        assert summary["total_trades"] == 2
        assert summary["short_term_count"] == 1
        assert summary["long_term_count"] == 1


class TestConstants:
    """Tests for tax constants."""

    def test_short_term_rate(self):
        """Short-term rate should be 37%."""
        assert SHORT_TERM_TAX_RATE == 0.37

    def test_long_term_rate(self):
        """Long-term rate should be 20%."""
        assert LONG_TERM_TAX_RATE == 0.20

    def test_long_term_threshold(self):
        """Long-term threshold should be 365 days."""
        assert LONG_TERM_THRESHOLD_DAYS == 365

    def test_pdt_minimum_equity(self):
        """PDT minimum equity should be $25,000."""
        assert PDT_MINIMUM_EQUITY == 25000.0

    def test_wash_sale_window(self):
        """Wash sale window should be 30 days."""
        assert WASH_SALE_WINDOW_DAYS == 30
