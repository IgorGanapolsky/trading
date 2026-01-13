"""
Tests for verify_stops_in_place.py - Stop-Loss Verification Script.

Tests the critical safety component that verifies all short option positions
have stop-loss orders in place before allowing new trades.

Author: AI Trading System
Date: January 13, 2026
"""

import json
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch


class TestIdentifyShortOptions:
    """Test identification of short option positions."""

    def test_identifies_short_put(self):
        """Short put options should be identified."""
        from scripts.verify_stops_in_place import identify_short_options

        positions = [
            {
                "symbol": "SOFI260206P00024000",  # SOFI Feb 6 2026 $24 Put
                "qty": -2.0,
                "side": "short",
                "asset_class": "option",
            }
        ]
        result = identify_short_options(positions)
        assert len(result) == 1
        assert result[0]["symbol"] == "SOFI260206P00024000"

    def test_identifies_short_call(self):
        """Short call options should be identified."""
        from scripts.verify_stops_in_place import identify_short_options

        positions = [
            {
                "symbol": "AAPL260117C00200000",  # AAPL Jan 17 2026 $200 Call
                "qty": -1.0,
                "side": "short",
                "asset_class": "option",
            }
        ]
        result = identify_short_options(positions)
        assert len(result) == 1

    def test_ignores_long_options(self):
        """Long option positions should not require stop verification."""
        from scripts.verify_stops_in_place import identify_short_options

        positions = [
            {
                "symbol": "SOFI260206P00020000",
                "qty": 2.0,  # Positive = long
                "side": "long",
                "asset_class": "option",
            }
        ]
        result = identify_short_options(positions)
        assert len(result) == 0

    def test_ignores_stock_positions(self):
        """Stock positions should not be identified as short options."""
        from scripts.verify_stops_in_place import identify_short_options

        positions = [
            {
                "symbol": "SOFI",  # Stock, not option
                "qty": -100.0,
                "side": "short",
                "asset_class": "stock",
            }
        ]
        result = identify_short_options(positions)
        assert len(result) == 0

    def test_mixed_positions(self):
        """Mixed portfolio should only identify short options."""
        from scripts.verify_stops_in_place import identify_short_options

        positions = [
            {"symbol": "SOFI", "qty": 24.0, "side": "long", "asset_class": "stock"},
            {"symbol": "SOFI260206P00024000", "qty": -2.0, "side": "short", "asset_class": "option"},
            {"symbol": "SOFI260206P00020000", "qty": 2.0, "side": "long", "asset_class": "option"},
        ]
        result = identify_short_options(positions)
        assert len(result) == 1
        assert result[0]["qty"] == -2.0


class TestCheckStopExists:
    """Test stop-loss order detection."""

    def test_finds_stop_order(self):
        """Should find matching stop order for symbol."""
        from scripts.verify_stops_in_place import check_stop_exists

        orders = [
            {
                "id": "order-123",
                "symbol": "SOFI260206P00024000",
                "side": "buy",
                "type": "stop",
                "stop_price": 1.50,
                "qty": 2.0,
            }
        ]
        result = check_stop_exists("SOFI260206P00024000", orders)
        assert result is not None
        assert result["stop_price"] == 1.50

    def test_finds_stop_limit_order(self):
        """Should also recognize stop_limit orders."""
        from scripts.verify_stops_in_place import check_stop_exists

        orders = [
            {
                "id": "order-456",
                "symbol": "AAPL260117C00200000",
                "side": "buy",
                "type": "stop_limit",
                "stop_price": 5.00,
                "qty": 1.0,
            }
        ]
        result = check_stop_exists("AAPL260117C00200000", orders)
        assert result is not None

    def test_finds_trailing_stop(self):
        """Should recognize trailing stop orders."""
        from scripts.verify_stops_in_place import check_stop_exists

        orders = [
            {
                "id": "order-789",
                "symbol": "SOFI260206P00024000",
                "side": "buy",
                "type": "trailing_stop",
                "stop_price": None,
                "qty": 2.0,
            }
        ]
        result = check_stop_exists("SOFI260206P00024000", orders)
        assert result is not None

    def test_returns_none_when_no_stop(self):
        """Should return None when no stop exists."""
        from scripts.verify_stops_in_place import check_stop_exists

        orders = [
            {
                "id": "order-111",
                "symbol": "SOFI260206P00024000",
                "side": "buy",
                "type": "limit",  # Not a stop order
                "stop_price": None,
                "qty": 2.0,
            }
        ]
        result = check_stop_exists("SOFI260206P00024000", orders)
        assert result is None

    def test_returns_none_wrong_symbol(self):
        """Should return None when stop is for different symbol."""
        from scripts.verify_stops_in_place import check_stop_exists

        orders = [
            {
                "id": "order-222",
                "symbol": "AAPL260117C00200000",
                "side": "buy",
                "type": "stop",
                "stop_price": 5.00,
                "qty": 1.0,
            }
        ]
        result = check_stop_exists("SOFI260206P00024000", orders)
        assert result is None


