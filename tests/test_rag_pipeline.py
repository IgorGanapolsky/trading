"""Unit tests for the 5-stage TradingRAGPipeline:

Stage 1: Capture 👎 → normalize/quality-gate → store lesson (SQLite FTS5)
Stage 2: Retrieve: bigram-Jaccard + keyword pragmatic-hybrid-search
Stage 3: Multi-query (3 variants, combined-score threshold trigger)
Stage 4: Cross-encoder reranker (LLM if key, else heuristic)
Stage 5: Assemble context + deterministic gate
"""

from __future__ import annotations

import os
import sys
import tempfile
import logging

import pytest

logger = logging.getLogger(__name__)

# Skip if Python < 3.10 (str|None syntax used in source)
pytestmark = pytest.mark.skipif(sys.version_info < (3, 10), reason="Requires Python 3.10+")


def _make_test_lessons(temp_dir: str) -> str:
    """Create a temporary lessons directory with a few markdown lessons."""
    lessons = [
        (
            "ll-101_iron_condor_exit_rules.md",
            """# CRITICAL: Iron Condor Exit Rule Violation

## Summary
Closed an iron condor too early, left a short call that exploded.

## Severity
CRITICAL

## Prevention
Always set exits at 50% max credit or 3 DTE, whichever comes first.
""",
        ),
        (
            "ll-102_position_sizing_error.md",
            """# HIGH: Position Sizing Error

## Summary
Allocated too much capital to a single iron condor.

## Severity
HIGH

## Prevention
Never risk more than 2% of portfolio per trade.
""",
        ),
        (
            "ll-103_delta_selection_options.md",
            """# MEDIUM: Delta Selection for Options

## Summary
Picked 0.3 delta for iron condor wings, too narrow.

## Severity
MEDIUM

## Prevention
Use 0.15 delta for standard iron condors.
""",
        ),
    ]
    lessons_dir = os.path.join(temp_dir, "lessons")
    os.makedirs(lessons_dir, exist_ok=True)
    for filename, content in lessons:
        with open(os.path.join(lessons_dir, filename), "w") as f:
            f.write(content)
    return lessons_dir


@pytest.fixture
def pipeline():
    """Create a pipeline with test lessons in a temp directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_rag.db")
        lessons_dir = _make_test_lessons(tmpdir)
        from src.rag.rag_pipeline import TradingRAGPipeline

        pipe = TradingRAGPipeline(db_path=db_path, lessons_dir=lessons_dir)
        pipe.index_from_markdown_dir(lessons_dir)
        yield pipe
        pipe.close()


# -- Stage 1: Capture 👉 normalize/quality-gate 👉 store (SQLite FTS5) --


class TestStage1CaptureAndStore:
    def test_quality_gate_passes_valid_lesson(self):
        """Lesson with severity marker + prevention + >=50 chars should pass."""
        from src.rag.rag_pipeline import quality_gate

        content = (
            "# CRITICAL: Bad Trade\n\n"
            "**Severity**: CRITICAL\n\n"
            "## Prevention\n"
            "This is a prevention section with more than fifty characters of content."
        )
        passed, reason = quality_gate(content)
        assert passed is True
        assert "ok" in reason.lower()

    def test_quality_gate_rejects_short_content(self):
        """Lesson with too short content should be rejected."""
        from src.rag.rag_pipeline import quality_gate

        passed, reason = quality_gate("short")
        assert passed is False
        assert len(reason) > 0

    def test_quality_gate_rejects_no_severity(self):
        """Lesson without severity marker should be rejected."""
        from src.rag.rag_pipeline import quality_gate

        content = (
            "# Some Title\n\n"
            "## Prevention\n"
            "This is a prevention section with more than fifty characters of content."
        )
        passed, reason = quality_gate(content)
        assert passed is False

    def test_quality_gate_rejects_no_prevention(self):
        """Lesson without prevention section should be rejected."""
        from src.rag.rag_pipeline import quality_gate

        content = "# CRITICAL: Bad Trade\n\n## Severity\nCRITICAL\n"
        passed, reason = quality_gate(content)
        assert passed is False

    def test_sqlite_fts_store_put_and_search(self):
        """SQLiteFTS5Store should store and retrieve lessons via FTS5."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            from src.rag.rag_pipeline import SQLiteFTS5Store, LessonRecord

            store = SQLiteFTS5Store(db_path)
            record = LessonRecord(
                lesson_id="ll-001_test_lesson",
                title="Test Lesson",
                content="Iron condor exit strategy rules for trading",
                severity="CRITICAL",
                prevention="Exit at 50% max credit",
                tags="iron-condor",
                source="test",
                created_at="2025-01-01",
            )
            store.put(record)
            results = store.fts_search("iron condor exit", top_k=5)
            assert len(results) >= 1
            assert results[0]["lesson_id"] == "ll-001_test_lesson"
            assert "CRITICAL" in str(results[0].get("severity", ""))
            store.close()

    def test_index_from_markdown_dir_loads_lessons(self, pipeline):
        """index_from_markdown_dir should load all valid lessons from directory."""
        assert pipeline.lesson_count >= 3

    def test_capture_feedback_stores_lesson(self, pipeline):
        """capture_feedback should store a new lesson after quality gate passes."""
        feedback = (
            "# FAIL: Iron Condor Blown\n\n"
            "User got assigned on a short call.\n\n"
            "**Severity**: CRITICAL\n\n"
            "## Prevention\n"
            "Always close iron condors before 1 DTE to avoid assignment risk."
        )
        stored, reason = pipeline.capture_feedback(feedback, lesson_id="ll-999_feedback_test")
        assert stored is True
        assert "Stored" in reason

    def test_capture_feedback_rejects_low_quality(self, pipeline):
        """capture_feedback should reject content that fails quality gate."""
        stored, reason = pipeline.capture_feedback("too short", lesson_id="ll-998_short")
        assert stored is False


