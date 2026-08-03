"""Tests for offline LLM batching helper."""

from __future__ import annotations

from src.utils.llm_batch import chunked, estimate_batch_savings, map_in_batches


def test_chunked():
    assert list(chunked([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]


def test_map_in_batches():
    out = map_in_batches([1, 2, 3, 4], lambda b: [x * 2 for x in b], batch_size=2)
    assert out == [2, 4, 6, 8]


def test_estimate_savings():
    s = estimate_batch_savings(64, batch_size=32, per_call_overhead_tokens=40)
    assert s["saved_overhead_tokens"] > 0
    assert s["savings_ratio"] > 0.5
