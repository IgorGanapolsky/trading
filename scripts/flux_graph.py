#!/usr/bin/env python3
"""CLI for deterministic Flux-style operator task graphs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ops.flux_task_graph import list_graphs, plan_graph, write_receipt  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--list", action="store_true")
    p.add_argument("--graph", default="dry_run_readiness")
    p.add_argument("--receipt", action="store_true")
    p.add_argument(
        "--receipt-path",
        default="logs/flux_graph_receipts.jsonl",
        help="Append receipt path when --receipt",
    )
    args = p.parse_args(argv)
    if args.list:
        print(json.dumps({"graphs": list_graphs()}, indent=2))
        return 0
    plan = plan_graph(args.graph)
    payload = plan.to_dict()
    if args.receipt:
        payload = write_receipt(plan, Path(args.receipt_path))
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if plan.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
