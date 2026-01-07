"""
Tests for Position Enforcer module.

Created: Jan 7, 2026
Purpose: 100% test coverage for position_enforcer.py
"""

import pytest
from unittest.mock import MagicMock, patch

from src.safety.position_enforcer import (
    EnforcementResult,
    enforce_positions,
    _check_symbol_banned,
    BANNED_SYMBOLS,
)


class TestEnforcementResult:
    """Tests for EnforcementResult dataclass."""

    def test_default_values(self):
        """Test default initialization."""
        result = EnforcementResult()
        assert result.violations_found == 0
        assert result.violations == []
        assert result.positions_checked == 0
        assert result.positions_closed == 0
        assert result.error is None

    def test_custom_values(self):
        """Test custom initialization."""
        result = EnforcementResult(
            violations_found=2,
            violations=[{"symbol": "BTCUSD"}],
            positions_checked=5,
            positions_closed=1,
            error="test error"
        )
        assert result.violations_found == 2
        assert len(result.violations) == 1
        assert result.positions_checked == 5
        assert result.positions_closed == 1
        assert result.error == "test error"


class TestCheckSymbolBanned:
    """Tests for _check_symbol_banned function."""

    def test_crypto_symbols_banned(self):
        """Test that crypto symbols are correctly identified as banned."""
        banned = ["BTCUSD", "ETHUSD", "BTC/USD", "ETH/USD", "BITO", "GBTC"]
        for symbol in banned:
            is_banned, reason = _check_symbol_banned(symbol)
            assert is_banned, f"{symbol} should be banned"
            assert "LL-052" in reason

    def test_valid_symbols_allowed(self):
        """Test that valid stock symbols are allowed."""
        allowed = ["SPY", "AAPL", "MSFT", "GOOGL", "NVDA", "AMD", "QQQ"]
        for symbol in allowed:
            is_banned, reason = _check_symbol_banned(symbol)
            assert not is_banned, f"{symbol} should be allowed"
            assert reason == ""

    def test_case_insensitive(self):
        """Test case insensitivity."""
        is_banned, _ = _check_symbol_banned("btcusd")
        assert is_banned

    def test_crypto_pair_detection(self):
        """Test crypto pair suffix detection."""
        is_banned, _ = _check_symbol_banned("SOLUSD")
        assert is_banned


class TestEnforcePositions:
    """Tests for enforce_positions function."""

    def test_no_positions(self):
        """Test with empty positions list."""
        trader = MagicMock()
        trader.get_positions.return_value = []

        result = enforce_positions(trader)

        assert result.violations_found == 0
        assert result.positions_checked == 0
        assert result.error is None

    def test_valid_positions(self):
        """Test with only valid positions."""
        trader = MagicMock()
        mock_positions = [
            MagicMock(symbol="SPY"),
            MagicMock(symbol="AAPL"),
            MagicMock(symbol="MSFT"),
        ]
        trader.get_positions.return_value = mock_positions

        result = enforce_positions(trader)

        assert result.violations_found == 0
        assert result.positions_checked == 3
        assert result.positions_closed == 0

    def test_banned_position_detected(self):
        """Test that banned positions are detected."""
        trader = MagicMock()
        mock_positions = [
            MagicMock(symbol="SPY"),
            MagicMock(symbol="BTCUSD"),  # Banned
        ]
        trader.get_positions.return_value = mock_positions
        trader.close_position.return_value = True

        result = enforce_positions(trader)

        assert result.violations_found == 1
        assert result.positions_checked == 2
        assert result.positions_closed == 1
        trader.close_position.assert_called_once_with("BTCUSD")

    def test_close_position_failure(self):
        """Test handling of close position failure."""
        trader = MagicMock()
        mock_positions = [MagicMock(symbol="BTCUSD")]
        trader.get_positions.return_value = mock_positions
        trader.close_position.side_effect = Exception("API error")

        result = enforce_positions(trader)

        assert result.violations_found == 1
        assert result.positions_closed == 0  # Failed to close

    def test_get_positions_failure(self):
        """Test handling of get_positions failure."""
        trader = MagicMock()
        trader.get_positions.side_effect = Exception("Connection error")

        result = enforce_positions(trader)

        assert result.error == "Connection error"


class TestBannedSymbols:
    """Tests for BANNED_SYMBOLS constant."""

    def test_crypto_in_banned(self):
        """Verify crypto symbols are in banned list."""
        assert "BTCUSD" in BANNED_SYMBOLS
        assert "ETHUSD" in BANNED_SYMBOLS

    def test_crypto_etfs_banned(self):
        """Verify crypto ETFs are banned."""
        assert "BITO" in BANNED_SYMBOLS
        assert "GBTC" in BANNED_SYMBOLS
