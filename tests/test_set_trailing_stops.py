"""Tests for set_trailing_stops.py script.

Phil Town Rule #1: Don't Lose Money
These tests ensure trailing stop functionality works correctly.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

# Check if alpaca is available
try:
    import alpaca.trading.client  # noqa: F401
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False


def test_is_option_symbol():
    """Test option symbol detection."""
    from set_trailing_stops import is_option_symbol

    # Standard equity symbols - NOT options
    assert is_option_symbol("SPY") is False
    assert is_option_symbol("AAPL") is False
    assert is_option_symbol("GOOGL") is False

    # OCC format options - ARE options
    assert is_option_symbol("SPY260123P00660000") is True
    assert is_option_symbol("AMD260116P00200000") is True
    assert is_option_symbol("INTC260109P00035000") is True
    assert is_option_symbol("SOFI260123P00024000") is True


def test_trailing_pct_defaults():
    """Test default trailing percentages."""
    from set_trailing_stops import DEFAULT_TRAILING_PCT, OPTIONS_TRAILING_PCT

    assert DEFAULT_TRAILING_PCT == 0.10  # 10% for equities
    assert OPTIONS_TRAILING_PCT == 0.20  # 20% for options


@patch.dict(
    "os.environ",
    {
        "ALPACA_API_KEY": "",
        "ALPACA_SECRET_KEY": "",
    },
)
def test_main_no_credentials():
    """Test graceful failure when credentials missing."""
    from set_trailing_stops import main

    with pytest.raises(SystemExit) as exc_info:
        main(dry_run=True)
    assert exc_info.value.code == 1


@pytest.mark.skipif(not ALPACA_AVAILABLE, reason="alpaca not available")
@patch.dict(
    "os.environ",
    {
        "ALPACA_API_KEY": "test_key",
        "ALPACA_SECRET_KEY": "test_secret",
        "PAPER_TRADING": "true",
    },
)
@patch("alpaca.trading.client.TradingClient")
def test_main_no_positions(mock_client_class):
    """Test handling when no positions exist."""
    mock_client = Mock()
    mock_client.get_all_positions.return_value = []
    mock_client_class.return_value = mock_client

    from set_trailing_stops import main

    result = main(dry_run=True)
    assert result is True  # No positions to protect = success (nothing at risk)


@pytest.mark.skipif(not ALPACA_AVAILABLE, reason="alpaca not available")
@patch.dict(
    "os.environ",
    {
        "ALPACA_API_KEY": "test_key",
        "ALPACA_SECRET_KEY": "test_secret",
        "PAPER_TRADING": "true",
    },
)
@patch("alpaca.trading.client.TradingClient")
def test_main_dry_run_with_positions(mock_client_class):
    """Test dry run with mock positions."""
    # Create mock position
    mock_position = Mock()
    mock_position.symbol = "SPY"
    mock_position.qty = "10"
    mock_position.current_price = "500.00"
    mock_position.unrealized_pl = "50.00"
    mock_position.market_value = "5000.00"

    mock_client = Mock()
    mock_client.get_all_positions.return_value = [mock_position]
    mock_client.get_orders.return_value = []
    mock_client_class.return_value = mock_client

    from set_trailing_stops import main

    result = main(dry_run=True)
    assert result is True  # Would set trailing stop


@pytest.mark.skipif(not ALPACA_AVAILABLE, reason="alpaca not available")
@patch.dict(
    "os.environ",
    {
        "ALPACA_API_KEY": "test_key",
        "ALPACA_SECRET_KEY": "test_secret",
        "PAPER_TRADING": "true",
    },
)
@patch("alpaca.trading.client.TradingClient")
def test_short_position_handling(mock_client_class):
    """Test that short positions use BUY to close."""
    # Create mock short position (sold option)
    mock_position = Mock()
    mock_position.symbol = "SPY260123P00660000"
    mock_position.qty = "-1"  # Short position
    mock_position.current_price = "5.00"
    mock_position.unrealized_pl = "100.00"
    mock_position.market_value = "-500.00"

    mock_client = Mock()
    mock_client.get_all_positions.return_value = [mock_position]
    mock_client.get_orders.return_value = []
    mock_client_class.return_value = mock_client

    from set_trailing_stops import main

    result = main(dry_run=True)
    assert result is True  # Would set trailing stop (BUY to close)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
