"""Tests for zg-style local-first four-route search."""

from __future__ import annotations

from pathlib import Path

from src.rag.hybrid_retriever import HybridRAGRetriever
from src.rag.zg_local_search import EvidenceHit, SearchRoute, ZgLocalSearch, _looks_like_symbol


def test_looks_like_symbol():
    assert _looks_like_symbol("TradeGateway") is True
    assert _looks_like_symbol("spy_put_credit") is True
    assert _looks_like_symbol("IRON_CONDOR_STOP_LOSS_MULTIPLIER") is True
    assert _looks_like_symbol("where are put credit exits managed") is False


def test_rrf_multi_prefers_overlap():
    retriever = HybridRAGRetriever(k_rrf=60.0)
    fts = [
        {"id": "A", "title": "only fts", "snippet": "a"},
        {"id": "B", "title": "both", "snippet": "b"},
    ]
    vec = [
        {"id": "B", "title": "both", "snippet": "b"},
        {"id": "C", "title": "only vec", "snippet": "c"},
    ]
    merged = retriever.rrf_merge_multi({"fts": fts, "vector": vec}, top_n=3)
    assert merged[0].id == "B"
    assert "fts" in merged[0].route and "vector" in merged[0].route


def test_rrf_merge_still_works_for_legacy_tests():
    retriever = HybridRAGRetriever(k_rrf=60.0)
    vec = [{"id": "LL-323", "title": "Iron Condor Management", "score": 0.95}]
    bm25 = [
        {"id": "LL-323", "title": "Iron Condor Management", "score": 12.4},
        {"id": "LL-268", "title": "Win Rate", "score": 10.1},
    ]
    merged = retriever.rrf_merge(vec, bm25, top_n=2)
    assert merged[0].lesson_id == "LL-323"
    assert merged[0].vector_rank == 1
    assert merged[0].bm25_rank == 1


def test_zg_hybrid_with_injected_fns(tmp_path: Path):
    def fts_fn(q: str, limit: int):
        return [
            {"id": "fts-1", "path": "rag_knowledge/a.md", "snippet": f"fts {q}", "score": 2.0},
            {"id": "both", "path": "rag_knowledge/b.md", "snippet": "overlap", "score": 1.5},
        ][:limit]

    def vector_fn(q: str, limit: int):
        return [
            {"id": "both", "path": "rag_knowledge/b.md", "snippet": "overlap", "score": 0.9},
            {"id": "vec-1", "path": "rag_knowledge/c.md", "snippet": f"vec {q}", "score": 0.8},
        ][:limit]

    engine = ZgLocalSearch(
        root=tmp_path,
        fts_fn=fts_fn,
        vector_fn=vector_fn,
        rewrite_queries=False,
    )
    hits = engine.search("put credit stop loss", route=SearchRoute.HYBRID, limit=3, fuse_rg=False)
    assert hits
    assert hits[0].id == "both"
    compact = engine.format_compact(hits)
    assert "both" in compact or "rag_knowledge/b.md" in compact
    assert "[" in compact


def test_zg_fts_and_vector_routes():
    engine = ZgLocalSearch(
        fts_fn=lambda q, n: [{"id": "f", "path": "f.md", "snippet": q, "score": 1.0}],
        vector_fn=lambda q, n: [{"id": "v", "path": "v.md", "snippet": q, "score": 0.5}],
        rewrite_queries=False,
    )
    fts = engine.search("x", route="fts", limit=1)
    vec = engine.search("x", route="vector", limit=1)
    assert fts[0].route == "fts" and fts[0].id == "f"
    assert vec[0].route == "vector" and vec[0].id == "v"


