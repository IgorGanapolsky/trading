#!/usr/bin/env python3
"""
Tests for iron condor position validation.

Created: Jan 21, 2026 (LL-268 Prevention Item #1)
Purpose: Ensure iron condors have BOTH put AND call spreads - no partial executions.

CRITICAL: This test exists because on Jan 19, 2026 we had iron condors with only
PUT legs filled (no CALL legs), creating directional exposure that violates
CLAUDE.md's iron condor mandate.
"""

import json
import pytest
from pathlib import Path


class TestIronCondorValidation:
    """Validate iron condor positions have all 4 legs."""

    def test_system_state_has_balanced_positions(self):
        """
        Test that system_state.json positions form complete spreads when executing iron condors.

        A valid iron condor has 4 legs:
        - Long put (buy)
        - Short put (sell)
        - Short call (sell)
        - Long call (buy)

        IMPORTANT: This test only flags PARTIAL IRON CONDOR executions, not:
        - Single long puts (protective positions)
        - Single long calls (bullish speculation)
        - Bull put spreads (puts only - valid strategy per CLAUDE.md)
        - Bear call spreads (calls only)

        The violation occurs when we have evidence of a FAILED iron condor execution:
        - Multiple put strikes with both long AND short positions, but no calls
        - Multiple call strikes with both long AND short positions, but no puts
        """
        state_file = Path("data/system_state.json")
        if not state_file.exists():
            pytest.skip("system_state.json not found")

        with open(state_file) as f:
            state = json.load(f)

        positions = state.get("positions", [])
        if not positions:
            # No positions is valid
            return

        # Count puts and calls - filter for OPTIONS only (not stocks)
        # Option symbols have format: UNDERLYING + YYMMDD + P/C + STRIKE (e.g., SPY260220P00658000)
        # Must have digits to be an option symbol
        def is_option_symbol(symbol):
            return symbol and any(c.isdigit() for c in symbol)

        def is_put_option(symbol):
            return is_option_symbol(symbol) and "P" in symbol

        def is_call_option(symbol):
            return is_option_symbol(symbol) and "C" in symbol

        puts = [p for p in positions if isinstance(p, dict) and is_put_option(p.get("symbol", ""))]
        calls = [p for p in positions if isinstance(p, dict) and is_call_option(p.get("symbol", ""))]

        # If we have OPTIONS positions at all, validate for PARTIAL iron condor execution
        if puts or calls:
            # Check if puts form a spread (multiple strikes with long AND short)
            put_has_spread = self._has_spread_structure(puts)
            call_has_spread = self._has_spread_structure(calls)

            # VIOLATION: Put SPREAD exists but no call spread = partial iron condor
            # This is different from just having long puts (which is valid)
            if put_has_spread and not calls:
                pytest.fail(
                    f"IRON CONDOR VIOLATION: Have PUT SPREAD ({len(puts)} positions) but NO CALL positions. "
                    "This creates directional exposure from a partial iron condor. See LL-268."
                )
            if call_has_spread and not puts:
                pytest.fail(
                    f"IRON CONDOR VIOLATION: Have CALL SPREAD ({len(calls)} positions) but NO PUT positions. "
                    "This creates directional exposure from a partial iron condor. See LL-268."
                )

    def _has_spread_structure(self, options):
        """
        Check if option positions have a spread structure (both long and short).

        A spread has:
        - At least 2 different strikes
        - Both positive (long) and negative (short) quantities
        """
        if len(options) < 2:
            return False

        # Extract unique strikes from symbols
        strikes = set()
        has_long = False
        has_short = False

        for opt in options:
            symbol = opt.get("symbol", "")
            qty = opt.get("qty", 0)

            # Extract strike from symbol (e.g., SPY260220P00658000 -> 658000)
            if "P" in symbol or "C" in symbol:
                try:
                    strike_part = symbol.split("P")[-1] if "P" in symbol else symbol.split("C")[-1]
                    strikes.add(strike_part)
                except (ValueError, IndexError):
                    pass

            if qty > 0:
                has_long = True
            elif qty < 0:
                has_short = True

        # Spread = multiple strikes OR both long and short positions
        return len(strikes) >= 2 or (has_long and has_short)

    def test_iron_condor_trader_validates_4_legs(self):
        """Test that iron_condor_trader.py has 4-leg validation."""
        trader_file = Path("scripts/iron_condor_trader.py")
        if not trader_file.exists():
            pytest.skip("iron_condor_trader.py not found")

        content = trader_file.read_text()

        # Must check for exactly 4 legs
        assert "len(order_ids) == 4" in content, (
            "iron_condor_trader.py MUST validate all 4 legs filled. "
            "See LL-268: previous bug only checked 'if order_ids' (any legs)."
        )

        # Must have partial fill handling
        assert "LIVE_PARTIAL_FAILED" in content or "PARTIAL" in content, (
            "iron_condor_trader.py MUST handle partial fills (1-3 legs). "
            "See LL-268: incomplete iron condors create directional risk."
        )

    def test_iron_condor_has_critical_alerts(self):
        """Test that iron_condor_trader.py alerts on incomplete execution."""
        trader_file = Path("scripts/iron_condor_trader.py")
        if not trader_file.exists():
            pytest.skip("iron_condor_trader.py not found")

        content = trader_file.read_text()

        # Must log errors for partial fills
        assert "INCOMPLETE IRON CONDOR" in content or "missing_legs" in content, (
            "iron_condor_trader.py MUST alert when not all 4 legs fill. "
            "See LL-268 Prevention Item #3."
        )


