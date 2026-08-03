#!/usr/bin/env python3
"""Query curated repository lessons with semantic search or keyword fallback."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="Natural-language lesson query")
    parser.add_argument("--limit", "--top-k", dest="limit", type=int, default=5)
    parser.add_argument("--severity", choices=("CRITICAL", "HIGH", "MEDIUM", "LOW"))
    parser.add_argument("--knowledge-dir", type=Path)
    parser.add_argument("--keyword-only", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args(argv)


def _result_payload(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": result.get("id", "unknown"),
        "title": result.get("title", ""),
        "severity": result.get("severity", "LOW"),
        "score": result.get("score"),
        "file": result.get("file", ""),
        "snippet": " ".join(str(result.get("snippet") or "").split()),
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.limit < 1:
        raise SystemExit("--limit must be at least 1")
    if args.keyword_only:
        os.environ["LANCEDB_RAG"] = "false"

    from src.rag.lessons_learned_rag import LessonsLearnedRAG

    rag = LessonsLearnedRAG(
        knowledge_dir=str(args.knowledge_dir) if args.knowledge_dir is not None else None
    )
    results = rag.query(args.query, top_k=args.limit, severity_filter=args.severity)
    payload = {
        "query": args.query,
        "source": rag.last_source,
        "count": len(results),
        "results": [_result_payload(item) for item in results],
    }

    if args.as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    print(f"source={payload['source']} results={payload['count']}")
    for index, item in enumerate(payload["results"], start=1):
        score = item["score"]
        score_text = f" score={score:.3f}" if isinstance(score, (float, int)) else ""
        title = f" — {item['title']}" if item["title"] else ""
        print(f"{index}. [{item['severity']}] {item['id']}{title}{score_text}")
        if item["file"]:
            print(f"   {item['file']}")
        if item["snippet"]:
            print(f"   {item['snippet'][:300]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
