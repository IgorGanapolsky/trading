"""Stub module - original RAG deleted in cleanup."""


class FREDCollector:
    """Stub for deleted FRED collector."""

    def __init__(self, *args, **kwargs):
        pass

    def get_10y_yield(self) -> float:
        return 4.5  # Reasonable default

    def get_2y_yield(self) -> float:
        return 4.3

    def fetch(self, *args, **kwargs) -> dict:
        return {}
