#!/usr/bin/env python3
"""CLI for financial Graph RAG (build / query / stats).

Examples:
  python scripts/graph_rag_query.py --rebuild
  python scripts/graph_rag_query.py --stats
  python scripts/graph_rag_query.py --query "why is iron condor killed?"
  python scripts/graph_rag_query.py --query "put credit stop loss rules" --graph-only
  python scripts/graph_rag_query.py --query "vix impact on SPY put credit" --json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Ensure repo root on path when invoked as a script
_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from src.rag.graph.pipeline import GraphRAGPipeline  # noqa: E402
from src.rag.graph.store import FinancialGraphStore  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Financial Graph RAG operator CLI")
    parser.add_argument("--repo-root", type=Path, default=_REPO, help="Repository root")
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Graph SQLite path (default: <repo>/data/rag/financial_graph.sqlite)",
    )
    parser.add_argument("--rebuild", action="store_true", help="Full rebuild from ledgers")
    parser.add_argument("--stats", action="store_true", help="Print graph statistics")
    parser.add_argument("--query", type=str, default=None, help="Natural language query")
    parser.add_argument("--graph-only", action="store_true", help="Skip vector fusion")
    parser.add_argument("--max-tokens", type=int, default=1800, help="Soft context budget")
    parser.add_argument("--hard-max-tokens", type=int, default=3200, help="Hard halt budget")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    parser.add_argument("--explain", type=str, default=None, help="Explain a node id")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    db_path = args.db or (repo_root / "data/rag/financial_graph.sqlite")
    store = FinancialGraphStore(db_path=db_path)
    pipeline = GraphRAGPipeline(
        store=store,
        repo_root=repo_root,
        auto_build_if_empty=not args.stats or args.rebuild or bool(args.query),
        max_tokens=args.max_tokens,
        hard_max_tokens=args.hard_max_tokens,
    )

    exit_code = 0
    payload: dict = {}

    if args.rebuild:
        t0 = time.perf_counter()
        result = pipeline.rebuild(clear=True)
        result["rebuild_latency_ms"] = (time.perf_counter() - t0) * 1000.0
        payload["rebuild"] = result
        if not args.json:
            stats = result.get("stats") or {}
            print(
                f"Rebuilt graph: nodes={stats.get('nodes')} edges={stats.get('edges')} "
                f"active_edges={stats.get('active_edges')} "
                f"latency_ms={result['rebuild_latency_ms']:.1f}"
            )
            print(f"  db={stats.get('db_path')}")
            print(f"  by_type={stats.get('nodes_by_type')}")

    if args.stats or (not args.query and not args.rebuild and not args.explain):
        stats = pipeline.stats()
        payload["stats"] = stats
        if not args.json:
            print(json.dumps(stats, indent=2))

    if args.explain:
        expl = pipeline.retriever.explain_node(args.explain)
        payload["explain"] = expl
        if not args.json:
            print(json.dumps(expl, indent=2))

    if args.query:
        result = pipeline.query(
            args.query,
            max_tokens=args.max_tokens,
            hard_max_tokens=args.hard_max_tokens,
            force_graph_only=args.graph_only,
        )
        payload["query_result"] = result.to_dict()
        if not result.allowed:
            exit_code = 2
        if args.json:
            pass  # printed below
        else:
            print(f"intent={result.route.get('intent')} latency_ms={result.latency_ms:.1f}")
            print(f"seeds={result.retrieval.get('seeds')}")
            print(
                f"token_guard allowed={result.allowed} "
                f"tokens={result.token_guard.get('estimated_tokens')}/"
                f"{result.token_guard.get('max_tokens')}"
            )
            if result.warnings:
                print(f"warnings={result.warnings}")
            print("--- context ---")
            print(result.context)

    if args.json:
        print(json.dumps(payload, indent=2, default=str))

    pipeline.close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
