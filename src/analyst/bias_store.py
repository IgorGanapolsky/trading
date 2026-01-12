"""Stub file - BiasStore (original deleted in cleanup)."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class BiasSnapshot:
    """Stub for BiasSnapshot."""

    sentiment: str = "neutral"
    confidence: float = 0.0
    score: float = 0.0
    direction: str = "neutral"
    conviction: float = 0.0
    reason: str = ""
    symbol: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(default_factory=datetime.now)
    model: str = ""
    sources: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return dict representation."""
        return {
            "sentiment": self.sentiment,
            "confidence": self.confidence,
            "score": self.score,
            "reason": self.reason,
        }


class BiasProvider:
    """Stub for BiasProvider - not used in Phil Town strategy."""

    def __init__(self, *args, **kwargs):
        pass

    def get_bias(self, *args, **kwargs) -> BiasSnapshot:
        return BiasSnapshot()


class BiasStore:
    """Stub for BiasStore - not used in Phil Town strategy."""

    def __init__(self, *args, **kwargs):
        pass

    def store(self, *args, **kwargs):
        pass

    def persist(self, *args, **kwargs):
        """Persist a snapshot (stub does nothing)."""
        pass

    def retrieve(self, *args, **kwargs) -> BiasSnapshot:
        return BiasSnapshot()
