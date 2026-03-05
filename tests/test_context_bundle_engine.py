from __future__ import annotations

import json
from pathlib import Path

from src.memory.context_bundle_engine import ContextBundleEngine


def _seed_project_tree(project: Path) -> None:
    lessons_dir = project / "rag_knowledge" / "lessons_learned"
    lessons_dir.mkdir(parents=True)
    (lessons_dir / "ll_001.md").write_text(
        "# Iron Condor Loss Mitigation\n\n**Severity**: HIGH\n\nUse tighter risk guardrails when VIX spikes.",
        encoding="utf-8",
    )

    rag_dir = project / "data" / "rag"
    rag_dir.mkdir(parents=True)
    (rag_dir / "lessons_query.json").write_text(
        json.dumps(
            [
                {
                    "id": "rq-1",
                    "title": "Thompson feedback loop",
                    "content": "Thumbs down should decrease confidence and trigger rollback patterns.",
                    "tags": ["rlhf", "feedback"],
                    "timestamp": "2026-02-19T15:00:00+00:00",
                }
            ]
        ),
        encoding="utf-8",
    )

    feedback_dir = project / ".claude" / "memory" / "feedback"
    feedback_dir.mkdir(parents=True)
    (feedback_dir / "thompson_feedback_log.jsonl").write_text(
        json.dumps(
            {
                "event_key": "evt-1",
                "timestamp": "2026-02-19T15:01:00+00:00",
                "feedback_type": "negative",
                "signal": "thumbs_down",
                "context_preview": "User said answer was too shallow on options risk controls",
                "bandit": {"delta_mean": -0.02},
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_build_index_and_super_retrieve(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _seed_project_tree(project)

    engine = ContextBundleEngine(project_root=project)
    built = engine.build_index(top_per_source=100)

    assert built["doc_count"] >= 3
    assert "lesson" in built["sources"]
    assert (project / "data" / "context_engine" / "context_index.json").exists()

    result = engine.super_retrieve("thumbs down options risk", top_k=5)
    assert result["meta"]["returned"] >= 1
    top = result["results"][0]
    assert top["score"] > 0
    assert "thumbs" in result["context"].lower() or "risk" in result["context"].lower()


def test_super_retrieve_builds_index_if_missing(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _seed_project_tree(project)

    engine = ContextBundleEngine(project_root=project)
    out = engine.super_retrieve("iron condor guardrails", top_k=3)

    assert out["meta"]["index_doc_count"] >= 1
    assert (project / "data" / "context_engine" / "context_index.json").exists()


def test_build_index_skips_untracked_sources_when_git_tracked_paths_present(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _seed_project_tree(project)

    engine = ContextBundleEngine(project_root=project)
    engine._git_tracked_paths = {"data/rag/lessons_query.json"}
    built = engine.build_index(top_per_source=100)

    assert built["doc_count"] == 1
    assert built["sources"] == {"rag_query": 1}


def test_rag_query_loader_accepts_event_timestamp_schema(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    lessons_dir = project / "rag_knowledge" / "lessons_learned"
    lessons_dir.mkdir(parents=True)
    (lessons_dir / "ll_001.md").write_text("# title", encoding="utf-8")

    rag_dir = project / "data" / "rag"
    rag_dir.mkdir(parents=True)
    (rag_dir / "lessons_query.json").write_text(
        json.dumps(
            [
                {
                    "id": "rq-evt",
                    "title": "Schema compatibility",
                    "content": "Uses event timestamp field.",
                    "tags": ["rag"],
                    "event_timestamp_utc": "2026-03-05T17:00:00Z",
                }
            ]
        ),
        encoding="utf-8",
    )

    engine = ContextBundleEngine(project_root=project)
    engine._git_tracked_paths = {"data/rag/lessons_query.json", "rag_knowledge/lessons_learned/ll_001.md"}
    monkeypatch.delenv("RAG_WRITE_PROFILE", raising=False)
    built = engine.build_index(top_per_source=50)

    index_path = project / "data" / "context_engine" / "context_index.json"
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    rag_doc = next(doc for doc in payload["docs"] if doc["source"] == "rag_query")

    assert built["doc_count"] >= 1
    assert rag_doc["timestamp"] == "2026-03-05T17:00:00Z"
