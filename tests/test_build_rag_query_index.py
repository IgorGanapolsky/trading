from __future__ import annotations

import re
from pathlib import Path

from scripts import build_rag_query_index


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_build_index_filters_tars_artifact_ingest_by_default(tmp_path: Path, monkeypatch) -> None:
    rag_root = tmp_path / "rag_knowledge"
    monkeypatch.setattr(build_rag_query_index, "RAG_ROOT", rag_root)
    monkeypatch.setattr(build_rag_query_index, "ADDITIONAL_MARKDOWN_SOURCES", [])
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
    monkeypatch.setattr(build_rag_query_index, "ADDITIONAL_MARKDOWN_SOURCES", [])
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
    assert lessons[0]["event_timestamp_utc"] == "2026-02-16T16:27:33Z"
    assert re.match(r"^20\d{2}-\d{2}-\d{2}T", lessons[0]["source_mtime_utc"])
    assert re.match(r"^20\d{2}-\d{2}-\d{2}T", lessons[0]["indexed_at_utc"])


def test_build_index_parses_bold_date_with_colon_inside_markup(tmp_path: Path, monkeypatch) -> None:
    rag_root = tmp_path / "rag_knowledge"
    monkeypatch.setattr(build_rag_query_index, "RAG_ROOT", rag_root)
    monkeypatch.setattr(build_rag_query_index, "ADDITIONAL_MARKDOWN_SOURCES", [])

    _write(
        rag_root / "lessons_learned" / "ll_999_markup_date.md",
        """# LL-999: Markup Date Format

**Date:** 2026-02-16
**Severity:** HIGH
""",
    )

    lessons = build_rag_query_index.build_index()
    assert len(lessons) == 1
    assert lessons[0]["id"] == "ll_999_markup_date"
    assert lessons[0]["date"] == "2026-02-16"
    assert re.match(r"^20\d{2}-\d{2}-\d{2}T", lessons[0]["event_timestamp_utc"])
    assert re.match(r"^20\d{2}-\d{2}-\d{2}T", lessons[0]["source_mtime_utc"])
    assert re.match(r"^20\d{2}-\d{2}-\d{2}T", lessons[0]["indexed_at_utc"])


def test_build_index_falls_back_to_filename_date_when_metadata_missing(
    tmp_path: Path, monkeypatch
) -> None:
    rag_root = tmp_path / "rag_knowledge"
    monkeypatch.setattr(build_rag_query_index, "RAG_ROOT", rag_root)
    monkeypatch.setattr(build_rag_query_index, "ADDITIONAL_MARKDOWN_SOURCES", [])

    _write(
        rag_root / "lessons_learned" / "ll_proactive_scan_20260216.md",
        """# Ralph Proactive Scan Findings

No explicit date metadata in this lesson body.
""",
    )
    _write(
        rag_root / "lessons_learned" / "ll_proactive_scan_20260215.md",
        """# Ralph Proactive Scan Findings

No explicit date metadata in this lesson body.
""",
    )

    lessons = build_rag_query_index.build_index()
    assert [lesson["id"] for lesson in lessons[:2]] == [
        "ll_proactive_scan_20260216",
        "ll_proactive_scan_20260215",
    ]
    assert lessons[0]["date"] == "2026-02-16"


def test_build_index_includes_sql_analytics_report_markdown(tmp_path: Path, monkeypatch) -> None:
    rag_root = tmp_path / "rag_knowledge"
    monkeypatch.setattr(build_rag_query_index, "RAG_ROOT", rag_root)
    monkeypatch.setattr(
        build_rag_query_index,
        "ADDITIONAL_MARKDOWN_SOURCES",
        [tmp_path / "docs" / "_reports" / "sql-analytics-summary.md"],
    )

    _write(
        tmp_path / "docs" / "_reports" / "sql-analytics-summary.md",
        """---
title: "Automated SQL Analytics Summary"
description: "Latest period-over-period trading analytics summary generated from canonical trading JSON sources."
date: 2026-03-13T20:00:00Z
severity: INFO
category: analytics
---

# Automated SQL Analytics Summary

## Answer Block
Q: How did today compare to the previous snapshot?
A: Equity improved.
""",
    )

    lessons = build_rag_query_index.build_index()
    assert len(lessons) == 1
    assert lessons[0]["id"] == "reports/sql-analytics-summary"
    assert lessons[0]["title"] == "Automated SQL Analytics Summary"
    assert lessons[0]["category"] == "analytics"
    assert lessons[0]["severity"] == "INFO"
    assert lessons[0]["date"] == "2026-03-13T20:00:00Z"


def test_build_index_adds_retrieval_quality_metadata(tmp_path: Path, monkeypatch) -> None:
    rag_root = tmp_path / "rag_knowledge"
    monkeypatch.setattr(build_rag_query_index, "RAG_ROOT", rag_root)
    monkeypatch.setattr(build_rag_query_index, "ADDITIONAL_MARKDOWN_SOURCES", [])

    _write(
        rag_root / "lessons_learned" / "ll_quality_rich.md",
        """---
title: "Quality Rich Lesson"
description: "A structured lesson with enough metadata for retrieval ranking."
date: 2026-05-06T14:00:00Z
severity: HIGH
category: ingestion
tags: [rag, ingestion]
---

# Quality Rich Lesson

## Summary
This lesson has current metadata, source tags, and enough text to be trusted by retrieval.

## Citations
- https://example.com/source
""",
    )
    _write(
        rag_root / "lessons_learned" / "ll_stale_sparse_20200101.md",
        """# Sparse Historical Lesson

Thin stale note.
""",
    )

    lessons = {lesson["id"]: lesson for lesson in build_rag_query_index.build_index()}

    rich = lessons["ll_quality_rich"]
    assert rich["source_age_days"] is not None  # nosec B101
    assert rich["metadata_completeness"] >= 0.8  # nosec B101
    assert rich["confidence_score"] >= 0.72  # nosec B101
    assert rich["lifecycle"] == "active"  # nosec B101
    assert {"rag", "ingestion"}.issubset(set(rich["tags"]))  # nosec B101

    stale = lessons["ll_stale_sparse_20200101"]
    assert stale["source_age_days"] > 90  # nosec B101
    assert stale["recency_score"] == 0.25  # nosec B101
    assert stale["lifecycle"] in {"watch", "archive"}  # nosec B101
