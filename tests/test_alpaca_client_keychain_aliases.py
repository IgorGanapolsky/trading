"""Keychain alias bootstrap for Alpaca paper credentials (AGENT-587)."""

from __future__ import annotations

import src.utils.alpaca_client as alpaca_client


def test_bootstrap_prefers_trading_paper_alias_when_hermes_fleet_missing(monkeypatch):
    monkeypatch.delenv("ALPACA_PAPER_TRADING_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_PAPER_TRADING_API_SECRET", raising=False)
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)

    def fake_keychain(service: str, account: str = "hermes-fleet"):
        if service == "trading.alpaca.paper.api-key" and account == "paper":
            return "PAPERKEY123"
        if service == "trading.alpaca.paper.api-secret" and account == "paper":
            return "PAPERSECRET456"
        return None

    monkeypatch.setattr(alpaca_client, "_keychain_generic_password", fake_keychain)
    alpaca_client._bootstrap_env_from_keychain()

    assert alpaca_client.os.environ["ALPACA_PAPER_TRADING_API_KEY"] == "PAPERKEY123"
    assert alpaca_client.os.environ["ALPACA_PAPER_TRADING_API_SECRET"] == "PAPERSECRET456"


def test_bootstrap_prefers_hermes_fleet_env_named_services(monkeypatch):
    monkeypatch.delenv("ALPACA_PAPER_TRADING_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_PAPER_TRADING_API_SECRET", raising=False)

    def fake_keychain(service: str, account: str = "hermes-fleet"):
        if service == "ALPACA_PAPER_TRADING_API_KEY" and account == "hermes-fleet":
            return "HERMESKEY"
        if service == "ALPACA_PAPER_TRADING_API_SECRET" and account == "hermes-fleet":
            return "HERMESSECRET"
        if service.startswith("trading.alpaca.paper"):
            return "SHOULD_NOT_USE"
        return None

    monkeypatch.setattr(alpaca_client, "_keychain_generic_password", fake_keychain)
    alpaca_client._bootstrap_env_from_keychain()

    assert alpaca_client.os.environ["ALPACA_PAPER_TRADING_API_KEY"] == "HERMESKEY"
    assert alpaca_client.os.environ["ALPACA_PAPER_TRADING_API_SECRET"] == "HERMESSECRET"


def test_bootstrap_skips_when_env_already_set(monkeypatch):
    monkeypatch.setenv("ALPACA_PAPER_TRADING_API_KEY", "ENVKEY")
    monkeypatch.setenv("ALPACA_PAPER_TRADING_API_SECRET", "ENVSECRET")
    calls: list[tuple[str, str]] = []

    def fake_keychain(service: str, account: str = "hermes-fleet"):
        calls.append((service, account))
        return "IGNORED"

    monkeypatch.setattr(alpaca_client, "_keychain_generic_password", fake_keychain)
    alpaca_client._bootstrap_env_from_keychain()

    assert alpaca_client.os.environ["ALPACA_PAPER_TRADING_API_KEY"] == "ENVKEY"
    assert alpaca_client.os.environ["ALPACA_PAPER_TRADING_API_SECRET"] == "ENVSECRET"
    # Only fallback env names (ALPACA_API_KEY / SECRET) may still be probed.
    assert all(not s.startswith("trading.alpaca.paper") for s, _ in calls)