def test_zg_rg_route_finds_file(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    target = src / "sample_marker_mod.py"
    target.write_text("def unique_zg_marker_fn():\n    return 42\n")

    # Force Python fallback so CI runners without ripgrep still pass.
    engine = ZgLocalSearch(root=tmp_path, rewrite_queries=False, rg_bin="rg-not-installed-for-test")
    hits = engine.search("unique_zg_marker_fn", route=SearchRoute.RG, limit=5, globs=["*.py"])
    assert hits, "rg route should find the marker via Python fallback"
    assert hits[0].line == 1
    assert "sample_marker_mod.py" in hits[0].path
    assert hits[0].route == "rg"


def test_zg_rg_python_fallback_literal(tmp_path: Path):
    (tmp_path / "note.md").write_text("hello TradeGateway world\n")
    engine = ZgLocalSearch(root=tmp_path, rewrite_queries=False, rg_bin="/no/such/rg")
    hits = engine.search("TradeGateway", route="rg", limit=3)
    assert len(hits) == 1
    assert hits[0].path.endswith("note.md")


def test_evidence_hit_compact_line():
    hit = EvidenceHit(
        id="x",
        path="src/risk/trade_gateway.py",
        line=42,
        preview="class TradeGateway:",
        score=0.123456,
        route="rg",
        title="TradeGateway",
    )
    line = hit.compact_line()
    assert "src/risk/trade_gateway.py:42" in line
    assert "TradeGateway" in line


def test_hybrid_rrf_wiring_in_lessons_learned_rag(monkeypatch):
    """When both vector and keyword return hits, last_source becomes hybrid_rrf."""
    from src.rag import lessons_learned_rag as llr

    class FakeLesson:
        def __init__(self):
            self.id = "LL-301"
            self.severity = "HIGH"
            self.snippet = "IC position management"
            self.file = "rag_knowledge/lessons_learned/ll_301.md"
            self.title = "IC Position Management"
            self.prevention = ""

    class FakeSearch:
        def search(self, query, top_k=5, severity_filter=None):
            return [(FakeLesson(), 12.0)]

    class FakeRAG(llr.LessonsLearnedRAG):
        def __init__(self):
            # Bypass heavy __init__
            self._custom_dir = True  # skip defended path
            self._pipeline = None
            self.lancedb_rag = object()  # truthy
            self.search_engine = FakeSearch()
            self.lessons = []
            self.last_source = None
            self.last_retrieve_meta = None

        def _query_lancedb(self, query, top_k=5):
            return [
                {
                    "id": "LL-301",
                    "title": "IC Position Management",
                    "score": 0.9,
                    "snippet": "IC position management",
                    "content": "FULL VECTOR DOCUMENT CONTENT FOR LESSON 301 " * 3,
                    "file": "rag_knowledge/lessons_learned/ll_301.md",
                    "severity": "HIGH",
                }
            ]

        def _reposition_results(self, query, results, top_k):
            return results[:top_k]

    monkeypatch.setenv("TRADING_RAG_DEFENDED", "0")
    rag = FakeRAG()
    out = rag.query("iron condor management", top_k=3)
    assert out
    assert rag.last_source == "hybrid_rrf"
    assert out[0]["id"] == "LL-301"
    assert out[0].get("rrf") is True
    assert "FULL VECTOR DOCUMENT" in str(out[0].get("content") or "")
    assert 0.0 <= float(out[0]["score"]) <= 12.0
    assert "rrf_score" in out[0]


def test_canonical_doc_id_unifies_lesson_prefixes():
    from src.rag.zg_local_search import _canonical_doc_id

    assert _canonical_doc_id("lesson:LL-301") == "LL-301"
    assert _canonical_doc_id("ll_301") == "LL-301"
    assert _canonical_doc_id("rag_knowledge/lessons_learned/LL-301_foo.md") == "LL-301"


def test_cli_rejects_negative_limit():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "scripts" / "zg_search.py"
    spec = importlib.util.spec_from_file_location("zg_search_cli", path)
    assert spec and spec.loader
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    try:
        cli.main(["--limit", "-1", "query"])
        raised = False
    except SystemExit as exc:
        raised = True
        assert exc.code != 0
    assert raised
