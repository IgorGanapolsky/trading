"""Tests for src/utils/ticker_validator.py and src/core/trading_constants.extract_underlying."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.trading_constants import ALLOWED_TICKERS, extract_underlying
from src.utils.ticker_validator import (
    TickerViolationError,
    block_trade,
    is_allowed_ticker,
    validate_ticker,
)

# ---------------------------------------------------------------------------
# validate_ticker
# ---------------------------------------------------------------------------


def test_validate_ticker_spy():
    assert validate_ticker("SPY") == "SPY"


def test_validate_ticker_all_allowed():
    for ticker in ALLOWED_TICKERS:
        assert validate_ticker(ticker) == ticker


def test_validate_ticker_lowercase_normalizes():
    assert validate_ticker("spy") == "SPY"


def test_validate_ticker_strips_whitespace():
    assert validate_ticker("  SPY  ") == "SPY"


def test_validate_ticker_mixed_case():
    assert validate_ticker("sPy") == "SPY"


def test_validate_ticker_rejects_individual_stock():
    with pytest.raises(TickerViolationError, match="TICKER VIOLATION"):
        validate_ticker("SOFI")


def test_validate_ticker_rejects_aapl():
    with pytest.raises(TickerViolationError, match="NOT in whitelist"):
        validate_ticker("AAPL")


def test_validate_ticker_rejects_empty():
    with pytest.raises(TickerViolationError):
        validate_ticker("")


def test_validate_ticker_rejects_random_string():
    with pytest.raises(TickerViolationError):
        validate_ticker("XYZNOTREAL")


def test_validate_ticker_context_in_error():
    with pytest.raises(TickerViolationError, match="iron_condor"):
        validate_ticker("TSLA", context="iron_condor")


def test_validate_ticker_default_context():
    """When no context supplied, error says 'unknown'."""
    with pytest.raises(TickerViolationError, match="unknown"):
        validate_ticker("TSLA")


# ---------------------------------------------------------------------------
# is_allowed_ticker
# ---------------------------------------------------------------------------


def test_is_allowed_spy():
    assert is_allowed_ticker("SPY") is True


def test_is_allowed_all_whitelisted():
    for ticker in ALLOWED_TICKERS:
        assert is_allowed_ticker(ticker) is True


def test_is_allowed_lowercase():
    assert is_allowed_ticker("spy") is True


def test_is_not_allowed_qqq():
    assert is_allowed_ticker("QQQ") is False
    assert is_allowed_ticker("  QQQ  ") is False


def test_is_not_allowed_sofi():
    assert is_allowed_ticker("SOFI") is False


def test_is_not_allowed_empty():
    assert is_allowed_ticker("") is False


# ---------------------------------------------------------------------------
# block_trade
# ---------------------------------------------------------------------------


def test_block_trade_always_raises():
    with pytest.raises(TickerViolationError, match="TRADE BLOCKED"):
        block_trade("test reason")


def test_block_trade_includes_reason():
    with pytest.raises(TickerViolationError, match="margin violation"):
        block_trade("margin violation")


# ---------------------------------------------------------------------------
# extract_underlying (OCC symbol parsing)
# ---------------------------------------------------------------------------


def test_extract_plain_ticker():
    assert extract_underlying("SPY") == "SPY"


def test_extract_plain_ticker_lowercase():
    assert extract_underlying("spy") == "SPY"


def test_extract_plain_ticker_whitespace():
    assert extract_underlying("  SPY  ") == "SPY"


def test_extract_short_ticker():
    """Tickers <= 6 chars returned as-is (uppercased)."""
    assert extract_underlying("QQQ") == "QQQ"
    assert extract_underlying("IWM") == "IWM"
    assert extract_underlying("ABCDEF") == "ABCDEF"


def test_extract_occ_call():
    assert extract_underlying("SPY260115C00600000") == "SPY"


def test_extract_occ_put():
    assert extract_underlying("SPY260115P00500000") == "SPY"


def test_extract_occ_sofi():
    """Even non-whitelisted tickers parse correctly from OCC symbols."""
    assert extract_underlying("SOFI260206P00024000") == "SOFI"


def test_extract_occ_long_underlying():
    """Underlying can be up to 6 chars in OCC format."""
    # Construct a valid OCC: ABCDEF + 260115 + C + 00100000
    assert extract_underlying("ABCDEF260115C00100000") == "ABCDEF"


def test_extract_fallback_15char_suffix():
    """If regex fails but symbol >= 15 chars with alpha prefix, use fallback."""
    # 15-char suffix after 'XYZ' = 18 chars total, but doesn't match OCC regex
    # because it lacks proper P/C format -- the fallback path strips last 15
    symbol = "XYZ" + "0" * 15  # 'XYZ000000000000000'
    result = extract_underlying(symbol)
    assert result == "XYZ"


def test_extract_returns_original_on_unparseable():
    """Symbols > 6 chars that don't match any pattern returned as-is."""
    assert extract_underlying("TOOLONG") == "TOOLONG"


def test_extract_single_char_underlying():
    """Single-char underlying in OCC format."""
    assert extract_underlying("X260115C00050000") == "X"


# ---------------------------------------------------------------------------
# Whitelist integrity
# ---------------------------------------------------------------------------


def test_allowed_tickers_contains_expected():
    expected = {"SPY"}
    assert expected == ALLOWED_TICKERS


def test_allowed_tickers_no_individual_stocks():
    """Whitelist must never contain individual stocks (lesson: SOFI loss)."""
    banned = {"SOFI", "AAPL", "TSLA", "AMZN", "GOOG", "NVDA"}
    assert ALLOWED_TICKERS.isdisjoint(banned)
