"""
Unit tests for Kalshi Prediction Markets Client.

Tests cover:
- Client initialization and configuration
- Authentication flow
- Market data retrieval
- Order placement and cancellation
- Position management
- Error handling

Author: Trading System
Created: 2025-12-09
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from src.brokers.kalshi_client import (
    KalshiAccount,
    KalshiAuth,
    KalshiClient,
    KalshiMarket,
    KalshiOrder,
    KalshiOrderSide,
    KalshiPosition,
    get_kalshi_client,
)


class TestKalshiClientInit:
    """Test client initialization."""

    def test_init_with_credentials(self):
        """Test initialization with email/password."""
        client = KalshiClient(
            email="test@example.com",
            password="testpass",
            paper=True,
        )

        assert client.email == "test@example.com"
        assert client.password == "testpass"
        assert client.paper is True
        assert client.base_url == KalshiClient.DEMO_URL

    def test_init_production_url(self):
        """Test initialization for production."""
        client = KalshiClient(
            email="test@example.com",
            password="testpass",
            paper=False,
        )

        assert client.base_url == KalshiClient.PROD_URL

    def test_is_configured_with_credentials(self):
        """Test is_configured with credentials."""
        client = KalshiClient(
            email="test@example.com",
            password="testpass",
        )

        assert client.is_configured() is True

    def test_is_configured_without_credentials(self):
        """Test is_configured without credentials."""
        client = KalshiClient()

        assert client.is_configured() is False

    @patch.dict(
        "os.environ",
        {
            "KALSHI_EMAIL": "env@example.com",
            "KALSHI_PASSWORD": "envpass",
        },
    )
    def test_init_from_env_vars(self):
        """Test initialization from environment variables."""
        client = KalshiClient()

        assert client.email == "env@example.com"
        assert client.password == "envpass"
        assert client.is_configured() is True


class TestKalshiAuth:
    """Test authentication."""

    def test_auth_not_expired(self):
        """Test auth token not expired."""
        auth = KalshiAuth(
            token="test_token",
            user_id="test_user",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        )

        assert auth.is_expired() is False

    def test_auth_expired(self):
        """Test auth token expired."""
        auth = KalshiAuth(
            token="test_token",
            user_id="test_user",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )

        assert auth.is_expired() is True


class TestKalshiDataClasses:
    """Test dataclass functionality."""

    def test_kalshi_market(self):
        """Test KalshiMarket dataclass."""
        market = KalshiMarket(
            ticker="TRUMP-24",
            title="Will Trump win 2024 election?",
            subtitle="Presidential race",
            status="open",
            yes_price=55.0,
            no_price=45.0,
            volume=50000,
            open_interest=25000,
        )

        assert market.ticker == "TRUMP-24"
        assert market.yes_probability == 0.55
        assert market.no_probability == 0.45

    def test_kalshi_position(self):
        """Test KalshiPosition dataclass."""
        position = KalshiPosition(
            market_ticker="TRUMP-24",
            market_title="Will Trump win?",
            side="yes",
            quantity=100,
            cost_basis=55.0,
            market_value=60.0,
            unrealized_pl=5.0,
            avg_price=55.0,
        )

        assert position.market_ticker == "TRUMP-24"
        assert position.unrealized_pl == 5.0

    def test_kalshi_order(self):
        """Test KalshiOrder dataclass."""
        order = KalshiOrder(
            id="order123",
            market_ticker="TRUMP-24",
            side="yes",
            type="limit",
            quantity=10,
            price=55.0,
            filled_quantity=5,
            status="active",
            created_at="2025-01-01T00:00:00Z",
        )

        assert order.id == "order123"
        assert order.filled_quantity == 5

    def test_kalshi_account(self):
        """Test KalshiAccount dataclass."""
        account = KalshiAccount(
            user_id="user123",
            balance=1000.0,
            portfolio_value=1500.0,
            total_deposits=2000.0,
            total_withdrawals=500.0,
        )

        assert account.balance == 1000.0
        assert account.status == "active"


class TestKalshiClientMocked:
    """Test client methods with mocked HTTP calls."""

    @pytest.fixture
    def mock_client(self):
        """Create client with mocked auth."""
        client = KalshiClient(
            email="test@example.com",
            password="testpass",
            paper=True,
        )

        # Mock auth state
        client._auth = KalshiAuth(
            token="mock_token",
            user_id="mock_user",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        )

        return client

    @patch("src.brokers.kalshi_client.urlopen")
    def test_get_account(self, mock_urlopen, mock_client):
        """Test get_account method."""
        # Mock response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "balance": 100000,  # cents
                "portfolio_value": 150000,
                "total_deposits": 200000,
                "total_withdrawals": 50000,
            }
        ).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        account = mock_client.get_account()

        assert account.balance == 1000.0  # Converted to USD
        assert account.portfolio_value == 1500.0
        assert account.user_id == "mock_user"

    @patch("src.brokers.kalshi_client.urlopen")
    def test_get_positions(self, mock_urlopen, mock_client):
        """Test get_positions method."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "market_positions": [
                    {
                        "ticker": "TRUMP-24",
                        "title": "Trump 2024",
                        "position": 100,
                        "average_price": 55,
                        "market_price": 60,
                    },
                    {
                        "ticker": "FED-DEC",
                        "title": "Fed Rate Dec",
                        "position": -50,  # Short position
                        "average_price": 70,
                        "market_price": 65,
                    },
                ]
            }
        ).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        positions = mock_client.get_positions()

        assert len(positions) == 2
        assert positions[0].market_ticker == "TRUMP-24"
        assert positions[0].side == "yes"
        assert positions[0].quantity == 100
        assert positions[1].side == "no"  # Negative position = no side
        assert positions[1].quantity == 50

    @patch("src.brokers.kalshi_client.urlopen")
    def test_get_markets(self, mock_urlopen, mock_client):
        """Test get_markets method."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "markets": [
                    {
                        "ticker": "TRUMP-24",
                        "title": "Trump 2024",
                        "subtitle": "Will Trump win?",
                        "status": "open",
                        "yes_bid": 54,
                        "yes_ask": 56,
                        "no_bid": 44,
                        "no_ask": 46,
                        "volume": 50000,
                        "open_interest": 25000,
                        "category": "elections",
                    },
                ]
            }
        ).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        markets = mock_client.get_markets(status="open", limit=10)

        assert len(markets) == 1
        assert markets[0].ticker == "TRUMP-24"
        assert markets[0].yes_price == 55.0  # Average of bid/ask
        assert markets[0].volume == 50000

    @patch("src.brokers.kalshi_client.urlopen")
    def test_place_order(self, mock_urlopen, mock_client):
        """Test place_order method."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "order": {
                    "order_id": "order123",
                    "ticker": "TRUMP-24",
                    "side": "yes",
                    "type": "limit",
                    "count": 10,
                    "yes_price": 55,
                    "filled_count": 0,
                    "status": "active",
                    "created_time": "2025-01-01T00:00:00Z",
                }
            }
        ).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        order = mock_client.place_order(
            ticker="TRUMP-24",
            side="yes",
            quantity=10,
            limit_price=55,
        )

        assert order.id == "order123"
        assert order.market_ticker == "TRUMP-24"
        assert order.side == "yes"
        assert order.quantity == 10
        assert order.status == "active"

    @patch("src.brokers.kalshi_client.urlopen")
    def test_cancel_order_success(self, mock_urlopen, mock_client):
        """Test successful order cancellation."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({}).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = mock_client.cancel_order("order123")

        assert result is True

    @patch("src.brokers.kalshi_client.urlopen")
    def test_get_orderbook(self, mock_urlopen, mock_client):
        """Test get_orderbook method."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "yes": {
                    "bids": [[54, 100], [53, 200]],
                    "asks": [[56, 150], [57, 250]],
                },
                "no": {
                    "bids": [[44, 150], [43, 300]],
                    "asks": [[46, 100], [47, 200]],
                },
            }
        ).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        orderbook = mock_client.get_orderbook("TRUMP-24")

        assert "yes" in orderbook
        assert "no" in orderbook
        assert len(orderbook["yes"]["bids"]) == 2
        assert len(orderbook["yes"]["asks"]) == 2


