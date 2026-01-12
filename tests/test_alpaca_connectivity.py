"""
Tests for Alpaca connectivity script.

These tests verify the connectivity testing logic works correctly
without actually connecting to Alpaca (mocked).
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add scripts to path for import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

# Check if pydantic is available (required for alpaca-py)
try:
    import pydantic  # noqa: F401
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False

# Skip all tests in this module if pydantic is not available
pytestmark = pytest.mark.skipif(
    not PYDANTIC_AVAILABLE,
    reason="pydantic not available - required for alpaca-py"
)


class TestAlpacaConnectivity:
    """Tests for Alpaca API connectivity testing."""

    def test_import_script(self):
        """Verify script can be imported."""
        import test_alpaca_connectivity

        assert hasattr(test_alpaca_connectivity, "test_connectivity")
        assert hasattr(test_alpaca_connectivity, "main")

    def test_connectivity_without_keys(self):
        """Test behavior when API keys are missing."""
        import test_alpaca_connectivity

        # Clear any existing keys
        with patch.dict(os.environ, {}, clear=True):
            result = test_alpaca_connectivity.test_connectivity(paper=True)

        assert result["connected"] is False
        assert "not found" in result["error"].lower() or "not installed" in result["error"].lower()

    @patch("test_alpaca_connectivity.TradingClient")
    def test_connectivity_success_paper(self, mock_client_class):
        """Test successful paper trading connection."""
        import test_alpaca_connectivity

        # Mock account response
        mock_account = MagicMock()
        mock_account.status = "ACTIVE"
        mock_account.cash = 5000.0
        mock_account.buying_power = 5000.0

        mock_client = MagicMock()
        mock_client.get_account.return_value = mock_account
        mock_client_class.return_value = mock_client

        with patch.dict(
            os.environ,
            {
                "ALPACA_PAPER_TRADING_5K_API_KEY": "test_key",
                "ALPACA_PAPER_TRADING_5K_API_SECRET": "test_secret",
            },
        ):
            result = test_alpaca_connectivity.test_connectivity(paper=True)

        assert result["connected"] is True
        assert result["account_status"] == "ACTIVE"
        assert result["cash"] == 5000.0

    @patch("test_alpaca_connectivity.TradingClient")
    def test_connectivity_failure(self, mock_client_class):
        """Test connection failure handling."""
        import test_alpaca_connectivity

        mock_client_class.side_effect = Exception("Connection refused")

        with patch.dict(
            os.environ,
            {
                "ALPACA_API_KEY": "bad_key",
                "ALPACA_SECRET_KEY": "bad_secret",
            },
        ):
            result = test_alpaca_connectivity.test_connectivity(paper=True)

        assert result["connected"] is False
        assert "Connection refused" in result["error"]

    def test_mode_selection(self):
        """Test paper vs live mode selection."""
        import test_alpaca_connectivity

        # Verify mode is correctly set in result
        with patch.dict(os.environ, {}, clear=True):
            paper_result = test_alpaca_connectivity.test_connectivity(paper=True)
            live_result = test_alpaca_connectivity.test_connectivity(paper=False)

        assert paper_result["mode"] == "paper"
        assert live_result["mode"] == "live"
