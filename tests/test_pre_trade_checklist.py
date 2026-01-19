#!/usr/bin/env python3
"""
Tests for Pre-Trade Checklist Module - CLAUDE.md Enforcement

Comprehensive test suite covering:
- Ticker validation (SPY/IWM only)
- Position size limits (5% max)
- Spread requirement enforcement
- Earnings blackout detection
- DTE range validation (30-45)
- Stop-loss requirement
- Options symbol parsing

Created: January 15, 2026
Phil Town Rule #1: Don't Lose Money
"""

import pytest
from datetime import datetime
from unittest.mock import patch

from src.risk.pre_trade_checklist import PreTradeChecklist


class TestPreTradeChecklistInitialization:
    """Tests for PreTradeChecklist initialization."""

    def test_initialization_with_valid_equity(self):
        """Checklist initializes correctly with valid equity."""
        checklist = PreTradeChecklist(account_equity=5000.0)
        assert checklist.account_equity == 5000.0
        assert checklist.max_risk == 250.0  # 5% of $5000

    def test_initialization_with_zero_equity(self):
        """Checklist handles zero equity."""
        checklist = PreTradeChecklist(account_equity=0.0)
        assert checklist.account_equity == 0.0
        assert checklist.max_risk == 0.0

    def test_initialization_with_negative_equity_raises(self):
        """Negative equity should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be negative"):
            PreTradeChecklist(account_equity=-1000.0)

    def test_constants_match_claude_md(self):
        """Verify constants match CLAUDE.md specification (Jan 19, 2026 update)."""
        # UPDATED Jan 19, 2026 (LL-244): SPY ONLY per CLAUDE.md
        assert {"SPY"} == PreTradeChecklist.ALLOWED_TICKERS
        assert PreTradeChecklist.MAX_POSITION_PCT == 0.05
        assert PreTradeChecklist.MIN_DTE == 30
        assert PreTradeChecklist.MAX_DTE == 45


class TestTickerValidation:
    """Tests for ticker validation (Checklist item 1)."""

    @pytest.fixture
    def checklist(self):
        """Create a checklist with $5000 equity."""
        return PreTradeChecklist(account_equity=5000.0)

    def test_spy_allowed(self, checklist):
        """SPY should pass ticker check."""
        passed, failures = checklist.validate(symbol="SPY", max_loss=100.0, dte=35, is_spread=True)
        assert passed is True
        assert len(failures) == 0

    def test_iwm_not_allowed(self, checklist):
        """IWM should fail ticker check - UPDATED Jan 19, 2026: SPY ONLY per CLAUDE.md."""
        passed, failures = checklist.validate(symbol="IWM", max_loss=100.0, dte=35, is_spread=True)
        assert passed is False
        assert any("IWM not allowed" in f for f in failures)

    def test_spy_lowercase_allowed(self, checklist):
        """Lowercase spy should pass ticker check."""
        passed, failures = checklist.validate(symbol="spy", max_loss=100.0, dte=35, is_spread=True)
        assert passed is True

    def test_iwm_mixed_case_not_allowed(self, checklist):
        """Mixed case IwM should fail - UPDATED Jan 19, 2026: SPY ONLY per CLAUDE.md."""
        passed, failures = checklist.validate(symbol="IwM", max_loss=100.0, dte=35, is_spread=True)
        assert passed is False

    def test_f_not_allowed(self, checklist):
        """F (Ford) should fail ticker check."""
        passed, failures = checklist.validate(symbol="F", max_loss=100.0, dte=35, is_spread=True)
        assert passed is False
        assert any("F not allowed" in f for f in failures)

    def test_sofi_not_allowed(self, checklist):
        """SOFI should fail ticker check."""
        passed, failures = checklist.validate(symbol="SOFI", max_loss=100.0, dte=35, is_spread=True)
        assert passed is False
        assert any("SOFI not allowed" in f for f in failures)

    def test_t_not_allowed(self, checklist):
        """T (AT&T) should fail ticker check."""
        passed, failures = checklist.validate(symbol="T", max_loss=100.0, dte=35, is_spread=True)
        assert passed is False
        assert any("T not allowed" in f for f in failures)

    def test_aapl_not_allowed(self, checklist):
        """AAPL should fail ticker check."""
        passed, failures = checklist.validate(symbol="AAPL", max_loss=100.0, dte=35, is_spread=True)
        assert passed is False
        assert any("AAPL not allowed" in f for f in failures)


class TestOptionsSymbolParsing:
    """Tests for options symbol parsing."""

    @pytest.fixture
    def checklist(self):
        """Create a checklist with $5000 equity."""
        return PreTradeChecklist(account_equity=5000.0)

    def test_spy_options_symbol_extraction(self, checklist):
        """SPY options symbol should extract SPY underlying."""
        # OCC format: SPY260221P00555000 (SPY Feb 21, 2026 $555 Put)
        passed, failures = checklist.validate(
            symbol="SPY260221P00555000", max_loss=100.0, dte=35, is_spread=True
        )
        assert passed is True

    def test_iwm_options_symbol_rejected(self, checklist):
        """IWM options symbol should fail - UPDATED Jan 19, 2026: SPY ONLY."""
        passed, failures = checklist.validate(
            symbol="IWM260221C00220000", max_loss=100.0, dte=35, is_spread=True
        )
        assert passed is False
        assert any("IWM not allowed" in f for f in failures)

    def test_aapl_options_symbol_rejected(self, checklist):
        """AAPL options symbol should be rejected."""
        passed, failures = checklist.validate(
            symbol="AAPL260221C00185000", max_loss=100.0, dte=35, is_spread=True
        )
        assert passed is False
        assert any("AAPL not allowed" in f for f in failures)

    def test_extract_underlying_simple_ticker(self, checklist):
        """Simple ticker extraction."""
        assert checklist._extract_underlying("SPY") == "SPY"
        assert checklist._extract_underlying("IWM") == "IWM"
        assert checklist._extract_underlying("AAPL") == "AAPL"

    def test_extract_underlying_with_whitespace(self, checklist):
        """Ticker extraction handles whitespace."""
        assert checklist._extract_underlying("  SPY  ") == "SPY"
        assert checklist._extract_underlying("iwm") == "IWM"


class TestPositionSizeValidation:
    """Tests for position size validation (Checklist item 2)."""

    @pytest.fixture
    def checklist(self):
        """Create a checklist with $5000 equity (max risk = $250)."""
        return PreTradeChecklist(account_equity=5000.0)

    def test_position_within_limit_passes(self, checklist):
        """Position at 3% ($150) should pass."""
        passed, failures = checklist.validate(symbol="SPY", max_loss=150.0, dte=35, is_spread=True)
        assert passed is True

    def test_position_at_exactly_limit_passes(self, checklist):
        """Position at exactly 5% ($250) should pass."""
        passed, failures = checklist.validate(symbol="SPY", max_loss=250.0, dte=35, is_spread=True)
        assert passed is True

    def test_position_exceeds_limit_fails(self, checklist):
        """Position at 6% ($300) should fail."""
        passed, failures = checklist.validate(symbol="SPY", max_loss=300.0, dte=35, is_spread=True)
        assert passed is False
        assert any("exceeds 5% limit" in f for f in failures)

    def test_large_position_fails(self, checklist):
        """Large position ($500 = 10%) should fail."""
        passed, failures = checklist.validate(symbol="SPY", max_loss=500.0, dte=35, is_spread=True)
        assert passed is False
        assert any("$500.00" in f for f in failures)
        assert any("$250.00" in f for f in failures)

    def test_zero_loss_passes(self, checklist):
        """Zero max loss should pass."""
        passed, failures = checklist.validate(symbol="SPY", max_loss=0.0, dte=35, is_spread=True)
        assert passed is True

    def test_small_account_proportional_limit(self):
        """Smaller account should have proportionally smaller limit."""
        small_checklist = PreTradeChecklist(account_equity=1000.0)
        # 5% of $1000 = $50
        passed, failures = small_checklist.validate(
            symbol="SPY", max_loss=60.0, dte=35, is_spread=True
        )
        assert passed is False
        assert any("$50.00" in f for f in failures)

    def test_large_account_proportional_limit(self):
        """Larger account should have proportionally larger limit."""
        large_checklist = PreTradeChecklist(account_equity=50000.0)
        # 5% of $50000 = $2500
        passed, failures = large_checklist.validate(
            symbol="SPY", max_loss=2000.0, dte=35, is_spread=True
        )
        assert passed is True


class TestSpreadValidation:
    """Tests for spread requirement validation (Checklist item 3)."""

    @pytest.fixture
    def checklist(self):
        """Create a checklist with $5000 equity."""
        return PreTradeChecklist(account_equity=5000.0)

    def test_spread_passes(self, checklist):
        """Spread position should pass."""
        passed, failures = checklist.validate(symbol="SPY", max_loss=100.0, dte=35, is_spread=True)
        assert passed is True

    def test_naked_fails(self, checklist):
        """Naked position should fail."""
        passed, failures = checklist.validate(symbol="SPY", max_loss=100.0, dte=35, is_spread=False)
        assert passed is False
        assert any("Naked positions not allowed" in f for f in failures)

    def test_naked_with_spy_fails(self, checklist):
        """Even SPY naked positions should fail."""
        passed, failures = checklist.validate(symbol="SPY", max_loss=100.0, dte=35, is_spread=False)
        assert passed is False
        assert any("must use spreads" in f for f in failures)


class TestEarningsBlackoutValidation:
    """Tests for earnings blackout validation (Checklist item 4)."""

    @pytest.fixture
    def checklist(self):
        """Create a checklist with $5000 equity."""
        return PreTradeChecklist(account_equity=5000.0)

    def test_spy_no_blackout(self, checklist):
        """SPY has no earnings blackout."""
        # Any date should pass for SPY
        passed, failures = checklist.validate(symbol="SPY", max_loss=100.0, dte=35, is_spread=True)
        assert passed is True
        assert not any("blackout" in f.lower() for f in failures)

    def test_iwm_fails_ticker_check(self, checklist):
        """IWM should fail ticker check - UPDATED Jan 19, 2026: SPY ONLY per CLAUDE.md."""
        passed, failures = checklist.validate(symbol="IWM", max_loss=100.0, dte=35, is_spread=True)
        assert passed is False
        assert any("IWM not allowed" in f for f in failures)

    def test_sofi_during_blackout_fails(self, checklist):
        """SOFI during earnings blackout should fail."""
        # SOFI blackout: 2026-01-23 to 2026-02-01
        with patch("src.risk.pre_trade_checklist.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = datetime(2026, 1, 25).date()
            mock_dt.strptime = datetime.strptime

            passed, failures = checklist.validate(
                symbol="SOFI", max_loss=100.0, dte=35, is_spread=True
            )

        # Should fail for both ticker AND blackout
        assert passed is False
        assert any("SOFI not allowed" in f for f in failures)
        assert any("blackout" in f.lower() for f in failures)

    def test_sofi_outside_blackout(self, checklist):
        """SOFI outside blackout period only fails ticker check."""
        # Before blackout start (Jan 20 < Jan 23)
        with patch("src.risk.pre_trade_checklist.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = datetime(2026, 1, 20).date()
            mock_dt.strptime = datetime.strptime

            passed, failures = checklist.validate(
                symbol="SOFI", max_loss=100.0, dte=35, is_spread=True
            )

        # Should fail for ticker but NOT blackout
        assert passed is False
        assert any("SOFI not allowed" in f for f in failures)
        assert not any("blackout" in f.lower() for f in failures)

    def test_f_during_blackout_fails(self, checklist):
        """F during earnings blackout should fail."""
        # F blackout: 2026-02-03 to 2026-02-11
        with patch("src.risk.pre_trade_checklist.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = datetime(2026, 2, 5).date()
            mock_dt.strptime = datetime.strptime

            passed, failures = checklist.validate(
                symbol="F", max_loss=100.0, dte=35, is_spread=True
            )

        assert passed is False
        assert any("F not allowed" in f for f in failures)
        assert any("blackout until 2026-02-11" in f for f in failures)

    def test_blackout_start_date_inclusive(self, checklist):
        """Blackout start date should be inclusive."""
        with patch("src.risk.pre_trade_checklist.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = datetime(2026, 1, 23).date()
            mock_dt.strptime = datetime.strptime

            passed, failures = checklist.validate(
                symbol="SOFI", max_loss=100.0, dte=35, is_spread=True
            )

        assert any("blackout" in f.lower() for f in failures)

    def test_blackout_end_date_inclusive(self, checklist):
        """Blackout end date should be inclusive."""
        with patch("src.risk.pre_trade_checklist.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = datetime(2026, 2, 1).date()
            mock_dt.strptime = datetime.strptime

            passed, failures = checklist.validate(
                symbol="SOFI", max_loss=100.0, dte=35, is_spread=True
            )

        assert any("blackout" in f.lower() for f in failures)


class TestDTEValidation:
    """Tests for DTE range validation (Checklist item 5)."""

    @pytest.fixture
    def checklist(self):
        """Create a checklist with $5000 equity."""
        return PreTradeChecklist(account_equity=5000.0)

    def test_dte_30_passes(self, checklist):
        """DTE at minimum (30) should pass."""
        passed, failures = checklist.validate(symbol="SPY", max_loss=100.0, dte=30, is_spread=True)
        assert passed is True

    def test_dte_45_passes(self, checklist):
        """DTE at maximum (45) should pass."""
        passed, failures = checklist.validate(symbol="SPY", max_loss=100.0, dte=45, is_spread=True)
        assert passed is True

    def test_dte_37_passes(self, checklist):
        """DTE in middle (37) should pass."""
        passed, failures = checklist.validate(symbol="SPY", max_loss=100.0, dte=37, is_spread=True)
        assert passed is True

    def test_dte_29_fails(self, checklist):
        """DTE below minimum (29) should fail."""
        passed, failures = checklist.validate(symbol="SPY", max_loss=100.0, dte=29, is_spread=True)
        assert passed is False
        assert any("DTE 29 outside range" in f for f in failures)

    def test_dte_46_fails(self, checklist):
        """DTE above maximum (46) should fail."""
        passed, failures = checklist.validate(symbol="SPY", max_loss=100.0, dte=46, is_spread=True)
        assert passed is False
        assert any("DTE 46 outside range" in f for f in failures)

    def test_dte_0_fails(self, checklist):
        """DTE at 0 (expiring today) should fail."""
        passed, failures = checklist.validate(symbol="SPY", max_loss=100.0, dte=0, is_spread=True)
        assert passed is False
        assert any("DTE 0 outside range" in f for f in failures)

    def test_dte_7_fails(self, checklist):
        """DTE at 7 (weekly) should fail."""
        passed, failures = checklist.validate(symbol="SPY", max_loss=100.0, dte=7, is_spread=True)
        assert passed is False
        assert any("DTE 7 outside range" in f for f in failures)

    def test_dte_60_fails(self, checklist):
        """DTE at 60 should fail."""
        passed, failures = checklist.validate(symbol="SPY", max_loss=100.0, dte=60, is_spread=True)
        assert passed is False
        assert any("DTE 60 outside range" in f for f in failures)


class TestStopLossValidation:
    """Tests for stop-loss requirement validation (Checklist item 6)."""

    @pytest.fixture
    def checklist(self):
        """Create a checklist with $5000 equity."""
        return PreTradeChecklist(account_equity=5000.0)

    def test_stop_loss_defined_passes(self, checklist):
        """Trade with stop-loss defined should pass."""
        passed, failures = checklist.validate(
            symbol="SPY",
            max_loss=100.0,
            dte=35,
            is_spread=True,
            stop_loss_defined=True,
        )
        assert passed is True

    def test_stop_loss_not_defined_fails(self, checklist):
        """Trade without stop-loss should fail."""
        passed, failures = checklist.validate(
            symbol="SPY",
            max_loss=100.0,
            dte=35,
            is_spread=True,
            stop_loss_defined=False,
        )
        assert passed is False
        assert any("Stop-loss must be defined" in f for f in failures)

    def test_stop_loss_default_is_true(self, checklist):
        """Default stop_loss_defined should be True."""
        passed, failures = checklist.validate(symbol="SPY", max_loss=100.0, dte=35, is_spread=True)
        assert passed is True
        assert not any("stop" in f.lower() for f in failures)


class TestMultipleFailures:
    """Tests for scenarios with multiple validation failures."""

    @pytest.fixture
    def checklist(self):
        """Create a checklist with $5000 equity."""
        return PreTradeChecklist(account_equity=5000.0)

    def test_all_failures(self, checklist):
        """Trade violating all rules should have all failures."""
        passed, failures = checklist.validate(
            symbol="AAPL",  # Not allowed
            max_loss=500.0,  # Exceeds 5%
            dte=7,  # Too short
            is_spread=False,  # Naked
            stop_loss_defined=False,  # No stop
        )
        assert passed is False
        assert len(failures) == 5
        assert any("AAPL not allowed" in f for f in failures)
        assert any("exceeds 5%" in f for f in failures)
        assert any("DTE 7 outside range" in f for f in failures)
        assert any("Naked positions" in f for f in failures)
        assert any("Stop-loss" in f for f in failures)

    def test_two_failures(self, checklist):
        """Trade with two violations should have two failures."""
        passed, failures = checklist.validate(
            symbol="SPY",  # OK
            max_loss=100.0,  # OK
            dte=7,  # Too short
            is_spread=False,  # Naked
            stop_loss_defined=True,  # OK
        )
        assert passed is False
        assert len(failures) == 2

    def test_only_ticker_failure(self, checklist):
        """Trade with only ticker violation."""
        passed, failures = checklist.validate(
            symbol="AAPL",  # Not allowed
            max_loss=100.0,  # OK
            dte=35,  # OK
            is_spread=True,  # OK
            stop_loss_defined=True,  # OK
        )
        assert passed is False
        assert len(failures) == 1
        assert "AAPL not allowed" in failures[0]


class TestChecklistStatus:
    """Tests for get_checklist_status method."""

    @pytest.fixture
    def checklist(self):
        """Create a checklist with $5000 equity."""
        return PreTradeChecklist(account_equity=5000.0)

    def test_all_passing_status(self, checklist):
        """Status for all-passing trade."""
        status = checklist.get_checklist_status(
            symbol="SPY",
            max_loss=100.0,
            dte=35,
            is_spread=True,
            stop_loss_defined=True,
        )

        assert status["ticker_allowed"]["passed"] is True
        assert status["ticker_allowed"]["value"] == "SPY"
        assert status["position_size"]["passed"] is True
        assert status["is_spread"]["passed"] is True
        assert status["earnings_blackout"]["passed"] is True
        assert status["dte_range"]["passed"] is True
        assert status["stop_loss"]["passed"] is True

    def test_failing_status(self, checklist):
        """Status for failing trade."""
        status = checklist.get_checklist_status(
            symbol="AAPL",
            max_loss=500.0,
            dte=7,
            is_spread=False,
            stop_loss_defined=False,
        )

        assert status["ticker_allowed"]["passed"] is False
        assert status["ticker_allowed"]["value"] == "AAPL"
        assert status["position_size"]["passed"] is False
        assert status["is_spread"]["passed"] is False
        assert status["is_spread"]["value"] == "Naked"
        assert status["dte_range"]["passed"] is False
        assert status["dte_range"]["value"] == "7"
        assert status["stop_loss"]["passed"] is False
        assert status["stop_loss"]["value"] == "Missing"

    def test_status_includes_requirements(self, checklist):
        """Status should include requirement descriptions."""
        status = checklist.get_checklist_status(
            symbol="SPY", max_loss=100.0, dte=35, is_spread=True
        )

        assert "SPY or IWM only" in status["ticker_allowed"]["requirement"]
        assert "5%" in status["position_size"]["requirement"]
        assert "spread" in status["is_spread"]["requirement"].lower()
        assert "30-45" in status["dte_range"]["requirement"]


class TestEquityUpdate:
    """Tests for equity update functionality."""

    def test_update_equity(self):
        """Equity update should recalculate max risk."""
        checklist = PreTradeChecklist(account_equity=5000.0)
        assert checklist.max_risk == 250.0

        checklist.update_equity(10000.0)
        assert checklist.account_equity == 10000.0
        assert checklist.max_risk == 500.0

    def test_update_equity_negative_raises(self):
        """Negative equity update should raise."""
        checklist = PreTradeChecklist(account_equity=5000.0)
        with pytest.raises(ValueError, match="cannot be negative"):
            checklist.update_equity(-1000.0)

    def test_update_affects_validation(self):
        """Equity update should affect validation."""
        checklist = PreTradeChecklist(account_equity=5000.0)

        # $300 exceeds 5% of $5000 ($250)
        passed, _ = checklist.validate(symbol="SPY", max_loss=300.0, dte=35, is_spread=True)
        assert passed is False

        # Update equity to $10000 - now $300 is within 5% ($500)
        checklist.update_equity(10000.0)
        passed, _ = checklist.validate(symbol="SPY", max_loss=300.0, dte=35, is_spread=True)
        assert passed is True


class TestEarningsBlackoutManagement:
    """Tests for earnings blackout management."""

    def test_add_earnings_blackout(self):
        """Add new earnings blackout."""
        # Store original to restore after test
        original = PreTradeChecklist.EARNINGS_BLACKOUTS.copy()

        try:
            PreTradeChecklist.add_earnings_blackout("NVDA", "2026-02-15", "2026-02-25")
            assert "NVDA" in PreTradeChecklist.EARNINGS_BLACKOUTS
            assert PreTradeChecklist.EARNINGS_BLACKOUTS["NVDA"]["start"] == "2026-02-15"
            assert PreTradeChecklist.EARNINGS_BLACKOUTS["NVDA"]["end"] == "2026-02-25"
        finally:
            PreTradeChecklist.EARNINGS_BLACKOUTS = original

    def test_add_earnings_blackout_uppercase(self):
        """Ticker should be converted to uppercase."""
        original = PreTradeChecklist.EARNINGS_BLACKOUTS.copy()

        try:
            PreTradeChecklist.add_earnings_blackout("nvda", "2026-02-15", "2026-02-25")
            assert "NVDA" in PreTradeChecklist.EARNINGS_BLACKOUTS
        finally:
            PreTradeChecklist.EARNINGS_BLACKOUTS = original

    def test_add_earnings_blackout_invalid_date_raises(self):
        """Invalid date format should raise."""
        with pytest.raises(ValueError, match="Invalid date format"):
            PreTradeChecklist.add_earnings_blackout("NVDA", "02-15-2026", "02-25-2026")

    def test_remove_earnings_blackout(self):
        """Remove existing earnings blackout."""
        original = PreTradeChecklist.EARNINGS_BLACKOUTS.copy()

        try:
            PreTradeChecklist.add_earnings_blackout("NVDA", "2026-02-15", "2026-02-25")
            assert "NVDA" in PreTradeChecklist.EARNINGS_BLACKOUTS

            result = PreTradeChecklist.remove_earnings_blackout("NVDA")
            assert result is True
            assert "NVDA" not in PreTradeChecklist.EARNINGS_BLACKOUTS
        finally:
            PreTradeChecklist.EARNINGS_BLACKOUTS = original

    def test_remove_nonexistent_blackout(self):
        """Removing nonexistent blackout returns False."""
        result = PreTradeChecklist.remove_earnings_blackout("NONEXISTENT")
        assert result is False


class TestCLAUDEMDCompliance:
    """Integration tests for CLAUDE.md compliance."""

    @pytest.fixture
    def checklist_4959(self):
        """Create checklist with current account equity ($4,959.26)."""
        return PreTradeChecklist(account_equity=4959.26)

    def test_max_risk_matches_claude_md(self, checklist_4959):
        """Max risk should be ~$248 per CLAUDE.md."""
        # CLAUDE.md: 5% max = $248 risk (5% of $4959.26 = $247.96)
        assert checklist_4959.max_risk == pytest.approx(247.96, rel=0.01)

    def test_valid_credit_spread_passes(self, checklist_4959):
        """Valid credit spread per CLAUDE.md should pass."""
        # CLAUDE.md: Sell 30-delta put, buy 20-delta put = ~$500 collateral, ~$50-70 premium
        # Max loss on credit spread = spread width - premium = ~$430-450
        # This exceeds our 5% limit, so we need smaller position
        # Let's say max loss is $200 (within limit)
        passed, failures = checklist_4959.validate(
            symbol="SPY",
            max_loss=200.0,  # Within $248 limit
            dte=35,  # Within 30-45 DTE
            is_spread=True,  # Required
            stop_loss_defined=True,
        )
        assert passed is True
        assert len(failures) == 0

    def test_naked_put_rejected(self, checklist_4959):
        """Naked put should be rejected per CLAUDE.md."""
        # CLAUDE.md: "NO NAKED PUTS"
        passed, failures = checklist_4959.validate(
            symbol="SPY",
            max_loss=200.0,
            dte=35,
            is_spread=False,  # Naked position
        )
        assert passed is False
        assert any("Naked positions not allowed" in f for f in failures)

    def test_individual_stock_rejected(self, checklist_4959):
        """Individual stocks (F, SOFI) should be rejected per CLAUDE.md."""
        # CLAUDE.md: "SPY or IWM? (NO individual stocks until proven)"
        for ticker in ["F", "SOFI", "T", "AAPL", "NVDA"]:
            passed, failures = checklist_4959.validate(
                symbol=ticker,
                max_loss=100.0,
                dte=35,
                is_spread=True,
            )
            assert passed is False
            assert any("not allowed" in f for f in failures)

    def test_weekly_options_rejected(self, checklist_4959):
        """Weekly options (7 DTE) should be rejected per CLAUDE.md."""
        # CLAUDE.md: 30-45 DTE expiration
        passed, failures = checklist_4959.validate(
            symbol="SPY",
            max_loss=100.0,
            dte=7,  # Weekly
            is_spread=True,
        )
        assert passed is False
        assert any("DTE 7 outside range" in f for f in failures)

    def test_oversized_position_rejected(self, checklist_4959):
        """Position >5% should be rejected per CLAUDE.md."""
        # CLAUDE.md: "Position limit: 1 spread at a time (5% max = $248 risk)"
        passed, failures = checklist_4959.validate(
            symbol="SPY",
            max_loss=300.0,  # > $248
            dte=35,
            is_spread=True,
        )
        assert passed is False
        assert any("exceeds 5% limit" in f for f in failures)


class TestPhilTownRule1:
    """Tests for Phil Town Rule #1: Don't Lose Money."""

    def test_conservative_defaults(self):
        """Default settings should be conservative."""
        # 5% max position is conservative for capital preservation
        assert PreTradeChecklist.MAX_POSITION_PCT == 0.05

    def test_spread_requirement_protects_capital(self):
        """Spread requirement limits max loss."""
        checklist = PreTradeChecklist(account_equity=5000.0)
        # Naked puts have unlimited risk - should fail
        passed, failures = checklist.validate(symbol="SPY", max_loss=100.0, dte=35, is_spread=False)
        assert passed is False

    def test_ticker_restriction_limits_volatility(self):
        """Limiting to SPY/IWM reduces single-stock volatility risk."""
        checklist = PreTradeChecklist(account_equity=5000.0)
        # Meme stocks like GME should fail
        passed, failures = checklist.validate(symbol="GME", max_loss=100.0, dte=35, is_spread=True)
        assert passed is False

    def test_dte_requirement_avoids_gamma_risk(self):
        """30-45 DTE requirement avoids gamma risk."""
        checklist = PreTradeChecklist(account_equity=5000.0)
        # 0 DTE has extreme gamma risk - should fail
        passed, failures = checklist.validate(symbol="SPY", max_loss=100.0, dte=0, is_spread=True)
        assert passed is False
