"""Official Graphify-Labs/graphify contract: graph.json, not SQLite/HTML."""

from __future__ import annotations

import json
from pathlib import Path

from src.rag.graphify.cli import resolve_graphify_bin
from src.rag.graphify.contract import (
    CONFIDENCE_AMBIGUOUS,
    CONFIDENCE_EXTRACTED,
    CONFIDENCE_INFERRED,
    FORBIDDEN_INSTALL_SNIPPETS,
    OFFICIAL_PYPI_PACKAGE,
    is_html_visualization,
    validate_graphify_payload,
)
from src.rag.graphify.fuse import fuse_hits_with_graph
from src.rag.graphify.graph import load_code_graph

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests/fixtures/graphify/graph.json"
OPS = REPO / "scripts/graphify_ops.py"
ADAPTER_DIR = REPO / "src/rag/graphify"


def test_fixture_matches_official_schema() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert validate_graphify_payload(payload) == []
    graph = load_code_graph(FIXTURE)
    counts = graph.confidence_counts()
    assert counts[CONFIDENCE_EXTRACTED] >= 1
    assert counts[CONFIDENCE_INFERRED] >= 1
    assert counts[CONFIDENCE_AMBIGUOUS] >= 1


def test_path_and_explain_preserve_extracted_vs_inferred() -> None:
    graph = load_code_graph(FIXTURE)
    trail = graph.shortest_path("plan_put_credit", "TradeGateway")
    assert trail is not None
    assert trail[0]["node"]["label"] == "plan_put_credit()"
    assert trail[-1]["node"]["label"] == "TradeGateway"
    via_conf = {hop["via"]["confidence"] for hop in trail if hop["via"]}
    assert CONFIDENCE_EXTRACTED in via_conf or CONFIDENCE_INFERRED in via_conf
    explained = graph.explain("TradeGateway")
    assert explained is not None
    confs = {item["edge"]["confidence"] for item in explained["connections"]}
    assert CONFIDENCE_EXTRACTED in confs
    assert explained["validity_window"] is None


def test_query_returns_calls_edge() -> None:
    result = load_code_graph(FIXTURE).query("what calls TradeGateway")
    labels = {node["label"] for node in result["nodes"]}
    assert "TradeGateway" in labels
    assert "plan_put_credit()" in labels
    relations = {(edge["relation"], edge["confidence"]) for edge in result["edges"]}
    assert ("calls", CONFIDENCE_EXTRACTED) in relations


def test_fuse_always_traverses_and_skips_html() -> None:
    graph = load_code_graph(FIXTURE)
    hits = [
        {"id": "strategy.py", "title": "put credit", "file": "strategy.py"},
        {"id": "viz", "title": "pretty graph", "file": "graphify-out/graph.html"},
    ]
    fused = fuse_hits_with_graph(hits, graph, max_hops=2)
    assert fused["graph_used"] is True
    assert fused["dropped_html"] == ["graphify-out/graph.html"]
    assert fused["graph_edges"], "retrieval must traverse graph.json, not skip it"
    assert fused["validity_window"] is None
    assert any(edge["confidence"] == CONFIDENCE_EXTRACTED for edge in fused["graph_edges"])
    assert is_html_visualization("graphify-out/graph.html")
    assert not is_html_visualization("graphify-out/graph.json")


def test_ops_and_adapter_do_not_install_wrong_pip_package() -> None:
    blobs = [
        OPS.read_text(encoding="utf-8"),
        (ADAPTER_DIR / "cli.py").read_text(encoding="utf-8"),
        (ADAPTER_DIR / "__init__.py").read_text(encoding="utf-8"),
    ]
    joined = "\n".join(blobs)
    assert OFFICIAL_PYPI_PACKAGE in joined
    assert "uv tool install" in joined
    for snippet in FORBIDDEN_INSTALL_SNIPPETS:
        assert snippet not in joined
    assert "financial_graph.sqlite" not in joined
    assert "CREATE TABLE IF NOT EXISTS graphify_nodes" not in joined
    assert "gremlin" not in joined.lower()


def test_graphify_out_stays_gitignored_and_hygiene_forbidden() -> None:
    gitignore = (REPO / ".gitignore").read_text(encoding="utf-8")
    assert "graphify-out/" in gitignore
    hygiene = (REPO / "scripts/audit_repository_hygiene.py").read_text(encoding="utf-8")
    assert '"graphify-out/"' in hygiene
    ignore = (REPO / ".graphifyignore").read_text(encoding="utf-8")
    assert "rag_knowledge/arxiv/" in ignore


def test_status_reports_official_package() -> None:
    from scripts.graphify_ops import cmd_status, main

    payload = cmd_status(REPO, FIXTURE)
    assert payload["official_package"] == "graphifyy"
    assert payload["official_cli"] == "graphify"
    assert payload["html_is_not_retrieval"] is True
    assert payload["financial_graph_is_separate"] is True
    assert payload["confidence_counts"][CONFIDENCE_INFERRED] >= 1
    binary = resolve_graphify_bin(REPO)
    if binary is not None:
        assert payload["binary"]
        assert "graphify" in payload["version"].lower()
    assert main(["status", "--graph", str(FIXTURE), "--json"]) == 0
