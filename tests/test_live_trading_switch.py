import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.trading.live_trading_switch import LiveTradingSwitch, LiveReadinessReport


def test_live_trading_switch_missing_credentials(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SOME_OTHER_KEY=123", encoding="utf-8")

    switch = LiveTradingSwitch(env_path=env_file)
    report = switch.inspect_live_readiness()

    assert report.live_credentials_present is False
    assert report.live_trading_active is False
    assert "ALPACA_LIVE_API_KEY" in report.status_message


@patch("requests.get")
def test_live_trading_switch_active_cash(mock_get, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("ALPACA_LIVE_API_KEY=test_key\nALPACA_LIVE_API_SECRET=test_secret", encoding="utf-8")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "cash": "5000.00",
        "buying_power": "20000.00",
        "options_approved_level": "3",
    }
    mock_get.return_value = mock_resp

    switch = LiveTradingSwitch(env_path=env_file)
    report = switch.inspect_live_readiness()

    assert report.live_credentials_present is True
    assert report.live_api_valid is True
    assert report.live_cash_balance == 5000.0
    assert report.options_approved_level == 3
    assert report.live_trading_active is True
