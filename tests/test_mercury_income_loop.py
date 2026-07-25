import json

from scripts.mercury_income_loop import _load_state, _save_state, run_once
from src.adapters.bank_adapter import PaperBankAdapter, TransferResult
from src.strategies.dividend_growth_strategy import DividendGrowthStrategy


def _fresh_state():
    return {"principal_deployed_usd": 0.0, "realized_profit_usd": 0.0, "events": []}


class TestRunOnce:
    def test_withdraws_surplus_above_buffer(self):
        bank = PaperBankAdapter(starting_balance_usd=1000.0)
        strategy = DividendGrowthStrategy()
        state = run_once(bank, strategy, _fresh_state(), bank_buffer_usd=500.0)

        assert state["principal_deployed_usd"] == 500.0
        assert bank.get_balance().available_usd == 500.0
        withdraw_events = [e for e in state["events"] if e["type"] == "withdraw"]
        assert len(withdraw_events) == 1
        assert withdraw_events[0]["success"] is True

    def test_no_withdrawal_when_balance_at_or_below_buffer(self):
        bank = PaperBankAdapter(starting_balance_usd=500.0)
        strategy = DividendGrowthStrategy()
        state = run_once(bank, strategy, _fresh_state(), bank_buffer_usd=500.0)

        assert state["principal_deployed_usd"] == 0.0
        assert not [e for e in state["events"] if e["type"] == "withdraw"]

    def test_dca_buy_planned_events_recorded_after_withdrawal(self):
        bank = PaperBankAdapter(starting_balance_usd=1500.0)
        strategy = DividendGrowthStrategy()
        state = run_once(bank, strategy, _fresh_state(), bank_buffer_usd=500.0)

        buy_events = [e for e in state["events"] if e["type"] == "dca_buy_planned"]
        assert len(buy_events) == 1
        assert buy_events[0]["symbol"] == "SCHD"
        assert buy_events[0]["notional_usd"] == 1000.0

    def test_sends_realized_profit_back_once_threshold_crossed(self):
        bank = PaperBankAdapter(starting_balance_usd=0.0)
        strategy = DividendGrowthStrategy()
        state = _fresh_state()
        state["realized_profit_usd"] = 60.0

        state = run_once(
            bank, strategy, state, bank_buffer_usd=500.0, profit_return_threshold_usd=50.0
        )

        assert state["realized_profit_usd"] == 0.0
        deposit_events = [e for e in state["events"] if e["type"] == "deposit"]
        assert len(deposit_events) == 1
        assert bank.get_balance().available_usd == 60.0

    def test_no_deposit_when_profit_below_threshold(self):
        bank = PaperBankAdapter(starting_balance_usd=0.0)
        strategy = DividendGrowthStrategy()
        state = _fresh_state()
        state["realized_profit_usd"] = 10.0

        state = run_once(
            bank, strategy, state, bank_buffer_usd=500.0, profit_return_threshold_usd=50.0
        )

        assert state["realized_profit_usd"] == 10.0
        assert not [e for e in state["events"] if e["type"] == "deposit"]

    def test_failed_withdrawal_does_not_increment_principal_or_plan_buys(self, monkeypatch):
        bank = PaperBankAdapter(starting_balance_usd=1000.0)
        # Simulate a broker-side rejection despite a real surplus being
        # available, independent of the adapter's own balance check.
        monkeypatch.setattr(
            bank,
            "send_to_broker",
            lambda amount_usd, idempotency_key: TransferResult(
                success=False,
                transfer_id=None,
                amount_usd=amount_usd,
                direction="to_broker",
                initiated_at="2026-01-01T00:00:00+00:00",
                error="simulated broker rejection",
            ),
        )
        strategy = DividendGrowthStrategy()
        state = run_once(bank, strategy, _fresh_state(), bank_buffer_usd=500.0)

        assert state["principal_deployed_usd"] == 0.0
        assert not [e for e in state["events"] if e["type"] == "dca_buy_planned"]
        withdraw_events = [e for e in state["events"] if e["type"] == "withdraw"]
        assert withdraw_events[0]["success"] is False


class TestStatePersistence:
    def test_load_state_returns_fresh_default_when_file_missing(self, tmp_path):
        path = tmp_path / "does_not_exist.json"
        state = _load_state(path)
        assert state == _fresh_state()

    def test_save_then_load_round_trips(self, tmp_path):
        path = tmp_path / "state.json"
        state = _fresh_state()
        state["principal_deployed_usd"] = 250.0
        _save_state(path, state)

        assert path.exists()
        reloaded = _load_state(path)
        assert reloaded["principal_deployed_usd"] == 250.0

    def test_saved_file_is_valid_json(self, tmp_path):
        path = tmp_path / "state.json"
        _save_state(path, _fresh_state())
        with path.open() as handle:
            json.load(handle)  # raises if invalid
