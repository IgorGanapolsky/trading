"""Unit tests for AlpacaSDKAdapter — no live broker credentials required in CI."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.brokers.alpaca_sdk_adapter import AlpacaSDKAdapter


def test_alpaca_sdk_adapter_missing_client_returns_error(tmp_path):
    env = tmp_path / ".env"
    env.write_text("", encoding="utf-8")
    with patch.object(AlpacaSDKAdapter, "_init_trading_client", return_value=None):
        adapter = AlpacaSDKAdapter(env_path=env)
    summary = adapter.get_account_summary()
    assert summary == {"error": "TradingClient not initialized"}
    assert adapter.get_open_positions_count() == 0


def test_alpaca_sdk_adapter_connection_mocked():
    """Happy-path account summary without hitting the network."""
    mock_client = MagicMock()
    mock_client.get_account.return_value = SimpleNamespace(
        account_number="PA3C5AG0CECQ",
        status="ACTIVE",
        cash="94100.52",
        portfolio_value="94100.52",
        equity="94100.52",
        buying_power="372934.08",
        options_approved_level=3,
    )
    with patch.object(AlpacaSDKAdapter, "_init_trading_client", return_value=mock_client):
        adapter = AlpacaSDKAdapter()
        summary = adapter.get_account_summary()

    assert "error" not in summary
    assert summary["status"] in ("ACTIVE", "AccountStatus.ACTIVE")
    assert summary["cash"] > 0.0
    assert summary["account_number"] == "PA3C5AG0CECQ"
    assert summary["options_approved_level"] == 3


def test_alpaca_sdk_adapter_open_positions_mocked():
    mock_client = MagicMock()
    mock_client.get_all_positions.return_value = [object(), object()]
    with patch.object(AlpacaSDKAdapter, "_init_trading_client", return_value=mock_client):
        adapter = AlpacaSDKAdapter()
        count = adapter.get_open_positions_count()
    assert count == 2
