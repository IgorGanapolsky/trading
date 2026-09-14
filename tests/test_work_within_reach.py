"""Astra FORMAT completed-task receipt — not GPT-6, not OpenAI primary."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.work_within_reach import (
    evaluate_attempt_efficiency,
    evaluate_capital_discipline,
    evaluate_completed_task,
    evaluate_unsupported_assertion,
    is_completed_paper_fill,
)


def test_unconfirmed_journal_is_not_a_completed_task():
    row = {
        "status": "submitted_unconfirmed",
        "credit_source": "limit_estimate_unconfirmed",
        "order_id": "10f40701-1508-4b77-9027-27942f402f31",
    }
    assert is_completed_paper_fill(row) is False
    report = evaluate_completed_task({"PCS_x": row}, execute_rc=0)
    assert report["ok"] is False
    assert report["reason"] == "execute_rc_0_without_broker_fill"


def test_broker_fill_is_completed_task():
    row = {
        "key": "PCS_261023",
        "status": "open",
        "credit_source": "broker_fill",
        "fill_confirmed_at": "2026-09-14T13:38:32Z",
        "credit": 0.62,
    }
    assert is_completed_paper_fill(row) is True
    report = evaluate_completed_task({"PCS_261023": row}, execute_rc=0)
    assert report["ok"] is True
    assert report["completed_n"] == 1


def test_honest_skip_is_not_a_false_green():
    report = evaluate_completed_task({}, execute_rc=1)
    assert report["ok"] is True
    assert "honest_skip" in report["reason"]


def test_attempt_efficiency_rejects_invented_fills():
    assert evaluate_attempt_efficiency(attempts=2, completed=3)["ok"] is False
    assert evaluate_attempt_efficiency(attempts=3, completed=1)["ok"] is True


def test_capital_discipline_blocks_live_and_gpt6_primary():
    ok = evaluate_capital_discipline(
        {"paper_only": True, "live_blocked": True, "active_family": "spy_put_credit"},
        env={},
    )
    assert ok["ok"] is True
    live = evaluate_capital_discipline(
        {"paper_only": True, "live_blocked": False, "active_family": "spy_put_credit"},
        env={},
    )
    assert live["ok"] is False
    ic = evaluate_capital_discipline(
        {"paper_only": True, "live_blocked": True, "active_family": "iron_condor"},
        env={},
    )
    assert ic["ok"] is False
    astra = evaluate_capital_discipline(
        {"paper_only": True, "live_blocked": True, "active_family": "spy_put_credit"},
        env={"TRADING_OPENAI_PRIMARY": "astra"},
    )
    assert astra["ok"] is False


def test_unsupported_assertion_blocks_profit_claim_before_n30():
    bad = evaluate_unsupported_assertion(
        {"n_closed": 3, "claim_profitable": True, "live_deposit_ready": False}
    )
    assert bad["ok"] is False
    good = evaluate_unsupported_assertion(
        {"n_closed": 3, "claim_profitable": False, "live_deposit_ready": False}
    )
    assert good["ok"] is True


def test_evaluate_all_and_cli_from_journal(tmp_path, monkeypatch):
    entries = tmp_path / "entries.json"
    kill = tmp_path / "kill.json"
    out = tmp_path / "out.json"
    entries.write_text(
        json.dumps(
            {
                "PCS_261023": {
                    "status": "open",
                    "credit_source": "broker_fill",
                    "fill_confirmed_at": "2026-09-14T13:38:32Z",
                    "entry_time": "2026-09-14T13:33:34Z",
                }
            }
        ),
        encoding="utf-8",
    )
    kill.write_text(
        json.dumps(
            {
                "paper_only": True,
                "live_blocked": True,
                "active_family": "spy_put_credit",
            }
        ),
        encoding="utf-8",
    )
    from scripts import work_within_reach as wwr

    monkeypatch.setattr(
        wwr,
        "_honesty_from_scorecard",
        lambda _path: {"n_closed": 3, "claim_profitable": False},
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "work_within_reach.py",
            "--from-journal",
            "--entries",
            str(entries),
            "--kill-switch",
            str(kill),
            "--execute-rc",
            "0",
            "--json",
            "--out",
            str(out),
        ],
    )
    assert wwr.main() == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["ok"] is True
    assert report["not"] == ["gpt-6-astra-product", "openai-api-primary", "chatgpt-work"]


def test_cli_fails_when_execute_rc_0_but_unconfirmed(tmp_path, monkeypatch):
    entries = tmp_path / "entries.json"
    kill = tmp_path / "kill.json"
    out = tmp_path / "out.json"
    entries.write_text(
        json.dumps(
            {
                "PCS_x": {
                    "status": "submitted_unconfirmed",
                    "credit_source": "limit_estimate_unconfirmed",
                    "entry_time": "2026-09-14T13:33:34Z",
                }
            }
        ),
        encoding="utf-8",
    )
    kill.write_text(
        json.dumps(
            {"paper_only": True, "live_blocked": True, "active_family": "spy_put_credit"}
        ),
        encoding="utf-8",
    )
    from scripts import work_within_reach as wwr

    monkeypatch.setattr(wwr, "_honesty_from_scorecard", lambda _path: {"n_closed": 3})
    monkeypatch.setattr(
        "sys.argv",
        [
            "work_within_reach.py",
            "--from-journal",
            "--entries",
            str(entries),
            "--kill-switch",
            str(kill),
            "--execute-rc",
            "0",
            "--out",
            str(out),
        ],
    )
    assert wwr.main() == 2
    assert Path(out).is_file()