class TestVerifyAllStops:
    """Test complete verification workflow."""

    def test_all_stops_present(self):
        """All stops verified should return OK status."""
        from scripts.verify_stops_in_place import verify_all_stops

        positions = [
            {"symbol": "SOFI260206P00024000", "qty": -2.0, "side": "short", "asset_class": "option", "unrealized_pl": -7.0, "current_price": 0.67},
        ]
        orders = [
            {"id": "stop-1", "symbol": "SOFI260206P00024000", "side": "buy", "type": "stop", "stop_price": 1.50, "qty": 2.0},
        ]

        result = verify_all_stops(positions, orders)
        assert result["status"] == "OK"
        assert len(result["verified_stops"]) == 1
        assert len(result["missing_stops"]) == 0

    def test_missing_stops(self):
        """Missing stops should return MISSING_STOPS status."""
        from scripts.verify_stops_in_place import verify_all_stops

        positions = [
            {"symbol": "SOFI260206P00024000", "qty": -2.0, "side": "short", "asset_class": "option", "unrealized_pl": -7.0, "current_price": 0.67},
        ]
        orders = []  # No stop orders

        result = verify_all_stops(positions, orders)
        assert result["status"] == "MISSING_STOPS"
        assert len(result["missing_stops"]) == 1
        assert len(result["verified_stops"]) == 0

    def test_partial_stops(self):
        """Partial coverage should return MISSING_STOPS."""
        from scripts.verify_stops_in_place import verify_all_stops

        positions = [
            {"symbol": "SOFI260206P00024000", "qty": -2.0, "side": "short", "asset_class": "option", "unrealized_pl": -7.0, "current_price": 0.67},
            {"symbol": "F260117P00010000", "qty": -5.0, "side": "short", "asset_class": "option", "unrealized_pl": -10.0, "current_price": 0.30},
        ]
        orders = [
            {"id": "stop-1", "symbol": "SOFI260206P00024000", "side": "buy", "type": "stop", "stop_price": 1.50, "qty": 2.0},
            # No stop for F position
        ]

        result = verify_all_stops(positions, orders)
        assert result["status"] == "MISSING_STOPS"
        assert len(result["verified_stops"]) == 1
        assert len(result["missing_stops"]) == 1
        assert result["missing_stops"][0]["symbol"] == "F260117P00010000"

    def test_no_short_options(self):
        """No short options should return OK with empty lists."""
        from scripts.verify_stops_in_place import verify_all_stops

        positions = [
            {"symbol": "SOFI", "qty": 24.0, "side": "long", "asset_class": "stock", "unrealized_pl": 16.87, "current_price": 27.09},
        ]
        orders = []

        result = verify_all_stops(positions, orders)
        assert result["status"] == "OK"
        assert "No short option positions" in result["message"]


class TestSaveVerificationResult:
    """Test result persistence."""

    def test_saves_to_data_directory(self, tmp_path, monkeypatch):
        """Result should be saved to data/stop_verification.json."""
        from scripts.verify_stops_in_place import save_verification_result

        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()

        result = {
            "status": "OK",
            "message": "All stops verified",
            "timestamp": datetime.now().isoformat(),
        }

        save_verification_result(result)

        saved_file = tmp_path / "data" / "stop_verification.json"
        assert saved_file.exists()

        with open(saved_file) as f:
            saved = json.load(f)

        assert saved["status"] == "OK"


