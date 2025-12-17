"""
Execution Edge Case Tests for Trading System.

Critical gap identified Dec 11, 2025: Limited execution testing.
These tests cover edge cases in order execution.

Tests:
1. Partial fill handling
2. Order rejection recovery
3. Orphaned position detection
4. Order state reconciliation
5. Broker error handling
6. Market hours edge cases
"""

import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

import pytest


class OrderStatus(Enum):
    """Order status enum."""

    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass
class MockOrder:
    """Mock order for testing."""

    id: str
    symbol: str
    side: str  # "buy" or "sell"
    qty: float
    filled_qty: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    reject_reason: str | None = None
    avg_fill_price: float | None = None


class TestPartialFillHandling:
    """Test handling of partial order fills."""

    def test_partial_fill_detection(self):
        """Detect when order is partially filled."""
        order = MockOrder(
            id="ORD001",
            symbol="SPY",
            side="buy",
            qty=100.0,
            filled_qty=50.0,
            status=OrderStatus.PARTIALLY_FILLED,
        )

        is_partial = order.filled_qty > 0 and order.filled_qty < order.qty
        assert is_partial, "Should detect partial fill"

        fill_percentage = (order.filled_qty / order.qty) * 100
        assert fill_percentage == 50.0, "Should calculate fill percentage"

    def test_partial_fill_position_tracking(self):
        """Track position correctly with partial fills."""
        positions = {}

        def update_position(symbol: str, filled_qty: float, avg_price: float):
            if symbol not in positions:
                positions[symbol] = {"qty": 0, "avg_price": 0, "cost_basis": 0}

            pos = positions[symbol]
            new_cost = filled_qty * avg_price
            total_cost = pos["cost_basis"] + new_cost
            total_qty = pos["qty"] + filled_qty

            pos["qty"] = total_qty
            pos["cost_basis"] = total_cost
            pos["avg_price"] = total_cost / total_qty if total_qty > 0 else 0

        # Simulate partial fills
        update_position("SPY", 50, 450.0)  # First fill: 50 @ $450
        update_position("SPY", 30, 451.0)  # Second fill: 30 @ $451
        update_position("SPY", 20, 449.0)  # Third fill: 20 @ $449

        assert positions["SPY"]["qty"] == 100
        expected_avg = (50 * 450 + 30 * 451 + 20 * 449) / 100
        assert abs(positions["SPY"]["avg_price"] - expected_avg) < 0.01

    def test_partial_fill_timeout_handling(self):
        """Handle orders that remain partially filled."""
        order = MockOrder(
            id="ORD002",
            symbol="QQQ",
            side="buy",
            qty=100.0,
            filled_qty=60.0,
            status=OrderStatus.PARTIALLY_FILLED,
        )

        # Simulate timeout after 30 minutes
        order_age_minutes = 45
        partial_fill_timeout_minutes = 30

        should_cancel_remaining = (
            order.status == OrderStatus.PARTIALLY_FILLED
            and order_age_minutes > partial_fill_timeout_minutes
        )

        assert should_cancel_remaining, "Should cancel remaining after timeout"

        # Cancel remaining quantity
        remaining_qty = order.qty - order.filled_qty
        assert remaining_qty == 40.0, "Should calculate remaining quantity"


