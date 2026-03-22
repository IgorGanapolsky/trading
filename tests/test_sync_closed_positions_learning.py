from __future__ import annotations

import json
from pathlib import Path

import scripts.sync_closed_positions as sync_closed
from src.learning import rlhf_storage


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _seed_system_state(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    legs = [
        "SPY260320P00645000",
        "SPY260320P00655000",
        "SPY260320C00725000",
        "SPY260320C00735000",
    ]
    payload = {
        "trade_history": [
            {
                "id": "entry-1",
                "filled_at": "2026-02-10T15:30:00+00:00",
                "side": "sell",
                "qty": 1,
                "price": 2.5,
                "legs": legs,
            },
            {
                "id": "exit-1",
                "filled_at": "2026-02-14T15:30:00+00:00",
                "side": "buy",
                "qty": 1,
                "price": 1.0,
                "legs": legs,
            },
        ]
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _configure_paths(monkeypatch, project_root: Path) -> tuple[Path, Path]:
    data_dir = project_root / "data"
    system_state_file = data_dir / "system_state.json"
    trades_file = data_dir / "trades.json"
    trajectory_file = data_dir / "feedback" / "trade_trajectories.jsonl"

    monkeypatch.setattr(sync_closed, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(sync_closed, "DATA_DIR", data_dir)
    monkeypatch.setattr(sync_closed, "SYSTEM_STATE_FILE", system_state_file)
    monkeypatch.setattr(sync_closed, "TRADES_FILE", trades_file)

    monkeypatch.setattr(rlhf_storage, "TRAJECTORY_PATH", trajectory_file)
    return trades_file, trajectory_file


def test_learning_update_idempotent_by_event_key(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    _, trajectory_file = _configure_paths(monkeypatch, project_root)

    trade = {
        "id": "IC_test_trade",
        "symbol": "SPY",
        "strategy": "iron_condor",
        "outcome": "win",
        "realized_pnl": 150.0,
        "exit_time": "2026-02-14T15:30:00+00:00",
        "legs": {"expiry": "2026-03-20"},
    }

    first = sync_closed._apply_learning_update_for_trade(trade, project_root=project_root)
    second = sync_closed._apply_learning_update_for_trade(trade, project_root=project_root)

    assert first["event_key"] == "closed_trade_sync::IC_test_trade"
    assert first["distributed_applied"] is True
    assert second["distributed_applied"] is False
    assert second["distributed_skipped_reason"] == "duplicate_event"

    rows = _read_jsonl(trajectory_file)
    assert len(rows) == 1
    assert rows[0]["event_type"] == "outcome"
    assert rows[0]["event_key"] == "closed_trade_sync::IC_test_trade"

    episodes = _read_json(project_root / "data" / "feedback" / "trade_episodes.json")
    assert len(episodes["episodes"]) == 1
    assert episodes["episodes"][0]["episode_id"] == "IC_test_trade"
    assert episodes["episodes"][0]["outcome"]["outcome"] == "won"

    stats = _read_json(project_root / "data" / "feedback" / "stats.json")
    assert stats["total"] == 1
    assert stats["positive"] == 1
    assert stats["negative"] == 0


def test_sync_closed_positions_dry_run_has_no_learning_side_effects(
    monkeypatch, tmp_path: Path
) -> None:
    project_root = tmp_path / "project"
    trades_file, trajectory_file = _configure_paths(monkeypatch, project_root)
    _seed_system_state(project_root / "data" / "system_state.json")

    result = sync_closed.sync_closed_positions(dry_run=True)

    assert result["success"] is True
    assert result["dry_run"] is True
    assert result["new_closed"] == 1
    assert not trades_file.exists()
    assert not trajectory_file.exists()
    assert not (project_root / "data" / "feedback" / "stats.json").exists()
    assert not (project_root / "data" / "feedback" / "trade_episodes.json").exists()
    assert not (
        project_root / ".claude" / "memory" / "feedback" / "distributed_feedback_state.json"
    ).exists()


def test_sync_closed_positions_applies_learning_once_for_new_rows(
    monkeypatch, tmp_path: Path
) -> None:
    project_root = tmp_path / "project"
    trades_file, trajectory_file = _configure_paths(monkeypatch, project_root)
    _seed_system_state(project_root / "data" / "system_state.json")

    first = sync_closed.sync_closed_positions(dry_run=False)
    second = sync_closed.sync_closed_positions(dry_run=False)

    assert first["success"] is True
    assert first["new_closed"] == 1
    assert first["learning_applied"] == 1
    assert first["learning_duplicates"] == 0
    assert first["learning_errors"] == 0

    assert second["success"] is True
    assert second["new_closed"] == 0
    assert second["learning_applied"] == 0
    assert second["learning_duplicates"] == 0
    assert second["learning_errors"] == 0

    trades_payload = _read_json(trades_file)
    assert len(trades_payload.get("trades", [])) == 1

    rows = _read_jsonl(trajectory_file)
    assert len(rows) == 1

    episodes = _read_json(project_root / "data" / "feedback" / "trade_episodes.json")
    assert len(episodes["episodes"]) == 1
    assert episodes["episodes"][0]["status"] == "closed"
    assert episodes["episodes"][0]["outcome"]["reward"] == 150.0

    stats = _read_json(project_root / "data" / "feedback" / "stats.json")
    assert stats["total"] == 1
