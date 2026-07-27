import json

import pytest

import scripts.mercury_cli as mercury_cli
from src.adapters.mercury_readonly import MercuryReadOnlyClient

ACCOUNTS_RESPONSE = {
    "accounts": [
        {
            "id": "644ce680-aaaa-bbbb-cccc-dddddddddddd",
            "name": "Mercury Checking",
            "kind": "checking",
            "status": "active",
            "currentBalance": 12.5,
            "availableBalance": 10.0,
            "accountNumber": "123456787725",
        }
    ]
}

TRANSACTIONS_RESPONSE = {
    "total": 1,
    "transactions": [
        {
            "id": "txn-12345678",
            "amount": -25.0,
            "kind": "externalTransfer",
            "status": "sent",
            "createdAt": "2026-07-26T00:00:00Z",
            "counterpartyName": "Discover",
        }
    ],
}


def _fake_client(response):
    return MercuryReadOnlyClient("tok", http_get=lambda u, p, h: response)


def _run(argv, client, monkeypatch):
    monkeypatch.setattr(
        mercury_cli.MercuryReadOnlyClient, "from_env", staticmethod(lambda: client)
    )
    return mercury_cli.main(argv)


class TestCommands:
    def test_accounts_table_masks_and_totals(self, capsys, monkeypatch):
        assert _run(["accounts"], _fake_client(ACCOUNTS_RESPONSE), monkeypatch) == 0
        out = capsys.readouterr().out
        assert "Mercury Checking" in out
        assert "TOTAL available: $10.00" in out
        assert "123456787725" not in out

    def test_accounts_json_is_machine_readable(self, capsys, monkeypatch):
        assert _run(["accounts", "--json"], _fake_client(ACCOUNTS_RESPONSE), monkeypatch) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["read_only"] is True
        assert payload["total_available_usd"] == 10.0

    def test_transactions_table(self, capsys, monkeypatch):
        code = _run(
            ["transactions", "--account", "checking", "--limit", "5"],
            _fake_client(TRANSACTIONS_RESPONSE),
            monkeypatch,
        )
        assert code == 0
        out = capsys.readouterr().out
        assert "externalTransfer" in out
        assert "Discover" in out

    def test_transactions_json(self, capsys, monkeypatch):
        code = _run(
            ["transactions", "--json"], _fake_client(TRANSACTIONS_RESPONSE), monkeypatch
        )
        assert code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["total"] == 1

    def test_transactions_empty_book(self, capsys, monkeypatch):
        code = _run(
            ["transactions"], _fake_client({"total": 0, "transactions": []}), monkeypatch
        )
        assert code == 0
        assert "(no transactions)" in capsys.readouterr().out

    def test_sync_writes_snapshot_file(self, tmp_path, capsys, monkeypatch):
        state_path = tmp_path / "mercury_state.json"
        code = _run(
            ["sync", "--state-path", str(state_path)],
            _fake_client(ACCOUNTS_RESPONSE),
            monkeypatch,
        )
        assert code == 0
        snapshot = json.loads(state_path.read_text(encoding="utf-8"))
        assert snapshot["total_available_usd"] == 10.0
        assert "✅ Mercury sync complete" in capsys.readouterr().out

    def test_health_reports_active_accounts(self, capsys, monkeypatch):
        assert _run(["health"], _fake_client(ACCOUNTS_RESPONSE), monkeypatch) == 0
        assert "2 accounts" not in capsys.readouterr().out  # exactly one account in fixture


class TestFailurePaths:
    def test_missing_credentials_exits_1(self, capsys, monkeypatch):
        def raise_value_error():
            raise ValueError("MERCURY_API_TOKEN missing")

        monkeypatch.setattr(
            mercury_cli.MercuryReadOnlyClient, "from_env", staticmethod(raise_value_error)
        )
        assert mercury_cli.main(["accounts"]) == 1
        assert "❌ Mercury credentials missing" in capsys.readouterr().out

    def test_api_failure_exits_1_without_traceback(self, capsys, monkeypatch):
        def boom(url, params, headers):
            raise RuntimeError("api down")

        client = MercuryReadOnlyClient("tok", http_get=boom)
        assert _run(["health"], client, monkeypatch) == 1
        out = capsys.readouterr().out
        assert "❌ Mercury health failed: api down" in out
        assert "Traceback" not in out


class TestParser:
    def test_requires_subcommand(self):
        with pytest.raises(SystemExit):
            mercury_cli.build_parser().parse_args([])
