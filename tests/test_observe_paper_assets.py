"""Dagster asset-health FORMAT on real ledgers — not Dagster+, not PR #4639 engine."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.observe_paper_assets import observe_all


AS_OF = datetime(2026, 9, 14, 14, 0, tzinfo=UTC)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_healthy_paper_book_allows_entry(tmp_path: Path):
    kill = tmp_path / "kill.json"
    state = tmp_path / "state.json"
    entries = tmp_path / "entries.json"
    _write(
        kill,
        {"paper_only": True, "live_blocked": True, "active_family": "spy_put_credit"},
    )
    _write(
        state,
        {
            "last_updated": "2026-09-14T13:46:27.250424+00:00",
            "paper_account": {"equity": 94144.9, "positions_count": 4},
            "live_account": {"equity": 0.0},
            "positions": [{"symbol": "SPY261023P00728000", "qty": -1}],
        },
    )
    _write(
        entries,
        {
            "PCS_261023": {
                "status": "open",
                "credit_source": "broker_fill",
                "fill_confirmed_at": "2026-09-14T13:38:32Z",
                "entry_time": "2026-09-14T13:33:34Z",
            }
        },
    )
    report = observe_all(
        entries=json.loads(entries.read_text()),
        state=json.loads(state.read_text()),
        kill=json.loads(kill.read_text()),
        entries_path=entries,
        state_path=state,
        kill_path=kill,
        as_of=AS_OF,
    )
    assert report["kind"] == "observation"
    assert report["not"] == ["dagster-plus", "dagit", "openlineage", "in-memory-sda-engine"]
    assert report["health"] == "healthy"
    assert report["new_entry_allowed"] is True
    assert report["ok"] is True


def test_live_unblocked_is_degraded_and_blocks_entry(tmp_path: Path):
    kill = tmp_path / "kill.json"
    state = tmp_path / "state.json"
    entries = tmp_path / "entries.json"
    _write(kill, {"paper_only": True, "live_blocked": False, "active_family": "spy_put_credit"})
    _write(state, {"last_updated": "2026-09-14T13:46:27+00:00", "live_account": {"equity": 0}})
    _write(entries, {})
    report = observe_all(
        entries={},
        state=json.loads(state.read_text()),
        kill=json.loads(kill.read_text()),
        entries_path=entries,
        state_path=state,
        kill_path=kill,
        as_of=AS_OF,
    )
    assert report["health"] == "degraded"
    assert report["new_entry_allowed"] is False
    assert any("live_blocked" in item for item in report["blocking_checks"])
    assert report["ok"] is False


def test_stale_snapshot_is_warning_not_a_fill(tmp_path: Path):
    kill = tmp_path / "kill.json"
    state = tmp_path / "state.json"
    entries = tmp_path / "entries.json"
    _write(kill, {"paper_only": True, "live_blocked": True, "active_family": "spy_put_credit"})
    stale = (AS_OF - timedelta(hours=30)).isoformat()
    _write(state, {"last_updated": stale, "live_account": {"equity": 0}})
    _write(
        entries,
        {
            "PCS_x": {
                "status": "open",
                "credit_source": "broker_fill",
                "fill_confirmed_at": "2026-09-14T13:00:00Z",
                "entry_time": "2026-09-14T13:00:00Z",
            }
        },
    )
    report = observe_all(
        entries=json.loads(entries.read_text()),
        state=json.loads(state.read_text()),
        kill=json.loads(kill.read_text()),
        entries_path=entries,
        state_path=state,
        kill_path=kill,
        as_of=AS_OF,
    )
    broker = next(a for a in report["assets"] if a["key"] == "broker/system_state")
    assert broker["freshness"]["status"] == "warning"
    assert report["new_entry_allowed"] is True
    assert report["health"] == "warning"


def test_cli_json_and_exit(tmp_path, monkeypatch):
    kill = tmp_path / "kill.json"
    state = tmp_path / "state.json"
    entries = tmp_path / "entries.json"
    out = tmp_path / "out.json"
    kill.write_text(
        json.dumps({"paper_only": True, "live_blocked": True, "active_family": "spy_put_credit"}),
        encoding="utf-8",
    )
    state.write_text(
        json.dumps({"last_updated": "2026-09-14T13:46:27+00:00", "live_account": {"equity": 0}}),
        encoding="utf-8",
    )
    entries.write_text("{}", encoding="utf-8")
    from scripts import observe_paper_assets as obs

    monkeypatch.setattr(
        "sys.argv",
        [
            "observe_paper_assets.py",
            "--entries",
            str(entries),
            "--system-state",
            str(state),
            "--kill-switch",
            str(kill),
            "--as-of",
            "2026-09-14T14:00:00Z",
            "--json",
            "--out",
            str(out),
        ],
    )
    rc = obs.main()
    assert rc == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["kind"] == "observation"
    assert "dagster-plus" in report["not"]
