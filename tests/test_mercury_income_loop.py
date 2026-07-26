import json
from pathlib import Path

from scripts.mercury_income_loop import _load_state, _save_state, run_once
from src.adapters.bank_adapter import PaperBankAdapter, TransferResult
from src.adapters.equity_broker_adapter import PaperEquityBrokerAdapter
from src.bank.remittance import MONTHLY_AFTER_TAX_TARGET_USD
from src.bank.transfer_ledger import load_transfer_ledger
from src.strategies.dividend_growth_strategy import DividendGrowthStrategy


def _fresh_state():
    return {
        "principal_deployed_usd": 0.0,
        "realized_profit_usd": 0.0,
        "realized_pre_tax_pnl_usd": 0.0,
        "events": [],
    }


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

    def test_dividend_income_collected_and_added_to_realized_profit(self):
        bank = PaperBankAdapter(starting_balance_usd=0.0)
        equity_broker = PaperEquityBrokerAdapter()
        equity_broker._positions["SCHD"] = 1000.0
        equity_broker.accrue_dividends_for_days(30)
        state = _fresh_state()

        state = run_once(
            bank,
            DividendGrowthStrategy(),
            state,
            equity_broker=equity_broker,
            bank_buffer_usd=500.0,
            profit_return_threshold_usd=9999.0,  # keep it from also being paid out this step
        )

        income_events = [e for e in state["events"] if e["type"] == "dividend_income_collected"]
        assert len(income_events) == 1
        assert state["realized_profit_usd"] > 0
        # collecting again immediately should yield nothing new
        assert equity_broker.collect_dividend_income().total_usd == 0.0

    def test_no_dividend_event_when_nothing_accrued(self):
        bank = PaperBankAdapter(starting_balance_usd=0.0)
        equity_broker = PaperEquityBrokerAdapter()
        state = run_once(
            bank,
            DividendGrowthStrategy(),
            _fresh_state(),
            equity_broker=equity_broker,
            bank_buffer_usd=500.0,
        )

        assert not [e for e in state["events"] if e["type"] == "dividend_income_collected"]

    def test_sends_realized_profit_back_once_threshold_crossed(self):
        bank = PaperBankAdapter(starting_balance_usd=0.0)
        state = _fresh_state()
        state["realized_profit_usd"] = 60.0

        state = run_once(
            bank,
            DividendGrowthStrategy(),
            state,
            equity_broker=PaperEquityBrokerAdapter(),
            bank_buffer_usd=500.0,
            profit_return_threshold_usd=50.0,
        )

        assert state["realized_profit_usd"] == 0.0
        deposit_events = [e for e in state["events"] if e["type"] == "deposit"]
        assert len(deposit_events) == 1
        assert bank.get_balance().available_usd == 60.0

    def test_no_deposit_when_profit_below_threshold(self):
        bank = PaperBankAdapter(starting_balance_usd=0.0)
        state = _fresh_state()
        state["realized_profit_usd"] = 10.0

        state = run_once(
            bank,
            DividendGrowthStrategy(),
            state,
            equity_broker=PaperEquityBrokerAdapter(),
            bank_buffer_usd=500.0,
            profit_return_threshold_usd=50.0,
        )

        assert state["realized_profit_usd"] == 10.0
        assert not [e for e in state["events"] if e["type"] == "deposit"]

    def test_failed_withdrawal_does_not_increment_principal_or_execute_buys(self, monkeypatch):
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


