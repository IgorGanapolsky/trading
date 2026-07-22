"""CLI coverage for the strategy-pivot evidence report."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import strategy_pivot_report as cli


def _report() -> dict:
    return {
        "system_action": "RETIRE_INCUMBENT_PAPER_VALIDATE_SUCCESSOR",
        "research_action": "RUN_ACTIVE_SUCCESSOR_PAPER_COHORT",
        "north_star": {
            "on_course": False,
            "current_equity": 94_062.0,
            "total_pl": -5_938.0,
            "drawdown_pct": 5.94,
        },
        "incumbent": {
            "strategy_id": "ic_simple",
            "decision": {
                "status": "RETIRE_NEW_ENTRIES",
                "may_open_new_positions": False,
                "may_manage_existing_positions": True,
                "reasons": ["Negative mature expectancy."],
            },
            "ledger_audit": {"clean": False},
        },
        "operational_inventory": {
            "clean": True,
            "authority": "broker_filled_mleg_orders",
        },
        "broker": {"current_role": "RESEARCH_ONLY"},
        "candidates": [
            {
                "strategy_id": "spy_put_credit",
                "decision": {"status": "PAPER_VALIDATION_ONLY"},
                "broker_assessment": {
                    "execution_eligible": False,
                    "blockers": ["No supported atomic multi-leg option API."],
                },
            }
        ],
    }


def _args(root: Path, *, json_output: bool) -> SimpleNamespace:
    paths = [root / f"input-{index}.json" for index in range(6)]
    for path in paths:
        path.write_text("{}\n", encoding="utf-8")
    return SimpleNamespace(
        system_state=paths[0],
        trades=paths[1],
        entries=paths[2],
        tournament=paths[3],
        broker=paths[4],
        inventory_audit=paths[5],
        json=json_output,
    )


def test_load_json_accepts_repo_object_and_rejects_escape_or_array(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    valid = tmp_path / "valid.json"
    valid.write_text('{"ok": true}\n', encoding="utf-8")
    array = tmp_path / "array.json"
    array.write_text("[]\n", encoding="utf-8")

    assert cli._load_json(Path("valid.json")) == {"ok": True}
    with pytest.raises(ValueError, match="Expected JSON object"):
        cli._load_json(array)
    with pytest.raises(ValueError, match="inside repository root"):
        cli._load_json(tmp_path.parent / "outside.json")


def test_parse_args_supports_json_mode(monkeypatch):
    monkeypatch.setattr("sys.argv", ["strategy_pivot_report.py", "--json"])
    assert cli.parse_args().json is True


@pytest.mark.parametrize("json_output", [False, True])
def test_main_prints_report_and_returns_north_star_failure(
    tmp_path, monkeypatch, capsys, json_output
):
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(cli, "parse_args", lambda: _args(tmp_path, json_output=json_output))
    monkeypatch.setattr(cli, "build_pivot_report", lambda *payloads: _report())

    assert cli.main() == 2
    output = capsys.readouterr().out
    if json_output:
        assert json.loads(output)["north_star"]["on_course"] is False
    else:
        assert "STRATEGY PIVOT GATE" in output
        assert "Operational broker inventory clean: True" in output
        assert "Clear Street role: RESEARCH_ONLY" in output
