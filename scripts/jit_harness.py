#!/usr/bin/env python3
"""CLI: just-in-time trading ops harness packs (deterministic).

Inspired by JIT-Agent (arxiv:2608.25593v2, Sept 2026) — task-adaptive harness,
not a fatter model. Does not train or call a harness-generation LLM.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ops.jit_harness import (  # noqa: E402
    append_selection_receipt,
    estimate_savings_vs_full_context,
    readiness_report,
    select_harness,
    selection_receipt,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=("Select a task-specific trading harness pack (memory/plan/actions/capability)")
    )
    parser.add_argument("prompt", nargs="?", default="", help="Operator task prompt")
    parser.add_argument("--json", action="store_true", help="Emit JSON pack")
    parser.add_argument("--list", action="store_true", help="List task classes")
    parser.add_argument(
        "--full-budget",
        type=int,
        default=12000,
        help="Assumed fat-harness token budget for savings hint",
    )
    parser.add_argument(
        "--check-ready",
        action="store_true",
        help="Print catalog readiness JSON and exit 0 when ready",
    )
    parser.add_argument(
        "--receipt",
        action="store_true",
        help="Emit full selection receipt (conflicts, capability_ok, fingerprint)",
    )
    parser.add_argument(
        "--record",
        action="store_true",
        help="Append selection receipt to logs/jit_harness_receipts.jsonl",
    )
    args = parser.parse_args(argv)

    if args.check_ready or args.list:
        payload = readiness_report(repo_root=ROOT)
        print(json.dumps(payload, indent=2))
        return 0 if payload.get("ready") else 1

    if not (args.prompt or "").strip():
        parser.error("prompt is required unless --list / --check-ready")

    if args.receipt or args.record:
        receipt = selection_receipt(
            args.prompt, repo_root=ROOT, full_budget=max(0, args.full_budget)
        )
        if args.record:
            path = append_selection_receipt(receipt, repo_root=ROOT)
            receipt["receipt_path"] = str(path)
        print(json.dumps(receipt, indent=2))
        return 0 if receipt.get("capability_ok") else 2

    pack = select_harness(args.prompt)
    savings = estimate_savings_vs_full_context(pack, full_budget=max(0, args.full_budget))

    if args.json:
        out = pack.to_dict()
        out["savings_hint"] = savings
        out["prompt"] = args.prompt
        print(json.dumps(out, indent=2))
    else:
        print(pack.compact())
        print(
            f"\nsavings_hint: ~{savings['saved_pct_hint']}% vs "
            f"{savings['full_budget']} tok fat pack "
            f"(pack={savings['pack_budget']})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