class TestLedgerIntegration:
    """Verify transfers are logged to the durable transfer ledger."""

    def test_withdrawal_logs_mercury_to_broker_record(self, tmp_path: Path):
        ledger = tmp_path / "ledger.jsonl"
        bank = PaperBankAdapter(starting_balance_usd=1000.0)
        run_once(
            bank,
            DividendGrowthStrategy(),
            _fresh_state(),
            equity_broker=PaperEquityBrokerAdapter(),
            bank_buffer_usd=500.0,
            ledger_path=ledger,
        )
        records = load_transfer_ledger(ledger_path=ledger)
        withdraws = [r for r in records if r.direction == "mercury_to_broker"]
        assert len(withdraws) == 1
        assert withdraws[0].amount_usd == 500.0
        assert withdraws[0].status == "confirmed"
        assert withdraws[0].dry_run is True

    def test_deposit_logs_broker_to_mercury_record(self, tmp_path: Path):
        ledger = tmp_path / "ledger.jsonl"
        bank = PaperBankAdapter(starting_balance_usd=0.0)
        state = _fresh_state()
        state["realized_profit_usd"] = 60.0
        run_once(
            bank,
            DividendGrowthStrategy(),
            state,
            equity_broker=PaperEquityBrokerAdapter(),
            bank_buffer_usd=500.0,
            profit_return_threshold_usd=50.0,
            ledger_path=ledger,
        )
        records = load_transfer_ledger(ledger_path=ledger)
        deposits = [r for r in records if r.direction == "broker_to_mercury"]
        assert len(deposits) == 1
        assert deposits[0].amount_usd == 60.0
        assert deposits[0].status == "confirmed"

    def test_failed_withdrawal_logs_failed_record(self, tmp_path: Path):
        ledger = tmp_path / "ledger.jsonl"
        bank = PaperBankAdapter(starting_balance_usd=1000.0)
        # Force a failed withdrawal
        bank.send_to_broker = lambda amount_usd, idempotency_key: TransferResult(
            success=False,
            transfer_id=None,
            amount_usd=amount_usd,
            direction="to_broker",
            initiated_at="2026-01-01T00:00:00+00:00",
            error="simulated",
        )
        run_once(
            bank,
            DividendGrowthStrategy(),
            _fresh_state(),
            equity_broker=PaperEquityBrokerAdapter(),
            bank_buffer_usd=500.0,
            ledger_path=ledger,
        )
        records = load_transfer_ledger(ledger_path=ledger)
        failed = [r for r in records if r.status == "failed"]
        assert len(failed) == 1
        assert failed[0].amount_usd == 500.0

    def test_no_ledger_path_does_not_crash(self):
        """run_once must not crash when ledger_path is None."""
        bank = PaperBankAdapter(starting_balance_usd=1000.0)
        state = run_once(
            bank,
            DividendGrowthStrategy(),
            _fresh_state(),
            equity_broker=PaperEquityBrokerAdapter(),
            bank_buffer_usd=500.0,
            ledger_path=None,
        )
        assert state["principal_deployed_usd"] == 500.0


