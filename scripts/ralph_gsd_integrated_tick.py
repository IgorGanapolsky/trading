#!/usr/bin/env python3
"""Integrated Ralph/GSD observe+pick — all harness CLIs in one automated tick.

CEO 2026-09-15: all commands integrated and automated; Igor never runs them.

Runs (fail-soft per probe, always emits JSON):
  1. ops_daily_brief (recommend-only, alert budget)
  2. eval_first_ledger summary
  3. agent_fanout_memory
  4. hydrafusion_route for the picked residual
  5. default ralph_gsd_tick pick + phase_loop + STATE/CONTEXT

LaunchAgent / make ralph-integrated / scheduler should call THIS entrypoint.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))


def _safe(label: str, fn):
    try:
        return {"ok": True, "label": label, "result": fn()}
    except Exception as exc:  # noqa: BLE001 — observe must not abort tick
        return {"ok": False, "label": label, "error": f"{type(exc).__name__}: {exc}"}


def run_integrated(
    *,
    alert_budget: int = 5,
    log_candidates: bool = True,
    write_state: bool = True,
    verify: bool = False,
) -> dict:
    from agent_fanout_memory import evaluate as fanout_eval  # noqa: I001
    from astra_harness_gate import evaluate as astra_gate
    from eval_first_ledger import summary as eval_summary
    from hydrafusion_execute import execute as hydra_execute
    from hydrafusion_route import route as hydra_route
    from ops_daily_brief import build_brief
    from pair_fleet_router import inventory as pair_inventory
    from ralph_gsd_tick import (
        _open_prs,
        _phase_loop,
        _pick,
        _scorecard,
        verify_evidence,
        write_context,
        write_state as _write_state,
    )
    from search_stack_pipeline import run_pipeline as search_stack

    observe = {}
    observe["ops_brief"] = _safe(
        "ops_brief",
        lambda: build_brief(alert_budget=alert_budget, log_candidates=log_candidates),
    )
    observe["eval_ledger"] = _safe("eval_ledger", eval_summary)
    observe["fanout_memory"] = _safe("fanout_memory", fanout_eval)
    observe["pair_fleet"] = _safe("pair_fleet", pair_inventory)

    score = _scorecard()
    prs = _open_prs()
    pick = _pick(score if "error" not in score else {}, prs)
    phase = _phase_loop(pick)

    task = str(pick.get("residual") or pick.get("action") or "ops residual")
    high_risk = task in {"fix_required_ci", "cash_fee_yes"} or "kill" in task
    observe["astra_gate"] = _safe(
        "astra_gate",
        lambda: astra_gate(proposed_action=task),
    )
    observe["search_stack"] = _safe(
        "search_stack",
        lambda: search_stack(task or "trading ops", limit=5, use_cache=True),
    )
    observe["hydrafusion"] = _safe(
        "hydrafusion",
        lambda: hydra_route(
            task=task,
            high_risk=high_risk,
            multi_constraint=high_risk,
            throwaway=False,
        ),
    )
    observe["hydrafusion_execute"] = _safe(
        "hydrafusion_execute",
        lambda: hydra_execute(
            task=task,
            high_risk=high_risk,
            multi_constraint=high_risk,
            throwaway=False,
            dry_rails=True,  # control-flow + accounting every tick; full rails via --hydrafusion-execute
        ),
    )

    verification = (
        verify_evidence(pick, live_checkout=False)
        if verify
        else {
            "status": "pending",
            "ok": None,
            "note": "integrated tick observe; pass --verify for fail-closed gate",
        }
    )
    state_path = context_path = None
    if write_state:
        state_path = str(
            _write_state(
                pick, phase, verification, overall=(score.get("overall") or {}).get("letter")
            )
        )
        context_path = str(write_context(pick, phase))

    # Surface top recommend-only actions from brief (agent acts; human never typed CLI)
    recommends = []
    brief = (observe.get("ops_brief") or {}).get("result") or {}
    for a in brief.get("alerts_shown") or []:
        recommends.append(
            {
                "workflow": a.get("workflow"),
                "recommend": a.get("recommend"),
                "severity": a.get("severity"),
                "provenance": a.get("provenance"),
            }
        )

    return {
        "ok": True,
        "framework": "ralph_gsd_integrated",
        "tick": "integrated",
        "skill": "/trading-ralph-gsd-24-7",
        "stolen_format": "all harness CLIs automated into one tick (zero manual)",
        "ts": datetime.now(UTC).isoformat(),
        "repo": str(ROOT),
        "pick": pick,
        "phase_loop": phase,
        "verification": verification,
        "state_md": state_path,
        "context_md": context_path,
        "open_pr_count": len(prs),
        "cash_ok": bool((score.get("cash_fee_yes") or {}).get("ok")),
        "overall_letter": (score.get("overall") or {}).get("letter"),
        "observe": observe,
        "recommends": recommends,
        "automation": {
            "entrypoint": "scripts/ralph_gsd_integrated_tick.py",
            "make": "make ralph-integrated",
            "launchagent": "com.igor.trading.ralph-gsd-integrated",
            "note": "Igor never runs these — agent/LaunchAgent/scheduler only",
        },
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--alert-budget", type=int, default=5)
    p.add_argument("--no-log", action="store_true")
    p.add_argument("--no-write-state", action="store_true")
    p.add_argument("--verify", action="store_true")
    p.add_argument("--strict", action="store_true")
    args = p.parse_args(argv)
    out = run_integrated(
        alert_budget=args.alert_budget,
        log_candidates=not args.no_log,
        write_state=not args.no_write_state,
        verify=args.verify,
    )
    print(json.dumps(out, indent=2, sort_keys=True))
    if args.strict and not out.get("cash_ok") and out.get("overall_letter") in {"A", "A+", "A-"}:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
