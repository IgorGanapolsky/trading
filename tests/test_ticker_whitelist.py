"""
Tests for ticker whitelist enforcement.

Critical safety gate to prevent non-SPY trades.
"""

import pytest
from src.utils.ticker_whitelist import (
    is_ticker_allowed,
    validate_ticker,
    extract_underlying,
    TickerWhitelistViolation,
    ALLOWED_UNDERLYING,
)


class TestExtractUnderlying:
    """Test underlying extraction from option symbols."""

    def test_stock_ticker(self):
        assert extract_underlying("SPY") == "SPY"
        assert extract_underlying("SOFI") == "SOFI"
        assert extract_underlying("AAPL") == "AAPL"

    def test_option_symbol_put(self):
        assert extract_underlying("SPY260220P00653000") == "SPY"
        assert extract_underlying("SOFI260213P00032000") == "SOFI"

    def test_option_symbol_call(self):
        assert extract_underlying("SPY260115C00700000") == "SPY"

    def test_lowercase_conversion(self):
        assert extract_underlying("spy") == "SPY"
        assert extract_underlying("Spy260220P00653000") == "SPY"


class TestIsTickerAllowed:
    """Test whitelist checking."""

    def test_spy_allowed(self):
        assert is_ticker_allowed("SPY") == True

    def test_spy_options_allowed(self):
        assert is_ticker_allowed("SPY260220P00653000") == True
        assert is_ticker_allowed("SPY260115C00700000") == True

    def test_sofi_blocked(self):
        assert is_ticker_allowed("SOFI") == False
        assert is_ticker_allowed("SOFI260213P00032000") == False

    def test_other_tickers_blocked(self):
        assert is_ticker_allowed("AAPL") == False
        assert is_ticker_allowed("TSLA") == False
        assert is_ticker_allowed("NVDA") == False
        assert is_ticker_allowed("QQQ") == False
        assert is_ticker_allowed("IWM") == False


class TestValidateTicker:
    """Test validation with exception raising."""

    def test_spy_passes(self):
        assert validate_ticker("SPY") == True
        assert validate_ticker("SPY260220P00653000") == True

    def test_sofi_raises_exception(self):
        with pytest.raises(TickerWhitelistViolation) as excinfo:
            validate_ticker("SOFI260213P00032000")
        assert "BLOCKED" in str(excinfo.value)
        assert "SOFI" in str(excinfo.value)

    def test_sofi_no_raise_returns_false(self):
        result = validate_ticker("SOFI", raise_on_violation=False)
        assert result == False

    def test_random_ticker_raises(self):
        with pytest.raises(TickerWhitelistViolation):
            validate_ticker("RANDOM_TICKER")


class TestWhitelistConfiguration:
    """Test whitelist is correctly configured."""

    def test_only_spy_in_whitelist(self):
        assert ALLOWED_UNDERLYING == frozenset({"SPY"})

    def test_whitelist_is_immutable(self):
        # frozenset cannot be modified
        with pytest.raises(AttributeError):
            ALLOWED_UNDERLYING.add("SOFI")
