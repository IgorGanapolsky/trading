"""Tests for pre-trade smoke tests.

CRITICAL: These tests verify that smoke tests actually FAIL when they should.
A smoke test that always passes is useless and dangerous.

Created Dec 30, 2025 - Part of the test quality overhaul.
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from src.safety.pre_trade_smoke_test import SmokeTestResult, run_smoke_tests


def _alpaca_available():
    """Check if alpaca module is available."""
    try:
        import alpaca.trading.client  # noqa: F401

        return True
    except ImportError:
        return False


class TestSmokeTestResult:
    """Tests for SmokeTestResult dataclass defaults."""

    def test_defaults_are_fail_safe(self):
        """CRITICAL: All boolean defaults must be FALSE (fail-safe).

        If we forget to set a value, the test should FAIL, not pass.
        """
        result = SmokeTestResult()

        # All individual tests default to False (fail-safe)
        assert result.alpaca_connected is False
        assert result.account_readable is False
        assert result.positions_readable is False
        assert result.buying_power_valid is False
        assert result.equity_valid is False

        # Aggregate result defaults to False
        assert result.all_passed is False
        assert result.passed is False

    def test_numeric_defaults_are_zero(self):
        """Numeric values should default to zero."""
        result = SmokeTestResult()

        assert result.buying_power == 0.0
        assert result.equity == 0.0
        assert result.positions_count == 0
        assert result.cash == 0.0

    def test_errors_and_warnings_default_empty(self):
        """Error and warning lists should default to empty."""
        result = SmokeTestResult()

        assert result.errors == []
        assert result.warnings == []


class TestRunSmokeTests:
    """Tests for the run_smoke_tests function."""

    def test_fails_without_api_key(self):
        """Test that smoke tests fail without ALPACA_API_KEY."""
        with patch.dict(os.environ, {}, clear=True):
            result = run_smoke_tests()

            assert result.all_passed is False
            assert result.passed is False
            assert "ALPACA_API_KEY not set" in str(result.errors)

    def test_fails_without_secret_key(self):
        """Test that smoke tests fail without ALPACA_SECRET_KEY."""
        with patch.dict(os.environ, {"ALPACA_API_KEY": "test"}, clear=True):
            result = run_smoke_tests()

            assert result.all_passed is False
            assert result.passed is False
            assert "ALPACA_SECRET_KEY not set" in str(result.errors)

    @pytest.mark.skipif(not _alpaca_available(), reason="alpaca not available in sandbox")
    def test_fails_when_alpaca_connection_fails(self):
        """Test that smoke tests fail when Alpaca connection fails."""
        with patch.dict(
            os.environ,
            {"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"},
            clear=True,
        ):
            with patch(
                "alpaca.trading.client.TradingClient",
                side_effect=Exception("Connection refused"),
            ):
                result = run_smoke_tests()

                assert result.all_passed is False
                assert result.alpaca_connected is False
                assert "connection failed" in str(result.errors).lower()

    @pytest.mark.skipif(not _alpaca_available(), reason="alpaca not available in sandbox")
    def test_fails_when_account_not_readable(self):
        """Test that smoke tests fail when account cannot be read."""
        mock_client = MagicMock()
        mock_client.get_account.side_effect = Exception("Account not found")

        with patch.dict(
            os.environ,
            {"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"},
            clear=True,
        ):
            with patch(
                "alpaca.trading.client.TradingClient",
                return_value=mock_client,
            ):
                result = run_smoke_tests()

                assert result.all_passed is False
                assert result.alpaca_connected is True  # Connection succeeded
                assert result.account_readable is False  # But account failed
                assert "Cannot read account" in str(result.errors)

    @pytest.mark.skipif(not _alpaca_available(), reason="alpaca not available in sandbox")
    def test_fails_when_positions_not_readable(self):
        """Test that smoke tests fail when positions cannot be read."""
        mock_account = MagicMock()
        mock_account.equity = 100000.0
        mock_account.buying_power = 50000.0
        mock_account.cash = 50000.0
        mock_account.status = "ACTIVE"

        mock_client = MagicMock()
        mock_client.get_account.return_value = mock_account
        mock_client.get_all_positions.side_effect = Exception("Positions API error")

        with patch.dict(
            os.environ,
            {"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"},
            clear=True,
        ):
            with patch(
                "alpaca.trading.client.TradingClient",
                return_value=mock_client,
            ):
                result = run_smoke_tests()

                assert result.all_passed is False
                assert result.alpaca_connected is True
                assert result.account_readable is True
                assert result.positions_readable is False
                assert "Cannot read positions" in str(result.errors)

    @pytest.mark.skipif(not _alpaca_available(), reason="alpaca not available in sandbox")
    def test_fails_when_buying_power_zero(self):
        """Test that smoke tests fail when buying power is zero."""
        mock_account = MagicMock()
        mock_account.equity = 100000.0
        mock_account.buying_power = 0.0  # No buying power
        mock_account.cash = 0.0
        mock_account.status = "ACTIVE"

        mock_client = MagicMock()
        mock_client.get_account.return_value = mock_account
        mock_client.get_all_positions.return_value = []

        with patch.dict(
            os.environ,
            {"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"},
            clear=True,
        ):
            with patch(
                "alpaca.trading.client.TradingClient",
                return_value=mock_client,
            ):
                result = run_smoke_tests()

                assert result.all_passed is False
                assert result.buying_power_valid is False
                assert "Buying power is $0" in str(result.errors)

    @pytest.mark.skipif(not _alpaca_available(), reason="alpaca not available in sandbox")
    def test_fails_when_equity_zero(self):
        """Test that smoke tests fail when equity is zero."""
        mock_account = MagicMock()
        mock_account.equity = 0.0  # No equity
        mock_account.buying_power = 1000.0
        mock_account.cash = 1000.0
        mock_account.status = "ACTIVE"

        mock_client = MagicMock()
        mock_client.get_account.return_value = mock_account
        mock_client.get_all_positions.return_value = []

        with patch.dict(
            os.environ,
            {"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"},
            clear=True,
        ):
            with patch(
                "alpaca.trading.client.TradingClient",
                return_value=mock_client,
            ):
                result = run_smoke_tests()

                assert result.all_passed is False
                assert result.equity_valid is False
                assert "Equity is $0" in str(result.errors)

    @pytest.mark.skipif(not _alpaca_available(), reason="alpaca not available in sandbox")
    def test_fails_when_account_not_active(self):
        """Test that smoke tests fail when account is not ACTIVE."""
        mock_account = MagicMock()
        mock_account.equity = 100000.0
        mock_account.buying_power = 50000.0
        mock_account.cash = 50000.0
        mock_account.status = "SUSPENDED"  # Not active

        mock_client = MagicMock()
        mock_client.get_account.return_value = mock_account
        mock_client.get_all_positions.return_value = []

        with patch.dict(
            os.environ,
            {"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"},
            clear=True,
        ):
            with patch(
                "alpaca.trading.client.TradingClient",
                return_value=mock_client,
            ):
                result = run_smoke_tests()

                assert result.all_passed is False
                assert "Account status is SUSPENDED" in str(result.errors)

    @pytest.mark.skipif(not _alpaca_available(), reason="alpaca not available in sandbox")
    def test_passes_when_all_conditions_met(self):
        """Test that smoke tests pass when all conditions are met."""
        mock_account = MagicMock()
        mock_account.equity = 100000.0
        mock_account.buying_power = 50000.0
        mock_account.cash = 50000.0
        mock_account.status = "ACTIVE"

        mock_positions = [MagicMock(), MagicMock()]  # 2 positions

        mock_client = MagicMock()
        mock_client.get_account.return_value = mock_account
        mock_client.get_all_positions.return_value = mock_positions

        with patch.dict(
            os.environ,
            {"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"},
            clear=True,
        ):
            with patch(
                "alpaca.trading.client.TradingClient",
                return_value=mock_client,
            ):
                result = run_smoke_tests()

                assert result.all_passed is True
                assert result.passed is True
                assert result.alpaca_connected is True
                assert result.account_readable is True
                assert result.positions_readable is True
                assert result.buying_power_valid is True
                assert result.equity_valid is True
                assert result.equity == 100000.0
                assert result.buying_power == 50000.0
                assert result.positions_count == 2
                assert len(result.errors) == 0


class TestSmokeTestNeverAlwaysTrue:
    """CRITICAL: Verify the old bug is fixed.

    The old smoke test always returned True regardless of conditions.
    These tests ensure that bug never returns.
    """

    def test_result_is_not_always_true(self):
        """Verify that SmokeTestResult doesn't default to passed=True."""
        result = SmokeTestResult()
        assert result.passed is False, "SmokeTestResult must default to passed=False"
        assert result.all_passed is False, "SmokeTestResult must default to all_passed=False"

    def test_run_smoke_tests_can_fail(self):
        """Verify that run_smoke_tests can actually return a failure."""
        # Without credentials, it MUST fail
        with patch.dict(os.environ, {}, clear=True):
            result = run_smoke_tests()
            assert result.all_passed is False, "Smoke tests must be able to fail"
            assert result.passed is False, "Smoke tests must be able to fail"
