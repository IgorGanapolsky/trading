#!/usr/bin/env python3
"""InfoQ Sep 8 2026 control-plane doctor for trading (FORMAT steal, not SaaS).

Checks:
  - context gist (in/out + ≥2 ACs under budget)
  - entry challenge matrix snapshot
  - flux task graph readiness
  - PR risk classifier (no billed Copilot review)
  - package-manager honesty (uv.lock)

Exit 0 only when every dimension ok=true.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ops.context_gist import gist_context  # noqa: E402
from src.ops.flux_task_graph import list_graphs, plan_graph  # noqa: E402
from src.ops.package_manager_honesty import scan_tree  # noqa: E402
from src.ops.pr_risk_classifier import classify_pr_paths  # noqa: E402
from src.risk.entry_challenge_matrix import evaluate_entry_challenges  # noqa: E402


def _parse_csv(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [p.strip() for p in raw.replace("|", ",").split(",") if p.strip()]


def build_report(args: argparse.Namespace) -> dict:
    gist = gist_context(
        goal=args.goal,
        in_scope=args.in_scope,
        out_scope=args.out_scope,
        acceptance_criteria=_parse_csv(args.acs),
        constraints=_parse_csv(args.constraints),
        extras=_parse_csv(args.extras),
        token_budget=args.token_budget,
    )

    snap = {
        "paper": args.paper,
        "trading_mode": "paper" if args.paper else args.trading_mode,
        "active_family": args.active_family,
        "live_blocked": args.live_blocked,
        "ic_entries_killed": args.ic_entries_killed,
        "inventory_clean": args.inventory_clean,
        "iv_rank_proxy": args.iv_rank_proxy,
        "min_iv_rank": args.min_iv_rank,
        "lot_size": args.lot_size,
        "max_lot_size": 1,
        "open_put_credits": args.open_put_credits,
        "max_concurrent_put_credits": args.max_concurrent,
        "structures_today": args.structures_today,
        "max_daily_structures": args.max_daily,
    }
    challenges = evaluate_entry_challenges(snap)
    graph = plan_graph(args.graph)
    paths = _parse_csv(args.paths)
    pr = classify_pr_paths(paths, propose_billed_copilot=args.propose_billed_copilot)
    pkg = scan_tree(ROOT)

    dims = {
        "context_gist": gist.to_dict(),
        "entry_challenges": challenges.to_dict(),
        "flux_graph": graph.to_dict(),
        "pr_risk": pr.to_dict(),
        "package_manager": pkg,
    }
    failing = []
    if not gist.ok:
        failing.append("context_gist")
    if not challenges.allowed and args.require_entry_allowed:
        failing.append("entry_challenges")
    if not graph.ok:
        failing.append("flux_graph")
    if not pr.ok:
        failing.append("pr_risk")
    if not pkg.get("ok"):
        failing.append("package_manager")

    score = sum(
        1
        for ok in (
            gist.ok,
            challenges.allowed or not args.require_entry_allowed,
            graph.ok,
            pr.ok,
            bool(pkg.get("ok")),
        )
        if ok
    )
    return {
        "ok": not failing,
        "score": score,
        "max_score": 5,
        "failing": failing,
        "available_graphs": list_graphs(),
        "dimensions": dims,
        "source": "infoq-2026-09-08-format-steal",
        "not_cloned": [
            "Shopify Gisting tokens",
            "DoorDash Flux cloud",
            "Airbnb Flexible Auth product",
            "billed Copilot Code Review",
            "Harness webinar",
            "Foundry Model Router",
            "pnpm 12",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--goal", default="trading InfoQ control plane doctor")
    p.add_argument("--in-scope", default="deterministic gist+challenges+flux+pr-risk")
    p.add_argument("--out-scope", default="Harness webinar; billed Copilot review; Flux cloud")
    p.add_argument(
        "--acs",
        default="tests pass,CLI fail-closed when dimension red",
        help="Comma/pipe-separated acceptance criteria (≥2)",
    )
    p.add_argument("--constraints", default="paper_only,uv.lock")
    p.add_argument("--extras", default="")
    p.add_argument("--token-budget", type=int, default=1200)
    p.add_argument("--graph", default="dry_run_readiness")
    p.add_argument(
        "--paths",
        default="src/ops/context_gist.py,tests/test_context_gist.py,docs/INFOQ_CONTROL_PLANE.md",
    )
    p.add_argument("--propose-billed-copilot", action="store_true")
    p.add_argument("--paper", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--trading-mode", default="paper")
    p.add_argument("--active-family", default="spy_put_credit")
    p.add_argument("--live-blocked", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--ic-entries-killed", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--inventory-clean", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--iv-rank-proxy", type=float, default=35.0)
    p.add_argument("--min-iv-rank", type=float, default=30.0)
    p.add_argument("--lot-size", type=int, default=1)
    p.add_argument("--open-put-credits", type=int, default=0)
    p.add_argument("--max-concurrent", type=int, default=2)
    p.add_argument("--structures-today", type=int, default=0)
    p.add_argument("--max-daily", type=int, default=3)
    p.add_argument(
        "--require-entry-allowed",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Fail doctor when entry challenges block (default true)",
    )
    args = p.parse_args(argv)
    report = build_report(args)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
