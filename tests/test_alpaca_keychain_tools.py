from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str) -> ModuleType:
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    assert spec is not None
    assert spec.loader is not None
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


def test_clipboard_and_keychain_fail_closed(monkeypatch):
    module = load_script("store_alpaca_keychain.py")
    results = iter(
        [
            subprocess.CompletedProcess([], 1, "", "denied"),
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 1, "", "denied"),
            subprocess.CompletedProcess([], 1, "", "denied"),
        ]
    )
    monkeypatch.setattr(module, "_run", lambda *args, **kwargs: next(results))

    for operation, message in (
        (module.read_clipboard, "could not read"),
        (module.read_clipboard, "clipboard is empty"),
        (lambda: module.keychain_read("service"), "verification failed"),
        (lambda: module.keychain_write("service", "value"), "write failed"),
    ):
        try:
            operation()
        except (RuntimeError, ValueError) as exc:
            assert message in str(exc)
        else:
            raise AssertionError(f"expected failure containing {message}")


def test_clear_clipboard_reports_failure(monkeypatch):
    module = load_script("store_alpaca_keychain.py")
    monkeypatch.setattr(
        module,
        "_run",
        lambda *args, **kwargs: subprocess.CompletedProcess([], 1, "", "denied"),
    )

    try:
        module.clear_clipboard()
    except RuntimeError as exc:
        assert "clipboard clearing failed" in str(exc)
    else:
        raise AssertionError("expected clipboard clearing failure")


def test_store_main_success_and_failure(monkeypatch, capsys):
    module = load_script("store_alpaca_keychain.py")
    result = module.StoreResult(service="service", length=7, fingerprint="abc123")
    monkeypatch.setattr(module, "store_from_clipboard", lambda kind: result)
    assert module.main(["api-key", "--from-clipboard"]) == 0
    assert "clipboard=cleared" in capsys.readouterr().out

    def fail(kind):
        raise RuntimeError("denied")

    monkeypatch.setattr(module, "store_from_clipboard", fail)
    assert module.main(["api-secret", "--from-clipboard"]) == 2
    assert "error: denied" in capsys.readouterr().err


def test_wrapper_main_check_and_command_paths(monkeypatch, capsys):
    module = load_script("run_with_alpaca_keychain.py")
    credentials = module.Credentials(api_key="key", api_secret="secret")
    monkeypatch.setattr(module, "load_credentials", lambda: credentials)

    assert module.main(["--check"]) == 0
    assert "alpaca_keychain=ready" in capsys.readouterr().out
    assert module.main(["--check", "echo"]) == 2
    assert "does not accept" in capsys.readouterr().err
    assert module.main([]) == 2
    assert "provide --check" in capsys.readouterr().err

    observed = {}

    def run(command, *, env, check):
        observed["command"] = command
        observed["env"] = env
        observed["check"] = check
        return subprocess.CompletedProcess(command, 7)

    monkeypatch.setattr(module.subprocess, "run", run)
    assert module.main(["--", "example", "arg"]) == 7
    assert observed["command"] == ["example", "arg"]
    assert observed["env"]["ALPACA_PAPER_TRADING_API_KEY"] == "key"
    assert observed["check"] is False


def test_wrapper_missing_credentials_and_keychain_reads(monkeypatch, capsys):
    module = load_script("run_with_alpaca_keychain.py")
    monkeypatch.setattr(module, "load_credentials", lambda: None)
    assert module.main(["--check"]) == 2
    assert "credentials are incomplete" in capsys.readouterr().err

    responses = iter(
        [
            subprocess.CompletedProcess([], 1, "", "denied"),
            subprocess.CompletedProcess([], 0, "\n", ""),
            subprocess.CompletedProcess([], 0, "value\n", ""),
        ]
    )
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: next(responses))
    assert module._keychain_read("service") is None
    assert module._keychain_read("service") is None
    assert module._keychain_read("service") == "value"
