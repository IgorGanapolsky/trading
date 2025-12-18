"""Stub module - original RAG deleted in cleanup."""


class HindsightAdapter:
    """Stub for deleted Hindsight adapter."""

    def __init__(self, *args, **kwargs):
        pass

    def query(self, *args, **kwargs) -> dict:
        return {"confidence": 0.5, "opinion": "neutral", "stub": True}


def get_hindsight_adapter(*args, **kwargs):
    """Return stub adapter."""
    return HindsightAdapter()
