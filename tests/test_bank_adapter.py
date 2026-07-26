import pytest

from src.adapters.bank_adapter import MercuryBankAdapter, PaperBankAdapter


class TestPaperBankAdapter:
    def test_starting_balance_reflected_in_get_balance(self):
        bank = PaperBankAdapter(starting_balance_usd=1000.0)
        balance = bank.get_balance()
        assert balance.available_usd == 1000.0
        assert balance.account_id == "paper-mercury-sim"

    def test_send_to_broker_debits_balance_on_success(self):
        bank = PaperBankAdapter(starting_balance_usd=1000.0)
        result = bank.send_to_broker(300.0, idempotency_key="k1")
        assert result.success is True
        assert result.direction == "to_broker"
        assert bank.get_balance().available_usd == 700.0

    def test_send_to_broker_rejects_non_positive_amount(self):
        bank = PaperBankAdapter(starting_balance_usd=1000.0)
        result = bank.send_to_broker(0.0, idempotency_key="k1")
        assert result.success is False
        assert "positive" in result.error
        assert bank.get_balance().available_usd == 1000.0

    def test_send_to_broker_rejects_insufficient_balance(self):
        bank = PaperBankAdapter(starting_balance_usd=100.0)
        result = bank.send_to_broker(300.0, idempotency_key="k1")
        assert result.success is False
        assert "insufficient balance" in result.error
        assert bank.get_balance().available_usd == 100.0

    def test_record_incoming_from_broker_credits_balance(self):
        bank = PaperBankAdapter(starting_balance_usd=0.0)
        result = bank.record_incoming_from_broker(75.0)
        assert result.success is True
        assert result.direction == "to_bank"
        assert bank.get_balance().available_usd == 75.0


class TestMercuryBankAdapterSafety:
    def test_refuses_construction_without_token(self):
        with pytest.raises(ValueError, match="MERCURY_API_TOKEN"):
            MercuryBankAdapter(
                account_id="acct-1",
                recipient_id="recipient-1",
                _api_token="",
                _live_enabled=True,
            )

    def test_refuses_construction_without_live_flag_even_with_token(self):
        with pytest.raises(RuntimeError, match="MERCURY_LIVE_TRANSFERS_ENABLED"):
            MercuryBankAdapter(
                account_id="acct-1",
                recipient_id="recipient-1",
                _api_token="fake-token",
                _live_enabled=False,
            )

    def test_from_env_requires_both_token_and_account_id(self, monkeypatch, tmp_path):
        monkeypatch.delenv("MERCURY_API_TOKEN", raising=False)
        monkeypatch.delenv("MERCURY_ACCOUNT_ID", raising=False)
        monkeypatch.setenv("MERCURY_SECRETS_PATH", str(tmp_path / "nonexistent.json"))
        with pytest.raises(ValueError, match="MERCURY_API_TOKEN"):
            MercuryBankAdapter.from_env(recipient_id="recipient-1")

    def test_from_env_defaults_live_disabled(self, monkeypatch):
        monkeypatch.setenv("MERCURY_API_TOKEN", "fake-token")
        monkeypatch.setenv("MERCURY_ACCOUNT_ID", "acct-1")
        monkeypatch.delenv("MERCURY_LIVE_TRANSFERS_ENABLED", raising=False)
        with pytest.raises(RuntimeError, match="MERCURY_LIVE_TRANSFERS_ENABLED"):
            MercuryBankAdapter.from_env(recipient_id="recipient-1")

    def test_from_env_constructs_when_explicitly_enabled(self, monkeypatch):
        monkeypatch.setenv("MERCURY_API_TOKEN", "fake-token")
        monkeypatch.setenv("MERCURY_ACCOUNT_ID", "acct-1")
        monkeypatch.setenv("MERCURY_LIVE_TRANSFERS_ENABLED", "1")
        adapter = MercuryBankAdapter.from_env(recipient_id="recipient-1")
        assert adapter.account_id == "acct-1"
