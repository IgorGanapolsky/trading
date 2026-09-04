"""Official SuperMemory contract: v3 documents, v4 hybrid search, not a lookalike."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.rag.supermemory.client import (
    SuperMemoryClient,
    SuperMemoryError,
    _assert_http_url,
    build_auth_headers,
    build_document_body,
    build_search_body,
    load_api_key,
)
from src.rag.supermemory.contract import (
    DEFAULT_CONTAINER_TAG,
    DEFAULT_INGEST_TASK_TYPE,
    DEFAULT_SEARCH_MODE,
    DOCUMENTS_PATH,
    FOREIGN_CONTAINER_TAGS,
    LOOKALIKE_SNIPPETS,
    SEARCH_PATH,
    lookalike_hits,
    route_query,
    slug_custom_id,
    validate_auth_headers,
    validate_container_tag,
    validate_v3_document_body,
    validate_v4_search_body,
)
from src.rag.supermemory.fuse import fuse_local_with_supermemory, normalize_supermemory_results
from src.rag.supermemory.ingest import is_arxiv_path, plan_ingest, select_lessons

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests/fixtures/supermemory/v4_search.json"
ADAPTER = REPO / "src/rag/supermemory"
OPS = REPO / "scripts/supermemory_ops.py"
SHIM = REPO / "scripts/integrate_supermemory.py"


def _source_blobs() -> list[str]:
    blobs = [OPS.read_text(encoding="utf-8"), SHIM.read_text(encoding="utf-8")]
    for path in ADAPTER.glob("*.py"):
        if path.name == "contract.py":
            continue
        blobs.append(path.read_text(encoding="utf-8"))
    return blobs


def test_fixture_matches_v4_search_shape() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rows = normalize_supermemory_results(payload)
    assert len(rows) == 2
    assert rows[0]["not_edge_evidence"] is True
    assert rows[0]["source"] == "supermemory"
    assert "inventory" in rows[0]["text"].lower()


def test_search_body_uses_singular_container_tag_and_hybrid() -> None:
    body = build_search_body("why is inventory unclean", container_tag=DEFAULT_CONTAINER_TAG)
    assert body["containerTag"] == "trading-lab"
    assert "containerTags" not in body
    assert body["searchMode"] == DEFAULT_SEARCH_MODE
    assert validate_v4_search_body(body) == []
    assert validate_v4_search_body({"q": "x", "containerTags": ["trading-lab"]})


def test_document_body_is_v3_superrag_with_custom_id() -> None:
    body = build_document_body(
        "Open inventory must be clean before new risk.",
        custom_id=slug_custom_id("ll_open_inventory.md"),
    )
    assert body["containerTag"] == "trading-lab"
    assert body["taskType"] == DEFAULT_INGEST_TASK_TYPE
    assert body["customId"] == "ll_open_inventory"
    assert validate_v3_document_body(body) == []
    assert validate_v3_document_body({"content": "x", "containerTags": ["trading-lab"]})


def test_auth_is_bearer_not_custom_headers() -> None:
    headers = build_auth_headers("sm_test_key")
    assert headers["Authorization"].startswith("Bearer ")
    assert validate_auth_headers(headers) == []
    assert validate_auth_headers({"x-api-key": "sm_test_key", "Authorization": "Bearer x"})


def test_foreign_secure_yolo_container_is_rejected() -> None:
    assert "secure-yolo" in FOREIGN_CONTAINER_TAGS
    errors = validate_container_tag("secure-yolo")
    assert errors
    with pytest.raises(SuperMemoryError):
        SuperMemoryClient(container_tag="secure-yolo", api_key="sm_test")


def test_route_query_keeps_edge_on_local_ledgers() -> None:
    assert route_query("what is put-credit expectancy and profit factor?") == "local_ledger"
    assert route_query("remember the operator prefers Thursday entries") == "memory"
    assert route_query("why is iron condor killed?") == "hybrid"


def test_fuse_without_key_keeps_local_hits() -> None:
    local = [{"id": "ll-1", "title": "inventory hygiene", "snippet": "audit first"}]
    fused = fuse_local_with_supermemory("why is inventory unclean?", local, None)
    assert fused["edge_source"] == "local_ledgers"
    assert fused["supermemory_authoritative_for_edge"] is False
    assert fused["supermemory_used"] is False
    assert fused["hits"]
    assert fused["hits"][0]["source"] == "local_rag"


def test_fuse_does_not_let_supermemory_own_edge_queries() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    local = [{"id": "trades", "title": "paired ledger", "snippet": "n=0"}]
    fused = fuse_local_with_supermemory(
        "what is the put-credit profit factor?",
        local,
        payload,
    )
    assert fused["route"] == "local_ledger"
    assert fused["supermemory_used"] is False
    assert all(hit.get("source") != "supermemory" for hit in fused["hits"])


def test_client_search_posts_v4_with_mock_transport() -> None:
    captured: dict[str, object] = {}

    def transport(method: str, url: str, headers: dict[str, str], body: bytes | None):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = json.loads(body.decode("utf-8")) if body else None
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        return 200, {"Content-Type": "application/json"}, json.dumps(fixture)

    client = SuperMemoryClient(api_key="sm_test", transport=transport)
    result = client.search(build_search_body("inventory hygiene"))
    assert captured["method"] == "POST"
    assert str(captured["url"]).endswith(SEARCH_PATH)
    assert captured["body"]["containerTag"] == "trading-lab"
    assert "Authorization" in captured["headers"]
    assert result["total"] == 2


def test_client_add_document_posts_v3() -> None:
    captured: dict[str, object] = {}

    def transport(method: str, url: str, headers: dict[str, str], body: bytes | None):
        captured["url"] = url
        captured["body"] = json.loads(body.decode("utf-8")) if body else None
        return 200, {}, json.dumps({"id": "doc_1", "status": "queued"})

    client = SuperMemoryClient(api_key="sm_test", transport=transport)
    result = client.add_document(build_document_body("lesson text", custom_id="ll-1"))
    assert str(captured["url"]).endswith(DOCUMENTS_PATH)
    assert captured["body"]["taskType"] == "superrag"
    assert result["status"] == "queued"


def test_transport_rejects_non_http_schemes() -> None:
    with pytest.raises(SuperMemoryError, match="non-http"):
        _assert_http_url("file:///etc/passwd")


def test_missing_key_degrades() -> None:
    assert load_api_key({}) is None
    client = SuperMemoryClient(api_key=None, transport=lambda *_args: (500, {}, "{}"))
    client.api_key = None
    assert client.configured is False
    with pytest.raises(SuperMemoryError):
        client.search(build_search_body("hello"))


def test_ingest_skips_arxiv_and_is_bounded() -> None:
    fake_arxiv = REPO / "rag_knowledge" / "arxiv" / "paper.md"
    assert is_arxiv_path(fake_arxiv, REPO) is True
    planned = plan_ingest(REPO, max_lessons=12)
    assert planned, "curated lesson ingest must select at least one local lesson"
    assert len(planned) <= 12
    for body in planned:
        assert body["containerTag"] == "trading-lab"
        assert body["customId"]
        assert "arxiv" not in str(body.get("metadata", {})).lower()
    lessons_dir = REPO / "rag_knowledge" / "lessons_learned"
    selected = select_lessons(lessons_dir, REPO, max_lessons=5)
    assert all("arxiv" not in path.as_posix() for path in selected)


def test_adapter_sources_reject_lookalike_snippets() -> None:
    for blob in _source_blobs():
        hits = lookalike_hits(blob)
        assert hits == [], hits
    # The constant list itself must still name the forbidden patterns.
    assert "from supermemory import Client" in LOOKALIKE_SNIPPETS
    assert "client.memories.create" in LOOKALIKE_SNIPPETS


def test_ops_cli_status_and_search_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts.supermemory_ops import cmd_search, cmd_status

    monkeypatch.delenv("SUPERMEMORY_API_KEY", raising=False)
    client = SuperMemoryClient(api_key=None)
    status = cmd_status(client)
    assert status["search_path"] == SEARCH_PATH
    assert status["documents_path"] == DOCUMENTS_PATH
    assert status["edge_truth"] == "local_ledgers"
    fused = cmd_search(client, REPO, "iron condor killed", 5)
    assert fused["edge_source"] == "local_ledgers"
    assert fused["supermemory_used"] is False
