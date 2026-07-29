"""Unit tests for ML trade confidence gate integration and system safety checks."""

from __future__ import annotations

from src.safety.mandatory_trade_gate import (
    _check_ml_trade_confidence,
    validate_ticker,
    validate_trade_mandatory,
)


def test_validate_ticker_supports_xsp_and_spy():
    """Verify validate_ticker allows XSP and SPY index/ETF tickers."""
    valid_xsp, err_xsp = validate_ticker("XSP")
    assert valid_xsp is True
    assert err_xsp == ""

    valid_spy, err_spy = validate_ticker("SPY")
    assert valid_spy is True
    assert err_spy == ""

    valid_opt, err_opt = validate_ticker("XSP260821P00500000")
    assert valid_opt is True
    assert err_opt == ""


def test_check_ml_trade_confidence_gate():
    """Verify _check_ml_trade_confidence returns float confidence score and list."""
    conf, warnings = _check_ml_trade_confidence(strategy="spy_put_credit", symbol="SPY")
    assert isinstance(conf, float)
    assert isinstance(warnings, list)


def test_validate_trade_mandatory_paper_execution():
    """Verify validate_trade_mandatory runs all pre-flight checks on paper trade."""
    res = validate_trade_mandatory(
        symbol="SPY",
        amount=500.0,
        side="BUY",
        strategy="spy_put_credit",
        context={"equity": 100000.0},
    )
    assert hasattr(res, "approved")
    assert hasattr(res, "checks_performed")