class TestOrderRejectionRecovery:
    """Test recovery from order rejections."""

    def test_rejection_reason_parsing(self):
        """Parse and categorize rejection reasons."""
        rejection_reasons = {
            "insufficient_buying_power": "insufficient",
            "pattern_day_trader_restriction": "pdt",
            "market_closed": "market_hours",
            "invalid_symbol": "invalid",
            "price_outside_range": "price",
            "unknown_error": "unknown",
        }

        def categorize_rejection(reason: str) -> str:
            for keyword, category in [
                ("insufficient", "insufficient"),
                ("buying_power", "insufficient"),
                ("pattern_day", "pdt"),
                ("market_closed", "market_hours"),
                ("invalid", "invalid"),
                ("price", "price"),
            ]:
                if keyword in reason.lower():
                    return category
            return "unknown"

        for reason, expected_category in rejection_reasons.items():
            category = categorize_rejection(reason)
            assert category == expected_category, f"Wrong category for {reason}"

    def test_rejection_retry_logic(self):
        """Test retry logic for recoverable rejections."""
        retryable_reasons = {"market_closed", "insufficient_liquidity", "timeout"}

        def should_retry(reject_reason: str) -> bool:
            return any(retryable in reject_reason.lower() for retryable in retryable_reasons)

        assert should_retry("market_closed"), "Should retry market_closed"
        assert not should_retry("insufficient_buying_power"), "Should not retry insufficient funds"

    def test_rejection_callback_execution(self):
        """Execute callbacks on rejection."""
        callbacks_executed = []

        def on_rejection(order: MockOrder):
            callbacks_executed.append(
                {
                    "order_id": order.id,
                    "reason": order.reject_reason,
                    "time": time.time(),
                }
            )

        order = MockOrder(
            id="ORD003",
            symbol="AAPL",
            side="buy",
            qty=10.0,
            status=OrderStatus.REJECTED,
            reject_reason="insufficient_buying_power",
        )

        on_rejection(order)

        assert len(callbacks_executed) == 1
        assert callbacks_executed[0]["order_id"] == "ORD003"


class TestOrphanedPositionDetection:
    """Test detection of orphaned positions."""

    def test_detect_orphaned_position(self):
        """Detect position without corresponding order."""
        orders = {
            "ORD001": MockOrder(
                id="ORD001", symbol="SPY", side="buy", qty=100, status=OrderStatus.FILLED
            ),
            "ORD002": MockOrder(
                id="ORD002", symbol="QQQ", side="buy", qty=50, status=OrderStatus.FILLED
            ),
        }

        positions = {
            "SPY": {"qty": 100, "source_order": "ORD001"},
            "QQQ": {"qty": 50, "source_order": "ORD002"},
            "AAPL": {"qty": 25, "source_order": None},  # Orphaned!
        }

        orphaned = []
        for symbol, pos in positions.items():
            if pos.get("source_order") is None or pos["source_order"] not in orders:
                orphaned.append(symbol)

        assert "AAPL" in orphaned, "Should detect orphaned AAPL position"
        assert len(orphaned) == 1, "Only AAPL should be orphaned"

    def test_reconcile_positions_with_broker(self):
        """Reconcile local positions with broker."""
        local_positions = {
            "SPY": 100,
            "QQQ": 50,
            "AAPL": 25,
        }

        broker_positions = {
            "SPY": 100,  # Matches
            "QQQ": 45,  # Mismatch!
            # AAPL missing at broker
        }

        discrepancies = []

        for symbol, local_qty in local_positions.items():
            broker_qty = broker_positions.get(symbol, 0)
            if local_qty != broker_qty:
                discrepancies.append(
                    {
                        "symbol": symbol,
                        "local": local_qty,
                        "broker": broker_qty,
                        "diff": local_qty - broker_qty,
                    }
                )

        assert len(discrepancies) == 2, "Should find 2 discrepancies"
        assert any(d["symbol"] == "QQQ" for d in discrepancies)
        assert any(d["symbol"] == "AAPL" for d in discrepancies)


class TestOrderStateReconciliation:
    """Test order state reconciliation."""

    def test_stale_order_detection(self):
        """Detect orders with stale status."""
        orders = [
            {
                "id": "ORD001",
                "status": "submitted",
                "submitted_at": time.time() - 3600,
            },  # 1 hour old
            {"id": "ORD002", "status": "submitted", "submitted_at": time.time() - 60},  # 1 min old
            {
                "id": "ORD003",
                "status": "filled",
                "submitted_at": time.time() - 3600,
            },  # Old but filled
        ]

        stale_threshold_seconds = 300  # 5 minutes

        stale_orders = [
            o
            for o in orders
            if o["status"] == "submitted"
            and (time.time() - o["submitted_at"]) > stale_threshold_seconds
        ]

        assert len(stale_orders) == 1
        assert stale_orders[0]["id"] == "ORD001"

    def test_order_status_transition_validation(self):
        """Validate order status transitions are valid."""
        valid_transitions = {
            OrderStatus.PENDING: {
                OrderStatus.SUBMITTED,
                OrderStatus.REJECTED,
                OrderStatus.CANCELLED,
            },
            OrderStatus.SUBMITTED: {
                OrderStatus.PARTIALLY_FILLED,
                OrderStatus.FILLED,
                OrderStatus.REJECTED,
                OrderStatus.CANCELLED,
                OrderStatus.EXPIRED,
            },
            OrderStatus.PARTIALLY_FILLED: {OrderStatus.FILLED, OrderStatus.CANCELLED},
            OrderStatus.FILLED: set(),  # Terminal state
            OrderStatus.REJECTED: set(),  # Terminal state
            OrderStatus.CANCELLED: set(),  # Terminal state
            OrderStatus.EXPIRED: set(),  # Terminal state
        }

        def is_valid_transition(from_status: OrderStatus, to_status: OrderStatus) -> bool:
            return to_status in valid_transitions.get(from_status, set())

        assert is_valid_transition(OrderStatus.PENDING, OrderStatus.SUBMITTED)
        assert is_valid_transition(OrderStatus.SUBMITTED, OrderStatus.FILLED)
        assert not is_valid_transition(OrderStatus.FILLED, OrderStatus.PENDING)  # Invalid
        assert not is_valid_transition(OrderStatus.REJECTED, OrderStatus.FILLED)  # Invalid


