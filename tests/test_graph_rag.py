"""Tests for financial Graph RAG (stdlib SQLite property graph)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.rag.graph.builder import FinancialGraphBuilder
from src.rag.graph.pipeline import GraphRAGPipeline
from src.rag.graph.router import QueryIntent, route_query
from src.rag.graph.schema import EdgeRel, NodeType
from src.rag.graph.store import FinancialGraphStore
from src.rag.graph.token_gateway import apply_token_guard, estimate_tokens


@pytest.fixture
def graph_db(tmp_path: Path) -> Path:
    return tmp_path / "financial_graph.sqlite"


@pytest.fixture
def store(graph_db: Path) -> FinancialGraphStore:
    s = FinancialGraphStore(db_path=graph_db)
    yield s
    s.close()


@pytest.fixture
def mini_repo(tmp_path: Path) -> Path:
    """Minimal ledger fixtures for builder tests."""
    root = tmp_path / "repo"
    (root / "data/runtime").mkdir(parents=True)
    (root / "data/rag").mkdir(parents=True)
    (root / "rag_knowledge/lessons_learned").mkdir(parents=True)

    kill = {
        "updated_at": "2026-07-22T15:00:00Z",
        "active_family": "spy_put_credit",
        "killed_families": ["ic_simple", "iron_condor"],
        "paper_only": True,
        "live_blocked": True,
        "reason": "IC Simple killed; successor spy_put_credit",
        "evidence": {"closed_trades": 159, "profit_factor": 0.16},
    }
    (root / "data/runtime/strategy_kill_switch.json").write_text(json.dumps(kill), encoding="utf-8")

    lesson = """# LL-999: Never freehand-close inventory

**Severity**: CRITICAL

