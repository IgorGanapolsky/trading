import importlib

import pytest

import mcp.servers.mercury as mercury_server
from mcp.registry import load_registry
from src.adapters.mercury_readonly import MercuryReadOnlyClient


@pytest.fixture(autouse=True)
def reset_cached_client():
    mercury_server._reset_client()
    yield
    mercury_server._reset_client()


class TestRegistryConsistency:
    def test_mercury_server_registered(self):
        registry = load_registry()
        assert "mercury" in registry

    def test_registered_tools_exist_in_module(self):
        """Drift guard: every registry tool must resolve to a module function."""
        server = load_registry().get("mercury")
        module = importlib.import_module(server.module)
        for tool_name, function_name in server.tools.items():
            assert callable(getattr(module, function_name, None)), (
                f"registry tool '{tool_name}' points at missing function "
                f"'{server.module}.{function_name}'"
            )


def _install_fake_client(monkeypatch, response):
    client = MercuryReadOnlyClient("tok", http_get=lambda u, p, h: response)
    monkeypatch.setattr(mercury_server, "_client", client)
    return client


class TestTools:
    def test_get_bank_status_success(self, monkeypatch):
        _install_fake_client(
            monkeypatch,
            {"accounts": [{"id": "a", "availableBalance": 42.0, "status": "active"}]},
        )
        result = mercury_server.get_bank_status()
        assert result["success"] is True
        assert result["total_available_usd"] == 42.0
        assert result["read_only"] is True

    def test_get_bank_transactions_success(self, monkeypatch):
        _install_fake_client(
            monkeypatch,
            {"total": 1, "transactions": [{"id": "t1", "amount": -5.0}]},
        )
        result = mercury_server.get_bank_transactions(account="checking", limit=5)
        assert result["success"] is True
        assert result["account"] == "checking"
        assert result["total"] == 1

    def test_get_bank_health_success(self, monkeypatch):
        _install_fake_client(monkeypatch, {"accounts": [{"id": "a"}, {"id": "b"}]})
        result = mercury_server.get_bank_health()
        assert result["success"] is True
        assert result["reachable"] is True
        assert result["accounts"] == 2

    def test_tools_report_errors_instead_of_raising(self, monkeypatch):
        def boom(url, params, headers):
            raise RuntimeError("api down")

        client = MercuryReadOnlyClient("tok", http_get=boom)
        monkeypatch.setattr(mercury_server, "_client", client)

        for tool in (
            mercury_server.get_bank_status,
            mercury_server.get_bank_transactions,
            mercury_server.get_bank_health,
        ):
            result = tool()
            assert result["success"] is False
            assert "api down" in result["error"]

    def test_missing_credentials_is_reported_not_raised(self, monkeypatch, tmp_path):
        monkeypatch.delenv("MERCURY_API_TOKEN", raising=False)
        monkeypatch.setenv("MERCURY_SECRETS_PATH", str(tmp_path / "missing.json"))
        result = mercury_server.get_bank_status()
        assert result["success"] is False
        assert "MERCURY_API_TOKEN" in result["error"]
