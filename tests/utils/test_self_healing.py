"""Tests for the self-healing cache clearing utilities."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from src.utils import self_healing, sentiment


def test_clear_cached_resources_resets_sentiment_cache() -> None:
    """Ensure the VADER analyzer cache is cleared."""

    pytest.importorskip("vaderSentiment")

    sentiment._get_analyzer.cache_clear()
    sentiment._get_analyzer()
    assert sentiment._get_analyzer.cache_info().currsize == 1

    cleared = self_healing.clear_cached_resources()

    assert sentiment._get_analyzer.cache_info().currsize == 0
    assert "sentiment analyzer" in cleared


def test_clear_cached_resources_handles_clearer_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that a failing clearer does not abort the routine."""

    calls: list[str] = []

    def good_clearer() -> bool:
        calls.append("good")
        return True

    def bad_clearer() -> bool:
        calls.append("bad")
        raise RuntimeError("boom")

    custom_clearers: tuple[tuple[str, Callable[[], bool]], ...] = (
        ("good", good_clearer),
        ("bad", bad_clearer),
    )
    monkeypatch.setattr(self_healing, "_CACHE_CLEARERS", custom_clearers)

    cleared = self_healing.clear_cached_resources()

    assert cleared == ["good"]
    assert calls == ["good", "bad"]
