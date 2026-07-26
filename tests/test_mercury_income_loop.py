import json
import pytest

from scripts.mercury_income_loop import _load_state, _save_state, parse_args, run_once
from src.adapters.bank_adapter import PaperBankAdapter, TransferResult
from src.adapters.equity_broker_adapter import PaperEquityBrokerAdapter
from src.strategies.dividend_growth_strategy import DividendGrowthStrategy


def _fresh_state():
    return {
        "principal_deployed_usd": 0.0,
        "gross_profit_usd": 0.0,
        "realized_profit_usd": 0.0,
        "realized_after_tax_profit_usd": 0.0,
        "tax_reserve_usd": 0.0,
        "total_deposited_to_bank_usd": 0.0,
        "positions": {},
        "events": [],
    }


class TestParseArgs:
    def test_default_args(self):
        args = parse_args([])
        assert args.mode == "paper"
        assert args.profit_return_threshold_usd == 1000.0
        assert args.tax_rate_pct == 20.0


class TestRunOnce:
    def test_withdraws_surplus_above_buffer(self):
        bank = PaperBankAdapter(starting_balance_usd=1000.0)
        state = run_once(
            bank,
            DividendGrowthStrategy(),
            _fresh_state(),
            equity_broker=PaperEquityBrokerAdapter(),
            bank_buffer_usd=500.0,
        )

        assert state["principal_deployed_usd"] == 500.0
        assert bank.get_balance().available_usd == 500.0
        withdraw_events = [e for e in state["events"] if e["type"] == "withdraw"]
        assert len(withdraw_events) == 1
        assert withdraw_events[0]["success"] is True

    def test_no_withdrawal_when_balance_at_or_below_buffer(self):
        bank = PaperBankAdapter(starting_balance_usd=500.0)
        state = run_once(
            bank,
            DividendGrowthStrategy(),
            _fresh_state(),
            equity_broker=PaperEquityBrokerAdapter(),
            bank_buffer_usd=500.0,
        )

        assert state["principal_deployed_usd"] == 0.0
        assert not [e for e in state["events"] if e["type"] == "withdraw"]

    def test_dca_buy_executed_after_withdrawal(self):
        bank = PaperBankAdapter(starting_balance_usd=1500.0)
        equity_broker = PaperEquityBrokerAdapter()
        state = run_once(
            bank,
            DividendGrowthStrategy(),
            _fresh_state(),
            equity_broker=equity_broker,
            bank_buffer_usd=500.0,
        )

        buy_events = [e for e in state["events"] if e["type"] == "dca_buy"]
        assert len(buy_events) == 1
        assert buy_events[0]["symbol"] == "SCHD"
        assert buy_events[0]["notional_usd"] == 1000.0
        assert buy_events[0]["success"] is True
        assert equity_broker._positions["SCHD"] == 1000.0
        assert state["positions"]["SCHD"] == 1000.0

    def test_tax_reservation_and_after_tax_profit_accounting(self):
        bank = PaperBankAdapter(starting_balance_usd=0.0)
        equity_broker = PaperEquityBrokerAdapter()
        equity_broker._positions["SCHD"] = 10000.0
        equity_broker.accrue_dividends_for_days(365)  # $330 gross @ 3.3% yield
        state = _fresh_state()

        state = run_once(
            bank,
            DividendGrowthStrategy(),
            state,
            equity_broker=equity_broker,
            bank_buffer_usd=500.0,
            profit_return_threshold_usd=9999.0,  # hold payout
            tax_rate_pct=20.0,  # 20% tax reserve
        )

        income_events = [e for e in state["events"] if e["type"] == "dividend_income_collected"]
        assert len(income_events) == 1
        gross = income_events[0]["gross_amount_usd"]
        assert pytest.approx(gross, 0.01) == 330.0
        assert pytest.approx(state["tax_reserve_usd"], 0.01) == 66.0  # 20% of 330
        assert pytest.approx(state["realized_after_tax_profit_usd"], 0.01) == 264.0  # 80% of 330

    def test_sends_after_tax_profit_back_once_1000_threshold_crossed(self):
        bank = PaperBankAdapter(starting_balance_usd=0.0)
        state = _fresh_state()
        state["realized_after_tax_profit_usd"] = 1050.0

        state = run_once(
            bank,
            DividendGrowthStrategy(),
            state,
            equity_broker=PaperEquityBrokerAdapter(),
            bank_buffer_usd=500.0,
            profit_return_threshold_usd=1000.0,
        )

        assert state["realized_after_tax_profit_usd"] == 0.0
        assert state["total_deposited_to_bank_usd"] == 1050.0
        deposit_events = [e for e in state["events"] if e["type"] == "deposit"]
        assert len(deposit_events) == 1
        assert bank.get_balance().available_usd == 1050.0

    def test_no_deposit_when_after_tax_profit_below_1000_threshold(self):
        bank = PaperBankAdapter(starting_balance_usd=0.0)
        state = _fresh_state()
        state["realized_after_tax_profit_usd"] = 750.0

        state = run_once(
            bank,
            DividendGrowthStrategy(),
            state,
            equity_broker=PaperEquityBrokerAdapter(),
            bank_buffer_usd=500.0,
            profit_return_threshold_usd=1000.0,
        )

        assert state["realized_after_tax_profit_usd"] == 750.0
        assert state["total_deposited_to_bank_usd"] == 0.0
        assert not [e for e in state["events"] if e["type"] == "deposit"]

    def test_failed_withdrawal_does_not_increment_principal_or_execute_buys(self, monkeypatch):
        bank = PaperBankAdapter(starting_balance_usd=1000.0)
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
        equity_broker = PaperEquityBrokerAdapter()
        state = run_once(
            bank,
            DividendGrowthStrategy(),
            _fresh_state(),
            equity_broker=equity_broker,
            bank_buffer_usd=500.0,
        )

        assert state["principal_deployed_usd"] == 0.0
        assert not [e for e in state["events"] if e["type"] == "dca_buy"]
        assert not equity_broker._positions
        withdraw_events = [e for e in state["events"] if e["type"] == "withdraw"]
        assert withdraw_events[0]["success"] is False


class TestStatePersistence:
    def test_load_state_returns_fresh_default_when_file_missing(self, tmp_path):
        path = tmp_path / "does_not_exist.json"
        state = _load_state(path)
        assert state["principal_deployed_usd"] == 0.0
        assert state["tax_reserve_usd"] == 0.0

    def test_save_then_load_round_trips(self, tmp_path):
        path = tmp_path / "state.json"
        state = _fresh_state()
        state["principal_deployed_usd"] = 250.0
        state["tax_reserve_usd"] = 50.0
        state["positions"] = {"SCHD": 1000.0}
        _save_state(path, state)

        assert path.exists()
        reloaded = _load_state(path)
        assert reloaded["principal_deployed_usd"] == 250.0
        assert reloaded["tax_reserve_usd"] == 50.0
        assert reloaded["positions"]["SCHD"] == 1000.0

    def test_saved_file_is_valid_json(self, tmp_path):
        path = tmp_path / "state.json"
        _save_state(path, _fresh_state())
        with path.open() as handle:
            json.load(handle)