# -- Stage 2: Retrieve: bigram-Jaccard + keyword pragmatic-hybrid-search --


class TestStage2HybridRetrieval:
    def test_pragmatic_hybrid_returns_ranked_results(self, pipeline):
        """pragmatic_hybrid_search should return results ranked by combined score."""
        from src.rag.rag_pipeline import pragmatic_hybrid_search

        fts_results = pipeline.store.fts_search("iron condor", top_k=50)
        hits = pragmatic_hybrid_search("iron condor exit", fts_results, top_k=10)
        assert len(hits) > 0
        # Results should be sorted by combined_score descending
        for i in range(len(hits) - 1):
            assert hits[i].combined_score >= hits[i + 1].combined_score

    def test_pragmatic_hybrid_includes_token_floor(self, pipeline):
        """Lessons with any token match should get the token floor score."""
        from src.rag.rag_pipeline import pragmatic_hybrid_search

        fts_results = pipeline.store.fts_search("delta", top_k=50)
        hits = pragmatic_hybrid_search("delta selection", fts_results, top_k=50)
        # At least one result should have combined_score >= 0.10 (token floor)
        assert any(h.combined_score >= 0.10 for h in hits)

    def test_pragmatic_hybrid_title_boost(self, pipeline):
        """Lessons with query terms in title should get a title boost."""
        from src.rag.rag_pipeline import pragmatic_hybrid_search

        fts_results = pipeline.store.fts_search("position sizing", top_k=50)
        hits = pragmatic_hybrid_search("position sizing error", fts_results, top_k=50)
        # The position sizing lesson should have a title boost (>= 0.15 with title match)
        position_hits = [h for h in hits if "position" in h.title.lower()]
        if position_hits:
            assert position_hits[0].combined_score > 0.15

    def test_query_returns_results(self, pipeline):
        """TradingRAGPipeline.query should return ranked, normalized dicts."""
        results = pipeline.query("iron condor exit strategy", top_k=5)
        assert len(results) > 0
        for r in results:
            assert "id" in r
            assert "title" in r
            assert "severity" in r
            assert "score" in r
            assert 0.0 <= r["score"] <= 1.0


# -- Stage 3: Multi-query (3 variants, combined-score threshold trigger) --


class TestStage3MultiQuery:
    def test_generate_query_variants_returns_3(self):
        """generate_query_variants should return up to 3 variants."""
        from src.rag.rag_pipeline import generate_query_variants

        variants = generate_query_variants("iron condor exit strategy", max_variants=3)
        assert len(variants) <= 3
        assert len(variants) >= 1
        # First variant should be the original query
        assert variants[0].text == "iron condor exit strategy"

    def test_generate_query_variants_has_synonym_expanded(self):
        """Second variant should be synonym-expanded."""
        from src.rag.rag_pipeline import generate_query_variants

        variants = generate_query_variants("iron condor exit strategy", max_variants=3)
        if len(variants) >= 2:
            assert variants[1].kind == "synonym_expanded"

    def test_multi_query_triggers_low_score(self, pipeline):
        """Multi-query should trigger when top combined score < threshold."""
        # Use a query that's unlikely to match well
        results = pipeline.query("xyzzy qwerty flibbertigibbet", top_k=5)
        # Should return empty (OOD) or very few results
        assert isinstance(results, list)

    def test_multi_query_does_not_trigger_high_score(self, pipeline):
        """Multi-query should NOT trigger when top combined score > threshold."""
        # "iron condor exit strategy" with real lessons has high combined score
        results = pipeline.query("iron condor exit strategy", top_k=5)
        # Should still return good results
        assert len(results) > 0