class TestPositionSpreadIntegrity:
    """Validate spread positions are properly paired."""

    def test_puts_are_paired(self):
        """Test that put positions come in long/short pairs."""
        state_file = Path("data/system_state.json")
        if not state_file.exists():
            pytest.skip("system_state.json not found")

        with open(state_file) as f:
            state = json.load(f)

        positions = state.get("positions", [])
        if not positions:
            return

        # Get put positions with quantities
        put_positions = {}
        for p in positions:
            if isinstance(p, dict) and "P" in p.get("symbol", ""):
                symbol = p.get("symbol", "")
                qty = p.get("qty", 0)
                put_positions[symbol] = qty

        if not put_positions:
            return

        # Check net quantity
        total_qty = sum(put_positions.values())

        # For a spread: long qty + short qty should roughly balance
        # (long = positive, short = negative in most systems)
        # If highly unbalanced, it's not a proper spread
        long_qty = sum(q for q in put_positions.values() if q > 0)
        short_qty = abs(sum(q for q in put_positions.values() if q < 0))

        if long_qty > 0 and short_qty > 0:
            # Should be roughly equal for a spread
            ratio = min(long_qty, short_qty) / max(long_qty, short_qty)
            assert ratio > 0.5, (
                f"PUT spread is unbalanced: {long_qty} long vs {short_qty} short. "
                "This may indicate an incomplete spread. See LL-268."
            )


class TestExecutionVerification:
    """Test execution verification requirements (LL-268 Prevention #2)."""

    def test_close_excess_spreads_uses_proper_api(self):
        """Test that close_excess_spreads.py uses proper Alpaca API."""
        script_file = Path("scripts/close_excess_spreads.py")
        if not script_file.exists():
            pytest.skip("close_excess_spreads.py not found")

        content = script_file.read_text()

        # Should NOT use non-existent methods
        assert "trader.sell_option" not in content, (
            "close_excess_spreads.py uses non-existent sell_option() method. "
            "Use Alpaca TradingClient.submit_order() instead."
        )
        assert "trader.buy_option" not in content, (
            "close_excess_spreads.py uses non-existent buy_option() method. "
            "Use Alpaca TradingClient.submit_order() instead."
        )

        # Should use proper Alpaca API
        assert "submit_order" in content, (
            "close_excess_spreads.py should use Alpaca submit_order() for options."
        )
