"""Targeted learning-path tests for AlpacaExecutor."""

from __future__ import annotations

import json
from pathlib import Path


def test_store_rlhf_trajectory_writes_canonical_episode_and_legacy_log(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ALPACA_SIMULATED", "true")

    from src.execution.alpaca_executor import AlpacaExecutor
    from src.learning import rlhf_storage

    monkeypatch.setattr(
        rlhf_storage,
        "TRAJECTORY_PATH",
        tmp_path / "data" / "feedback" / "trade_trajectories.jsonl",
    )

    executor = AlpacaExecutor(paper=True)
    order = {
        "id": "ord-123",
        "symbol": "SPY",
        "side": "buy",
        "qty": 2,
        "status": "filled",
        "filled_at": "2026-03-17T15:00:00Z",
    }

    executor._store_rlhf_trajectory(order, "iron_condor", 2.5)

    snapshot_path = tmp_path / "data" / "feedback" / "trade_episodes.json"
    assert snapshot_path.exists()
    episodes = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert len(episodes["episodes"]) == 1
    episode = episodes["episodes"][0]
    assert episode["episode_id"] == "ord-123"
    assert episode["entry"]["price"] == 2.5
    assert episode["entry"]["side"] == "buy"
    assert episode["status"] == "open"

    trajectory_path = tmp_path / "data" / "feedback" / "trade_trajectories.jsonl"
    rows = [
        json.loads(line)
        for line in trajectory_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    assert rows[0]["episode_id"] == "ord-123"
    assert rows[0]["event_type"] == "entry"
