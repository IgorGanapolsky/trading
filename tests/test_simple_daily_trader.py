"""
Tests for simple_daily_trader.py

Critical test: Ensure max_positions doesn't block trading
Root cause of 13-day trading outage (Dec 23 - Jan 5, 2026)
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestMaxPositionsConfig:
    """Test max_positions configuration to prevent trading blockage."""

    def test_max_positions_is_sufficient(self):
        """CRITICAL: max_positions must be >= 10 to prevent blocking trades.

        This test exists because max_positions=3 blocked all trades for 13 days.
        See lesson LL-079.
        """
        from scripts.simple_daily_trader import CONFIG

        assert CONFIG["max_positions"] >= 10, (
            f"max_positions is {CONFIG['max_positions']} but must be >= 10. "
            "Lower values can block trading when we have multiple options positions."
        )

    def test_config_has_required_keys(self):
        """Ensure all required config keys exist."""
        from scripts.simple_daily_trader import CONFIG

        required_keys = [
            "symbol",
            "strategy",
            "target_delta",
            "target_dte",
            "max_dte",
            "min_dte",
            "position_size_pct",
            "take_profit_pct",
            "max_positions",
        ]

        for key in required_keys:
            assert key in CONFIG, f"Missing required config key: {key}"


class TestShouldOpenPosition:
    """Test the should_open_position logic."""

    @patch('scripts.simple_daily_trader.get_current_positions')
    @patch('scripts.simple_daily_trader.get_account_info')
    def test_allows_new_position_under_max(self, mock_account, mock_positions):
        """Should allow new position when under max_positions limit."""
        from scripts.simple_daily_trader import should_open_position, CONFIG

        # Simulate 4 options positions (used to block with max=3)
        mock_positions.return_value = [
            {"symbol": "INTC260109P00035000"},  # Option
            {"symbol": "SOFI260123P00024000"},  # Option
            {"symbol": "AMD260116P00200000"},   # Option
            {"symbol": "SPY260123P00660000"},   # Option
        ]

        mock_account.return_value = {
            "equity": 100000,
            "cash": 50000,
            "buying_power": 10000,
        }

        mock_client = MagicMock()

        # With max_positions=10, 4 positions should NOT block
        result = should_open_position(mock_client, CONFIG)

        # Should return True because 4 < 10
        assert result is True, (
            "should_open_position returned False with 4 positions and max=10. "
            "This would cause the 13-day outage bug again!"
        )

    @patch('scripts.simple_daily_trader.get_current_positions')
    @patch('scripts.simple_daily_trader.get_account_info')
    def test_blocks_at_max_positions(self, mock_account, mock_positions):
        """Should block when at max_positions limit."""
        from scripts.simple_daily_trader import should_open_position, CONFIG

        # Simulate exactly max_positions options
        mock_positions.return_value = [
            {"symbol": f"OPT{i}260109P00035000"} for i in range(CONFIG["max_positions"])
        ]

        mock_account.return_value = {
            "equity": 100000,
            "cash": 50000,
            "buying_power": 10000,
        }

        mock_client = MagicMock()
        result = should_open_position(mock_client, CONFIG)

        assert result is False, "Should block when at max_positions"


class TestTradingIntegration:
    """Integration smoke tests."""

    def test_script_imports_successfully(self):
        """Smoke test: script should import without errors."""
        try:
            from scripts import simple_daily_trader
            assert hasattr(simple_daily_trader, 'run_daily_trading')
            assert hasattr(simple_daily_trader, 'CONFIG')
        except ImportError as e:
            pytest.fail(f"Failed to import simple_daily_trader: {e}")

    def test_config_values_are_reasonable(self):
        """Ensure config values are within reasonable ranges."""
        from scripts.simple_daily_trader import CONFIG

        assert 0.1 <= CONFIG["target_delta"] <= 0.5, "target_delta should be 0.1-0.5"
        assert 14 <= CONFIG["target_dte"] <= 60, "target_dte should be 14-60 days"
        assert 0.01 <= CONFIG["position_size_pct"] <= 0.2, "position_size should be 1-20%"
        assert 0.25 <= CONFIG["take_profit_pct"] <= 0.75, "take_profit should be 25-75%"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
