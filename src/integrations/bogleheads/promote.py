"""Promote high-relevance Bogleheads threads into rag_knowledge/bogleheads/."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_RAG_DIR = Path("rag_knowledge/bogleheads")
DEFAULT_RESEARCH_PATH = Path("data/research/bogleheads_latest.json")
DEFAULT_INDEX_PATH = Path("data/research/bogleheads_rag_index.json")


def _safe_stem(thread_id: str, title: str) -> str:
    base = (thread_id or "bh_unknown").lower()
    base = re.sub(r"[^a-z0-9_\-]+", "_", base)[:48]
    slug = re.sub(r"[^a-z0-9]+", "_", (title or "")[:40].lower()).strip("_")
    return f"{base}_{slug}"[:80] if slug else base


def thread_to_markdown(thread: dict[str, Any]) -> str:
    title = (thread.get("title") or "Bogleheads thread").rstrip("?.!")
    link = thread.get("link") or ""
    author = thread.get("author") or "unknown"
    updated = thread.get("updated") or ""
    snippet = thread.get("snippet") or ""
    score = float(thread.get("relevance_score") or 0.0)
    tid = thread.get("id") or ""
    fetched = datetime.now(UTC).strftime("%Y-%m-%d")

    return f"""# Bogleheads: {title}

**ID**: {tid}
**Date**: {fetched}
**Source**: Bogleheads forum (RSS)
**Author**: {author}
**Updated**: {updated}
**Relevance**: {score:.2f}
**URL**: <{link}>
**Severity**: LOW
**Category**: external-research

## Summary

Forum discussion ingested for long-term investing / tax / allocation context.
This is **not** a trade signal for spy_put_credit.

## Snippet

{snippet}

## Operator notes

- Use for FI / tax / three-fund *context* only.
- Do not promote passive-index dogma into put-credit entry logic.
- Verify freshness before citing in CEO answers.

## Tags

`bogleheads`, `external-research`, `passive-investing`, `ingestion`
"""


def promote_threads(
    threads: list[dict[str, Any]],
    *,
    rag_dir: Path | None = None,
    min_relevance: float = 0.25,
    max_promote: int = 12,
) -> dict[str, Any]:
    """Write markdown docs for relevant threads. Idempotent by file stem."""
    out_dir = Path(rag_dir or DEFAULT_RAG_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    candidates = [
        t
        for t in threads
        if float(t.get("relevance_score") or 0.0) >= min_relevance and t.get("title")
    ]
    candidates = candidates[:max_promote]

    written: list[str] = []
    skipped: list[str] = []
    for thread in candidates:
        stem = _safe_stem(str(thread.get("id") or ""), str(thread.get("title") or ""))
        path = out_dir / f"{stem}.md"
        if path.exists():
            skipped.append(str(path))
            continue
        path.write_text(thread_to_markdown(thread), encoding="utf-8")
        written.append(str(path))
        logger.info("Promoted Bogleheads thread → %s", path)

    index = {
        "updated_at": datetime.now(UTC).isoformat(),
        "written": written,
        "skipped_existing": skipped,
        "candidate_count": len(candidates),
        "min_relevance": min_relevance,
    }
    DEFAULT_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_INDEX_PATH.write_text(json.dumps(index, indent=2), encoding="utf-8")
    return index


def save_research_snapshot(
    threads: list[dict[str, Any]],
    *,
    path: Path | None = None,
) -> Path:
    out = Path(path or DEFAULT_RESEARCH_PATH)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": datetime.now(UTC).isoformat(),
        "total_threads": len(threads),
        "threads": threads,
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out
