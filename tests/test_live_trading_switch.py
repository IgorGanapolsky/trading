import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.trading.live_trading_switch import LiveTradingSwitch


def test_live_trading_switch_missing_credentials(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("SOME_OTHER_KEY=123", encoding="utf-8")
    kill = tmp_path / "kill.json"
    kill.write_text(
        json.dumps({"paper_only": True, "live_blocked": True, "reason": "test"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "src.trading.live_trading_switch.KILL_SWITCH_FILE", kill
    )
    monkeypatch.setattr(
        "src.trading.live_trading_switch.LIVE_READINESS_FILE",
        tmp_path / "readiness.json",
    )

    switch = LiveTradingSwitch(env_path=env_file)
    report = switch.inspect_live_readiness()

    assert report.live_credentials_present is False
    assert report.live_trading_active is False
    assert "ALPACA_LIVE_API_KEY" in report.status_message


@patch("requests.get")
def test_live_trading_switch_funded_but_policy_blocked(mock_get, tmp_path, monkeypatch):
    """Cash alone must NOT claim live trading active while kill switch blocks live."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ALPACA_LIVE_API_KEY=test_key\nALPACA_LIVE_API_SECRET=test_secret",
        encoding="utf-8",
    )
    kill = tmp_path / "kill.json"
    kill.write_text(
        json.dumps(
            {
                "paper_only": True,
                "live_blocked": True,
                "reason": "IC killed; put-credit paper validation only",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "src.trading.live_trading_switch.KILL_SWITCH_FILE", kill
    )
    monkeypatch.setattr(
        "src.trading.live_trading_switch.LIVE_READINESS_FILE",
        tmp_path / "readiness.json",
    )

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
    assert report.account_funded is True
    assert report.policy_live_blocked is True
    assert report.live_trading_active is False
    assert "LIVE RISK BLOCKED" in report.status_message
    assert "LIVE REAL MONEY TRADING ACTIVE" not in report.status_message


@patch("requests.get")
def test_live_trading_switch_active_when_policy_allows(mock_get, tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ALPACA_LIVE_API_KEY=test_key\nALPACA_LIVE_API_SECRET=test_secret",
        encoding="utf-8",
    )
    kill = tmp_path / "kill.json"
    kill.write_text(
        json.dumps(
            {
                "paper_only": False,
                "live_blocked": False,
                "reason": "edge proven",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "src.trading.live_trading_switch.KILL_SWITCH_FILE", kill
    )
    monkeypatch.setattr(
        "src.trading.live_trading_switch.LIVE_READINESS_FILE",
        tmp_path / "readiness.json",
    )

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

    assert report.live_trading_active is True
    assert report.account_funded is True
    assert report.policy_live_blocked is False
    assert "LIVE REAL MONEY TRADING ACTIVE" in report.status_message


@patch("requests.get")
def test_live_trading_switch_api_401(mock_get, tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ALPACA_LIVE_API_KEY=test_key\nALPACA_LIVE_API_SECRET=test_secret",
        encoding="utf-8",
    )
    kill = tmp_path / "kill.json"
    kill.write_text(json.dumps({"paper_only": True, "live_blocked": True}), encoding="utf-8")
    monkeypatch.setattr("src.trading.live_trading_switch.KILL_SWITCH_FILE", kill)
    monkeypatch.setattr(
        "src.trading.live_trading_switch.LIVE_READINESS_FILE",
        tmp_path / "readiness.json",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = '{"message": "unauthorized."}'
    mock_get.return_value = mock_resp

    report = LiveTradingSwitch(env_path=env_file).inspect_live_readiness()
    assert report.live_api_valid is False
    assert report.live_trading_active is False
    assert "401" in report.status_message