class TestRemittanceProgress:
    """Verify remittance progress toward $1000/mo is computed and stored."""

    def test_remittance_progress_in_state(self, tmp_path: Path):
        ledger = tmp_path / "ledger.jsonl"
        bank = PaperBankAdapter(starting_balance_usd=1000.0)
        state = run_once(
            bank,
            DividendGrowthStrategy(),
            _fresh_state(),
            equity_broker=PaperEquityBrokerAdapter(),
            bank_buffer_usd=500.0,
            ledger_path=ledger,
        )
        progress = state["remittance_progress"]
        assert progress["target_usd"] == MONTHLY_AFTER_TAX_TARGET_USD
        assert progress["remitted_to_bank_usd"] == 0.0
        assert progress["target_met"] is False
        assert progress["claim_allowed"] is False

    def test_remittance_progress_reflects_confirmed_deposits(self, tmp_path: Path):
        """Confirmed (non-dry-run) deposits count toward remittance target.

        PaperBankAdapter transfers are dry-run, so they are correctly NOT
        counted. This test manually adds a confirmed non-dry-run record to
        simulate what a live run would produce.
        """
        from src.bank.transfer_ledger import (
            TransferDirection,
            TransferStatus,
            append_transfer_record,
            build_transfer_record,
        )

        ledger = tmp_path / "ledger.jsonl"
        # Simulate a confirmed non-dry-run deposit (what live mode would log)
        append_transfer_record(
            build_transfer_record(
                direction=TransferDirection.BROKER_TO_MERCURY,
                amount_usd=60.0,
                status=TransferStatus.CONFIRMED,
                dry_run=False,
                timestamp="2026-07-25T12:00:00+00:00",
            ),
            ledger_path=ledger,
        )
        bank = PaperBankAdapter(starting_balance_usd=0.0)
        state = _fresh_state()
        state["realized_profit_usd"] = 60.0
        run_once(
            bank,
            DividendGrowthStrategy(),
            state,
            equity_broker=PaperEquityBrokerAdapter(),
            bank_buffer_usd=500.0,
            profit_return_threshold_usd=50.0,
            ledger_path=ledger,
        )
        progress = state["remittance_progress"]
        assert progress["remitted_to_bank_usd"] == 60.0
        assert progress["remittance_event_count"] == 1

    def test_dry_run_deposits_not_counted_toward_target(self, tmp_path: Path):
        """Paper mode deposits (dry_run=True) must NOT count toward $1000/mo target."""
        ledger = tmp_path / "ledger.jsonl"
        bank = PaperBankAdapter(starting_balance_usd=0.0)
        state = _fresh_state()
        state["realized_profit_usd"] = 60.0
        run_once(
            bank,
            DividendGrowthStrategy(),
            state,
            equity_broker=PaperEquityBrokerAdapter(),
            bank_buffer_usd=500.0,
            profit_return_threshold_usd=50.0,
            ledger_path=ledger,
        )
        progress = state["remittance_progress"]
        assert progress["remitted_to_bank_usd"] == 0.0
        assert progress["target_met"] is False
        assert progress["claim_allowed"] is False

    def test_remittance_progress_tracks_pre_tax_pnl(self, tmp_path: Path):
        ledger = tmp_path / "ledger.jsonl"
        bank = PaperBankAdapter(starting_balance_usd=0.0)
        equity_broker = PaperEquityBrokerAdapter()
        equity_broker._positions["SCHD"] = 1000.0
        equity_broker.accrue_dividends_for_days(30)
        state = _fresh_state()
        run_once(
            bank,
            DividendGrowthStrategy(),
            state,
            equity_broker=equity_broker,
            bank_buffer_usd=500.0,
            profit_return_threshold_usd=9999.0,
            ledger_path=ledger,
            tax_rate=0.15,
        )
        progress = state["remittance_progress"]
        assert progress["realized_pre_tax_pnl_usd"] is not None
        assert progress["realized_pre_tax_pnl_usd"] > 0
        assert progress["estimated_after_tax_profit_usd"] is not None
        # After-tax should be less than pre-tax at 15% rate
        assert progress["estimated_after_tax_profit_usd"] < progress["realized_pre_tax_pnl_usd"]


class TestTaxAwareProfit:
    """Verify tax-aware profit tracking in the income loop."""

    def test_dividend_event_includes_tax_rate_and_after_tax_estimate(self, tmp_path: Path):
        bank = PaperBankAdapter(starting_balance_usd=0.0)
        equity_broker = PaperEquityBrokerAdapter()
        equity_broker._positions["SCHD"] = 1000.0
        equity_broker.accrue_dividends_for_days(30)
        state = _fresh_state()
        run_once(
            bank,
            DividendGrowthStrategy(),
            state,
            equity_broker=equity_broker,
            bank_buffer_usd=500.0,
            profit_return_threshold_usd=9999.0,
            tax_rate=0.15,
        )
        dividend_events = [e for e in state["events"] if e["type"] == "dividend_income_collected"]
        assert len(dividend_events) == 1
        event = dividend_events[0]
        assert event["tax_rate"] == 0.15
        assert "after_tax_estimate" in event
        assert event["after_tax_estimate"] > 0

    def test_realized_pre_tax_pnl_accumulates(self, tmp_path: Path):
        bank = PaperBankAdapter(starting_balance_usd=0.0)
        equity_broker = PaperEquityBrokerAdapter()
        equity_broker._positions["SCHD"] = 1000.0
        equity_broker.accrue_dividends_for_days(30)
        state = _fresh_state()
        run_once(
            bank,
            DividendGrowthStrategy(),
            state,
            equity_broker=equity_broker,
            bank_buffer_usd=500.0,
            profit_return_threshold_usd=9999.0,
            tax_rate=0.15,
        )
        assert state["realized_pre_tax_pnl_usd"] > 0
        assert state["realized_profit_usd"] == state["realized_pre_tax_pnl_usd"]
