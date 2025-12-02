"""
Shared bias store utilities for decoupling the slow analyst loop from fast execution.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class BiasSnapshot:
    """
    Standardized payload published by the analyst loop.

    The fast trader consumes these payloads without needing to call an LLM.
    """

    symbol: str
    score: float
    direction: str
    conviction: float
    reason: str
    created_at: datetime
    expires_at: datetime
    model: str | None = None
    sources: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_fresh(self, *, as_of: datetime | None = None) -> bool:
        now = as_of or _now_utc()
        return self.created_at <= now <= self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol.upper(),
            "score": float(self.score),
            "direction": self.direction,
            "conviction": float(self.conviction),
            "reason": self.reason,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "model": self.model,
            "sources": self.sources,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> BiasSnapshot:
        return cls(
            symbol=payload["symbol"].upper(),
            score=float(payload.get("score", 0.0)),
            direction=payload.get("direction", "neutral"),
            conviction=float(payload.get("conviction", 0.0)),
            reason=payload.get("reason", ""),
            created_at=datetime.fromisoformat(payload["created_at"]),
            expires_at=datetime.fromisoformat(payload["expires_at"]),
            model=payload.get("model"),
            sources=list(payload.get("sources", [])),
            metadata=dict(payload.get("metadata", {})),
        )


class BiasStore:
    """
    Simple JSON/JSONL-backed store for analyst biases.

    * `latest_biases.json` contains the newest snapshot per symbol for fast lookups.
    * `bias_snapshots.jsonl` keeps an append-only audit log.
    """

    def __init__(self, root: str | Path = "data/bias") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.latest_path = self.root / "latest_biases.json"
        self.journal_path = self.root / "bias_snapshots.jsonl"

    # ------------------------------------------------------------------ #
    # Write path
    # ------------------------------------------------------------------ #
    def persist(self, snapshot: BiasSnapshot) -> None:
        """Append to the journal and upsert the latest map."""
        logger.info(
            "Persisting bias snapshot %s (score=%.2f, conviction=%.2f)",
            snapshot.symbol,
            snapshot.score,
            snapshot.conviction,
        )
        self._append_journal(snapshot)
        latest = self.load_latest()
        latest[snapshot.symbol] = snapshot.to_dict()
        self._write_latest(latest)

    def _append_journal(self, snapshot: BiasSnapshot) -> None:
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        with self.journal_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(snapshot.to_dict()))
            handle.write("\n")

    def _write_latest(self, payload: dict[str, dict[str, Any]]) -> None:
        tmp_path = self.latest_path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        tmp_path.replace(self.latest_path)

    # ------------------------------------------------------------------ #
    # Read path
    # ------------------------------------------------------------------ #
    def load_latest(self) -> dict[str, dict[str, Any]]:
        if not self.latest_path.exists():
            return {}
        try:
            with self.latest_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse %s: %s", self.latest_path, exc)
            return {}
        return {
            symbol.upper(): snapshot
            for symbol, snapshot in data.items()
            if isinstance(snapshot, dict)
        }

    def get_latest(self, symbol: str) -> BiasSnapshot | None:
        payload = self.load_latest().get(symbol.upper())
        if not payload:
            return None
        try:
            snapshot = BiasSnapshot.from_dict(payload)
            return snapshot
        except Exception as exc:
            logger.warning("Corrupt snapshot for %s: %s", symbol, exc)
            return None

    def list_fresh(
        self,
        *,
        as_of: datetime | None = None,
        max_age: timedelta = timedelta(hours=4),
    ) -> list[BiasSnapshot]:
        now = as_of or _now_utc()
        horizon = now - max_age
        snapshots: list[BiasSnapshot] = []
        for payload in self.load_latest().values():
            try:
                snapshot = BiasSnapshot.from_dict(payload)
            except Exception:
                continue
            if snapshot.created_at >= horizon and snapshot.is_fresh(as_of=now):
                snapshots.append(snapshot)
        return snapshots

    def iter_journal(self, limit: int | None = None):
        """
        Stream historical snapshots from the append-only journal.

        Args:
            limit: Optional maximum number of rows to yield (latest first).
        """
        if not self.journal_path.exists():
            return

        yielded = 0
        try:
            with self.journal_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if limit is not None and yielded >= limit:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                        yield BiasSnapshot.from_dict(payload)
                        yielded += 1
                    except Exception:
                        continue
        except FileNotFoundError:
            return


class BiasProvider:
    """
    Runtime helper that exposes fresh biases to the fast trader and backtests.
    """

    def __init__(
        self,
        store: BiasStore | None = None,
        *,
        freshness: timedelta = timedelta(minutes=90),
    ) -> None:
        self.store = store or BiasStore()
        self.freshness = freshness

    def get_bias(self, symbol: str, *, as_of: datetime | None = None) -> BiasSnapshot | None:
        snapshot = self.store.get_latest(symbol)
        if snapshot is None:
            return None
        now = as_of or _now_utc()
        if snapshot.created_at < now - self.freshness:
            logger.debug(
                "Bias for %s is stale (created %s, freshness=%s)",
                symbol,
                snapshot.created_at,
                self.freshness,
            )
            return None
        if snapshot.expires_at < now:
            logger.debug("Bias for %s expired at %s", symbol, snapshot.expires_at)
            return None
        return snapshot

    def warm_cache(self, snapshots: Iterable[BiasSnapshot]) -> None:
        """
        Allow tests/backtests to seed the store without calling an LLM.
        """
        for snapshot in snapshots:
            self.store.persist(snapshot)
