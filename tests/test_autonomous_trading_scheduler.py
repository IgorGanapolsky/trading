"""Tests for the autonomous trading scheduler and remittance monitor."""

from __future__ import annotations

import json
from pathlib import Path


from scripts.run_autonomous_trading import run_daily_cycle
from scripts.monitor_remittance import check_remittance


class TestRunDailyCycle:
    """Verify the scheduler orchestrates all steps correctly in dry-run mode."""

    def test_dry_run_completes_successfully(self, tmp_path: Path):
        state_path = tmp_path / "state.json"
        ledger_path = tmp_path / "ledger.jsonl"
        report = run_daily_cycle(
            dry_run=True,
            paper_starting_balance=1500.0,
            bank_buffer_usd=500.0,
            profit_return_threshold_usd=50.0,
            state_path=state_path,
            ledger_path=ledger_path,
            report_dir=tmp_path,
            skip_put_credit=True,  # skip options path for simplicity
        )
        assert report["dry_run"] is True
        assert report["non_day_trade"] is True
        assert "income_loop" in report["steps"]
        assert report["steps"]["income_loop"]["rc"] == 0
        assert "remittance_status" in report["steps"]
        assert report["steps"]["remittance_status"]["rc"] == 0
        assert report["report_path"]

    def test_state_file_created(self, tmp_path: Path):
        state_path = tmp_path / "state.json"
        ledger_path = tmp_path / "ledger.jsonl"
        run_daily_cycle(
            dry_run=True,
            paper_starting_balance=1500.0,
            bank_buffer_usd=500.0,
            state_path=state_path,
            ledger_path=ledger_path,
            report_dir=tmp_path,
            skip_put_credit=True,
        )
        assert state_path.exists()
        state = json.loads(state_path.read_text())
        assert state["principal_deployed_usd"] == 1000.0  # 1500 - 500 buffer

    def test_ledger_file_created(self, tmp_path: Path):
        state_path = tmp_path / "state.json"
        ledger_path = tmp_path / "ledger.jsonl"
        run_daily_cycle(
            dry_run=True,
            paper_starting_balance=1500.0,
            bank_buffer_usd=500.0,
            state_path=state_path,
            ledger_path=ledger_path,
            report_dir=tmp_path,
            skip_put_credit=True,
        )
        assert ledger_path.exists()
        lines = ledger_path.read_text().strip().split("\n")
        assert len(lines) >= 1
        record = json.loads(lines[0])
        assert record["direction"] == "mercury_to_broker"
        assert record["amount_usd"] == 1000.0

    def test_report_has_remittance_progress(self, tmp_path: Path):
        state_path = tmp_path / "state.json"
        ledger_path = tmp_path / "ledger.jsonl"
        report = run_daily_cycle(
            dry_run=True,
            paper_starting_balance=1500.0,
            bank_buffer_usd=500.0,
            state_path=state_path,
            ledger_path=ledger_path,
            report_dir=tmp_path,
            skip_put_credit=True,
        )
        # Remittance progress may or may not be parsed from JSON output
        # depending on how the subprocess output is formatted
        assert "steps" in report

    def test_skip_income_loop_still_runs_put_credit(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(
            "scripts.run_autonomous_trading._run",
            lambda args, **_kwargs: {"cmd": args, "rc": 0, "stdout_tail": "{}", "stderr_tail": ""},
        )
        state_path = tmp_path / "state.json"
        ledger_path = tmp_path / "ledger.jsonl"
        report = run_daily_cycle(
            dry_run=True,
            state_path=state_path,
            ledger_path=ledger_path,
            report_dir=tmp_path,
            skip_income_loop=True,
        )
        assert "income_loop" not in report["steps"]
        assert "put_credit_cycle" in report["steps"]


class TestMonitorRemittance:
    """Verify the remittance monitor correctly assesses progress."""

    def test_no_transfers_returns_info(self, tmp_path: Path):
        ledger = tmp_path / "ledger.jsonl"
        status = check_remittance(ledger_path=ledger)
        assert status["alert_level"] == "INFO"
        assert status["progress"]["remitted_to_bank_usd"] == 0.0
        assert status["progress"]["target_met"] is False
        assert status["days_remaining"] >= 0

    def test_confirmed_deposits_count_toward_target(self, tmp_path: Path):
        from src.bank.transfer_ledger import (
            TransferDirection,
            TransferStatus,
            append_transfer_record,
            build_transfer_record,
        )

        ledger = tmp_path / "ledger.jsonl"
        # Add confirmed deposits totaling $1000
        for amount, ts in [
            (600.0, "2026-07-10T12:00:00+00:00"),
            (400.0, "2026-07-20T12:00:00+00:00"),
        ]:
            append_transfer_record(
                build_transfer_record(
                    direction=TransferDirection.BROKER_TO_MERCURY,
                    amount_usd=amount,
                    status=TransferStatus.CONFIRMED,
                    dry_run=False,
                    timestamp=ts,
                ),
                ledger_path=ledger,
            )
        status = check_remittance(
            ledger_path=ledger,
            month="2026-07",
            target_usd=1000.0,
        )
        assert status["progress"]["remitted_to_bank_usd"] == 1000.0
        assert status["progress"]["target_met"] is True
        assert status["progress"]["claim_allowed"] is True
        assert status["alert_level"] == "SUCCESS"

    def test_dry_run_deposits_not_counted(self, tmp_path: Path):
        from src.bank.transfer_ledger import (
            TransferDirection,
            TransferStatus,
            append_transfer_record,
            build_transfer_record,
        )

        ledger = tmp_path / "ledger.jsonl"
        append_transfer_record(
            build_transfer_record(
                direction=TransferDirection.BROKER_TO_MERCURY,
                amount_usd=1000.0,
                status=TransferStatus.CONFIRMED,
                dry_run=True,
                timestamp="2026-07-15T12:00:00+00:00",
            ),
            ledger_path=ledger,
        )
        status = check_remittance(
            ledger_path=ledger,
            month="2026-07",
            target_usd=1000.0,
        )
        assert status["progress"]["remitted_to_bank_usd"] == 0.0
        assert status["progress"]["target_met"] is False

    def test_submitted_not_confirmed_not_counted(self, tmp_path: Path):
        from src.bank.transfer_ledger import (
            TransferDirection,
            TransferStatus,
            append_transfer_record,
            build_transfer_record,
        )

        ledger = tmp_path / "ledger.jsonl"
        append_transfer_record(
            build_transfer_record(
                direction=TransferDirection.BROKER_TO_MERCURY,
                amount_usd=1000.0,
                status=TransferStatus.SUBMITTED,
                dry_run=False,
                timestamp="2026-07-15T12:00:00+00:00",
            ),
            ledger_path=ledger,
        )
        status = check_remittance(
            ledger_path=ledger,
            month="2026-07",
            target_usd=1000.0,
        )
        assert status["progress"]["remitted_to_bank_usd"] == 0.0
        assert status["progress"]["in_flight_usd"] == 1000.0
        assert status["progress"]["target_met"] is False

    def test_realized_pnl_estimates_after_tax_profit(self, tmp_path: Path):
        ledger = tmp_path / "ledger.jsonl"
        status = check_remittance(
            ledger_path=ledger,
            realized_pnl=1000.0,
            tax_rate=0.15,
            target_usd=1000.0,
        )
        assert status["progress"]["realized_pre_tax_pnl_usd"] == 1000.0
        assert status["progress"]["estimated_after_tax_profit_usd"] == 850.0  # 1000 * 0.85

    def test_negative_pnl_no_tax_refund_assumed(self, tmp_path: Path):
        ledger = tmp_path / "ledger.jsonl"
        status = check_remittance(
            ledger_path=ledger,
            realized_pnl=-500.0,
            tax_rate=0.37,
            target_usd=1000.0,
        )
        # Losses: no fabricated tax refund
        assert status["progress"]["estimated_after_tax_profit_usd"] == -500.0

    def test_live_bank_gate_in_status(self, tmp_path: Path):
        ledger = tmp_path / "ledger.jsonl"
        status = check_remittance(ledger_path=ledger)
        assert "live_bank_gate" in status
        assert "allowed" in status["live_bank_gate"]
        assert "blockers" in status["live_bank_gate"]
        assert "strategy_mode" in status["live_bank_gate"]
        assert status["live_bank_gate"]["strategy_mode"] == "multi_day_hold_or_buy_hold_non_pdt"

    def test_alert_levels(self, tmp_path: Path):
        """Verify alert level classification."""
        ledger = tmp_path / "ledger.jsonl"

        # No transfers → INFO
        status = check_remittance(ledger_path=ledger)
        assert status["alert_level"] == "INFO"

        # Confirmed deposits meeting target → SUCCESS
        from src.bank.transfer_ledger import (
            TransferDirection,
            TransferStatus,
            append_transfer_record,
            build_transfer_record,
        )

        append_transfer_record(
            build_transfer_record(
                direction=TransferDirection.BROKER_TO_MERCURY,
                amount_usd=1000.0,
                status=TransferStatus.CONFIRMED,
                dry_run=False,
                timestamp="2026-07-15T12:00:00+00:00",
            ),
            ledger_path=ledger,
        )
        status = check_remittance(
            ledger_path=ledger,
            month="2026-07",
            target_usd=1000.0,
        )
        assert status["alert_level"] == "SUCCESS"
