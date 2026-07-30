import pytest
from pathlib import Path
from src.brokers.alpaca_sdk_adapter import AlpacaSDKAdapter


def test_alpaca_sdk_adapter_connection():
    adapter = AlpacaSDKAdapter()
    summary = adapter.get_account_summary()

    assert "error" not in summary
    assert summary["status"] == "AccountStatus.ACTIVE" or summary["status"] == "ACTIVE"
    assert summary["cash"] > 0.0
    assert summary["account_number"] == "PA3C5AG0CECQ"


def test_alpaca_sdk_adapter_open_positions():
    adapter = AlpacaSDKAdapter()
    count = adapter.get_open_positions_count()
    assert isinstance(count, int)
    assert count >= 0
