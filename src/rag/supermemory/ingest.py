"""Bounded SuperMemory ingest of curated local lessons. No arXiv dump."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from src.rag.supermemory.client import SuperMemoryClient, build_document_body
from src.rag.supermemory.contract import (
    DEFAULT_CONTAINER_TAG,
    DEFAULT_INGEST_TASK_TYPE,
    slug_custom_id,
)

DEFAULT_MAX_LESSONS = 12
DEFAULT_MAX_CHARS = 12_000
ARXIV_MARKERS = ("rag_knowledge/arxiv", "/arxiv/")
DEFAULT_GLOBS = (
    "*kill*.md",
    "*inventory*.md",
    "*boundary*.md",
    "*lookalike*.md",
    "*official*.md",
    "*graphify*.md",
    "*supermemory*.md",
    "*integrity*.md",
)


def is_arxiv_path(path: Path, repo_root: Path) -> bool:
    relative = str(path.resolve()).replace("\\", "/")
    root = str(repo_root.resolve()).replace("\\", "/")
    if relative.startswith(root):
        relative = relative[len(root) :].lstrip("/")
    return any(marker in relative for marker in ARXIV_MARKERS)


def select_lessons(
    lessons_dir: Path,
    repo_root: Path,
    *,
    globs: Iterable[str] = DEFAULT_GLOBS,
    max_lessons: int = DEFAULT_MAX_LESSONS,
) -> list[Path]:
    """Pick a bounded, curated lesson set. Never the whole arXiv corpus."""
    seen: set[Path] = set()
    chosen: list[Path] = []
    if not lessons_dir.is_dir():
        return []
    for pattern in globs:
        for path in sorted(lessons_dir.glob(pattern)):
            if not path.is_file() or path in seen:
                continue
            if is_arxiv_path(path, repo_root):
                continue
            seen.add(path)
            chosen.append(path)
            if len(chosen) >= max_lessons:
                return chosen
    return chosen


def lesson_document(
    path: Path,
    repo_root: Path,
    *,
    container_tag: str = DEFAULT_CONTAINER_TAG,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")[:max_chars]
    relative = path.resolve().relative_to(repo_root.resolve()).as_posix()
    return build_document_body(
        text,
        container_tag=container_tag,
        custom_id=slug_custom_id(path.name),
        metadata={
            "source": "rag_knowledge",
            "path": relative,
            "kind": "lesson",
        },
        task_type=DEFAULT_INGEST_TASK_TYPE,
    )


def plan_ingest(
    repo_root: Path,
    *,
    lessons_dir: Path | None = None,
    container_tag: str = DEFAULT_CONTAINER_TAG,
    max_lessons: int = DEFAULT_MAX_LESSONS,
) -> list[dict[str, Any]]:
    root = repo_root.resolve()
    directory = lessons_dir or (root / "rag_knowledge" / "lessons_learned")
    bodies = []
    for path in select_lessons(directory, root, max_lessons=max_lessons):
        bodies.append(lesson_document(path, root, container_tag=container_tag))
    return bodies


def ingest_lessons(
    client: SuperMemoryClient,
    repo_root: Path,
    *,
    dry_run: bool = True,
    max_lessons: int = DEFAULT_MAX_LESSONS,
) -> dict[str, Any]:
    planned = plan_ingest(repo_root, container_tag=client.container_tag, max_lessons=max_lessons)
    if dry_run:
        return {
            "dry_run": True,
            "count": len(planned),
            "custom_ids": [item.get("customId") for item in planned],
            "task_type": DEFAULT_INGEST_TASK_TYPE,
        }
    results = []
    for body in planned:
        results.append(client.add_document(body))
    return {"dry_run": False, "count": len(results), "results": results}
