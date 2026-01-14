"""Bias Store stub - returns neutral bias."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class BiasSnapshot:
    """Snapshot of market bias."""

    timestamp: datetime = field(default_factory=datetime.now)
    bias: str = "neutral"
    confidence: float = 0.5
    source: str = "stub"


class BiasStore:
    """Stub BiasStore for backward compatibility."""

    def __init__(self, bias_dir: str = "data/bias"):
        self.bias_dir = bias_dir

    def get_latest(self) -> Optional[BiasSnapshot]:
        return BiasSnapshot()

    def store(self, snapshot: BiasSnapshot) -> None:
        pass


class BiasProvider:
    """Stub BiasProvider for backward compatibility."""

    def __init__(self, store: BiasStore = None, **kwargs):
        self.store = store or BiasStore()

    def get_bias(self, symbol: str = None) -> BiasSnapshot:
        return BiasSnapshot()

    def get_sentiment(self, symbol: str = None) -> dict:
        return {"sentiment": "neutral", "confidence": 0.5}
