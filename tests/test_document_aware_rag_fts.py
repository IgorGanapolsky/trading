"""Regression tests for LanceDB single-field native FTS creation."""

from __future__ import annotations

import builtins

from src.memory.document_aware_rag import DocumentAwareRAG, FTS_COLUMNS


def test_fts_indexes_are_created_one_field_at_a_time() -> None:
    calls: list[tuple[object, bool]] = []

    class Table:
        def create_fts_index(self, field, *, replace):
            assert isinstance(field, str)
            calls.append((field, replace))

    rag = DocumentAwareRAG()
    rag._ensure_fts_index(Table())

    assert calls == [(column, False) for column in FTS_COLUMNS]


def test_existing_single_field_indexes_are_idempotent() -> None:
    class Table:
        def create_fts_index(self, _field, *, replace):
            assert replace is False
            raise RuntimeError("index already exists")

    rag = DocumentAwareRAG()
    rag._ensure_fts_index(Table())


def test_embedding_runtime_failure_disables_lancedb_without_retry_loop(monkeypatch) -> None:
    original_import = builtins.__import__

    def fail_sentence_transformers(name, *args, **kwargs):
        if name == "sentence_transformers":
            raise ValueError("incompatible embedding runtime")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_sentence_transformers)

    rag = DocumentAwareRAG()

    assert rag._init_lancedb() is False
    assert rag._initialized is False
