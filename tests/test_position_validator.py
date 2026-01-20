"""Tests for scripts/position_validator.py

Per CLAUDE.md (Jan 20, 2026): 100% test coverage on all changed code.

Tests the orphan detection and spread validation logic.
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "scripts"))


class TestParseOptionSymbol:
    """Test option symbol parsing."""

    def test_parse_valid_spy_put(self):
        """Test parsing valid SPY put symbol."""
        from position_validator import parse_option_symbol

        result = parse_option_symbol("SPY260220P00653000")
        assert result is not None
        assert result["underlying"] == "SPY"
        assert result["expiration"] == "260220"
        assert result["option_type"] == "P"
        assert result["strike"] == 653.0

    def test_parse_valid_spy_call(self):
        """Test parsing valid SPY call symbol."""
        from position_validator import parse_option_symbol

        result = parse_option_symbol("SPY260220C00700000")
        assert result is not None
        assert result["underlying"] == "SPY"
        assert result["option_type"] == "C"
        assert result["strike"] == 700.0

    def test_parse_invalid_symbol(self):
        """Test parsing invalid symbol returns None."""
        from position_validator import parse_option_symbol

        result = parse_option_symbol("INVALID")
        assert result is None

    def test_parse_stock_symbol(self):
        """Test that stock symbols return None."""
        from position_validator import parse_option_symbol

        result = parse_option_symbol("SPY")
        assert result is None


class TestFindSpreadPairs:
    """Test spread pair matching logic."""

    def test_complete_bull_put_spread(self):
        """Test identifying a complete bull put spread."""
        from position_validator import find_spread_pairs, OptionPosition

        positions = [
            OptionPosition(
                symbol="SPY260220P00565000",
                underlying="SPY",
                expiration="260220",
                option_type="P",
                strike=565.0,
                qty=1,
                market_value=100.0,
                unrealized_pl=5.0,
            ),
            OptionPosition(
                symbol="SPY260220P00570000",
                underlying="SPY",
                expiration="260220",
                option_type="P",
                strike=570.0,
                qty=-1,
                market_value=-150.0,
                unrealized_pl=-3.0,
            ),
        ]

        spreads, orphans = find_spread_pairs(positions)

        assert len(spreads) == 1
        assert len(orphans) == 0
        assert spreads[0].spread_type == "bull_put"
        assert spreads[0].width == 5.0

    def test_orphan_long_put(self):
        """Test detecting orphan long put."""
        from position_validator import find_spread_pairs, OptionPosition

        positions = [
            OptionPosition(
                symbol="SPY260220P00653000",
                underlying="SPY",
                expiration="260220",
                option_type="P",
                strike=653.0,
                qty=2,  # 2 longs
                market_value=200.0,
                unrealized_pl=7.0,
            ),
            OptionPosition(
                symbol="SPY260220P00658000",
                underlying="SPY",
                expiration="260220",
                option_type="P",
                strike=658.0,
                qty=-1,  # Only 1 short
                market_value=-150.0,
                unrealized_pl=-3.0,
            ),
        ]

        spreads, orphans = find_spread_pairs(positions)

        # Should have 1 complete spread and 1 orphan
        assert len(spreads) == 1
        assert len(orphans) >= 1  # At least 1 orphan (the extra long)

    def test_no_positions(self):
        """Test empty positions list."""
        from position_validator import find_spread_pairs

        spreads, orphans = find_spread_pairs([])

        assert len(spreads) == 0
        assert len(orphans) == 0


class TestValidateIronCondor:
    """Test iron condor validation."""

    def test_valid_iron_condor(self):
        """Test identifying a valid iron condor (bull put + bear call)."""
        from position_validator import validate_iron_condor, SpreadPair, OptionPosition

        # Create mock positions for a complete iron condor
        bull_put_long = OptionPosition(
            symbol="SPY260220P00565000",
            underlying="SPY",
            expiration="260220",
            option_type="P",
            strike=565.0,
            qty=1,
            market_value=100.0,
            unrealized_pl=5.0,
        )
        bull_put_short = OptionPosition(
            symbol="SPY260220P00570000",
            underlying="SPY",
            expiration="260220",
            option_type="P",
            strike=570.0,
            qty=-1,
            market_value=-150.0,
            unrealized_pl=-3.0,
        )
        bear_call_long = OptionPosition(
            symbol="SPY260220C00620000",
            underlying="SPY",
            expiration="260220",
            option_type="C",
            strike=620.0,
            qty=1,
            market_value=100.0,
            unrealized_pl=5.0,
        )
        bear_call_short = OptionPosition(
            symbol="SPY260220C00615000",
            underlying="SPY",
            expiration="260220",
            option_type="C",
            strike=615.0,
            qty=-1,
            market_value=-150.0,
            unrealized_pl=-3.0,
        )

        spreads = [
            SpreadPair(
                long_leg=bull_put_long,
                short_leg=bull_put_short,
                spread_type="bull_put",
                width=5.0,
                max_loss=500.0,
                max_profit=0.0,
            ),
            SpreadPair(
                long_leg=bear_call_long,
                short_leg=bear_call_short,
                spread_type="bear_call",
                width=5.0,
                max_loss=500.0,
                max_profit=0.0,
            ),
        ]

        is_valid, warnings = validate_iron_condor(spreads)

        assert is_valid is True
        assert len(warnings) == 0

    def test_only_bull_put_not_iron_condor(self):
        """Test that only having bull put spreads is not a valid iron condor."""
        from position_validator import validate_iron_condor, SpreadPair, OptionPosition

        bull_put_long = OptionPosition(
            symbol="SPY260220P00565000",
            underlying="SPY",
            expiration="260220",
            option_type="P",
            strike=565.0,
            qty=1,
            market_value=100.0,
            unrealized_pl=5.0,
        )
        bull_put_short = OptionPosition(
            symbol="SPY260220P00570000",
            underlying="SPY",
            expiration="260220",
            option_type="P",
            strike=570.0,
            qty=-1,
            market_value=-150.0,
            unrealized_pl=-3.0,
        )

        spreads = [
            SpreadPair(
                long_leg=bull_put_long,
                short_leg=bull_put_short,
                spread_type="bull_put",
                width=5.0,
                max_loss=500.0,
                max_profit=0.0,
            ),
        ]

        is_valid, warnings = validate_iron_condor(spreads)

        assert is_valid is False
        assert len(warnings) >= 1
        assert any("missing bear call" in w.lower() for w in warnings)


class TestValidationResult:
    """Test full validation flow."""

    @patch("position_validator.load_positions")
    def test_validate_positions_with_orphans(self, mock_load):
        """Test validation detects orphans."""
        from position_validator import validate_positions, OptionPosition

        mock_load.return_value = [
            OptionPosition(
                symbol="SPY260220P00653000",
                underlying="SPY",
                expiration="260220",
                option_type="P",
                strike=653.0,
                qty=1,
                market_value=100.0,
                unrealized_pl=7.0,
            ),
        ]

        result = validate_positions()

        assert result.orphan_positions is not None
        # Single long with no matching short = orphan
        assert result.is_valid_iron_condor is False
