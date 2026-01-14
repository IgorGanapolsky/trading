"""Tests for daily VOO DCA script."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestGetBrokerageCredentials:
    """Test brokerage credential retrieval."""

    def test_returns_credentials_when_set(self):
        """Should return credentials when environment variables are set."""
        with patch.dict(
            "os.environ",
            {
                "ALPACA_BROKERAGE_TRADING_API_KEY": "test_key",
                "ALPACA_BROKERAGE_TRADING_API_SECRET": "test_secret",
            },
        ):
            from src.utils.alpaca_client import get_brokerage_credentials

            key, secret = get_brokerage_credentials()
            assert key == "test_key"
            assert secret == "test_secret"

    def test_returns_none_when_not_set(self):
        """Should return None when credentials not set."""
        with patch.dict("os.environ", {}, clear=True):
            from src.utils.alpaca_client import get_brokerage_credentials

            key, secret = get_brokerage_credentials()
            assert key is None
            assert secret is None


class TestGetBrokerageClient:
    """Test brokerage client creation."""

    def test_returns_none_without_credentials(self):
        """Should return None when credentials not available."""
        with patch.dict("os.environ", {}, clear=True):
            from src.utils.alpaca_client import get_brokerage_client

            client = get_brokerage_client()
            assert client is None

    def test_creates_client_with_paper_false(self):
        """Should create TradingClient with paper=False when alpaca available."""
        try:
            import alpaca  # noqa: F401
        except ImportError:
            pytest.skip("alpaca-py not installed in sandbox")

        with patch("src.utils.alpaca_client.get_brokerage_credentials") as mock_creds:
            mock_creds.return_value = ("key", "secret")
            with patch("alpaca.trading.client.TradingClient") as mock_client:
                from src.utils.alpaca_client import get_brokerage_client

                get_brokerage_client()
                mock_client.assert_called_once_with("key", "secret", paper=False)


class TestDailyVooDca:
    """Test VOO DCA script functionality."""

    def test_script_imports(self):
        """Script should import without errors."""
        # This validates the script structure
        import scripts.daily_voo_dca as dca

        assert hasattr(dca, "buy_fractional_voo")
        assert hasattr(dca, "main")
        assert dca.SYMBOL == "VOO"
        assert dca.MIN_PURCHASE == 1.00

    def test_buy_fractional_returns_skip_for_low_amount(self):
        """Should skip orders below minimum."""
        from scripts.daily_voo_dca import buy_fractional_voo

        mock_client = MagicMock()

        with patch("scripts.daily_voo_dca.get_voo_price", return_value=500.0):
            result = buy_fractional_voo(mock_client, 0.50, dry_run=True)

        assert result["status"] == "SKIP"
        assert "below minimum" in result["reason"]

    def test_buy_fractional_dry_run_returns_details(self):
        """Dry run should return trade details without executing."""
        from scripts.daily_voo_dca import buy_fractional_voo

        mock_client = MagicMock()

        with patch("scripts.daily_voo_dca.get_voo_price", return_value=500.0):
            result = buy_fractional_voo(mock_client, 25.0, dry_run=True)

        assert result["status"] == "DRY_RUN"
        assert result["symbol"] == "VOO"
        assert result["amount"] == 25.0
        assert result["shares"] == 0.05  # 25 / 500
        assert result["price"] == 500.0