class TestBrokerErrorHandling:
    """Test handling of broker-specific errors."""

    def test_alpaca_error_codes(self):
        """Handle Alpaca-specific error codes."""
        alpaca_errors = {
            40010001: {"type": "insufficient_balance", "retryable": False},
            40010002: {"type": "invalid_symbol", "retryable": False},
            40310000: {"type": "forbidden", "retryable": False},
            42910000: {"type": "rate_limit", "retryable": True},
            50000000: {"type": "internal_error", "retryable": True},
        }

        def handle_alpaca_error(error_code: int) -> dict:
            error_info = alpaca_errors.get(error_code, {"type": "unknown", "retryable": False})
            return error_info

        assert handle_alpaca_error(42910000)["retryable"], "Rate limit should be retryable"
        assert not handle_alpaca_error(40010001)["retryable"], "Insufficient balance not retryable"

    def test_connection_error_recovery(self):
        """Recover from broker connection errors."""
        connection_attempts = [0]
        max_attempts = 3

        def connect_with_retry():
            connection_attempts[0] += 1
            if connection_attempts[0] < 3:
                raise ConnectionError("Connection refused")
            return True

        result = None
        for attempt in range(max_attempts):
            try:
                result = connect_with_retry()
                break
            except ConnectionError:
                if attempt < max_attempts - 1:
                    time.sleep(0.01)  # Brief delay

        assert result is True, "Should eventually connect"
        assert connection_attempts[0] == 3, "Should take 3 attempts"


class TestMarketHoursEdgeCases:
    """Test edge cases around market hours."""

    def test_pre_market_order_handling(self):
        """Handle orders submitted pre-market."""

        def is_pre_market(current_hour: int) -> bool:
            # Pre-market: 4:00 AM - 9:30 AM ET
            return 4 <= current_hour < 9 or (current_hour == 9 and True)  # Simplified

        def can_execute_in_pre_market(order_type: str) -> bool:
            # Only limit orders in pre-market
            return order_type == "limit"

        assert is_pre_market(5), "5 AM is pre-market"
        assert can_execute_in_pre_market("limit"), "Limit orders allowed pre-market"
        assert not can_execute_in_pre_market("market"), "Market orders not allowed pre-market"

    def test_after_hours_order_handling(self):
        """Handle orders submitted after hours."""

        def is_after_hours(current_hour: int) -> bool:
            # After hours: 4:00 PM - 8:00 PM ET
            return 16 <= current_hour < 20

        def should_queue_for_open(submit_hour: int, order_type: str) -> bool:
            return is_after_hours(submit_hour) and order_type == "market"

        assert should_queue_for_open(17, "market"), "Market order at 5 PM should queue"
        assert not should_queue_for_open(17, "limit"), "Limit order at 5 PM can execute"

    def test_market_holiday_handling(self):
        """Handle orders on market holidays."""
        holidays_2025 = [
            datetime(2025, 1, 1),  # New Year's
            datetime(2025, 1, 20),  # MLK Day
            datetime(2025, 2, 17),  # Presidents Day
            datetime(2025, 4, 18),  # Good Friday
            datetime(2025, 5, 26),  # Memorial Day
            datetime(2025, 7, 4),  # Independence Day
            datetime(2025, 9, 1),  # Labor Day
            datetime(2025, 11, 27),  # Thanksgiving
            datetime(2025, 12, 25),  # Christmas
        ]

        def is_holiday(date: datetime) -> bool:
            return date.date() in [h.date() for h in holidays_2025]

        test_date = datetime(2025, 12, 25)
        assert is_holiday(test_date), "Christmas should be a holiday"

        regular_date = datetime(2025, 12, 11)
        assert not is_holiday(regular_date), "Dec 11 should not be a holiday"


