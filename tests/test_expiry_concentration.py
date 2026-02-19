"""Tests for expiry concentration guard in TradeGateway."""

from __future__ import annotations

import pytest

from src.risk.trade_gateway import TradeGateway


def _make_option_pos(symbol: str, qty: int = -1) -> dict:
    """Build a minimal position dict that looks like an option leg."""
    return {
        "symbol": symbol,
        "qty": qty,
        "market_value": 100,
        "unrealized_pl": 0,
    }


# OCC symbols: SPY + YYMMDD + P/C + strike*1000
# Week of 2026-03-20 (ISO 2026-W12)
WEEK12_LEGS = [
    _make_option_pos("SPY260320P00560000", qty=-1),  # short put
    _make_option_pos("SPY260320P00550000", qty=1),   # long put
    _make_option_pos("SPY260320C00610000", qty=-1),  # short call
    _make_option_pos("SPY260320C00620000", qty=1),   # long call
]

# Week of 2026-03-27 (ISO 2026-W13)
WEEK13_LEGS = [
    _make_option_pos("SPY260327P00555000", qty=-1),
    _make_option_pos("SPY260327P00545000", qty=1),
    _make_option_pos("SPY260327C00615000", qty=-1),
    _make_option_pos("SPY260327C00625000", qty=1),
]


@pytest.fixture
def gateway():
    return TradeGateway(executor=None, paper=True)


def test_no_positions_passes(gateway):
    ok, reason = gateway._check_expiry_concentration([])
    assert not ok


def test_few_positions_passes(gateway):
    ok, reason = gateway._check_expiry_concentration(WEEK12_LEGS[:2])
    assert not ok


def test_single_expiry_week_rejected(gateway):
    """All 4 legs in one week = 100% concentration > 40%."""
    ok, reason = gateway._check_expiry_concentration(WEEK12_LEGS)
    assert ok
    assert "W12" in reason


def test_two_weeks_evenly_split_passes(gateway):
    """4 legs in each of 2 weeks = 50% each. 50% > 40% so still rejected."""
    positions = WEEK12_LEGS + WEEK13_LEGS
    ok, reason = gateway._check_expiry_concentration(positions)
    assert ok  # 50% > 40%


def test_three_weeks_passes(gateway):
    """Spread across 3+ weeks so each < 40%."""
    # Week 14
    week14 = [
        _make_option_pos("SPY260403P00560000", qty=-1),
        _make_option_pos("SPY260403P00550000", qty=1),
        _make_option_pos("SPY260403C00610000", qty=-1),
        _make_option_pos("SPY260403C00620000", qty=1),
    ]
    positions = WEEK12_LEGS + WEEK13_LEGS + week14
    ok, reason = gateway._check_expiry_concentration(positions)
    # 4/12 = 33% each — passes
    assert not ok


def test_mixed_stock_and_option_only_checks_options(gateway):
    """Stock positions (short symbols) should be ignored."""
    stock = {"symbol": "SPY", "qty": 100, "market_value": 50000, "unrealized_pl": 0}
    positions = [stock] + WEEK12_LEGS
    ok, reason = gateway._check_expiry_concentration(positions)
    assert ok  # 4/4 option legs in one week = 100%


def test_malformed_symbol_skipped(gateway):
    """Symbols that can't be parsed should be skipped, not crash."""
    bad = [_make_option_pos("BADFORMAT123456789")]
    ok, reason = gateway._check_expiry_concentration(bad)
    assert not ok  # graceful skip
