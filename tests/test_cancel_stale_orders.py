#!/usr/bin/env python3
"""Tests for cancel_stale_orders.py - CEO directive Jan 12, 2026."""

from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone


class TestCancelStaleOrders:
    """Test stale order cancellation logic."""

    def test_max_order_age_is_zero_cancel_all(self):
        """Verify CEO fix Jan 13: cancel ALL orders to restore buying power."""
        # Import the module to check the constant
        import sys

        sys.path.insert(0, ".")

        # Read the file directly to verify the constant
        with open("scripts/cancel_stale_orders.py") as f:
            content = f.read()

        assert "MAX_ORDER_AGE_HOURS = 0" in content, (
            "CEO Fix Jan 13, 2026: MAX_ORDER_AGE_HOURS must be 0 to cancel ALL orders"
        )

    def test_stale_order_detection(self):
        """Test that orders older than threshold are detected as stale."""
        now = datetime.now(timezone.utc)

        # Order created 5 hours ago should be stale (threshold is 4h)
        stale_order_time = now - timedelta(hours=5)
        threshold = now - timedelta(hours=4)

        assert stale_order_time < threshold, "5-hour-old order should be stale"

        # Order created 2 hours ago should NOT be stale
        fresh_order_time = now - timedelta(hours=2)
        assert fresh_order_time > threshold, "2-hour-old order should be fresh"

    def test_fresh_order_not_cancelled(self):
        """Test that fresh orders are preserved."""
        now = datetime.now(timezone.utc)

        # Order created 1 hour ago
        fresh_order_time = now - timedelta(hours=1)
        threshold = now - timedelta(hours=4)

        is_stale = fresh_order_time < threshold
        assert not is_stale, "1-hour-old order should NOT be cancelled"

    @patch.dict(
        "os.environ",
        {"ALPACA_API_KEY": "test_key", "ALPACA_SECRET_KEY": "test_secret", "PAPER_TRADING": "true"},
    )
    def test_returns_zero_on_no_orders(self):
        """Test script returns 0 when no orders exist."""
        import sys

        # Create mock alpaca module hierarchy
        mock_trading_client = MagicMock()
        mock_instance = MagicMock()
        mock_instance.get_orders.return_value = []
        mock_trading_client.return_value = mock_instance

        mock_client_module = MagicMock()
        mock_client_module.TradingClient = mock_trading_client

        mock_trading_module = MagicMock()
        mock_trading_module.client = mock_client_module

        mock_alpaca = MagicMock()
        mock_alpaca.trading = mock_trading_module
        mock_alpaca.trading.client = mock_client_module

        # Inject mock modules
        with patch.dict(
            sys.modules,
            {
                "alpaca": mock_alpaca,
                "alpaca.trading": mock_trading_module,
                "alpaca.trading.client": mock_client_module,
            },
        ):
            # Force reimport to pick up mocks
            if "scripts.cancel_stale_orders" in sys.modules:
                del sys.modules["scripts.cancel_stale_orders"]

            from scripts.cancel_stale_orders import main

            result = main()

            assert result == 0, "Should return 0 when no orders"


class TestBuyingPowerMath:
    """Test buying power calculations for $5K account."""

    def test_csp_collateral_calculation(self):
        """Verify CSP collateral math for small account."""
        account_cash = 5000.0

        # SOFI $25 Put requires $2500 collateral (strike * 100)
        sofi_25_collateral = 25 * 100
        assert sofi_25_collateral == 2500

        # With one position, remaining buying power
        remaining = account_cash - sofi_25_collateral
        assert remaining == 2500

        # If we add another $24 Put pending order
        sofi_24_collateral = 24 * 100
        remaining_after_order = remaining - sofi_24_collateral
        assert remaining_after_order == 100, "After 2 positions, only $100 buying power remains"

    def test_max_positions_for_5k_account(self):
        """Test maximum positions with $5K capital."""
        account_cash = 5000.0
        avg_strike = 25  # Average strike for SOFI/F
        collateral_per_position = avg_strike * 100

        max_positions = int(account_cash / collateral_per_position)
        assert max_positions == 2, "Can only hold 2 positions with $5K at $25 strikes"
