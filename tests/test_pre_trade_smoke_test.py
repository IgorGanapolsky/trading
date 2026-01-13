#!/usr/bin/env python3
"""
Tests for Pre-Trade Smoke Tests

Tests the smoke test functionality that validates Alpaca connection health
before trading operations. Uses mocking to avoid actual API calls.

Created: 2026-01-13
Reason: Add coverage for src/safety/pre_trade_smoke_test.py
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# Create mock alpaca module if not installed
def setup_alpaca_mock():
    """Setup mock alpaca module for testing without alpaca-py installed."""
    mock_alpaca = MagicMock()
    mock_trading = MagicMock()
    mock_client = MagicMock()

    mock_alpaca.trading = mock_trading
    mock_trading.client = mock_client

    sys.modules["alpaca"] = mock_alpaca
    sys.modules["alpaca.trading"] = mock_trading
    sys.modules["alpaca.trading.client"] = mock_client

    return mock_client


class TestSmokeTestResult:
    """Test the SmokeTestResult dataclass defaults (fail-safe)."""

    def test_import_successful(self):
        """Verify SmokeTestResult can be imported."""
        from src.safety.pre_trade_smoke_test import SmokeTestResult

        assert SmokeTestResult is not None

    def test_defaults_are_fail_safe(self):
        """All boolean defaults should be False (fail-safe behavior)."""
        from src.safety.pre_trade_smoke_test import SmokeTestResult

        result = SmokeTestResult()

        # All tests should default to failed (False)
        assert result.alpaca_connected is False
        assert result.account_readable is False
        assert result.positions_readable is False
        assert result.buying_power_valid is False
        assert result.equity_valid is False
        assert result.all_passed is False
        assert result.passed is False

    def test_numeric_defaults_are_zero(self):
        """Numeric values should default to 0."""
        from src.safety.pre_trade_smoke_test import SmokeTestResult

        result = SmokeTestResult()

        assert result.buying_power == 0.0
        assert result.equity == 0.0
        assert result.positions_count == 0
        assert result.cash == 0.0

    def test_error_lists_default_empty(self):
        """Error and warning lists should default to empty."""
        from src.safety.pre_trade_smoke_test import SmokeTestResult

        result = SmokeTestResult()

        assert result.errors == []
        assert result.warnings == []


class TestRunSmokeTestsSuccess:
    """Test run_smoke_tests when everything passes."""

    def test_all_tests_pass(self):
        """Smoke tests pass when Alpaca is healthy."""
        # Setup mock alpaca module
        mock_client_module = setup_alpaca_mock()

        # Setup mock account
        mock_account = MagicMock()
        mock_account.equity = "10000.00"
        mock_account.buying_power = "5000.00"
        mock_account.cash = "5000.00"
        mock_account.status = "ACTIVE"

        # Setup mock client instance
        mock_client = MagicMock()
        mock_client.get_account.return_value = mock_account
        mock_client.get_all_positions.return_value = []
        mock_client_module.TradingClient = MagicMock(return_value=mock_client)

        with patch(
            "src.utils.alpaca_client.get_alpaca_credentials"
        ) as mock_get_creds:
            mock_get_creds.return_value = ("test_api_key", "test_secret_key")

            with patch.dict(os.environ, {"PAPER_TRADING": "true"}):
                # Import after mocking
                from src.safety.pre_trade_smoke_test import run_smoke_tests

                result = run_smoke_tests()

        assert result.all_passed is True
        assert result.passed is True
        assert result.alpaca_connected is True
        assert result.account_readable is True
        assert result.positions_readable is True
        assert result.buying_power_valid is True
        assert result.equity_valid is True
        assert result.equity == 10000.00
        assert result.buying_power == 5000.00
        assert result.cash == 5000.00
        assert len(result.errors) == 0

    def test_with_existing_positions(self):
        """Smoke tests pass when account has positions."""
        mock_client_module = setup_alpaca_mock()

        mock_account = MagicMock()
        mock_account.equity = "15000.00"
        mock_account.buying_power = "3000.00"
        mock_account.cash = "3000.00"
        mock_account.status = "ACTIVE"

        # Create mock positions
        mock_position1 = MagicMock()
        mock_position2 = MagicMock()

        mock_client = MagicMock()
        mock_client.get_account.return_value = mock_account
        mock_client.get_all_positions.return_value = [mock_position1, mock_position2]
        mock_client_module.TradingClient = MagicMock(return_value=mock_client)

        with patch(
            "src.utils.alpaca_client.get_alpaca_credentials"
        ) as mock_get_creds:
            mock_get_creds.return_value = ("test_api_key", "test_secret_key")

            with patch.dict(os.environ, {"PAPER_TRADING": "true"}):
                from src.safety.pre_trade_smoke_test import run_smoke_tests

                result = run_smoke_tests()

        assert result.all_passed is True
        assert result.positions_count == 2


class TestRunSmokeTestsMissingCredentials:
    """Test run_smoke_tests when credentials are missing."""

    @patch("src.utils.alpaca_client.get_alpaca_credentials")
    def test_missing_api_key(self, mock_get_creds):
        """Smoke tests fail when API key is missing."""
        from src.safety.pre_trade_smoke_test import run_smoke_tests

        mock_get_creds.return_value = (None, "test_secret_key")

        result = run_smoke_tests()

        assert result.all_passed is False
        assert result.alpaca_connected is False
        assert len(result.errors) == 1
        assert "ALPACA_API_KEY not set" in result.errors[0]

    @patch("src.utils.alpaca_client.get_alpaca_credentials")
    def test_missing_secret_key(self, mock_get_creds):
        """Smoke tests fail when secret key is missing."""
        from src.safety.pre_trade_smoke_test import run_smoke_tests

        mock_get_creds.return_value = ("test_api_key", None)

        result = run_smoke_tests()

        assert result.all_passed is False
        assert result.alpaca_connected is False
        assert len(result.errors) == 1
        assert "ALPACA_SECRET_KEY not set" in result.errors[0]

    @patch("src.utils.alpaca_client.get_alpaca_credentials")
    def test_missing_both_keys(self, mock_get_creds):
        """Smoke tests fail when both keys are missing."""
        from src.safety.pre_trade_smoke_test import run_smoke_tests

        mock_get_creds.return_value = (None, None)

        result = run_smoke_tests()

        assert result.all_passed is False
        assert len(result.errors) >= 1
        # First error should be about API key
        assert "ALPACA_API_KEY not set" in result.errors[0]


class TestRunSmokeTestsConnectionFailure:
    """Test run_smoke_tests when Alpaca connection fails."""

    def test_connection_exception(self):
        """Smoke tests fail gracefully when Alpaca is down."""
        mock_client_module = setup_alpaca_mock()

        # Make TradingClient raise an exception
        mock_client_module.TradingClient = MagicMock(
            side_effect=Exception("Connection refused")
        )

        with patch(
            "src.utils.alpaca_client.get_alpaca_credentials"
        ) as mock_get_creds:
            mock_get_creds.return_value = ("test_api_key", "test_secret_key")

            with patch.dict(os.environ, {"PAPER_TRADING": "true"}):
                from src.safety.pre_trade_smoke_test import run_smoke_tests

                result = run_smoke_tests()

        assert result.all_passed is False
        assert result.alpaca_connected is False
        assert len(result.errors) == 1
        assert "Alpaca connection failed" in result.errors[0]

    def test_timeout_exception(self):
        """Smoke tests fail gracefully on timeout."""
        mock_client_module = setup_alpaca_mock()

        mock_client_module.TradingClient = MagicMock(
            side_effect=Exception("Request timeout")
        )

        with patch(
            "src.utils.alpaca_client.get_alpaca_credentials"
        ) as mock_get_creds:
            mock_get_creds.return_value = ("test_api_key", "test_secret_key")

            with patch.dict(os.environ, {"PAPER_TRADING": "true"}):
                from src.safety.pre_trade_smoke_test import run_smoke_tests

                result = run_smoke_tests()

        assert result.all_passed is False
        assert result.alpaca_connected is False
        assert "Request timeout" in result.errors[0]


class TestRunSmokeTestsAccountFailure:
    """Test run_smoke_tests when account operations fail."""

    def test_account_not_readable(self):
        """Smoke tests fail when account cannot be read."""
        mock_client_module = setup_alpaca_mock()

        mock_client = MagicMock()
        mock_client.get_account.side_effect = Exception("Account access denied")
        mock_client_module.TradingClient = MagicMock(return_value=mock_client)

        with patch(
            "src.utils.alpaca_client.get_alpaca_credentials"
        ) as mock_get_creds:
            mock_get_creds.return_value = ("test_api_key", "test_secret_key")

            with patch.dict(os.environ, {"PAPER_TRADING": "true"}):
                from src.safety.pre_trade_smoke_test import run_smoke_tests

                result = run_smoke_tests()

        assert result.all_passed is False
        assert result.alpaca_connected is True
        assert result.account_readable is False
        assert len(result.errors) == 1
        assert "Cannot read account" in result.errors[0]

    def test_account_not_active(self):
        """Smoke tests fail when account status is not ACTIVE."""
        mock_client_module = setup_alpaca_mock()

        mock_account = MagicMock()
        mock_account.equity = "10000.00"
        mock_account.buying_power = "5000.00"
        mock_account.cash = "5000.00"
        mock_account.status = "SUSPENDED"

        mock_client = MagicMock()
        mock_client.get_account.return_value = mock_account
        mock_client_module.TradingClient = MagicMock(return_value=mock_client)

        with patch(
            "src.utils.alpaca_client.get_alpaca_credentials"
        ) as mock_get_creds:
            mock_get_creds.return_value = ("test_api_key", "test_secret_key")

            with patch.dict(os.environ, {"PAPER_TRADING": "true"}):
                from src.safety.pre_trade_smoke_test import run_smoke_tests

                result = run_smoke_tests()

        assert result.all_passed is False
        assert result.account_readable is True
        assert len(result.errors) >= 1
        assert any("SUSPENDED" in error for error in result.errors)


class TestRunSmokeTestsPositionsFailure:
    """Test run_smoke_tests when position operations fail."""

    def test_positions_not_readable(self):
        """Smoke tests fail when positions cannot be read."""
        mock_client_module = setup_alpaca_mock()

        mock_account = MagicMock()
        mock_account.equity = "10000.00"
        mock_account.buying_power = "5000.00"
        mock_account.cash = "5000.00"
        mock_account.status = "ACTIVE"

        mock_client = MagicMock()
        mock_client.get_account.return_value = mock_account
        mock_client.get_all_positions.side_effect = Exception("Position API error")
        mock_client_module.TradingClient = MagicMock(return_value=mock_client)

        with patch(
            "src.utils.alpaca_client.get_alpaca_credentials"
        ) as mock_get_creds:
            mock_get_creds.return_value = ("test_api_key", "test_secret_key")

            with patch.dict(os.environ, {"PAPER_TRADING": "true"}):
                from src.safety.pre_trade_smoke_test import run_smoke_tests

                result = run_smoke_tests()

        assert result.all_passed is False
        assert result.alpaca_connected is True
        assert result.account_readable is True
        assert result.positions_readable is False
        assert any("Cannot read positions" in error for error in result.errors)


class TestRunSmokeTestsBuyingPower:
    """Test run_smoke_tests buying power validation logic."""

    def test_zero_buying_power_high_equity(self):
        """Smoke tests pass when buying power is 0 but equity is high (fully invested)."""
        mock_client_module = setup_alpaca_mock()

        mock_account = MagicMock()
        mock_account.equity = "5000.00"  # High equity (> $1000)
        mock_account.buying_power = "0.00"  # Zero buying power
        mock_account.cash = "0.00"
        mock_account.status = "ACTIVE"

        mock_client = MagicMock()
        mock_client.get_account.return_value = mock_account
        mock_client.get_all_positions.return_value = []
        mock_client_module.TradingClient = MagicMock(return_value=mock_client)

        with patch(
            "src.utils.alpaca_client.get_alpaca_credentials"
        ) as mock_get_creds:
            mock_get_creds.return_value = ("test_api_key", "test_secret_key")

            with patch.dict(os.environ, {"PAPER_TRADING": "true"}):
                from src.safety.pre_trade_smoke_test import run_smoke_tests

                result = run_smoke_tests()

        # Should pass because equity > $1000 (fully invested scenario)
        assert result.all_passed is True
        assert result.buying_power_valid is True
        assert result.equity_valid is True
        # Should have a warning about being fully invested
        assert len(result.warnings) >= 1
        assert any("fully invested" in warning for warning in result.warnings)

    def test_zero_buying_power_low_equity(self):
        """Smoke tests fail when both buying power and equity are too low."""
        mock_client_module = setup_alpaca_mock()

        mock_account = MagicMock()
        mock_account.equity = "500.00"  # Low equity (< $1000)
        mock_account.buying_power = "0.00"  # Zero buying power
        mock_account.cash = "0.00"
        mock_account.status = "ACTIVE"

        mock_client = MagicMock()
        mock_client.get_account.return_value = mock_account
        mock_client.get_all_positions.return_value = []
        mock_client_module.TradingClient = MagicMock(return_value=mock_client)

        with patch(
            "src.utils.alpaca_client.get_alpaca_credentials"
        ) as mock_get_creds:
            mock_get_creds.return_value = ("test_api_key", "test_secret_key")

            with patch.dict(os.environ, {"PAPER_TRADING": "true"}):
                from src.safety.pre_trade_smoke_test import run_smoke_tests

                result = run_smoke_tests()

        # Should fail because buying power is 0 AND equity < $1000
        assert result.all_passed is False
        assert result.buying_power_valid is False
        assert len(result.errors) >= 1

    def test_zero_equity(self):
        """Smoke tests fail when equity is zero."""
        mock_client_module = setup_alpaca_mock()

        mock_account = MagicMock()
        mock_account.equity = "0.00"
        mock_account.buying_power = "0.00"
        mock_account.cash = "0.00"
        mock_account.status = "ACTIVE"

        mock_client = MagicMock()
        mock_client.get_account.return_value = mock_account
        mock_client.get_all_positions.return_value = []
        mock_client_module.TradingClient = MagicMock(return_value=mock_client)

        with patch(
            "src.utils.alpaca_client.get_alpaca_credentials"
        ) as mock_get_creds:
            mock_get_creds.return_value = ("test_api_key", "test_secret_key")

            with patch.dict(os.environ, {"PAPER_TRADING": "true"}):
                from src.safety.pre_trade_smoke_test import run_smoke_tests

                result = run_smoke_tests()

        assert result.all_passed is False
        assert result.equity_valid is False
        assert any("Equity is $0" in error for error in result.errors)


class TestBlockTradingOnFailure:
    """Test the block_trading_on_failure function."""

    @patch("src.safety.pre_trade_smoke_test.run_smoke_tests")
    def test_returns_true_on_failure(self, mock_run_tests):
        """Should return True (block trading) when tests fail."""
        from src.safety.pre_trade_smoke_test import (
            SmokeTestResult,
            block_trading_on_failure,
        )

        mock_result = SmokeTestResult()
        mock_result.all_passed = False
        mock_run_tests.return_value = mock_result

        should_block = block_trading_on_failure()

        assert should_block is True

    @patch("src.safety.pre_trade_smoke_test.run_smoke_tests")
    def test_returns_false_on_success(self, mock_run_tests):
        """Should return False (allow trading) when tests pass."""
        from src.safety.pre_trade_smoke_test import (
            SmokeTestResult,
            block_trading_on_failure,
        )

        mock_result = SmokeTestResult()
        mock_result.all_passed = True
        mock_run_tests.return_value = mock_result

        should_block = block_trading_on_failure()

        assert should_block is False


class TestPaperTradingMode:
    """Test paper trading mode detection."""

    def test_paper_mode_true(self):
        """TradingClient should be called with paper=True when PAPER_TRADING=true."""
        mock_client_module = setup_alpaca_mock()

        mock_account = MagicMock()
        mock_account.equity = "10000.00"
        mock_account.buying_power = "5000.00"
        mock_account.cash = "5000.00"
        mock_account.status = "ACTIVE"

        mock_client = MagicMock()
        mock_client.get_account.return_value = mock_account
        mock_client.get_all_positions.return_value = []

        mock_trading_client = MagicMock(return_value=mock_client)
        mock_client_module.TradingClient = mock_trading_client

        with patch(
            "src.utils.alpaca_client.get_alpaca_credentials"
        ) as mock_get_creds:
            mock_get_creds.return_value = ("test_api_key", "test_secret_key")

            with patch.dict(os.environ, {"PAPER_TRADING": "true"}):
                from src.safety.pre_trade_smoke_test import run_smoke_tests

                run_smoke_tests()

        mock_trading_client.assert_called_once_with(
            "test_api_key", "test_secret_key", paper=True
        )

    def test_paper_mode_false(self):
        """TradingClient should be called with paper=False when PAPER_TRADING=false."""
        mock_client_module = setup_alpaca_mock()

        mock_account = MagicMock()
        mock_account.equity = "10000.00"
        mock_account.buying_power = "5000.00"
        mock_account.cash = "5000.00"
        mock_account.status = "ACTIVE"

        mock_client = MagicMock()
        mock_client.get_account.return_value = mock_account
        mock_client.get_all_positions.return_value = []

        mock_trading_client = MagicMock(return_value=mock_client)
        mock_client_module.TradingClient = mock_trading_client

        with patch(
            "src.utils.alpaca_client.get_alpaca_credentials"
        ) as mock_get_creds:
            mock_get_creds.return_value = ("test_api_key", "test_secret_key")

            with patch.dict(os.environ, {"PAPER_TRADING": "false"}):
                from src.safety.pre_trade_smoke_test import run_smoke_tests

                run_smoke_tests()

        mock_trading_client.assert_called_once_with(
            "test_api_key", "test_secret_key", paper=False
        )


class TestBackwardsCompatibility:
    """Test backwards compatibility features."""

    def test_passed_alias_for_all_passed(self):
        """SmokeTestResult.passed should be alias for all_passed."""
        from src.safety.pre_trade_smoke_test import SmokeTestResult

        result = SmokeTestResult()
        result.all_passed = True
        result.passed = True

        # Both should work
        assert result.all_passed is True
        assert result.passed is True


# =============================================================================
# Run Tests
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
