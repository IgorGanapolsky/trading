"""Stub file - TradeMemory (original deleted in cleanup)."""

from typing import Any


class TradeMemory:
    """Stub for TradeMemory - not used in Phil Town strategy."""

    def __init__(self, *args, **kwargs):
        pass

    def store(self, *args, **kwargs):
        pass

    def retrieve(self, *args, **kwargs) -> list[Any]:
        return []

    def get_recent(self, *args, **kwargs) -> list[Any]:
        return []

    def query_similar(self, strategy: str = "", entry_reason: str = "", *args, **kwargs) -> dict[str, Any]:
        """Stub for query_similar - returns no matches."""
        return {"found": False, "win_rate": 0.5, "sample_size": 0, "avg_pnl": 0.0}

    def add_trade(self, *args, **kwargs):
        """Stub for add_trade - does nothing."""
        pass
