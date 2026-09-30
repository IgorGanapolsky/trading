import pytest
from unittest.mock import MagicMock, patch


# Mock modules using patch.dict in an autouse fixture to avoid global state pollution
@pytest.fixture(autouse=True)
def mock_external_modules():
    from unittest.mock import MagicMock

    mock_modules = {
        'alpaca': MagicMock(),
        'alpaca.trading': MagicMock(),
        'alpaca.trading.client': MagicMock(),
        'alpaca.trading.enums': MagicMock(),
        'alpaca.trading.requests': MagicMock(),
        'alpaca.data': MagicMock(),
        'alpaca.data.historical': MagicMock(),
        'alpaca.data.requests': MagicMock(),
        'src.safety.mandatory_trade_gate': MagicMock(),
    }

    # Configure the mandatory_trade_gate mock
    mock_modules['src.safety.mandatory_trade_gate'].validate_ticker.return_value = (True, "")

    with patch.dict('sys.modules', mock_modules):
        yield

# Mock modules that might not be available or are nested

# Instead of patching 'src.safety.mandatory_trade_gate.validate_ticker' directly,
# we need to make sure the module is mocked first or patch where it's used.
# Let's mock the entire module to avoid AttributeError.



from src.brokers.multi_broker import BrokerType, OrderResult, MultiBroker, get_multi_broker


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the singleton instance before each test."""
    import src.brokers.multi_broker

    src.brokers.multi_broker._multi_broker = None
    yield


def test_broker_type():
    """Test BrokerType enum."""
    assert BrokerType.ALPACA.value == "alpaca"


def test_order_result():
    """Test OrderResult dataclass."""
    result = OrderResult(
        broker=BrokerType.ALPACA,
        order_id="123",
        symbol="AAPL",
        side="buy",
        quantity=10,
        status="filled",
        filled_price=150.0,
        timestamp="2023-01-01T00:00:00",
    )
    assert result.broker == BrokerType.ALPACA
    assert result.order_id == "123"
    assert result.symbol == "AAPL"
    assert result.side == "buy"
    assert result.quantity == 10
    assert result.status == "filled"
    assert result.filled_price == 150.0
    assert result.timestamp == "2023-01-01T00:00:00"


def test_get_multi_broker_singleton():
    """Test get_multi_broker returns a singleton."""
    broker1 = get_multi_broker()
    broker2 = get_multi_broker()
    assert broker1 is broker2
    assert isinstance(broker1, MultiBroker)


@patch("src.utils.alpaca_client.get_alpaca_credentials")
@patch("alpaca.trading.client.TradingClient")
def test_alpaca_lazy_load(mock_trading_client, mock_get_credentials):
    """Test lazy loading of Alpaca client."""
    mock_get_credentials.return_value = ("fake_api_key", "fake_secret_key")
    mock_trading_client.return_value = MagicMock()

    broker = MultiBroker()
    assert broker._alpaca_client is None

    # Trigger lazy load
    client = broker.alpaca
    assert client is not None
    assert broker._alpaca_client is not None

    # Second access shouldn't reinitialize
    client2 = broker.alpaca
    assert client is client2
    mock_trading_client.assert_called_once_with("fake_api_key", "fake_secret_key", paper=True)


@patch("src.utils.alpaca_client.get_alpaca_credentials")
@patch("alpaca.trading.client.TradingClient")
def test_alpaca_lazy_load_failure(mock_trading_client, mock_get_credentials):
    """Test lazy loading failure doesn't crash but logs warning."""
    mock_get_credentials.return_value = (None, None)

    broker = MultiBroker()
    client = broker.alpaca
    assert client is None
    mock_trading_client.assert_not_called()


def test_get_account():
    """Test get_account method."""
    broker = MultiBroker()
    mock_client = MagicMock()
    mock_account = MagicMock()
    mock_account.equity = "10000.50"
    mock_account.cash = "5000.25"
    mock_account.buying_power = "20000.00"
    mock_account.status = "ACTIVE"
    mock_client.get_account.return_value = mock_account
    broker._alpaca_client = mock_client

    account_info, broker_type = broker.get_account()

    assert broker_type == BrokerType.ALPACA
    assert account_info == {
        "equity": 10000.50,
        "cash": 5000.25,
        "buying_power": 20000.00,
        "status": "ACTIVE",
    }


def test_get_positions():
    """Test get_positions method."""
    broker = MultiBroker()
    mock_client = MagicMock()

    pos1 = MagicMock()
    pos1.symbol = "AAPL"
    pos1.qty = "10"
    pos1.market_value = "1500.00"
    pos1.unrealized_pl = "50.00"
    pos1.cost_basis = "1450.00"

    pos2 = MagicMock()
    pos2.symbol = "MSFT"
    pos2.qty = "5"
    pos2.market_value = "1600.00"
    pos2.unrealized_pl = "-20.00"
    pos2.cost_basis = "1620.00"

    mock_client.get_all_positions.return_value = [pos1, pos2]
    broker._alpaca_client = mock_client

    positions, broker_type = broker.get_positions()

    assert broker_type == BrokerType.ALPACA
    assert len(positions) == 2
    assert positions[0] == {
        "symbol": "AAPL",
        "quantity": 10.0,
        "market_value": 1500.0,
        "unrealized_pl": 50.0,
        "cost_basis": 1450.0,
    }
    assert positions[1] == {
        "symbol": "MSFT",
        "quantity": 5.0,
        "market_value": 1600.0,
        "unrealized_pl": -20.0,
        "cost_basis": 1620.0,
    }


