"""The cross-encoder must load once per process, not once per reranker.

Loading it per construction cost ~3-4s each time and a reranker is built per pipeline.
That doubled the test suite (640s -> 1277s) and put seconds on the first query of every
new pipeline. Caching is a latency fix, so the test asserts the load count -- timing
assertions are flaky, call counts are not.
"""

from __future__ import annotations

import pytest

from src.rag import rag_pipeline


@pytest.fixture(autouse=True)
def clear_cache():
    rag_pipeline._cross_encoder_cache.clear()
    yield
    rag_pipeline._cross_encoder_cache.clear()


def test_cross_encoder_loads_once_across_many_rerankers(monkeypatch) -> None:
    loads: list[str] = []

    class FakeCrossEncoder:
        def __init__(self, model_name: str) -> None:
            loads.append(model_name)

    fake_module = type("M", (), {"CrossEncoder": FakeCrossEncoder})
    monkeypatch.setitem(__import__("sys").modules, "sentence_transformers", fake_module)

    for _ in range(5):
        reranker = rag_pipeline.RAGEReranker()
        assert reranker.reranker_type == "cross-encoder"

    assert loads == [rag_pipeline.CROSS_ENCODER_MODEL], (
        f"model loaded {len(loads)} times; expected exactly 1"
    )


def test_cached_instance_is_shared(monkeypatch) -> None:
    class FakeCrossEncoder:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

    fake_module = type("M", (), {"CrossEncoder": FakeCrossEncoder})
    monkeypatch.setitem(__import__("sys").modules, "sentence_transformers", fake_module)

    first = rag_pipeline.RAGEReranker()._cross_encoder
    second = rag_pipeline.RAGEReranker()._cross_encoder
    assert first is second, "each reranker must reuse the one process-wide model"


def test_missing_dependency_still_falls_back(monkeypatch) -> None:
    """Caching must not break the degradation path that keeps trading unblocked."""

    def boom(name, *args, **kwargs):
        raise ImportError("sentence_transformers not installed")

    monkeypatch.setattr(rag_pipeline, "_load_cross_encoder", boom)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    assert rag_pipeline.RAGEReranker().reranker_type == "heuristic"
