"""
Utilities for replaying recorded bias snapshots inside backtests.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from src.analyst.bias_store import BiasSnapshot, BiasStore


def _ensure_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


class BiasReplay:
    """
    Lightweight in-memory lookup indexed by symbol + timestamp.
    """

    def __init__(self, snapshots: Iterable[BiasSnapshot]):
        self._index: dict[str, list[BiasSnapshot]] = {}
        for snapshot in snapshots:
            symbol = snapshot.symbol.upper()
            bucket = self._index.setdefault(symbol, [])
            bucket.append(snapshot)
        for bucket in self._index.values():
            bucket.sort(key=lambda snap: snap.created_at)

    @classmethod
    def from_store(cls, store: BiasStore, *, limit: int | None = None) -> BiasReplay:
        return cls(store.iter_journal(limit=limit) or [])

    def get_bias(self, symbol: str, as_of: datetime) -> BiasSnapshot | None:
        symbol = symbol.upper()
        snapshots = self._index.get(symbol)
        if not snapshots:
            return None
        ts = _ensure_utc(as_of)
        # Linear scan backwards (lists are short per symbol)
        for snapshot in reversed(snapshots):
            if snapshot.created_at <= ts <= snapshot.expires_at:
                return snapshot
            if snapshot.created_at <= ts and snapshot.expires_at < snapshot.created_at:
                # corrupted entry
                continue
        return None
