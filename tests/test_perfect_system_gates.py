"""Unit tests for ML trade confidence gate integration and system safety checks."""

from __future__ import annotations

from src.safety.mandatory_trade_gate import (
    _check_ml_trade_confidence,
    validate_ticker,
    validate_trade_mandatory,
)


def test_validate_ticker_spy_only_during_validation():
    """Verify validate_ticker is SPY-only while put-credit cohort validates."""
    valid_spy, err_spy = validate_ticker("SPY")
    assert valid_spy is True
    assert err_spy == ""

    valid_opt, err_opt = validate_ticker("SPY260821P00500000")
    assert valid_opt is True
    assert err_opt == ""

    valid_xsp, err_xsp = validate_ticker("XSP")
    assert valid_xsp is False
    assert err_xsp


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
