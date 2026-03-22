"""Canonical trade episode storage with JSONL event log + JSON snapshot."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

DEFAULT_EVENT_LOG_PATH = Path("data/feedback/trade_episode_events.jsonl")
DEFAULT_SNAPSHOT_PATH = Path("data/feedback/trade_episodes.json")

_TIMESTAMP_FIELDS = ("timestamp", "recorded_at", "occurred_at", "event_time", "ts")
_EVENT_PRIORITY = {"entry": 0, "outcome": 1}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _stable_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _event_timestamp(event: Mapping[str, Any]) -> str:
    for field in _TIMESTAMP_FIELDS:
        value = event.get(field)
        if value is not None and value != "":
            return str(value)
    return ""


def _normalize_event(
    event: Mapping[str, Any], forced_event_type: str | None = None
) -> dict[str, Any]:
    normalized: dict[str, Any] = deepcopy(dict(event))
    if forced_event_type:
        normalized["event_type"] = forced_event_type
    normalized["event_type"] = str(normalized.get("event_type") or "entry").lower()

    if normalized.get("episode_id") is not None:
        normalized["episode_id"] = str(normalized["episode_id"])
    if normalized.get("order_id") is not None:
        normalized["order_id"] = str(normalized["order_id"])

    normalized["timestamp"] = _event_timestamp(normalized) or _utc_now_iso()
    normalized.setdefault("recorded_at", normalized["timestamp"])

    if not normalized.get("event_key"):
        material = {k: v for k, v in normalized.items() if k != "event_key"}
        normalized["event_key"] = f"episode_event::{_stable_hash(material)}"
    else:
        normalized["event_key"] = str(normalized["event_key"])

    return normalized


def _merge_dict(base: Mapping[str, Any] | None, update: Mapping[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = deepcopy(dict(base or {}))
    for key, value in dict(update or {}).items():
        if value is None:
            continue
        if isinstance(merged.get(key), dict) and isinstance(value, Mapping):
            merged[key] = _merge_dict(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _event_sort_key(event: Mapping[str, Any]) -> tuple[int, int, str, int, str]:
    sequence = event.get("sequence")
    try:
        return (
            0,
            int(sequence),  # type: ignore[arg-type]
            _event_timestamp(event),
            _EVENT_PRIORITY.get(str(event.get("event_type") or "").lower(), 9),
            str(event.get("event_key") or ""),
        )
    except (TypeError, ValueError):
        return (
            1,
            0,
            _event_timestamp(event),
            _EVENT_PRIORITY.get(str(event.get("event_type") or "").lower(), 9),
            str(event.get("event_key") or ""),
        )


def _sorted_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(events, key=_event_sort_key)


class TradeEpisodeStore:
    """Canonical episode store backed by event log and snapshot files."""

    def __init__(
        self,
        *,
        event_log_path: Path | str = DEFAULT_EVENT_LOG_PATH,
        snapshot_path: Path | str = DEFAULT_SNAPSHOT_PATH,
    ) -> None:
        self.event_log_path = Path(event_log_path)
        self.snapshot_path = Path(snapshot_path)

    def load(self) -> dict[str, dict[str, Any]]:
        """Load canonical episode map keyed by episode_id."""
        episodes = self._load_snapshot()
        if episodes:
            return episodes
        episodes = self._rebuild_from_event_log()
        self._write_snapshot(episodes)
        return episodes

    def list(self) -> list[dict[str, Any]]:
        """List all episodes in deterministic order."""
        episodes = self.load()
        return [deepcopy(episodes[episode_id]) for episode_id in sorted(episodes)]

    def get(
        self, *, episode_id: str | None = None, order_id: str | None = None
    ) -> dict[str, Any] | None:
        """Get one episode by episode_id or order_id."""
        episodes = self.load()
        if episode_id:
            episode = episodes.get(str(episode_id))
            return deepcopy(episode) if episode else None
        if order_id:
            order = str(order_id)
            for episode in episodes.values():
                if str(episode.get("order_id") or "") == order:
                    return deepcopy(episode)
        return None

    def upsert_entry(self, event: Mapping[str, Any]) -> dict[str, Any]:
        return self.upsert(event, event_type="entry")

    def upsert_outcome(self, event: Mapping[str, Any]) -> dict[str, Any]:
        return self.upsert(event, event_type="outcome")

    def upsert(self, event: Mapping[str, Any], event_type: str | None = None) -> dict[str, Any]:
        """Upsert an entry or outcome event into canonical episode state."""
        normalized = _normalize_event(event, event_type)
        episodes = self.load()

        episode_id = self._resolve_episode_id(normalized, episodes)
        normalized["episode_id"] = episode_id

        episode = episodes.get(episode_id)
        if episode is None:
            episode = self._new_episode_shell(episode_id, normalized)
            episodes[episode_id] = episode

        self._merge_event_into_episode(episode, normalized)
        self._append_event_log(normalized)
        self._write_snapshot(episodes)
        return deepcopy(episode)

    def _load_snapshot(self) -> dict[str, dict[str, Any]]:
        if not self.snapshot_path.exists():
            return {}
        try:
            payload = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

        if isinstance(payload, dict) and isinstance(payload.get("episodes"), list):
            raw_episodes = payload["episodes"]
        elif isinstance(payload, list):
            raw_episodes = payload
        elif isinstance(payload, dict):
            raw_episodes = list(payload.values())
        else:
            raw_episodes = []

        episodes: dict[str, dict[str, Any]] = {}
        for raw in raw_episodes:
            if not isinstance(raw, Mapping):
                continue
            normalized = self._normalize_episode(raw)
            episodes[normalized["episode_id"]] = normalized
        return episodes

    def _read_event_log(self) -> list[dict[str, Any]]:
        if not self.event_log_path.exists():
            return []

        rows: list[dict[str, Any]] = []
        for line in self.event_log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, Mapping):
                rows.append(_normalize_event(parsed))
        return rows

    def _rebuild_from_event_log(self) -> dict[str, dict[str, Any]]:
        episodes: dict[str, dict[str, Any]] = {}
        for event in _sorted_events(self._read_event_log()):
            episode_id = self._resolve_episode_id(event, episodes)
            event["episode_id"] = episode_id
            episode = episodes.get(episode_id)
            if episode is None:
                episode = self._new_episode_shell(episode_id, event)
                episodes[episode_id] = episode
            self._merge_event_into_episode(episode, event)
        return episodes

    def _append_event_log(self, event: Mapping[str, Any]) -> None:
        self.event_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.event_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(dict(event), sort_keys=True, ensure_ascii=True) + "\n")

    def _write_snapshot(self, episodes: Mapping[str, Mapping[str, Any]]) -> None:
        self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        ordered = [episodes[episode_id] for episode_id in sorted(episodes)]
        payload = {"episodes": ordered}
        self.snapshot_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )

    def _resolve_episode_id(
        self,
        event: Mapping[str, Any],
        episodes: Mapping[str, Mapping[str, Any]],
    ) -> str:
        explicit_episode = event.get("episode_id")
        if explicit_episode:
            explicit = str(explicit_episode)
            if explicit in episodes:
                return explicit
            order_id = event.get("order_id")
            if order_id:
                existing = self._find_episode_by_order_id(str(order_id), episodes)
                if existing:
                    return existing
            return explicit

        order_id = event.get("order_id")
        if order_id:
            order = str(order_id)
            existing = self._find_episode_by_order_id(order, episodes)
            if existing:
                return existing
            return f"order::{order}"

        return f"episode::{_stable_hash(event)}"

    @staticmethod
    def _find_episode_by_order_id(
        order_id: str,
        episodes: Mapping[str, Mapping[str, Any]],
    ) -> str | None:
        for episode_id, episode in episodes.items():
            if str(episode.get("order_id") or "") == order_id:
                return episode_id
        return None

    @staticmethod
    def _new_episode_shell(episode_id: str, seed_event: Mapping[str, Any]) -> dict[str, Any]:
        timestamp = _event_timestamp(seed_event) or _utc_now_iso()
        episode: dict[str, Any] = {
            "episode_id": episode_id,
            "order_id": seed_event.get("order_id"),
            "symbol": seed_event.get("symbol"),
            "strategy": seed_event.get("strategy"),
            "status": "open",
            "entry": {},
            "outcome": {},
            "events": [],
            "created_at": timestamp,
            "updated_at": timestamp,
            "metadata": {},
        }
        return episode

    def _merge_event_into_episode(self, episode: dict[str, Any], event: Mapping[str, Any]) -> None:
        if event.get("order_id") and not episode.get("order_id"):
            episode["order_id"] = event.get("order_id")
        if event.get("symbol") and not episode.get("symbol"):
            episode["symbol"] = event.get("symbol")
        if event.get("strategy") and not episode.get("strategy"):
            episode["strategy"] = event.get("strategy")

        episode["metadata"] = _merge_dict(episode.get("metadata"), event.get("metadata"))

        events = list(episode.get("events", []))
        event_key = str(event.get("event_key"))
        existing_idx = next(
            (
                index
                for index, existing in enumerate(events)
                if str(existing.get("event_key")) == event_key
            ),
            None,
        )
        if existing_idx is None:
            events.append(deepcopy(dict(event)))
        else:
            events[existing_idx] = _merge_dict(events[existing_idx], event)
        episode["events"] = _sorted_events(events)

        event_type = str(event.get("event_type") or "").lower()
        if event_type == "entry":
            episode["entry"] = _merge_dict(episode.get("entry"), event)
        elif event_type == "outcome":
            episode["outcome"] = _merge_dict(episode.get("outcome"), event)

        episode["status"] = "closed" if episode.get("outcome") else "open"
        episode["updated_at"] = _event_timestamp(event) or _utc_now_iso()

    def _normalize_episode(self, raw: Mapping[str, Any]) -> dict[str, Any]:
        episode_id = str(raw.get("episode_id") or f"episode::{_stable_hash(raw)}")
        events: list[dict[str, Any]] = []
        for event in raw.get("events", []) if isinstance(raw.get("events"), list) else []:
            if isinstance(event, Mapping):
                events.append(_normalize_event(event))

        if not events:
            if isinstance(raw.get("entry"), Mapping) and raw["entry"]:
                events.append(_normalize_event(raw["entry"], "entry"))
            if isinstance(raw.get("outcome"), Mapping) and raw["outcome"]:
                events.append(_normalize_event(raw["outcome"], "outcome"))

        canonical = self._new_episode_shell(episode_id, raw)
        canonical["metadata"] = _merge_dict({}, raw.get("metadata"))
        for event in _sorted_events(events):
            event["episode_id"] = episode_id
            self._merge_event_into_episode(canonical, event)

        canonical["created_at"] = str(raw.get("created_at") or canonical.get("created_at"))
        canonical["updated_at"] = str(raw.get("updated_at") or canonical.get("updated_at"))
        canonical["status"] = str(raw.get("status") or canonical.get("status"))
        if raw.get("order_id"):
            canonical["order_id"] = raw.get("order_id")
        if raw.get("symbol"):
            canonical["symbol"] = raw.get("symbol")
        if raw.get("strategy"):
            canonical["strategy"] = raw.get("strategy")
        return canonical