class TestOrderQuantityEdgeCases:
    """Test edge cases in order quantities."""

    def test_minimum_quantity_enforcement(self):
        """Enforce minimum order quantity."""
        min_notional = 1.0  # Alpaca minimum is $1

        def validate_order_size(qty: float, price: float) -> bool:
            notional = qty * price
            return notional >= min_notional

        assert validate_order_size(1, 450.0), "1 share of $450 stock should be valid"
        assert not validate_order_size(0.001, 450.0), "0.001 shares of $450 = $0.45 < $1"

    def test_fractional_share_handling(self):
        """Handle fractional share orders correctly."""

        def round_to_supported_precision(qty: float, max_decimals: int = 4) -> float:
            return round(qty, max_decimals)

        assert round_to_supported_precision(1.23456789) == 1.2346
        assert round_to_supported_precision(0.00001) == 0.0

    def test_lot_size_rounding(self):
        """Round to appropriate lot sizes for options."""

        def round_to_lot_size(qty: float, lot_size: int = 100) -> int:
            # Options contracts are in lots of 100
            return int(qty // lot_size) * lot_size

        assert round_to_lot_size(150) == 100, "150 should round down to 100"
        assert round_to_lot_size(250) == 200, "250 should round down to 200"
        assert round_to_lot_size(50) == 0, "50 should round down to 0"


class TestPriceEdgeCases:
    """Test edge cases in pricing."""

    def test_zero_price_rejection(self):
        """Reject orders with zero or negative price."""

        def validate_price(price: float) -> bool:
            return price > 0

        assert not validate_price(0), "Zero price should be invalid"
        assert not validate_price(-10), "Negative price should be invalid"
        assert validate_price(0.01), "Small positive price should be valid"

    def test_price_precision(self):
        """Validate price precision for different assets."""

        def validate_price_precision(price: float, tick_size: float = 0.01) -> float:
            # Round to nearest tick
            return round(price / tick_size) * tick_size

        assert validate_price_precision(450.123) == 450.12
        assert validate_price_precision(0.0001, 0.0001) == 0.0001  # Crypto precision

    def test_limit_price_reasonableness(self):
        """Check limit prices are reasonable."""

        def is_reasonable_limit_price(
            limit_price: float,
            current_price: float,
            max_deviation_pct: float = 10.0,
        ) -> bool:
            deviation = abs(limit_price - current_price) / current_price * 100
            return deviation <= max_deviation_pct

        assert is_reasonable_limit_price(455, 450, 10), "455 is within 10% of 450"
        assert not is_reasonable_limit_price(500, 450, 10), "500 is >10% from 450"


class TestSlippageEdgeCases:
    """Test slippage handling edge cases."""

    def test_slippage_exceeds_threshold(self):
        """Detect when slippage exceeds threshold."""
        expected_price = 450.0
        fill_price = 451.5
        max_slippage_bps = 100  # 1%

        actual_slippage_bps = abs(fill_price - expected_price) / expected_price * 10000
        slippage_exceeded = actual_slippage_bps > max_slippage_bps

        assert abs(actual_slippage_bps - 33.33) < 0.1, "Should be ~33 bps slippage"
        assert not slippage_exceeded, "33 bps should not exceed 100 bps threshold"

    def test_negative_slippage_handling(self):
        """Handle positive slippage (better than expected fill)."""
        expected_price = 450.0
        fill_price = 449.0  # Got a better price

        slippage = fill_price - expected_price
        assert slippage < 0, "Negative slippage means better fill"

        # Should still record this as a successful fill
        is_valid_fill = fill_price > 0
        assert is_valid_fill


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