class TestKalshiOrderSideValidation:
    """Test order side validation."""

    def test_valid_yes_side(self):
        """Test valid YES side."""
        KalshiClient(email="test@example.com", password="pass")
        # Validation happens in place_order, tested via mocked tests
        assert KalshiOrderSide.YES.value == "yes"

    def test_valid_no_side(self):
        """Test valid NO side."""
        assert KalshiOrderSide.NO.value == "no"


class TestSingletonClient:
    """Test singleton pattern for client."""

    def test_get_kalshi_client_creates_singleton(self):
        """Test that get_kalshi_client returns same instance."""
        # Reset singleton
        import src.brokers.kalshi_client as module

        module._kalshi_client = None

        client1 = get_kalshi_client(paper=True)
        client2 = get_kalshi_client(paper=True)

        assert client1 is client2

        # Clean up
        module._kalshi_client = None


class TestMarketProbabilities:
    """Test probability calculations."""

    def test_yes_probability_calculation(self):
        """Test YES probability is calculated correctly."""
        market = KalshiMarket(
            ticker="TEST",
            title="Test",
            subtitle="",
            status="open",
            yes_price=75.0,
            no_price=25.0,
            volume=1000,
            open_interest=500,
        )

        assert market.yes_probability == 0.75
        assert market.no_probability == 0.25

    def test_extreme_probabilities(self):
        """Test extreme probability values."""
        market_high = KalshiMarket(
            ticker="HIGH",
            title="High Prob",
            subtitle="",
            status="open",
            yes_price=99.0,
            no_price=1.0,
            volume=1000,
            open_interest=500,
        )

        assert market_high.yes_probability == 0.99

        market_low = KalshiMarket(
            ticker="LOW",
            title="Low Prob",
            subtitle="",
            status="open",
            yes_price=1.0,
            no_price=99.0,
            volume=1000,
            open_interest=500,
        )

        assert market_low.yes_probability == 0.01
