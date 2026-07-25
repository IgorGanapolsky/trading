"""Tests for Mercury↔broker transfer ledger, remittance math, and live gates.

Drives real shipped modules — no reimplementation of gate logic in the test.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.bank.live_gate import evaluate_live_bank_gate
from src.bank.mercury_transfer import plan_fund_from_mercury, plan_remit_to_mercury, plan_transfer
from src.bank.remittance import (
    MONTHLY_AFTER_TAX_TARGET_USD,
    compute_remittance_progress,
    estimate_after_tax_profit,
)
from src.bank.transfer_ledger import (
    TransferDirection,
    TransferStatus,
    append_transfer_record,
    build_transfer_record,
    load_transfer_ledger,
)


def test_estimate_after_tax_profit_short_term():
    # $1000 pre-tax at 37% → $630 after-tax
    assert estimate_after_tax_profit(1000.0, tax_rate=0.37) == 630.0
    assert estimate_after_tax_profit(-500.0) == -500.0


def test_transfer_record_schema_has_amount_direction_time(tmp_path: Path):
    rec = build_transfer_record(
        direction=TransferDirection.MERCURY_TO_BROKER,
        amount_usd=250.0,
        status=TransferStatus.DRY_RUN,
        dry_run=True,
        reason="unit_test",
    )
    d = rec.as_dict()
    assert d["amount_usd"] == 250.0
    assert d["direction"] == "mercury_to_broker"
    assert d["timestamp"]
    assert d["source"] == "mercury_ai_bank"
    assert d["destination"] == "brokerage_live"
    # secrets stripped from metadata
    dirty = build_transfer_record(
        direction=TransferDirection.BROKER_TO_MERCURY,
        amount_usd=10,
        status=TransferStatus.PLANNED,
        dry_run=True,
        metadata={"api_key": "SECRET", "note": "ok"},
    )
    assert "api_key" not in dirty.as_dict()["metadata"]
    assert dirty.as_dict()["metadata"]["note"] == "ok"

    path = tmp_path / "ledger.jsonl"
    append_transfer_record(rec, ledger_path=path)
    loaded = load_transfer_ledger(ledger_path=path)
    assert len(loaded) == 1
    assert loaded[0].amount_usd == 250.0


def test_remittance_progress_never_claims_without_ledger(tmp_path: Path):
    progress = compute_remittance_progress([], month_yyyy_mm="2026-07")
    assert progress.target_usd == MONTHLY_AFTER_TAX_TARGET_USD
    assert progress.remitted_to_bank_usd == 0.0
    assert progress.target_met is False
    assert progress.claim_allowed is False

    path = tmp_path / "ledger.jsonl"
    # dry-run must not count
    append_transfer_record(
        build_transfer_record(
            direction=TransferDirection.BROKER_TO_MERCURY,
            amount_usd=5000,
            status=TransferStatus.DRY_RUN,
            dry_run=True,
            timestamp="2026-07-15T12:00:00+00:00",
        ),
        ledger_path=path,
    )
    # blocked must not count
    append_transfer_record(
        build_transfer_record(
            direction=TransferDirection.BROKER_TO_MERCURY,
            amount_usd=5000,
            status=TransferStatus.BLOCKED,
            dry_run=False,
            timestamp="2026-07-15T12:00:00+00:00",
        ),
        ledger_path=path,
    )
    p2 = compute_remittance_progress(
        load_transfer_ledger(ledger_path=path), month_yyyy_mm="2026-07"
    )
    assert p2.target_met is False
    assert p2.remitted_to_bank_usd == 0.0


def test_remittance_progress_counts_confirmed_deposits(tmp_path: Path):
    path = tmp_path / "ledger.jsonl"
    append_transfer_record(
        build_transfer_record(
            direction=TransferDirection.BROKER_TO_MERCURY,
            amount_usd=600.0,
            status=TransferStatus.CONFIRMED,
            dry_run=False,
            timestamp="2026-07-10T12:00:00+00:00",
        ),
        ledger_path=path,
    )
    append_transfer_record(
        build_transfer_record(
            direction=TransferDirection.BROKER_TO_MERCURY,
            amount_usd=400.0,
            status=TransferStatus.SUBMITTED,
            dry_run=False,
            timestamp="2026-07-20T12:00:00+00:00",
        ),
        ledger_path=path,
    )
    # fund direction must not count as remittance
    append_transfer_record(
        build_transfer_record(
            direction=TransferDirection.MERCURY_TO_BROKER,
            amount_usd=9999.0,
            status=TransferStatus.CONFIRMED,
            dry_run=False,
            timestamp="2026-07-12T12:00:00+00:00",
        ),
        ledger_path=path,
    )
    progress = compute_remittance_progress(
        load_transfer_ledger(ledger_path=path), month_yyyy_mm="2026-07"
    )
    assert progress.remitted_to_bank_usd == 1000.0
    assert progress.remittance_event_count == 2
    assert progress.target_met is True
    assert progress.claim_allowed is True


def test_live_bank_gate_refuses_when_kill_switch_blocks(tmp_path: Path, monkeypatch):
    """Drive real evaluate_live_bank_gate against kill switch + insufficient sample."""
    runtime = tmp_path / "data" / "runtime"
    runtime.mkdir(parents=True)
    audit = tmp_path / "data" / "audit"
    audit.mkdir(parents=True)
    kill = {
        "active_family": "spy_put_credit",
        "killed_families": ["ic_simple", "iron_condor"],
        "paper_only": True,
        "live_blocked": True,
        "reason": "test block",
        "successor_family": "spy_put_credit",
    }
    (runtime / "strategy_kill_switch.json").write_text(json.dumps(kill), encoding="utf-8")
    cohort = {
        "closed": {
            "closed_n": 0,
            "expectancy": None,
            "profit_factor": None,
            "kill_criteria": {"verdict": "INSUFFICIENT_SAMPLE"},
        },
        "honesty": {"live_deposit_ready": False, "claim_profitable": False},
    }
    cohort_path = audit / "put_credit_cohort_latest.json"
    cohort_path.write_text(json.dumps(cohort), encoding="utf-8")

    # Point active_strategy kill file at temp
    import src.core.active_strategy as active_mod
    import src.bank.live_gate as gate_mod

    monkeypatch.setattr(active_mod, "KILL_FILE", runtime / "strategy_kill_switch.json")
    monkeypatch.setattr(active_mod, "HYPOTHESIS_FILE", runtime / "strategy_validation_hypothesis.json")
    monkeypatch.setattr(gate_mod, "DEFAULT_COHORT", cohort_path)

    decision = evaluate_live_bank_gate(cohort_path=cohort_path)
    assert decision.allowed is False
    assert decision.live_trading_allowed is False
    assert decision.bank_transfer_allowed is False
    assert decision.strategy_mode == "multi_day_hold_or_buy_hold_non_pdt"
    assert any("live_blocked" in b for b in decision.blockers)
    assert any("insufficient_edge_sample" in b for b in decision.blockers)


def test_plan_transfer_dry_run_logs_and_execute_blocks(tmp_path: Path, monkeypatch):
    path = tmp_path / "ledger.jsonl"
    # Force gate blocked via empty sample + default kill from repo may vary;
    # monkeypatch evaluate_live_bank_gate
    import src.bank.mercury_transfer as mt
    from src.bank.live_gate import LiveBankGateDecision

    blocked = LiveBankGateDecision(
        allowed=False,
        live_trading_allowed=False,
        bank_transfer_allowed=False,
        blockers=("kill_switch.live_blocked: test",),
        paper_only=True,
        live_blocked=True,
        sample_closed_n=0,
        expectancy=None,
        profit_factor=None,
        strategy_mode="multi_day_hold_or_buy_hold_non_pdt",
        detail={},
    )
    monkeypatch.setattr(mt, "evaluate_live_bank_gate", lambda: blocked)

    dry = plan_fund_from_mercury(100.0, dry_run=True, ledger_path=path)
    assert dry.ok is True
    assert dry.dry_run is True
    assert dry.record["direction"] == "mercury_to_broker"
    assert dry.record["amount_usd"] == 100.0
    assert dry.record["timestamp"]
    assert dry.record["status"] == "dry_run"

    remit = plan_remit_to_mercury(50.0, dry_run=True, ledger_path=path)
    assert remit.ok is True
    assert remit.record["direction"] == "broker_to_mercury"

    real = plan_transfer(
        direction=TransferDirection.MERCURY_TO_BROKER,
        amount_usd=100.0,
        dry_run=False,
        force_execute=True,
        ledger_path=path,
    )
    assert real.ok is False
    assert real.blocked is True
    assert real.record["status"] == "blocked"
    assert "live_blocked" in real.record["block_reason"]

    rows = load_transfer_ledger(ledger_path=path)
    assert len(rows) >= 3
