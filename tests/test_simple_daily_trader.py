"""
Tests for simple_daily_trader.py

Critical test: Ensure max_positions doesn't block trading
Root cause of 13-day trading outage (Dec 23 - Jan 5, 2026)
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Check if dotenv is available
try:
    from dotenv import load_dotenv  # noqa: F401

    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

# Skip all tests if dotenv not available
pytestmark = pytest.mark.skipif(not DOTENV_AVAILABLE, reason="python-dotenv not available")


class TestMaxPositionsConfig:
    """Test max_positions configuration to prevent trading blockage."""

    def test_max_positions_is_valid(self):
        """Verify max_positions is configured.

        max_positions should be derived from canonical MAX_POSITIONS (option legs)
        to avoid drift between scripts.
        """
        from scripts.simple_daily_trader import CONFIG
        from src.core.trading_constants import MAX_POSITIONS

        assert CONFIG["max_positions"] >= 1, (
            f"max_positions is {CONFIG['max_positions']} but must be >= 1. "
            "At least 1 position must be allowed for trading."
        )
        assert CONFIG["max_positions"] == max(1, int(MAX_POSITIONS) // 2)

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

    @patch("scripts.simple_daily_trader.datetime")
    @patch("scripts.simple_daily_trader.get_current_positions")
    @patch("scripts.simple_daily_trader.get_account_info")
    def test_allows_new_position_under_max(self, mock_account, mock_positions, mock_datetime):
        """Should allow new position when under max_positions limit."""
        from scripts.simple_daily_trader import CONFIG, should_open_position

        # Mock datetime to be during market hours (10:30 AM ET on a Tuesday)
        try:
            from zoneinfo import ZoneInfo

            et_tz = ZoneInfo("America/New_York")
            mock_now = datetime(2026, 1, 13, 10, 30, 0, tzinfo=et_tz)  # Tuesday
        except ImportError:
            mock_now = datetime(2026, 1, 13, 10, 30, 0)

        mock_datetime.now.return_value = mock_now

        # Simulate 2 option legs. Canonical MAX_POSITIONS=8, this script uses 8//2=4.
        # 2 positions < 4 limit, so new entry should be allowed.
        mock_positions.return_value = [
            {"symbol": "SPY260123P00660000"},  # Option
            {"symbol": "SPY260123P00650000"},  # Option
        ]

        # Cash-secured puts require: strike_estimate * 100
        # For SPY ~$600, strike ~$570, required_bp = $57,000
        mock_account.return_value = {
            "equity": 100000,
            "cash": 70000,
            "buying_power": 60000,  # Must be >= $57,000 for CSP
        }

        mock_client = MagicMock()

        # With canonical max_positions currently at 8 option legs, 4 open legs remain under the limit.
        result = should_open_position(mock_client, CONFIG)

        assert result is True, (
            "should_open_position should allow a new spread when 4 option legs are below the configured limit."
        )

    @patch("scripts.simple_daily_trader.datetime")
    @patch("scripts.simple_daily_trader.get_current_positions")
    @patch("scripts.simple_daily_trader.get_account_info")
    def test_blocks_at_max_positions(self, mock_account, mock_positions, mock_datetime):
        """Should block when at max_positions limit."""
        from scripts.simple_daily_trader import CONFIG, should_open_position

        # Mock datetime to be during market hours (10:30 AM ET on a Tuesday)
        try:
            from zoneinfo import ZoneInfo

            et_tz = ZoneInfo("America/New_York")
            mock_now = datetime(2026, 1, 13, 10, 30, 0, tzinfo=et_tz)  # Tuesday
        except ImportError:
            mock_now = datetime(2026, 1, 13, 10, 30, 0)

        mock_datetime.now.return_value = mock_now

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

            assert hasattr(simple_daily_trader, "run_daily_trading")
            assert hasattr(simple_daily_trader, "CONFIG")
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
