#!/usr/bin/env python3
"""Operator CLI for official SuperMemory (v3 documents + v4 hybrid search).

This is not the lookalike Client/memories.create dump. Local ledgers remain
edge truth. Live writes require SUPERMEMORY_API_KEY and --live.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.rag.supermemory.client import (  # noqa: E402
    SuperMemoryClient,
    SuperMemoryError,
    build_search_body,
)
from src.rag.supermemory.contract import (  # noqa: E402
    API_KEY_ENV,
    DEFAULT_CONTAINER_TAG,
    DEFAULT_SEARCH_MODE,
    OFFICIAL_CONSOLE,
    OFFICIAL_DOCS,
    route_query,
)
from src.rag.supermemory.fuse import fuse_local_with_supermemory  # noqa: E402
from src.rag.supermemory.ingest import ingest_lessons  # noqa: E402


def _local_lesson_hits(repo: Path, query: str, limit: int = 8) -> list[dict[str, Any]]:
    lessons_dir = repo / "rag_knowledge" / "lessons_learned"
    if not lessons_dir.is_dir():
        return []
    needles = [token.lower() for token in query.split() if len(token) > 2]
    hits: list[dict[str, Any]] = []
    for path in sorted(lessons_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        blob = f"{path.name}\n{text[:2000]}".lower()
        if needles and not any(token in blob for token in needles):
            continue
        hits.append(
            {
                "id": path.stem,
                "title": path.name,
                "snippet": text[:280],
                "source": "local_rag",
            }
        )
        if len(hits) >= limit:
            break
    return hits


def cmd_status(client: SuperMemoryClient) -> dict[str, Any]:
    payload = client.status()
    payload.update(
        {
            "official_console": OFFICIAL_CONSOLE,
            "official_docs": OFFICIAL_DOCS,
            "memory_graph_ui_is_not_retrieval": True,
            "arxiv_dump_forbidden": True,
            "key_env": API_KEY_ENV,
        }
    )
    return payload


def cmd_search(client: SuperMemoryClient, repo: Path, query: str, limit: int) -> dict[str, Any]:
    local = _local_lesson_hits(repo, query, limit=limit)
    remote = None
    remote_error = None
    if client.configured and route_query(query) != "local_ledger":
        try:
            remote = client.search(
                build_search_body(
                    query,
                    container_tag=client.container_tag,
                    search_mode=DEFAULT_SEARCH_MODE,
                    limit=limit,
                )
            )
        except SuperMemoryError as exc:
            remote_error = str(exc)
    fused = fuse_local_with_supermemory(query, local, remote)
    if remote_error:
        fused["supermemory_error"] = remote_error
    return fused


def cmd_ingest(
    client: SuperMemoryClient, repo: Path, live: bool, max_lessons: int
) -> dict[str, Any]:
    return ingest_lessons(client, repo, dry_run=not live, max_lessons=max_lessons)


def cmd_profile(client: SuperMemoryClient) -> dict[str, Any]:
    if not client.configured:
        return {
            "configured": False,
            "container_tag": client.container_tag,
            "profile": None,
        }
    return client.profile()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Official SuperMemory trading adapter")
    parser.add_argument(
        "--container-tag",
        default=DEFAULT_CONTAINER_TAG,
        help=f"singular containerTag (default {DEFAULT_CONTAINER_TAG})",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="show adapter contract and key presence")
    search = sub.add_parser("search", help="fuse local lessons with v4 hybrid search")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=8)
    ingest = sub.add_parser("ingest-lessons", help="bounded curated lesson ingest")
    ingest.add_argument("--live", action="store_true", help="POST /v3/documents (default dry-run)")
    ingest.add_argument("--max-lessons", type=int, default=12)
    sub.add_parser("profile", help="POST /v4/profile for trading-lab")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    client = SuperMemoryClient(container_tag=args.container_tag)
    if args.command == "status":
        payload: Any = cmd_status(client)
    elif args.command == "search":
        payload = cmd_search(client, _REPO_ROOT, args.query, args.limit)
    elif args.command == "ingest-lessons":
        payload = cmd_ingest(client, _REPO_ROOT, args.live, args.max_lessons)
    else:
        payload = cmd_profile(client)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
