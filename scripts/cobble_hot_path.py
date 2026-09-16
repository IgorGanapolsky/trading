#!/usr/bin/env python3
"""CobbleDB FORMAT steal: durable lessons vs batched hot query path.

Source: https://www.perplexity.ai/hub/blog/cobbledb

Pillar analog  = rag_knowledge markdown (durable document state)
Lorry analog   = batch export of prepared records (this script's export)
Cobble analog  = JSONL hot store; query is batched get-by-key, not a markdown glob

Do not clone CobbleDB, RocksDB, YTsaurus, DynamoDB, or Pillar/Lorry.
Do not claim 5x latency or 20% DynamoDB savings.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DURABLE = ROOT / "rag_knowledge" / "lessons_learned"
DEFAULT_HOT = ROOT / "data" / "runtime" / "cobble_hot_lessons.jsonl"
SOURCE = "https://www.perplexity.ai/hub/blog/cobbledb"
EXCERPT_CHARS = 400


def _lesson_id(path: Path, text: str) -> str:
    m = re.search(r"^#\s+(\S+)", text, re.M)
    if m:
        return m.group(1).strip()
    return path.stem


def _title(text: str, fallback: str) -> str:
    m = re.search(r"^#\s+(.+)$", text, re.M)
    return (m.group(1).strip() if m else fallback)[:200]


def _severity(text: str) -> str:
    m = re.search(r"Severity[:\*]*\s*[:\*]*\s*([A-Z]+)", text, re.I)
    return (m.group(1).upper() if m else "LOW")[:16]


def prepare_record(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    excerpt = " ".join(text.split())[:EXCERPT_CHARS]
    return {
        "id": _lesson_id(path, text),
        "title": _title(text, path.stem),
        "severity": _severity(text),
        "path": str(path),
        "excerpt": excerpt,
        "mtime_ns": path.stat().st_mtime_ns,
        "bytes": path.stat().st_size,
    }


def export_hot(*, durable: Path, hot: Path) -> dict[str, Any]:
    """Lorry: batch durable markdown into prepared hot records."""
    files = sorted(p for p in durable.glob("*.md") if p.is_file())
    records = [prepare_record(p) for p in files]
    hot.parent.mkdir(parents=True, exist_ok=True)
    tmp = hot.with_suffix(hot.suffix + ".tmp")
    tmp.write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in records),
        encoding="utf-8",
    )
    tmp.replace(hot)
    return {
        "ok": True,
        "exported": len(records),
        "durable": str(durable),
        "hot": str(hot),
        "source": SOURCE,
    }


def load_hot(hot: Path) -> list[dict[str, Any]]:
    if not hot.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in hot.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def multiget(hot: Path, keys: list[str]) -> dict[str, Any]:
    """Cobble read path: batch get prepared records by id. No markdown glob."""
    by_id = {str(r.get("id")): r for r in load_hot(hot)}
    hits = []
    misses = []
    for key in keys:
        rec = by_id.get(key)
        if rec is None:
            misses.append(key)
        else:
            hits.append(rec)
    return {
        "ok": True,
        "n_requested": len(keys),
        "n_hits": len(hits),
        "n_misses": len(misses),
        "hits": hits,
        "misses": misses,
        "read_path": "hot_jsonl",
        "durable_globbed": False,
        "source": SOURCE,
    }


def query_hot(hot: Path, query: str, *, limit: int = 5) -> dict[str, Any]:
    """Keyword score over prepared excerpts only (query-time, not ingest)."""
    tokens = [t.lower() for t in re.findall(r"[a-z0-9_]+", query.lower()) if len(t) > 1]
    scored: list[tuple[int, dict[str, Any]]] = []
    for rec in load_hot(hot):
        blob = f"{rec.get('id', '')} {rec.get('title', '')} {rec.get('excerpt', '')}".lower()
        score = sum(blob.count(t) for t in tokens) if tokens else 0
        if score > 0:
            scored.append((score, rec))
    scored.sort(key=lambda x: (-x[0], str(x[1].get("id"))))
    hits = [{"score": s, **r} for s, r in scored[: max(1, limit)]]
    return {
        "ok": True,
        "query": query,
        "count": len(hits),
        "results": hits,
        "read_path": "hot_jsonl",
        "durable_globbed": False,
        "source": SOURCE,
    }


def status(*, durable: Path, hot: Path) -> dict[str, Any]:
    n_durable = len(list(durable.glob("*.md"))) if durable.exists() else 0
    n_hot = len(load_hot(hot))
    return {
        "ok": n_hot == n_durable and n_durable > 0,
        "n_durable": n_durable,
        "n_hot": n_hot,
        "stale": n_hot != n_durable,
        "hot_exists": hot.exists(),
        "split": {
            "pillar_durable": str(durable),
            "lorry_export": "cobble_hot_path.py export",
            "cobble_hot": str(hot),
        },
        "refuses": [
            "do_not_clone_cobbledb",
            "do_not_claim_5x_latency",
            "do_not_claim_dynamodb_20pct_savings",
            "query_must_not_glob_durable_markdown",
        ],
        "source": SOURCE,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--durable", type=Path, default=DEFAULT_DURABLE)
    p.add_argument("--hot", type=Path, default=DEFAULT_HOT)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("export", help="batch durable markdown into hot JSONL")
    q = sub.add_parser("query", help="keyword query over hot records only")
    q.add_argument("text")
    q.add_argument("--limit", type=int, default=5)
    g = sub.add_parser("get", help="batched MultiGet by lesson id")
    g.add_argument("--keys", required=True, help="comma-separated ids")
    sub.add_parser("status", help="durable vs hot counts")
    args = p.parse_args(argv)
    if args.cmd == "export":
        json.dump(export_hot(durable=args.durable, hot=args.hot), sys.stdout, indent=2)
    elif args.cmd == "query":
        json.dump(
            query_hot(args.hot, args.text, limit=args.limit),
            sys.stdout,
            indent=2,
        )
    elif args.cmd == "get":
        keys = [k.strip() for k in args.keys.split(",") if k.strip()]
        json.dump(multiget(args.hot, keys), sys.stdout, indent=2)
    else:
        json.dump(status(durable=args.durable, hot=args.hot), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