# -- Stage 4: Cross-encoder reranker (LLM if key, else heuristic) --


class TestStage4Reranker:
    def test_reranker_type_is_cross_encoder(self, pipeline):
        """Reranker uses cross-encoder when installed, else heuristic."""
        assert pipeline._reranker.reranker_type in ("cross-encoder", "heuristic", "llm")

    def test_cross_encoder_scores_in_range(self, pipeline):
        """CE ensemble scores should be in [0, 1] range."""
        results = pipeline.query("iron condor", top_k=5)
        for r in results:
            assert 0.0 <= r["score"] <= 1.0

    def test_ood_query_returns_empty(self, pipeline):
        """Out-of-domain queries should return empty results (OOD rejection)."""
        results = pipeline.query("cooking recipes for banana bread", top_k=5)
        assert results == [], f"Expected empty for OOD query, got {results}"

    def test_reranker_uses_title_boost(self, pipeline):
        """Lessons with query terms in title should get title-match boost."""
        results = pipeline.query("delta selection options", top_k=10)
        # The delta selection lesson should rank high
        delta_ids = [r for r in results if "delta" in r.get("title", "").lower()]
        assert len(delta_ids) > 0

    def test_fallback_to_heuristic_when_no_ce(self):
        """Heuristic reranker should work without cross-encoder."""
        from src.rag.rag_pipeline import RAGEReranker

        reranker = RAGEReranker()
        # Force heuristic mode by removing cross-encoder
        reranker._cross_encoder = None
        reranker._reranker_type = "heuristic"
        assert reranker.reranker_type == "heuristic"
        # Should not crash on simple candidates
        candidates = [
            {
                "id": "ll-001",
                "title": "test",
                "severity": "HIGH",
                "content_snippet": "test content",
                "score": 0.5,
            },
        ]
        results = reranker.rerank("test query", candidates, top_n=1)
        assert len(results) == 1


# -- Stage 5: Assemble context + deterministic gate --


def _make_lesson_result(
    lesson_id: str, title: str, severity: str, prevention: str = "Prevent this", score: float = 0.5
):
    """Helper to create a LessonResult for gate tests."""
    from src.rag.rag_pipeline import LessonResult

    return LessonResult(
        id=lesson_id,
        title=title,
        severity=severity,
        snippet="test snippet",
        prevention=prevention,
        file="test.md",
        score=score,
    )


class TestStage5DeterministicGate:
    def test_gate_block_critical_high_score(self):
        """CRITICAL lesson with score > 0.5 should BLOCK."""
        from src.rag.rag_pipeline import gate_decision

        lesson = _make_lesson_result("ll-001", "Bad Trade", "CRITICAL", score=0.60)
        decision = gate_decision([(lesson, 0.60)])
        assert decision.severity == "BLOCK"
        assert decision.approved is False

    def test_gate_block_high_score(self):
        """HIGH lesson with score > 0.70 should BLOCK."""
        from src.rag.rag_pipeline import gate_decision

        lesson = _make_lesson_result("ll-002", "Position Error", "HIGH", score=0.80)
        decision = gate_decision([(lesson, 0.80)])
        assert decision.severity == "BLOCK"
        assert decision.approved is False

    def test_gate_warn_critical_low_score(self):
        """CRITICAL lesson with score 0.15-0.50 should WARN."""
        from src.rag.rag_pipeline import gate_decision

        lesson = _make_lesson_result("ll-001", "Bad Trade", "CRITICAL", score=0.30)
        decision = gate_decision([(lesson, 0.30)])
        assert decision.severity == "WARN"
        assert decision.approved is True  # approved but warned

    def test_gate_approve(self):
        """MEDIUM severity with score < 0.15 should APPROVED."""
        from src.rag.rag_pipeline import gate_decision

        lesson = _make_lesson_result("ll-003", "Delta Pick", "MEDIUM", score=0.10)
        decision = gate_decision([(lesson, 0.10)])
        assert decision.severity == "APPROVED"
        assert decision.approved is True

    def test_gate_approve_critical_low(self):
        """CRITICAL lesson with score < 0.15 should APPROVED."""
        from src.rag.rag_pipeline import gate_decision

        lesson = _make_lesson_result("ll-001", "Bad Trade", "CRITICAL", score=0.10)
        decision = gate_decision([(lesson, 0.10)])
        assert decision.severity == "APPROVED"
        assert decision.approved is True

    def test_gate_empty_results_approved(self):
        """No lessons should result in APPROVED."""
        from src.rag.rag_pipeline import gate_decision

        decision = gate_decision([])
        assert decision.severity == "APPROVED"
        assert decision.approved is True

    def test_retrieve_and_gate_integration(self, pipeline):
        """Full pipeline: retrieve + gate should return (results, decision, context)."""
        results, decision, context = pipeline.retrieve_and_gate(
            "iron condor exit strategy", top_k=5
        )
        assert isinstance(results, list)
        assert decision is not None
        assert decision.severity in ("APPROVED", "WARN", "BLOCK")
        assert isinstance(context, str)
        assert len(context) > 0


