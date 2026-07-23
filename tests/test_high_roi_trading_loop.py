import json
from datetime import datetime, timedelta

from scripts import high_roi_trading_loop as loop


class FakeClient:
    def __init__(self):
        self.account_calls = 0

    def get_account(self):
        self.account_calls += 1
        return type(
            "Account",
            (),
            {
                "account_number": "PAPER123",
                "status": "ACTIVE",
                "equity": "100000",
                "last_equity": "99900",
                "cash": "95000",
                "buying_power": "190000",
            },
        )()


def make_ic(total_pl=120.0, credit_received=200.0):
    expiry = datetime.now() + timedelta(days=30)
    return {
        "expiry": expiry,
        "expiry_str": expiry.strftime("%Y-%m-%d"),
        "underlying": "SPY",
        "total_pl": total_pl,
        "credit_received": credit_received,
        "entry_date": (datetime.now() - timedelta(days=3)).isoformat(),
        "legs": [
            {
                "symbol": "SPY260731P00684000",
                "qty": 1,
                "type": "P",
                "strike": 684,
                "unrealized_pl": -5,
            },
            {
                "symbol": "SPY260731P00694000",
                "qty": -1,
                "type": "P",
                "strike": 694,
                "unrealized_pl": 75,
            },
            {
                "symbol": "SPY260731C00775000",
                "qty": -1,
                "type": "C",
                "strike": 775,
                "unrealized_pl": 80,
            },
            {
                "symbol": "SPY260731C00785000",
                "qty": 1,
                "type": "C",
                "strike": 785,
                "unrealized_pl": -30,
            },
        ],
    }


def make_ic_without_entry_date(total_pl=-420.0, credit_received=200.0, days_to_expiry=30):
    ic = make_ic(total_pl=total_pl, credit_received=credit_received)
    ic["expiry"] = datetime.now() + timedelta(days=days_to_expiry)
    ic["expiry_str"] = ic["expiry"].strftime("%Y-%m-%d")
    ic.pop("entry_date", None)
    return ic


def write_system_state(repo_root, *, block_new_positions=True):
    data_dir = repo_root / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "system_state.json").write_text(
        json.dumps(
            {
                "paper_account": {"equity": 100000, "win_rate": 16.7, "win_rate_sample_size": 179},
                "paper_trading": {"current_day": 90, "target_duration_days": 90},
                "north_star_weekly_gate": {
                    "mode": "quarantine" if block_new_positions else "validation",
                    "block_new_positions": block_new_positions,
                    "strategy_quarantine": {
                        "active": block_new_positions,
                        "block_new_positions": block_new_positions,
                        "paper_validation_allowed": False,
                        "reason": "Negative expectancy blocks new entries.",
                    },
                },
            }
        ),
        encoding="utf-8",
    )


def test_entry_gate_is_exit_only_and_blocks_when_halted(tmp_path):
    write_system_state(tmp_path)
    halt_file = tmp_path / "data" / "TRADING_HALTED"
    halt_file.write_text("operator halt", encoding="utf-8")

    gate = loop.build_entry_gate_summary(tmp_path)

    assert gate["exit_only"] is True
    assert gate["entries_allowed_by_loop"] is False
    assert gate["new_entries_blocked"] is True
    assert gate["new_entries_blocked_by_state"] is True
    assert gate["halt"]["active"] is True
    assert gate["north_star_guard"]["block_new_positions"] is True


def test_run_once_dry_run_would_close_without_submitting(monkeypatch, tmp_path):
    write_system_state(tmp_path)
    journal_path = tmp_path / "journal.jsonl"
    latest_path = tmp_path / "latest.json"

    monkeypatch.setattr(loop, "get_iron_condor_positions", lambda client: [{"symbol": "stub"}])
    monkeypatch.setattr(loop, "group_iron_condors", lambda positions: [make_ic()])

    close_calls = []
    monkeypatch.setattr(
        loop,
        "close_iron_condor",
        lambda *args, **kwargs: close_calls.append((args, kwargs)) or True,
    )

    event = loop.run_once(
        client=FakeClient(),
        execute=False,
        repo_root=tmp_path,
        journal_path=journal_path,
        latest_path=latest_path,
    )

    assert event["mode"] == "dry_run"
    assert event["exits_triggered"] == 1
    assert event["exits_submitted"] == 0
    assert event["decisions"][0]["action"] == "would_close"
    assert close_calls == []
    assert json.loads(journal_path.read_text(encoding="utf-8").splitlines()[0])["mode"] == "dry_run"
    assert json.loads(latest_path.read_text(encoding="utf-8"))["exits_triggered"] == 1


def test_run_once_execute_submits_exit_and_records_outcome(monkeypatch, tmp_path):
    write_system_state(tmp_path)
    journal_path = tmp_path / "journal.jsonl"
    latest_path = tmp_path / "latest.json"

    monkeypatch.setattr(loop, "get_iron_condor_positions", lambda client: [{"symbol": "stub"}])
    monkeypatch.setattr(loop, "group_iron_condors", lambda positions: [make_ic()])

    close_calls = []
    record_calls = []
    monkeypatch.setattr(
        loop,
        "close_iron_condor",
        lambda *args, **kwargs: close_calls.append((args, kwargs)) or True,
    )
    monkeypatch.setattr(
        loop,
        "record_trade_outcome",
        lambda *args, **kwargs: record_calls.append((args, kwargs)),
    )

    event = loop.run_once(
        client=FakeClient(),
        execute=True,
        repo_root=tmp_path,
        journal_path=journal_path,
        latest_path=latest_path,
    )

    assert event["mode"] == "execute"
    assert event["exits_triggered"] == 1
    assert event["exits_submitted"] == 1
    assert event["decisions"][0]["action"] == "closed"
    assert len(close_calls) == 1
    assert len(record_calls) == 1


def test_run_once_hold_records_evidence_without_exit(monkeypatch, tmp_path):
    write_system_state(tmp_path, block_new_positions=False)
    journal_path = tmp_path / "journal.jsonl"
    latest_path = tmp_path / "latest.json"

    monkeypatch.setattr(loop, "get_iron_condor_positions", lambda client: [{"symbol": "stub"}])
    monkeypatch.setattr(loop, "group_iron_condors", lambda positions: [make_ic(total_pl=20.0)])

    event = loop.run_once(
        client=FakeClient(),
        execute=False,
        repo_root=tmp_path,
        journal_path=journal_path,
        latest_path=latest_path,
    )

    assert event["exits_triggered"] == 0
    assert event["decisions"][0]["action"] == "hold"
    assert event["decisions"][0]["should_exit"] is False
    assert journal_path.exists()
    assert latest_path.exists()


def test_missing_entry_date_does_not_block_stop_loss_exit():
    decision = loop.build_exit_decision(make_ic_without_entry_date(total_pl=-420.0))

    assert decision["should_exit"] is True
    assert decision["exit_reason"] == "STOP_LOSS"
    assert "overrides missing entry_date" in decision["details"]


def test_missing_entry_date_does_not_block_dte_exit():
    decision = loop.build_exit_decision(make_ic_without_entry_date(total_pl=20.0, days_to_expiry=5))

    assert decision["should_exit"] is True
    assert decision["exit_reason"] == "DTE_EXIT"
    assert "overrides missing entry_date" in decision["details"]
