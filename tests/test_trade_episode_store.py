"""Tests for canonical trade episode storage."""

from __future__ import annotations

import json
from pathlib import Path

from src.learning.trade_episode_store import TradeEpisodeStore


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def test_upsert_entry_and_outcome_merges_by_episode_id(tmp_path):
    event_log = tmp_path / "feedback" / "trade_episode_events.jsonl"
    snapshot = tmp_path / "feedback" / "trade_episodes.json"
    store = TradeEpisodeStore(event_log_path=event_log, snapshot_path=snapshot)

    store.upsert_entry(
        {
            "episode_id": "ep-1",
            "order_id": "ord-1",
            "symbol": "SPY",
            "strategy": "iron_condor",
            "timestamp": "2026-03-17T13:00:00Z",
            "event_key": "evt-entry-1",
        }
    )
    episode = store.upsert_outcome(
        {
            "episode_id": "ep-1",
            "order_id": "ord-1",
            "symbol": "SPY",
            "strategy": "iron_condor",
            "reward": 42.5,
            "won": True,
            "timestamp": "2026-03-17T13:10:00Z",
            "event_key": "evt-outcome-1",
        }
    )

    assert episode["episode_id"] == "ep-1"
    assert episode["status"] == "closed"
    assert episode["entry"]["event_key"] == "evt-entry-1"
    assert episode["outcome"]["event_key"] == "evt-outcome-1"
    assert [event["event_type"] for event in episode["events"]] == ["entry", "outcome"]

    rows = _read_jsonl(event_log)
    assert len(rows) == 2
    assert rows[0]["event_key"] == "evt-entry-1"
    assert rows[1]["event_key"] == "evt-outcome-1"

    reloaded = TradeEpisodeStore(event_log_path=event_log, snapshot_path=snapshot)
    assert reloaded.get(episode_id="ep-1")["status"] == "closed"
    assert len(reloaded.list()) == 1


def test_upsert_outcome_without_episode_id_merges_by_order_id(tmp_path):
    event_log = tmp_path / "feedback" / "trade_episode_events.jsonl"
    snapshot = tmp_path / "feedback" / "trade_episodes.json"
    store = TradeEpisodeStore(event_log_path=event_log, snapshot_path=snapshot)

    store.upsert_entry(
        {
            "episode_id": "ep-merge",
            "order_id": "ord-merge",
            "symbol": "QQQ",
            "timestamp": "2026-03-17T14:00:00Z",
            "event_key": "evt-entry-merge",
        }
    )
    episode = store.upsert_outcome(
        {
            "order_id": "ord-merge",
            "symbol": "QQQ",
            "reward": -5.0,
            "won": False,
            "timestamp": "2026-03-17T14:05:00Z",
            "event_key": "evt-outcome-merge",
        }
    )

    assert episode["episode_id"] == "ep-merge"
    assert episode["order_id"] == "ord-merge"
    assert episode["status"] == "closed"
    assert store.get(order_id="ord-merge")["episode_id"] == "ep-merge"


def test_deterministic_event_ordering_when_inserted_out_of_order(tmp_path):
    event_log = tmp_path / "feedback" / "trade_episode_events.jsonl"
    snapshot = tmp_path / "feedback" / "trade_episodes.json"
    store = TradeEpisodeStore(event_log_path=event_log, snapshot_path=snapshot)

    store.upsert_outcome(
        {
            "order_id": "ord-sort",
            "symbol": "IWM",
            "timestamp": "2026-03-17T15:10:00Z",
            "event_key": "evt-outcome-sort",
        }
    )
    episode = store.upsert_entry(
        {
            "order_id": "ord-sort",
            "symbol": "IWM",
            "timestamp": "2026-03-17T15:00:00Z",
            "event_key": "evt-entry-sort",
        }
    )

    assert episode["episode_id"] == "order::ord-sort"
    assert [event["event_key"] for event in episode["events"]] == [
        "evt-entry-sort",
        "evt-outcome-sort",
    ]
    assert [event["event_type"] for event in episode["events"]] == ["entry", "outcome"]


def test_upsert_same_event_key_updates_event_instead_of_duplicating(tmp_path):
    event_log = tmp_path / "feedback" / "trade_episode_events.jsonl"
    snapshot = tmp_path / "feedback" / "trade_episodes.json"
    store = TradeEpisodeStore(event_log_path=event_log, snapshot_path=snapshot)

    store.upsert_entry(
        {
            "episode_id": "ep-dedupe",
            "order_id": "ord-dedupe",
            "symbol": "DIA",
            "price": 100.0,
            "metadata": {"version": 1},
            "event_key": "evt-dedupe",
        }
    )
    episode = store.upsert_entry(
        {
            "episode_id": "ep-dedupe",
            "order_id": "ord-dedupe",
            "symbol": "DIA",
            "price": 105.0,
            "metadata": {"source": "replay"},
            "event_key": "evt-dedupe",
        }
    )

    assert len(episode["events"]) == 1
    assert episode["events"][0]["price"] == 105.0
    assert episode["events"][0]["metadata"] == {"version": 1, "source": "replay"}
    assert episode["entry"]["metadata"] == {"version": 1, "source": "replay"}


def test_load_rebuilds_from_jsonl_when_snapshot_missing(tmp_path):
    event_log = tmp_path / "feedback" / "trade_episode_events.jsonl"
    snapshot = tmp_path / "feedback" / "trade_episodes.json"
    event_log.parent.mkdir(parents=True, exist_ok=True)

    rows = [
        {
            "event_type": "entry",
            "episode_id": "ep-rebuild",
            "order_id": "ord-rebuild",
            "symbol": "TSLA",
            "timestamp": "2026-03-17T16:00:00Z",
            "event_key": "evt-rebuild-entry",
        },
        {
            "event_type": "outcome",
            "order_id": "ord-rebuild",
            "symbol": "TSLA",
            "timestamp": "2026-03-17T16:10:00Z",
            "event_key": "evt-rebuild-outcome",
        },
    ]
    event_log.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    store = TradeEpisodeStore(event_log_path=event_log, snapshot_path=snapshot)
    episodes = store.load()

    assert "ep-rebuild" in episodes
    assert episodes["ep-rebuild"]["status"] == "closed"
    assert [event["event_type"] for event in episodes["ep-rebuild"]["events"]] == [
        "entry",
        "outcome",
    ]
    assert snapshot.exists()


def test_list_is_sorted_by_episode_id(tmp_path):
    event_log = tmp_path / "feedback" / "trade_episode_events.jsonl"
    snapshot = tmp_path / "feedback" / "trade_episodes.json"
    store = TradeEpisodeStore(event_log_path=event_log, snapshot_path=snapshot)

    store.upsert_entry({"episode_id": "ep-b", "order_id": "ord-b", "symbol": "B"})
    store.upsert_entry({"episode_id": "ep-a", "order_id": "ord-a", "symbol": "A"})

    episodes = store.list()
    assert [episode["episode_id"] for episode in episodes] == ["ep-a", "ep-b"]
