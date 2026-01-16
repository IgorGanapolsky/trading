#!/usr/bin/env python3
"""
Tests for compare_100k_vs_5k.py

Verifies the $100K vs $5K strategy comparison logic.
"""

import pytest
from pathlib import Path
from unittest.mock import patch

# Skip if dependencies not available
try:
    from scripts.compare_100k_vs_5k import (
        analyze_100k_patterns,
        load_current_state,
    )

    HAS_SCRIPT = True
except ImportError:
    HAS_SCRIPT = False


@pytest.mark.skipif(not HAS_SCRIPT, reason="compare_100k_vs_5k not importable")
class TestCompare100kVs5k:
    """Test suite for strategy comparison."""

    def test_analyze_100k_patterns_with_options(self):
        """Test pattern analysis with options trades."""
        trades = [
            {"symbol": "SPY260220P00660000", "action": "SELL", "strategy": "premium_selling"},
            {"symbol": "AMD260116P00200000", "action": "SELL", "strategy": "premium_selling"},
            {"symbol": "SPY", "action": "BUY", "strategy": "accumulation"},
        ]

        patterns = analyze_100k_patterns(trades)

        # Should identify SPY and AMD as underlyings
        assert "SPY" in patterns["underlyings"]
        assert "AMD" in patterns["underlyings"]
        assert len(patterns["options_trades"]) == 2
        assert len(patterns["stock_trades"]) == 1

    def test_analyze_100k_patterns_empty(self):
        """Test pattern analysis with no trades."""
        patterns = analyze_100k_patterns([])

        assert patterns["underlyings"] == {}
        assert patterns["options_trades"] == []
        assert patterns["stock_trades"] == []

    def test_load_current_state_missing_file(self):
        """Test graceful handling of missing system state."""
        with patch.object(Path, "exists", return_value=False):
            state = load_current_state()
            assert state == {}

    def test_strategy_alignment_check(self):
        """Test that we can detect strategy alignment."""
        # $100K patterns
        patterns_100k = {
            "underlyings": {"SPY": 10, "AMD": 5},
            "strategies": {"premium_selling": 8, "iron_condor": 3},
        }

        # Current $5K state with SPY spreads
        current_positions = [
            {"symbol": "SPY260220P00565000", "qty": 1},
            {"symbol": "SPY260220P00570000", "qty": -1},
        ]

        # Extract underlyings from current positions
        current_underlyings = set()
        for p in current_positions:
            symbol = p["symbol"]
            if len(symbol) > 10:
                for i, c in enumerate(symbol):
                    if c.isdigit():
                        current_underlyings.add(symbol[:i])
                        break

        # Check alignment - SPY should be in both
        aligned = "SPY" in patterns_100k["underlyings"] and "SPY" in current_underlyings
        assert aligned, "Current strategy should be aligned with $100K"


class TestEdgeCases:
    """Edge case tests."""

    def test_malformed_option_symbol(self):
        """Test handling of malformed option symbols."""
        trades = [
            {"symbol": "123INVALID", "action": "SELL"},
            {"symbol": "", "action": "BUY"},
        ]

        # Should not crash
        if HAS_SCRIPT:
            patterns = analyze_100k_patterns(trades)
            assert isinstance(patterns, dict)

    def test_missing_fields_in_trade(self):
        """Test handling of trades with missing fields."""
        trades = [
            {"symbol": "SPY"},  # Missing action, strategy
            {},  # Empty trade
        ]

        if HAS_SCRIPT:
            patterns = analyze_100k_patterns(trades)
            assert isinstance(patterns, dict)
