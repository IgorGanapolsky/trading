from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str) -> ModuleType:
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_store_from_clipboard_writes_verifies_and_clears(monkeypatch):
    module = load_script("store_alpaca_keychain.py")
    calls: list[tuple[str, str]] = []
    cleared: list[bool] = []
    value = "paper-secret-value"

    monkeypatch.setattr(module, "read_clipboard", lambda: value)
    monkeypatch.setattr(
        module, "keychain_write", lambda service, item: calls.append((service, item))
    )
    monkeypatch.setattr(module, "keychain_read", lambda service: value)
    monkeypatch.setattr(module, "clear_clipboard", lambda: cleared.append(True))

    result = module.store_from_clipboard("api-secret")

    assert calls == [("trading.alpaca.paper.api-secret", value)]
    assert cleared == [True]
    assert result.length == len(value)
    assert result.fingerprint == hashlib.sha256(value.encode()).hexdigest()[:12]


def test_store_from_clipboard_clears_when_verification_fails(monkeypatch):
    module = load_script("store_alpaca_keychain.py")
    cleared: list[bool] = []

    monkeypatch.setattr(module, "read_clipboard", lambda: "expected")
    monkeypatch.setattr(module, "keychain_write", lambda service, item: None)
    monkeypatch.setattr(module, "keychain_read", lambda service: "different")
    monkeypatch.setattr(module, "clear_clipboard", lambda: cleared.append(True))

    try:
        module.store_from_clipboard("api-key")
    except RuntimeError as exc:
        assert "verification mismatch" in str(exc)
    else:
        raise AssertionError("expected verification mismatch")

    assert cleared == [True]


def test_load_credentials_requires_both_keychain_values(monkeypatch):
    module = load_script("run_with_alpaca_keychain.py")

    monkeypatch.setattr(
        module,
        "_keychain_read",
        lambda service: "key" if service == module.KEY_SERVICE else None,
    )

    assert module.load_credentials() is None


def test_credential_env_sets_only_canonical_paper_names(monkeypatch):
    module = load_script("run_with_alpaca_keychain.py")
    monkeypatch.setenv("PRESERVE_ME", "yes")
    credentials = module.Credentials(api_key="key", api_secret="secret")

    env = module.credential_env(credentials)

    assert env["ALPACA_PAPER_TRADING_API_KEY"] == "key"
    assert env["ALPACA_PAPER_TRADING_API_SECRET"] == "secret"
    assert env["PRESERVE_ME"] == "yes"
    assert "ALPACA_BROKERAGE_TRADING_API_KEY" not in env
    assert "ALPACA_BROKERAGE_TRADING_API_SECRET" not in env