class TestMainFunction:
    """Test main CLI function."""

    @patch("scripts.verify_stops_in_place.get_alpaca_client")
    def test_main_no_client(self, mock_client):
        """When client unavailable, should warn but not fail."""
        mock_client.return_value = None

        from scripts.verify_stops_in_place import main
        exit_code = main()
        assert exit_code == 0  # Should not fail in sandbox

    @patch("scripts.verify_stops_in_place.get_alpaca_client")
    @patch("scripts.verify_stops_in_place.get_open_positions")
    @patch("scripts.verify_stops_in_place.get_open_orders")
    @patch("scripts.verify_stops_in_place.save_verification_result")
    @patch("scripts.verify_stops_in_place.update_system_state")
    def test_main_all_stops_ok(self, mock_state, mock_save, mock_orders, mock_positions, mock_client):
        """When all stops present, should return 0."""
        mock_client.return_value = MagicMock()
        mock_positions.return_value = [
            {"symbol": "SOFI260206P00024000", "qty": -2.0, "side": "short", "asset_class": "option", "unrealized_pl": -7.0, "current_price": 0.67},
        ]
        mock_orders.return_value = [
            {"id": "stop-1", "symbol": "SOFI260206P00024000", "side": "buy", "type": "stop", "stop_price": 1.50, "qty": 2.0},
        ]

        from scripts.verify_stops_in_place import main
        exit_code = main()
        assert exit_code == 0

    @patch("scripts.verify_stops_in_place.get_alpaca_client")
    @patch("scripts.verify_stops_in_place.get_open_positions")
    @patch("scripts.verify_stops_in_place.get_open_orders")
    @patch("scripts.verify_stops_in_place.save_verification_result")
    @patch("scripts.verify_stops_in_place.update_system_state")
    def test_main_missing_stops_blocks(self, mock_state, mock_save, mock_orders, mock_positions, mock_client):
        """When stops missing, should return 1 to block trading."""
        mock_client.return_value = MagicMock()
        mock_positions.return_value = [
            {"symbol": "SOFI260206P00024000", "qty": -2.0, "side": "short", "asset_class": "option", "unrealized_pl": -7.0, "current_price": 0.67},
        ]
        mock_orders.return_value = []  # No stop orders

        from scripts.verify_stops_in_place import main
        exit_code = main()
        assert exit_code == 1  # Should block


class TestPhilTownRule1Compliance:
    """Verify script enforces Phil Town Rule #1: Don't Lose Money."""

    def test_rule_1_in_docstring(self):
        """Script should document Rule #1 compliance."""
        from scripts import verify_stops_in_place
        assert "Phil Town Rule #1" in verify_stops_in_place.__doc__
        assert "Don't Lose Money" in verify_stops_in_place.__doc__

    def test_blocking_behavior_default(self):
        """Default behavior should BLOCK when stops missing."""
        from scripts.verify_stops_in_place import main
        # This is tested in test_main_missing_stops_blocks
        pass

    def test_warn_only_does_not_block(self):
        """--warn-only should not block even with missing stops."""
        import sys
        from unittest.mock import patch

        test_args = ["verify_stops_in_place.py", "--warn-only"]

        with patch.object(sys, 'argv', test_args):
            with patch("scripts.verify_stops_in_place.get_alpaca_client") as mock_client:
                with patch("scripts.verify_stops_in_place.get_open_positions") as mock_pos:
                    with patch("scripts.verify_stops_in_place.get_open_orders") as mock_ord:
                        with patch("scripts.verify_stops_in_place.save_verification_result"):
                            with patch("scripts.verify_stops_in_place.update_system_state"):
                                mock_client.return_value = MagicMock()
                                mock_pos.return_value = [
                                    {"symbol": "SOFI260206P00024000", "qty": -2.0, "side": "short", "asset_class": "option", "unrealized_pl": -7.0, "current_price": 0.67},
                                ]
                                mock_ord.return_value = []

                                from scripts.verify_stops_in_place import main
                                exit_code = main()
                                # With --warn-only, should not block
                                assert exit_code == 0
