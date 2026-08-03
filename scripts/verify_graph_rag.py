#!/usr/bin/env python3
"""Hard gate: rebuild financial Graph RAG and prove golden multi-hop queries.

Exit codes:
  0 — rebuild ok, all golden assertions pass, latency under budget
  1 — rebuild/query/assertion failure
  2 — TokenGuard hard-halt on a golden query

Usage:
  python scripts/verify_graph_rag.py
  python scripts/verify_graph_rag.py --repo-root . --json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from src.rag.graph.pipeline import GraphRAGPipeline  # noqa: E402
from src.rag.graph.store import FinancialGraphStore  # noqa: E402

# Golden queries: deterministic assertions on intent + required path/node tokens.
GOLDEN: list[dict[str, Any]] = [
    {
        "id": "kill_switch_succession",
        "query": "why is iron condor killed?",
        "intent": "strategy_status",
        "must_contain_any": [
            "KILLED",
            "strategy:iron_condor",
            "macro:strategy_kill",
            "spy_put_credit",
        ],
        "max_latency_ms": 500.0,
    },
    {
        "id": "live_blocked_gate",
        "query": "why is live capital blocked for put credit?",
        "intent": "strategy_status",
        "must_contain_any": [
            "live_gate",
            "live_blocked",
            "rule:live_gate_n30",
            "BLOCKS",
            "paper",
        ],
        "max_latency_ms": 500.0,
    },
    {
        "id": "macro_vix",
        "query": "how does VIX spike impact SPY put credit?",
        "intent": "macro_impact",
        "must_contain_any": [
            "vix",
            "concept:vix_spike",
            "IMPACTS",
            "strategy:spy_put_credit",
            "ticker:SPY",
        ],
        "max_latency_ms": 500.0,
    },
    {
        "id": "stop_loss_rule",
        "query": "put credit stop loss 200% rule",
        "intent": "lesson_risk",
        "must_contain_any": [
            "stop_loss",
            "200",
            "rule:stop_loss_200pct",
            "GOVERNS",
            "spy_put_credit",
        ],
        "max_latency_ms": 500.0,
    },
    {
        "id": "trade_evidence",
        "query": "iron condor expectancy and profit factor from paired trades",
        "intent": "trade_evidence",
        "must_contain_any": [
            "OUTCOME_OF",
            "strategy:iron_condor",
            "trade:",
            "realized_pnl",
        ],
        "max_latency_ms": 800.0,
    },
]


def _assert_golden(result: Any, case: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if not result.allowed:
        failures.append(f"token_guard_halted:{result.token_guard.get('halt_reason')}")
    intent = (result.route or {}).get("intent")
    if intent != case["intent"]:
        failures.append(f"intent_expected={case['intent']} got={intent}")
    if result.latency_ms > float(case["max_latency_ms"]):
        failures.append(f"latency_ms={result.latency_ms:.1f} > budget={case['max_latency_ms']}")
    blob = (
        result.context
        + " "
        + json.dumps(result.retrieval, default=str)
        + " "
        + json.dumps(result.route, default=str)
    ).lower()
    needles = [str(x).lower() for x in case["must_contain_any"]]
    if not any(n in blob for n in needles):
        failures.append(f"missing_all_needles={case['must_contain_any']}")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=_REPO)
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Optional graph DB path (default under repo data/rag/)",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--skip-rebuild",
        action="store_true",
        help="Use existing graph DB (still fails if empty)",
    )
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    db_path = args.db or (repo_root / "data/rag/financial_graph.sqlite")
    # Prefer isolated temp DB in CI-like runs when GRAPH_RAG_VERIFY_TMP=1
    store = FinancialGraphStore(db_path=db_path)
    pipeline = GraphRAGPipeline(
        store=store,
        repo_root=repo_root,
        auto_build_if_empty=True,
        max_tokens=1800,
        hard_max_tokens=3200,
    )

    report: dict[str, Any] = {
        "repo_root": str(repo_root),
        "db_path": str(db_path),
        "cases": [],
        "ok": False,
    }

    t0 = time.perf_counter()
    if not args.skip_rebuild:
        rebuild = pipeline.rebuild(clear=True)
        report["rebuild"] = rebuild
        report["rebuild_latency_ms"] = (time.perf_counter() - t0) * 1000.0
        nodes = (rebuild.get("stats") or {}).get("nodes", 0)
        edges = (rebuild.get("stats") or {}).get("edges", 0)
        if nodes < 20 or edges < 20:
            report["error"] = f"graph_too_small nodes={nodes} edges={edges}"
            if args.json:
                print(json.dumps(report, indent=2, default=str))
            else:
                print(report["error"], file=sys.stderr)
            pipeline.close()
            return 1
    else:
        stats = pipeline.stats()
        report["stats"] = stats
        if stats.get("nodes", 0) < 1:
            report["error"] = "graph_empty"
            print(json.dumps(report, indent=2) if args.json else report["error"])
            pipeline.close()
            return 1

    hard_halt = False
    failed = 0
    for case in GOLDEN:
        result = pipeline.query(
            case["query"],
            force_graph_only=True,
            max_tokens=1800,
            hard_max_tokens=3200,
        )
        failures = _assert_golden(result, case)
        if not result.allowed:
            hard_halt = True
        entry = {
            "id": case["id"],
            "query": case["query"],
            "intent": (result.route or {}).get("intent"),
            "latency_ms": result.latency_ms,
            "allowed": result.allowed,
            "failures": failures,
            "seeds": (result.retrieval or {}).get("seeds"),
            "path_count": len((result.retrieval or {}).get("paths") or []),
        }
        report["cases"].append(entry)
        if failures:
            failed += 1
            if not args.json:
                print(f"FAIL {case['id']}: {failures}", file=sys.stderr)
        elif not args.json:
            print(
                f"PASS {case['id']} intent={entry['intent']} "
                f"latency_ms={entry['latency_ms']:.1f} paths={entry['path_count']}"
            )

    report["failed"] = failed
    report["passed"] = len(GOLDEN) - failed
    report["ok"] = failed == 0 and not hard_halt
    report["total_latency_ms"] = (time.perf_counter() - t0) * 1000.0

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        stats = pipeline.stats()
        print(
            f"graph nodes={stats.get('nodes')} edges={stats.get('edges')} "
            f"passed={report['passed']}/{len(GOLDEN)} "
            f"total_ms={report['total_latency_ms']:.1f}"
        )

    pipeline.close()
    if hard_halt:
        return 2
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
