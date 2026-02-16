from __future__ import annotations

from pathlib import Path

from scripts import build_rag_query_index


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_build_index_filters_tars_artifact_ingest_by_default(tmp_path: Path, monkeypatch) -> None:
    rag_root = tmp_path / "rag_knowledge"
    monkeypatch.setattr(build_rag_query_index, "RAG_ROOT", rag_root)
    monkeypatch.delenv("INCLUDE_ARTIFACT_INGEST_LESSONS", raising=False)

    _write(
        rag_root / "lessons_learned" / "tars_20260216_env_status_deadbeef.md",
        """---
title: "TARS Artifact Ingest - env_status.txt"
description: "Normalized TARS artifact ingested for RAG retrieval."
date: 2026-02-16T13:46:26Z
severity: INFO
source: tars_artifact_ingest
---

# TARS Artifact Ingest: env_status.txt
""",
    )
    _write(
        rag_root / "lessons_learned" / "ll_900_real_lesson.md",
        """# LL-900: Keep Lessons User-Facing

**Severity**: HIGH
**Date**: 2026-02-16
""",
    )

    lessons = build_rag_query_index.build_index()
    ids = {item["id"] for item in lessons}

    assert "ll_900_real_lesson" in ids
    assert "tars_20260216_env_status_deadbeef" not in ids


def test_build_index_can_include_tars_artifact_ingest_with_opt_in(
    tmp_path: Path, monkeypatch
) -> None:
    rag_root = tmp_path / "rag_knowledge"
    monkeypatch.setattr(build_rag_query_index, "RAG_ROOT", rag_root)
    monkeypatch.setenv("INCLUDE_ARTIFACT_INGEST_LESSONS", "1")

    _write(
        rag_root / "lessons_learned" / "tars_20260216_smoke_metrics_deadbeef.md",
        """---
title: "TARS Artifact Ingest - smoke_metrics.txt"
date: 2026-02-16T16:27:33Z
severity: INFO
source: tars_artifact_ingest
---

# TARS Artifact Ingest: smoke_metrics.txt
""",
    )

    lessons = build_rag_query_index.build_index()
    assert len(lessons) == 1
    assert lessons[0]["id"] == "tars_20260216_smoke_metrics_deadbeef"
    assert lessons[0]["severity"] == "INFO"
    assert lessons[0]["date"] == "2026-02-16T16:27:33Z"

