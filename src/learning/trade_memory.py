"""Trade Memory stub - returns empty history."""


class TradeMemory:
    """Stub TradeMemory for backward compatibility."""

    def __init__(self, db_path: str = "data/trade_memory.db"):
        self.db_path = db_path

    def query(self, pattern: str = None, symbol: str = None) -> dict:
        """Return empty result."""
        return {"found": False, "trades": [], "win_rate": 0.0}

    def record(self, trade: dict) -> None:
        """No-op record."""
        pass

    def get_pattern_stats(self, pattern: str) -> dict:
        """Return empty stats."""
        return {"pattern": pattern, "count": 0, "win_rate": 0.0}