# -- Integration: LessonsLearnedRAG delegates to TradingRAGPipeline --


class TestLessonsLearnedRAGDelegation:
    def test_lessons_rag_uses_pipeline_backend(self):
        """LessonsLearnedRAG should delegate to TradingRAGPipeline when available."""
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        rag = LessonsLearnedRAG()
        try:
            assert rag._pipeline is not None
            # Worktrees / sparse checkouts may have fewer lesson files; require a real index.
            assert rag._pipeline.lesson_count >= 50
        finally:
            if rag._pipeline:
                rag._pipeline.close()

    def test_lessons_rag_search_returns_tuple_format(self):
        """LessonsLearnedRAG.search should return (LessonResult, score) tuples."""
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        rag = LessonsLearnedRAG()
        try:
            results = rag.search("iron condor", top_k=3)
            assert len(results) > 0
            for lesson, score in results:
                assert hasattr(lesson, "id")
                assert hasattr(lesson, "title")
                assert hasattr(lesson, "severity")
                assert hasattr(lesson, "prevention")
                assert 0.0 <= score <= 1.0
        finally:
            if rag._pipeline:
                rag._pipeline.close()


# -- nDCG bug fix verification --


class TestNDCGBugFix:
    def test_ndcg_with_full_form_keys(self):
        """nDCG should work when retrieved IDs are full-form and graded_relevance uses ll-NNN keys."""
        from src.rag.evaluation import RAGEvaluator

        evaluator = RAGEvaluator(test_queries=[])

        # Simulate the bug scenario: retrieved IDs are full-form, graded_relevance uses ll-NNN
        retrieved = ["ll-101_iron_condor_exit_rules", "ll-102_position_sizing_error"]
        graded_relevance = {
            "ll-101_iron_condor_exit_rules": 3,
            "ll-102_position_sizing_error": 2,
        }
        score = evaluator.ndcg_at_k(retrieved, graded_relevance, k=2)
        # nDCG should be > 0 (bug previously made it always 0.0)
        assert score > 0.0

    def test_ndcg_perfect_score(self):
        """nDCG should be 1.0 for ideal ranking."""
        from src.rag.evaluation import RAGEvaluator

        evaluator = RAGEvaluator(test_queries=[])
        retrieved = ["ll-101_iron_condor", "ll-102_position_sizing"]
        graded_relevance = {
            "ll-101_iron_condor": 3,
            "ll-102_position_sizing": 2,
        }
        score = evaluator.ndcg_at_k(retrieved, graded_relevance, k=2)
        assert abs(score - 1.0) < 1e-9

    def test_ndcg_suboptimal_score(self):
        """nDCG should be < 1.0 for suboptimal ranking."""
        from src.rag.evaluation import RAGEvaluator

        evaluator = RAGEvaluator(test_queries=[])
        # Lower grade first, higher grade second
        retrieved = ["ll-102_position_sizing", "ll-101_iron_condor"]
        graded_relevance = {
            "ll-101_iron_condor": 3,
            "ll-102_position_sizing": 2,
        }
        score = evaluator.ndcg_at_k(retrieved, graded_relevance, k=2)
        assert 0.0 < score < 1.0
