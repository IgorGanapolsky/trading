"""
Tests for ticker whitelist enforcement.

Critical safety gate to prevent non-whitelisted trades.
"""

import pytest

from src.core.trading_constants import ALLOWED_TICKERS
from src.utils.ticker_whitelist import (
    ALLOWED_UNDERLYING,
    TickerWhitelistViolation,
    extract_underlying,
    is_ticker_allowed,
    validate_ticker,
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
        assert is_ticker_allowed("SPY") is True

    def test_spy_options_allowed(self):
        assert is_ticker_allowed("SPY260220P00653000") is True
        assert is_ticker_allowed("SPY260115C00700000") is True

    def test_spx_allowed(self):
        assert is_ticker_allowed("SPX") is True

    def test_spx_options_allowed(self):
        assert is_ticker_allowed("SPX260220P00660000") is True
        assert is_ticker_allowed("SPX260313C00725000") is True

    def test_xsp_allowed(self):
        assert is_ticker_allowed("XSP") is True

    def test_xsp_options_allowed(self):
        assert is_ticker_allowed("XSP260220P00066000") is True
        assert is_ticker_allowed("XSP260313C00072500") is True

    def test_sofi_blocked(self):
        assert is_ticker_allowed("SOFI") is False
        assert is_ticker_allowed("SOFI260213P00032000") is False

    def test_other_tickers_blocked(self):
        assert is_ticker_allowed("AAPL") is False
        assert is_ticker_allowed("TSLA") is False
        assert is_ticker_allowed("NVDA") is False

    def test_liquid_etf_tickers_allowed(self):
        assert is_ticker_allowed("QQQ") is True
        assert is_ticker_allowed("IWM") is True
        assert is_ticker_allowed("QQQ260313C00420000") is True
        assert is_ticker_allowed("IWM260313P00200000") is True


class TestValidateTicker:
    """Test validation with exception raising."""

    def test_spy_passes(self):
        assert validate_ticker("SPY") is True
        assert validate_ticker("SPY260220P00653000") is True

    def test_spx_passes(self):
        assert validate_ticker("SPX") is True
        assert validate_ticker("SPX260220P00660000") is True

    def test_xsp_passes(self):
        assert validate_ticker("XSP") is True
        assert validate_ticker("XSP260220P00066000") is True

    def test_sofi_raises_exception(self):
        with pytest.raises(TickerWhitelistViolation) as excinfo:
            validate_ticker("SOFI260213P00032000")
        assert "BLOCKED" in str(excinfo.value)
        assert "SOFI" in str(excinfo.value)

    def test_sofi_no_raise_returns_false(self):
        result = validate_ticker("SOFI", raise_on_violation=False)
        assert result is False

    def test_random_ticker_raises(self):
        with pytest.raises(TickerWhitelistViolation):
            validate_ticker("RANDOM_TICKER")


class TestWhitelistConfiguration:
    """Test whitelist is correctly configured."""

    def test_whitelist_matches_canonical_constants(self):
        assert frozenset(ALLOWED_TICKERS) == ALLOWED_UNDERLYING

    def test_whitelist_is_immutable(self):
        # frozenset cannot be modified
        with pytest.raises(AttributeError):
            ALLOWED_UNDERLYING.add("SOFI")
