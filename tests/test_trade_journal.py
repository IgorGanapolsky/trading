"""Tests for the controlled-experiment trade journal."""

from __future__ import annotations

import json

from scripts import trade_journal


def test_malformed_validation_entry_is_reported_without_crashing(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    entries = tmp_path / "ic_entries.json"
    trades = tmp_path / "trades.json"
    entries.write_text(
        json.dumps(
            {
                "IC_260320": {
                    "validation_phase": True,
                    "date": "2026-03-26T09:56:10",
                    "strikes": {},
                    "put_delta": None,
                    "call_delta": None,
                    "credit": None,
                    "quantity": None,
                    "order_id": None,
                }
            }
        )
    )
    trades.write_text(json.dumps({"trades": []}))
    monkeypatch.setattr(trade_journal, "ENTRIES_FILE", entries)
    monkeypatch.setattr(trade_journal, "TRADES_FILE", trades)

    result = trade_journal.main()
    output = capsys.readouterr().out

    assert result == 1
    assert "entry deltas missing or invalid" in output
    assert "entry credit missing or invalid" in output
    assert "quantity missing or invalid" in output


def test_expectancy_uses_only_explicit_validation_rows(tmp_path, monkeypatch, capsys) -> None:
    entries = tmp_path / "ic_entries.json"
    trades = tmp_path / "trades.json"
    entries.write_text(json.dumps({}))
    valid = {
        "id": "valid",
        "status": "closed",
        "strategy": "iron_condor",
        "entry_time": "2026-04-10T14:00:00Z",
        "exit_time": "2026-04-11T14:00:00Z",
        "entry_date": "2026-04-10",
        "validation_phase": True,
        "realized_pnl": -100,
        "outcome": "loss",
    }
    date_only = {
        **valid,
        "id": "date-only",
        "validation_phase": False,
        "realized_pnl": 500,
        "outcome": "win",
    }
    trades.write_text(json.dumps({"trades": [valid, date_only]}))
    monkeypatch.setattr(trade_journal, "ENTRIES_FILE", entries)
    monkeypatch.setattr(trade_journal, "TRADES_FILE", trades)

    result = trade_journal.main()
    output = capsys.readouterr().out

    assert result == 0
    assert "Closed trades: 1" in output
    assert "Total P/L:     $-100.00" in output
