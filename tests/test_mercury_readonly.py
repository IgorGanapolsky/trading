import json

import pytest

from src.adapters.mercury_readonly import (
    MercuryReadOnlyClient,
    resolve_token,
    summarize_account,
    summarize_transaction,
)


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    """Isolate tests from the real env vars and the real vault file."""
    for key in ("MERCURY_API_TOKEN", "MERCURY_ACCOUNT_ID", "MERCURY_SAVINGS_ACCOUNT_ID"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("MERCURY_SECRETS_PATH", str(tmp_path / "missing.json"))
    return tmp_path


def _write_vault(tmp_path, payload):
    vault = tmp_path / "mercury.json"
    vault.write_text(json.dumps(payload), encoding="utf-8")
    return vault


class TestTokenResolution:
    def test_env_var_wins(self, clean_env, monkeypatch):
        monkeypatch.setenv("MERCURY_API_TOKEN", "env-token")
        assert resolve_token() == "env-token"

    def test_vault_canonical_key(self, clean_env, monkeypatch):
        vault = _write_vault(clean_env, {"MERCURY_API_TOKEN": "vault-token"})
        monkeypatch.setenv("MERCURY_SECRETS_PATH", str(vault))
        assert resolve_token() == "vault-token"

    def test_vault_legacy_key(self, clean_env, monkeypatch):
        vault = _write_vault(clean_env, {"api_token": "legacy-token"})
        monkeypatch.setenv("MERCURY_SECRETS_PATH", str(vault))
        assert resolve_token() == "legacy-token"

    def test_missing_everywhere_is_none(self, clean_env):
        assert resolve_token() is None

    def test_from_env_refuses_without_token(self, clean_env):
        with pytest.raises(ValueError, match="MERCURY_API_TOKEN"):
            MercuryReadOnlyClient.from_env()

    def test_from_env_loads_account_aliases(self, clean_env, monkeypatch):
        vault = _write_vault(
            clean_env,
            {
                "MERCURY_API_TOKEN": "vault-token",
                "MERCURY_ACCOUNT_ID": "checking-id",
                "MERCURY_SAVINGS_ACCOUNT_ID": "savings-id",
            },
        )
        monkeypatch.setenv("MERCURY_SECRETS_PATH", str(vault))
        client = MercuryReadOnlyClient.from_env(http_get=lambda u, p, h: {})
        assert client.resolve_account_id("checking") == "checking-id"
        assert client.resolve_account_id("savings") == "savings-id"
        assert client.resolve_account_id("raw-uuid") == "raw-uuid"


class TestReadOnlyGuarantee:
    def test_public_surface_is_read_only(self):
        client = MercuryReadOnlyClient("t", http_get=lambda u, p, h: {})
        public = {m for m in dir(client) if not m.startswith("_")}
        assert public == {
            "list_accounts",
            "get_account",
            "get_transactions",
            "snapshot",
            "resolve_account_id",
            "from_env",
            "READ_METHODS",
        }

    def test_no_transfer_methods_exist(self):
        for forbidden in ("send_to_broker", "create_transaction", "post", "transfer"):
            assert not hasattr(MercuryReadOnlyClient, forbidden)


class TestRequests:
    def _recording_client(self, response):
        calls = []

        def http_get(url, params, headers):
            calls.append({"url": url, "params": params, "headers": headers})
            return response

        return MercuryReadOnlyClient("tok", http_get=http_get), calls

    def test_list_accounts_masks_rows(self):
        response = {
            "accounts": [
                {
                    "id": "644ce680-aaaa-bbbb-cccc-dddddddddddd",
                    "name": "Mercury Checking",
                    "kind": "checking",
                    "status": "active",
                    "currentBalance": 12.5,
                    "availableBalance": 10.0,
                    "accountNumber": "123456787725",
                },
                "not-a-dict",
            ]
        }
        client, calls = self._recording_client(response)
        accounts = client.list_accounts()
        assert len(accounts) == 1
        assert accounts[0]["account_number_last4"] == "7725"
        assert accounts[0]["id_prefix"] == "644ce680"
        assert "123456787725" not in json.dumps(accounts)
        assert calls[0]["url"].endswith("/accounts")
        assert calls[0]["headers"]["Authorization"] == "Bearer tok"

    def test_transactions_clamps_limit_and_masks(self):
        response = {
            "total": 1,
            "transactions": [
                {
                    "id": "txn-12345678",
                    "amount": -25.0,
                    "kind": "externalTransfer",
                    "status": "sent",
                    "createdAt": "2026-07-26T00:00:00Z",
                    "counterpartyName": "Alpaca",
                }
            ],
        }
        client, calls = self._recording_client(response)
        result = client.get_transactions("acct-1", limit=9999, offset=-5)
        assert calls[0]["params"] == {"limit": 500, "offset": 0}
        assert result["total"] == 1
        assert result["transactions"][0]["counterparty"] == "Alpaca"
        assert result["transactions"][0]["id_prefix"] == "txn-1234"

    def test_snapshot_totals_available_balances(self):
        response = {
            "accounts": [
                {"id": "a", "availableBalance": 10.0},
                {"id": "b", "availableBalance": 5.5},
                {"id": "c", "availableBalance": None},
            ]
        }
        client, _ = self._recording_client(response)
        snapshot = client.snapshot()
        assert snapshot["total_available_usd"] == 15.5
        assert snapshot["read_only"] is True
        assert "generated_at" in snapshot


class TestSummarizers:
    def test_summarize_account_handles_missing_fields(self):
        assert summarize_account({})["account_number_last4"] is None
        assert summarize_account({})["id_prefix"] is None

    def test_summarize_transaction_handles_missing_fields(self):
        row = summarize_transaction({})
        assert row["id_prefix"] is None
        assert row["amount_usd"] is None