@patch("src.brokers.multi_broker.validate_ticker", create=True)
def test_submit_order_blocked_ticker(mock_validate_ticker):
    """Test submit_order blocks invalid tickers."""
    mock_validate_ticker.return_value = (False, "Invalid ticker")

    # In src.brokers.multi_broker, it does:
    # from src.safety.mandatory_trade_gate import validate_ticker
    with patch(
        "src.safety.mandatory_trade_gate.validate_ticker", return_value=(False, "Invalid ticker")
    ):
        broker = MultiBroker()

        with pytest.raises(ValueError, match="ORDER BLOCKED: Invalid ticker"):
            broker.submit_order("INVALID", 10, "buy")


@patch("src.safety.mandatory_trade_gate.validate_ticker")
@patch("alpaca.trading.requests.MarketOrderRequest")
@patch("alpaca.trading.enums.OrderSide")
@patch("alpaca.trading.enums.TimeInForce")
def test_submit_order_market(mock_tif, mock_side, mock_market_request, mock_validate_ticker):
    """Test submit_order for market order."""
    mock_validate_ticker.return_value = (True, "")
    broker = MultiBroker()
    mock_client = MagicMock()

    mock_order = MagicMock()
    mock_order.id = "order_123"
    mock_order.status = MagicMock()
    mock_order.status.value = "filled"
    mock_order.filled_avg_price = "150.5"
    mock_client.submit_order.return_value = mock_order

    broker._alpaca_client = mock_client

    mock_market_request.return_value = "mock_request"

    result = broker.submit_order("SPY", 10, "buy")

    assert result.broker == BrokerType.ALPACA
    assert result.order_id == "order_123"
    assert result.symbol == "SPY"
    assert result.side == "buy"
    assert result.quantity == 10
    assert result.status == "filled"
    assert result.filled_price == 150.5

    # Verify the request made to alpaca
    mock_client.submit_order.assert_called_once_with("mock_request")


@patch("src.safety.mandatory_trade_gate.validate_ticker")
@patch("alpaca.trading.requests.LimitOrderRequest")
@patch("alpaca.trading.enums.OrderSide")
@patch("alpaca.trading.enums.TimeInForce")
def test_submit_order_limit(mock_tif, mock_side, mock_limit_request, mock_validate_ticker):
    """Test submit_order for limit order."""
    mock_validate_ticker.return_value = (True, "")
    broker = MultiBroker()
    mock_client = MagicMock()

    mock_order = MagicMock()
    mock_order.id = "order_456"
    mock_order.status = "new"  # test string status instead of enum
    mock_order.filled_avg_price = None
    mock_client.submit_order.return_value = mock_order

    broker._alpaca_client = mock_client

    mock_limit_request.return_value = "mock_request"

    result = broker.submit_order("SPY", 5, "sell", order_type="limit", limit_price=500.0)

    assert result.broker == BrokerType.ALPACA
    assert result.order_id == "order_456"
    assert result.symbol == "SPY"
    assert result.side == "sell"
    assert result.quantity == 5
    assert result.status == "new"
    assert result.filled_price is None

    mock_client.submit_order.assert_called_once_with("mock_request")


@patch("alpaca.data.historical.StockHistoricalDataClient")
@patch("alpaca.data.requests.StockLatestQuoteRequest")
@patch("src.utils.alpaca_client.get_alpaca_credentials")
def test_get_quote(mock_get_credentials, mock_quote_request, mock_historical_client_cls):
    """Test get_quote method."""
    mock_get_credentials.return_value = ("key", "secret")

    mock_client = MagicMock()
    mock_historical_client_cls.return_value = mock_client

    mock_quote = MagicMock()
    mock_quote.bid_price = "150.00"
    mock_quote.ask_price = "150.10"

    mock_client.get_stock_latest_quote.return_value = {"SPY": mock_quote}

    broker = MultiBroker()
    quote, broker_type = broker.get_quote("SPY")

    assert broker_type == BrokerType.ALPACA
    assert quote == {
        "symbol": "SPY",
        "bid": 150.0,
        "ask": 150.1,
        "last": 150.05,
    }


def test_health_check_healthy():
    """Test health_check when alpaca is healthy."""
    broker = MultiBroker()
    mock_client = MagicMock()
    mock_account = MagicMock()
    mock_account.equity = "10000.0"
    mock_client.get_account.return_value = mock_account
    broker._alpaca_client = mock_client

    status = broker.health_check()
    assert "alpaca" in status
    assert status["alpaca"]["status"] == "healthy"
    assert status["alpaca"]["equity"] == 10000.0


def test_health_check_unhealthy():
    """Test health_check when alpaca throws an error."""
    broker = MultiBroker()
    mock_client = MagicMock()
    mock_client.get_account.side_effect = Exception("API Error")
    broker._alpaca_client = mock_client

    status = broker.health_check()
    assert "alpaca" in status
    assert status["alpaca"]["status"] == "unhealthy"
    assert status["alpaca"]["error"] == "API Error"
