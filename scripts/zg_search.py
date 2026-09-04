#!/usr/bin/env python3
"""CLI for zg-style local-first search (hybrid / fts / vector / rg).

Inspired by Qwen zvec-grep (zg): one interface, four routes, compact evidence.
Does not vendor @zvec/zvec-grep — maps the process onto trading RAG rails.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.rag.zg_local_search import SearchRoute, ZgLocalSearch  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Local-first search: hybrid (default) | fts | vector | rg"
    )
    parser.add_argument("query", nargs="?", default="", help="Search query")
    parser.add_argument(
        "--route",
        choices=[r.value for r in SearchRoute],
        default=SearchRoute.HYBRID.value,
        help="Retrieval route (default: hybrid = FTS+vector RRF, optional rg)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Max hits (must be >= 0)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON evidence hits instead of compact lines",
    )
    fuse_group = parser.add_mutually_exclusive_group()
    fuse_group.add_argument(
        "--fuse-rg",
        action="store_true",
        help="Force ripgrep into hybrid fusion (default: only for symbol-like queries)",
    )
    fuse_group.add_argument(
        "--no-fuse-rg",
        action="store_true",
        help="Never fuse ripgrep into hybrid",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Workspace root (default: repo root)",
    )
    parser.add_argument(
        "--check-ready",
        action="store_true",
        help="Exit 0 if engine imports; print routes (zg status analog)",
    )
    args = parser.parse_args(argv)

    if args.check_ready:
        engine = ZgLocalSearch(root=args.root)
        payload = {
            "ready": True,
            "routes": [r.value for r in SearchRoute],
            "root": str(engine.root),
            "rg": engine._rg_bin,  # noqa: SLF001
        }
        print(json.dumps(payload, indent=2))
        return 0

    if not args.query.strip():
        parser.error("query is required unless --check-ready")
    if args.limit < 0:
        parser.error("--limit must be >= 0")

    fuse_rg: bool | None = None
    if args.fuse_rg:
        fuse_rg = True
    elif args.no_fuse_rg:
        fuse_rg = False

    engine = ZgLocalSearch(root=args.root)
    hits = engine.search(
        args.query,
        route=args.route,
        limit=args.limit,
        fuse_rg=fuse_rg,
    )

    if args.json:
        print(json.dumps([h.to_dict() for h in hits], indent=2))
    else:
        print(engine.format_compact(hits))
    return 0 if hits or args.route == SearchRoute.VECTOR.value else (0 if hits else 0)


if __name__ == "__main__":
    raise SystemExit(main())
