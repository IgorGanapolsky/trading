"""Stub file - BiasStore (original deleted in cleanup)."""

from dataclasses import dataclass
from typing import Any


@dataclass
class BiasSnapshot:
    """Stub for BiasSnapshot."""

    sentiment: str = "neutral"
    confidence: float = 0.0


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

    def retrieve(self, *args, **kwargs) -> BiasSnapshot:
        return BiasSnapshot()
