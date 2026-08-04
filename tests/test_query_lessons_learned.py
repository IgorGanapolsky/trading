from __future__ import annotations

import json
from pathlib import Path

from scripts.query_lessons_learned import main, parse_args


def test_limit_aliases_share_one_destination() -> None:
    assert parse_args(["risk", "--limit", "3"]).limit == 3
    assert parse_args(["risk", "--top-k", "4"]).limit == 4


def test_query_cli_uses_dependency_free_custom_corpus(tmp_path: Path, capsys, monkeypatch) -> None:
    lesson = tmp_path / "ll_999_inventory_reconciliation.md"
    lesson.write_text(
        # Must satisfy quality_gate(): severity marker + a prevention/action section.
        # Without those the lesson is rejected at ingestion, the corpus is empty, and
        # the CLI correctly reports source="none" -- which looked like a search bug.
        """# LL-999 Inventory reconciliation

**Severity**: HIGH

## Summary
Reconcile broker inventory before allowing new risk.

## Prevention
Block new risk until the broker book matches the journal.

## Tags
`inventory`, `risk`
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("LANCEDB_RAG", "false")

    result = main(
        [
            "broker inventory risk",
            "--knowledge-dir",
            str(tmp_path),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["count"] == 1
    assert payload["results"][0]["id"] == "ll_999_inventory_reconciliation"
    # Provenance must name the backend that actually served the rows. "none" alongside
    # a non-empty result set is the bug this assertion exists to catch.
    assert payload["source"] in {"pipeline", "keyword"}
    assert payload["source"] != "none"


def test_last_source_is_never_none_when_results_are_returned(tmp_path: Path) -> None:
    """Regression: the pipeline path returned rows without recording provenance.

    `LessonsLearnedRAG.query()` delegated to TradingRAGPipeline and returned its results
    directly, leaving `last_source` at its "none" default. Callers then reported results
    with no retrievable source, which this repo's evidence rules forbid.
    """
    from src.rag.lessons_learned_rag import LessonsLearnedRAG

    lesson = tmp_path / "ll_998_stop_loss_discipline.md"
    lesson.write_text(
        """# LL-998 Stop loss discipline

**Severity**: CRITICAL

## Summary
Honor the defined stop on every structure.

## Prevention
Reject any exit rule that omits a stop.
""",
        encoding="utf-8",
    )

    rag = LessonsLearnedRAG(knowledge_dir=str(tmp_path))
    try:
        results = rag.query("stop loss discipline", top_k=3)
        assert results, "expected the seeded lesson to be retrievable"
        assert rag.last_source != "none", (
            f"returned {len(results)} result(s) but reported source 'none'"
        )
    finally:
        pipeline = getattr(rag, "_pipeline", None)
        if pipeline is not None:
            pipeline.close()


def test_add_lesson_is_immediately_retrievable(tmp_path: Path) -> None:
    """Regression: a written lesson must be visible to the very next read.

    `add_lesson()` wrote the markdown file and refreshed the legacy keyword list, but
    never re-indexed the pipeline that `query()` actually reads from. The file existed
    on disk and was unretrievable, which kept `system_health_check.py` reporting
    "RAG System: BROKEN" and held `make dry-run` red.
    """
    from src.rag.lessons_learned_rag import LessonsLearnedRAG

    rag = LessonsLearnedRAG(knowledge_dir=str(tmp_path))
    try:
        rag.add_lesson(
            "LL-HEALTH",
            "# Health Probe\n\n"
            "**Severity**: LOW\n\n"
            "## Summary\n"
            "RAG write and read round trip.\n\n"
            "## Prevention\n"
            "Keep the probe lesson valid so the round trip stays meaningful.",
        )

        assert (tmp_path / "LL-HEALTH.md").exists(), "lesson file was not written"
        results = rag.query("round trip", top_k=1)
        assert results, "lesson was written to disk but is not retrievable"
        assert results[0]["id"] == "LL-HEALTH"
    finally:
        pipeline = getattr(rag, "_pipeline", None)
        if pipeline is not None:
            pipeline.close()
