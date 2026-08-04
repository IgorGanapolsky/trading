#!/usr/bin/env python3
"""Build and query the temporal trade knowledge graph.

    python scripts/trade_graph.py --build
    python scripts/trade_graph.py --stats
    python scripts/trade_graph.py --losses
    python scripts/trade_graph.py --policy IRON_CONDOR_STOP_LOSS_MULTIPLIER
    python scripts/trade_graph.py --context "stop loss" "iron condor" --hops 2

Read-only with respect to trading: this inspects history, it never submits an order.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.rag.graph.build import (  # noqa: E402
    JOURNAL_PATH,
    TRADES_PATH,
    build_graph,  # noqa: E402
)
from src.rag.graph.queries import (  # noqa: E402
    graph_context,
    loss_attribution,
    policy_cohorts,
    seeds_from_terms,
)
from src.rag.graph.temporal_graph import TemporalGraph  # noqa: E402


def _emit(payload: object) -> None:
    print(json.dumps(payload, indent=2, default=str))


def stale_sources(db_path: Path, sources: list[Path]) -> list[str]:
    """Return source files newer than the graph database.

    A graph built before the last trade close answers cohort questions with a ledger
    that no longer exists, and it does so confidently. Staleness has to be loud --
    a silently outdated answer is the failure mode this whole module exists to remove.
    """
    if not db_path.exists():
        return []
    built_at = db_path.stat().st_mtime
    return [str(p) for p in sources if p.exists() and p.stat().st_mtime > built_at]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="rebuild the graph from repo data")
    parser.add_argument("--stats", action="store_true", help="show node/edge counts")
    parser.add_argument("--losses", action="store_true", help="loss attribution by exit path")
    parser.add_argument("--policy", metavar="NAME", help="cohort metrics per policy value")
    parser.add_argument("--strategy", metavar="NAME", help="restrict to one strategy family")
    parser.add_argument("--context", nargs="+", metavar="TERM", help="serialize a subgraph")
    parser.add_argument("--hops", type=int, default=2)
    parser.add_argument("--budget", type=int, default=60, help="max nodes in a context subgraph")
    parser.add_argument("--as-of", metavar="ISO_TS", help="traverse the graph as it was at a time")
    parser.add_argument("--db", metavar="PATH", help="graph database path")
    parser.add_argument(
        "--rebuild-if-stale",
        action="store_true",
        help="rebuild automatically when a source ledger is newer than the graph",
    )
    args = parser.parse_args()

    if args.build:
        _emit(build_graph(args.db))
        if not (args.stats or args.losses or args.policy or args.context):
            return 0

    graph = TemporalGraph(args.db)
    try:
        if graph.stats()["nodes"] == 0:
            print("Graph is empty. Run: python scripts/trade_graph.py --build", file=sys.stderr)
            return 2

        if not args.build:
            stale = stale_sources(graph.db_path, [TRADES_PATH, JOURNAL_PATH])
            if stale:
                if args.rebuild_if_stale:
                    print(
                        f"Graph is stale ({len(stale)} newer source(s)); rebuilding.",
                        file=sys.stderr,
                    )
                    graph.close()
                    build_graph(args.db)
                    graph = TemporalGraph(args.db)
                else:
                    for path in stale:
                        print(f"STALE: {path} is newer than the graph", file=sys.stderr)
                    print(
                        "Results below predate that data. Rerun with --build or "
                        "--rebuild-if-stale.",
                        file=sys.stderr,
                    )

        if args.stats:
            _emit(graph.stats())
        if args.losses:
            _emit(loss_attribution(graph, strategy=args.strategy))
        if args.policy:
            _emit(policy_cohorts(graph, args.policy, strategy=args.strategy))
        if args.context:
            seeds = seeds_from_terms(graph, args.context)
            if not seeds:
                print(f"No graph entities matched: {args.context}", file=sys.stderr)
                return 1
            print(
                graph_context(
                    graph, seeds, hops=args.hops, node_budget=args.budget, as_of=args.as_of
                )
            )

        if not any([args.stats, args.losses, args.policy, args.context, args.build]):
            parser.print_help()
    finally:
        graph.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