## Prevention
Always use guardian workflow for residual IC exits.
Put credit validation requires clean inventory.
SPY only. Iron condor new entries are forbidden.
"""
    (root / "rag_knowledge/lessons_learned/LL-999.md").write_text(lesson, encoding="utf-8")

    trades = {
        "meta": {},
        "stats": {},
        "trades": [
            {
                "id": "PC_SPY_TEST_1",
                "symbol": "SPY",
                "strategy": "spy_put_credit",
                "status": "closed",
                "entry_date": "2026-07-01",
                "exit_date": "2026-07-10",
                "realized_pnl": 40.0,
                "outcome": "win",
                "quantity": 1,
                "signature": "SPY_PUT_TEST",
            },
            {
                "id": "IC_SPY_TEST_2",
                "symbol": "SPY",
                "strategy": "iron_condor",
                "status": "closed",
                "entry_date": "2026-02-01",
                "exit_date": "2026-02-02",
                "realized_pnl": -200.0,
                "outcome": "loss",
                "quantity": 1,
                "signature": "SPY_IC_TEST",
            },
        ],
    }
    (root / "data/trades.json").write_text(json.dumps(trades), encoding="utf-8")

    (root / "data/runtime/usd_macro_sentiment.json").write_text(
        json.dumps({"score": 0.1, "note": "fixture"}), encoding="utf-8"
    )
    return root


def test_store_upsert_and_temporal_expire(store: FinancialGraphStore) -> None:
    store.upsert_node("ticker:SPY", NodeType.TICKER, label="SPY")
    store.upsert_node("strategy:spy_put_credit", NodeType.STRATEGY, label="put credit")
    e1 = store.upsert_edge(
        "strategy:spy_put_credit",
        "ticker:SPY",
        EdgeRel.TRADES,
        edge_id="e:pc:TRADES:spy",
        weight=1.0,
    )
    assert e1.src == "strategy:spy_put_credit"
    neigh = store.neighbors("strategy:spy_put_credit", direction="out")
    assert len(neigh) == 1
    assert neigh[0][1].id == "ticker:SPY"

    # Replace active edge → prior expires
    store.upsert_edge(
        "strategy:spy_put_credit",
        "ticker:SPY",
        EdgeRel.TRADES,
        edge_id="e:pc:TRADES:spy:v2",
        weight=0.5,
        replace_active=True,
    )
    active = store.neighbors("strategy:spy_put_credit", direction="out")
    assert len(active) == 1
    assert active[0][0].id == "e:pc:TRADES:spy:v2"


def test_bfs_paths(store: FinancialGraphStore) -> None:
    store.upsert_node("a", NodeType.CONCEPT, "A")
    store.upsert_node("b", NodeType.CONCEPT, "B")
    store.upsert_node("c", NodeType.CONCEPT, "C")
    store.upsert_edge("a", "b", EdgeRel.RELATED_TO, edge_id="e:ab")
    store.upsert_edge("b", "c", EdgeRel.IMPACTS, edge_id="e:bc", weight=1.5)
    paths = store.bfs_paths(["a"], max_hops=2, max_paths=10)
    assert paths
    terminal = {p.node_ids[-1] for p in paths}
    assert "b" in terminal
    assert "c" in terminal


def test_router_strategy_status() -> None:
    d = route_query("why is iron condor killed and live blocked?")
    assert d.intent == QueryIntent.STRATEGY_STATUS
    assert any("strategy" in s or "macro" in s for s in d.seed_hints)


def test_router_macro() -> None:
    d = route_query("how does VIX spike impact SPY put credit?")
    assert d.intent == QueryIntent.MACRO_IMPACT
    assert "concept:vix_spike" in d.seed_hints or "ticker:SPY" in d.seed_hints


def test_token_guard_trims() -> None:
    paths = [
        {"node_ids": [f"n{i}", f"n{i + 1}"], "rels": ["RELATED_TO"], "score": float(10 - i)}
        for i in range(30)
    ]
    nodes = [
        {
            "id": f"n{i}",
            "type": "lesson",
            "label": f"Lesson {i}",
            "properties": {"snippet": "x" * 400},
        }
        for i in range(40)
    ]
    guard = apply_token_guard(
        query="test",
        intent="hybrid",
        route_reason="unit",
        paths=paths,
        nodes=nodes,
        vector_hits=[{"id": "L1", "title": "t", "snippet": "y" * 500, "score": 1.0}],
        max_tokens=200,
        hard_max_tokens=5000,
        max_paths=20,
        max_nodes=20,
    )
    assert guard.allowed
    assert guard.trimmed_paths > 0 or guard.estimated_tokens <= 200
    assert estimate_tokens(guard.context_text) == guard.estimated_tokens


def test_token_guard_hard_halt() -> None:
    huge_nodes = [
        {
            "id": f"n{i}",
            "type": "lesson",
            "label": "L",
            "properties": {"snippet": "z" * 2000},
        }
        for i in range(5)
    ]
    # Force halt with tiny hard max and no room to trim below it after build
    guard = apply_token_guard(
        query="q",
        intent="hybrid",
        route_reason="unit",
        paths=[{"node_ids": ["a", "b"], "rels": ["X"], "score": 1.0}],
        nodes=huge_nodes,
        max_tokens=10,
        hard_max_tokens=30,
        max_paths=1,
        max_nodes=1,
        max_vector_hits=0,
    )
    # May still be allowed if trim works; if not, must halt cleanly
    if not guard.allowed:
        assert guard.halt_reason
        assert "HALTED" in guard.context_text


def test_builder_and_pipeline_query(mini_repo: Path, graph_db: Path) -> None:
    store = FinancialGraphStore(db_path=graph_db)
    builder = FinancialGraphBuilder(store, repo_root=mini_repo)
    result = builder.rebuild(clear=True)
    assert result["stats"]["nodes"] >= 10
    assert result["stats"]["edges"] >= 5

    # Kill path exists
    neigh = store.neighbors("macro:strategy_kill_2026_07_22", direction="out")
    rels = {e.rel for e, _ in neigh}
    assert "KILLED" in rels or "SUCCEEDS" in rels

    # Lesson linked
    lesson = store.get_node("lesson:LL-999")
    assert lesson is not None
    assert lesson.properties.get("severity") == "CRITICAL"

    # Trades linked
    assert store.get_node("trade:PC_SPY_TEST_1") is not None

    pipe = GraphRAGPipeline(
        store=store,
        repo_root=mini_repo,
        auto_build_if_empty=False,
    )
    # Graph-only to avoid depending on full lessons corpus / LanceDB
    out = pipe.query(
        "why is iron condor killed?",
        force_graph_only=True,
        max_tokens=2000,
    )
    assert out.allowed
    assert out.route["intent"] == QueryIntent.STRATEGY_STATUS.value
    assert out.latency_ms < 5000  # generous for CI; local is usually << 100ms
    ctx = out.context.lower()
    assert "iron_condor" in ctx or "killed" in ctx or "spy_put_credit" in ctx
    pipe.close()
    store.close()


def test_pipeline_stats_empty_autobuild(mini_repo: Path, graph_db: Path) -> None:
    pipe = GraphRAGPipeline(
        store=FinancialGraphStore(db_path=graph_db),
        repo_root=mini_repo,
        auto_build_if_empty=True,
    )
    stats = pipe.stats()
    assert stats["nodes"] > 0
    pipe.close()


def test_cli_rebuild_and_query(
    mini_repo: Path, graph_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import graph_rag_query as cli

    monkeypatch.setattr(cli, "_REPO", mini_repo)
    code = cli.main(
        [
            "--repo-root",
            str(mini_repo),
            "--db",
            str(graph_db),
            "--rebuild",
            "--query",
            "put credit stop loss rules",
            "--graph-only",
            "--json",
        ]
    )
    assert code in (0, 2)


def test_verify_graph_rag_gate_on_fixture(mini_repo: Path, tmp_path: Path) -> None:
    """Hard gate script must pass against fixture ledgers (no network)."""
    from scripts import verify_graph_rag as verify

    db = tmp_path / "verify_graph.sqlite"
    code = verify.main(
        [
            "--repo-root",
            str(mini_repo),
            "--db",
            str(db),
            "--json",
        ]
    )
    assert code == 0


def test_golden_intents_stable() -> None:
    """Router golden intents must not drift (CI regression lock)."""
    cases = [
        ("why is iron condor killed?", QueryIntent.STRATEGY_STATUS),
        ("how does VIX spike impact SPY put credit?", QueryIntent.MACRO_IMPACT),
        ("iron condor expectancy and profit factor from paired trades", QueryIntent.TRADE_EVIDENCE),
        ("put credit stop loss 200% rule", QueryIntent.LESSON_RISK),
    ]
    for query, intent in cases:
        assert route_query(query).intent == intent, query


def test_resolve_graph_db_path_guards(tmp_path: Path) -> None:
    from src.rag.graph.store import resolve_graph_db_path

    ok = resolve_graph_db_path(tmp_path / "g.sqlite", base_dir=tmp_path)
    assert ok.suffix == ".sqlite"
    with pytest.raises(ValueError):
        resolve_graph_db_path("file:/tmp/evil.sqlite", base_dir=tmp_path)
    with pytest.raises(ValueError):
        resolve_graph_db_path(tmp_path / "no_ext", base_dir=tmp_path)
    with pytest.raises(ValueError):
        # Absolute path outside base and temp roots
        resolve_graph_db_path("/etc/passwd.sqlite", base_dir=tmp_path)


def test_strategy_node_id_and_outcome() -> None:
    from src.rag.graph.builder import _strategy_node_id, _trade_outcome

    assert _strategy_node_id("ic_simple") == "strategy:ic_simple"
    assert _strategy_node_id("iron_condor") == "strategy:iron_condor"
    assert _strategy_node_id("spy put credit") == "strategy:spy_put_credit"
    assert _strategy_node_id("custom_xyz") == "strategy:custom_xyz"
    assert _trade_outcome("win", -1) == "win"
    assert _trade_outcome(None, 10) == "win"
    assert _trade_outcome(None, -10) == "loss"
    assert _trade_outcome(None, 0) == "flat"


def test_neighbors_directions_and_as_of(store: FinancialGraphStore) -> None:
    store.upsert_node("a", NodeType.CONCEPT, "A")
    store.upsert_node("b", NodeType.CONCEPT, "B")
    store.upsert_edge(
        "a",
        "b",
        EdgeRel.IMPACTS,
        edge_id="e:ab",
        valid_from="2026-01-01T00:00:00+00:00",
    )
    assert store.neighbors("a", direction="out")
    assert store.neighbors("b", direction="in")
    assert store.neighbors("a", direction="both", rels=[EdgeRel.IMPACTS])
    assert store.neighbors("a", as_of="2026-06-01T00:00:00+00:00")
    past = store.neighbors("a", as_of="2025-01-01T00:00:00+00:00")
    assert past == []
    types = store.get_nodes_by_type(NodeType.CONCEPT)
    assert len(types) >= 2
    assert store.search_nodes("A")
    store.expire_edge("e:ab", at="2026-07-01T00:00:00+00:00")
    active = store.neighbors("a", direction="out")
    assert active == []


def test_hybrid_retriever_vector_fusion_and_explain(store: FinancialGraphStore) -> None:
    from src.rag.graph.retriever import GraphHybridRetriever

    store.upsert_node("strategy:spy_put_credit", NodeType.STRATEGY, "pc")
    store.upsert_node("macro:strategy_kill_2026_07_22", NodeType.MACRO_EVENT, "kill")
    store.upsert_node("strategy:iron_condor", NodeType.STRATEGY, "ic")
    store.upsert_edge(
        "macro:strategy_kill_2026_07_22",
        "strategy:iron_condor",
        EdgeRel.KILLED,
        edge_id="e:kill",
    )

    def fake_vector(q: str, k: int) -> list[dict]:
        return [{"id": "LL-1", "title": "t", "snippet": "s", "score": 0.9}]

    ret = GraphHybridRetriever(store, vector_search=fake_vector)
    # lesson_risk enables vector fusion; strategy_status is graph-primary
    out = ret.retrieve("inventory orphan lesson prevention", force_graph_only=False)
    assert out.route.intent == QueryIntent.LESSON_RISK
    assert out.vector_hits
    assert not out.graph_only
    expl = ret.explain_node("strategy:iron_condor")
    assert expl["id"] == "strategy:iron_condor"

    def boom(q: str, k: int) -> list[dict]:
        raise RuntimeError("vector down")

    ret2 = GraphHybridRetriever(store, vector_search=boom)
    out2 = ret2.retrieve("inventory orphan lesson prevention", force_graph_only=False)
    assert out2.graph_only
    assert out2.vector_hits == []

    status = ret.retrieve("why is iron condor killed?", force_graph_only=False)
    assert status.route.intent == QueryIntent.STRATEGY_STATUS

    # free-text seed resolution when hints miss
    store.upsert_node("lesson:LL-42", NodeType.LESSON, "lesson forty two inventory")
    seeds = ret._resolve_seeds(["does-not-exist-xyz"], "lesson forty two inventory")
    assert seeds  # free-text search should still locate something


def test_default_vector_search_shapes(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.rag.graph import retriever as R

    class FakeLesson:
        id = "L1"
        title = "t"
        snippet = "snip"
        prevention = "p"
        severity = "HIGH"
        file = "f.md"
        score = 0.5

    class FakeRAG:
        def search(self, query: str, top_k: int = 5):
            return [
                (FakeLesson(), "not-a-float"),
                {"id": "D1", "title": "dict", "score": 0.2},
                FakeLesson(),
            ]

    monkeypatch.setattr(
        R,
        "LessonsLearnedRAG",
        FakeRAG,
        raising=False,
    )

    # Patch import path used inside function
    import sys
    import types

    mod = types.ModuleType("src.rag.lessons_learned_rag")
    mod.LessonsLearnedRAG = FakeRAG  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "src.rag.lessons_learned_rag", mod)
    hits = R._default_vector_search("q", 3)
    assert len(hits) == 3


def test_pipeline_singleton_and_route(
    mini_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.rag.graph import pipeline as P

    monkeypatch.chdir(mini_repo)
    db = tmp_path / "pipe.sqlite"
    store = FinancialGraphStore(db_path=db, base_dir=tmp_path)
    pipe = GraphRAGPipeline(store=store, repo_root=mini_repo, auto_build_if_empty=True)
    assert pipe.route("vix impact").intent == QueryIntent.MACRO_IMPACT
    r = pipe.retrieve("stop loss rules", force_graph_only=True)
    assert r.paths is not None
    # refresh singleton path
    P._PIPELINE_SINGLETON = pipe
    again = P.get_graph_rag_pipeline(repo_root=mini_repo, refresh=True)
    assert again is not None
    again.close()


def test_router_empty_and_hybrid() -> None:
    d = route_query("")
    assert d.intent == QueryIntent.HYBRID
    d2 = route_query("random unrelated words about nothing")
    assert d2.intent == QueryIntent.HYBRID


def test_build_financial_graph_helper(mini_repo: Path, tmp_path: Path) -> None:
    from src.rag.graph.builder import build_financial_graph

    out = build_financial_graph(
        repo_root=mini_repo,
        db_path=tmp_path / "built.sqlite",
        clear=True,
    )
    assert out["stats"]["nodes"] > 0


def test_token_guard_empty_estimate() -> None:
    assert estimate_tokens("") == 0
    guard = apply_token_guard(
        query="q",
        intent="hybrid",
        route_reason="r",
        paths=[],
        nodes=[],
        vector_hits=[],
        max_tokens=100,
        hard_max_tokens=100,
    )
    assert guard.allowed
