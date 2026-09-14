#!/usr/bin/env python3
"""Checkpoint / rope-length picker (layered stack: open-gsd / Spec Kit / Superpowers / BMAD).

Encodes docs/AGENT_WORKFLOW_STACK.md:
- Everyday default = open-gsd FORMAT (never archived gsd-build/get-shit-done)
- High-risk = Superpowers FORMAT
- Auditable = Spec Kit FORMAT
- Product-scale = BMAD FORMAT
- Compound overlays when the same correction repeats

Not a product install. Model runtime stays separable.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOUND = ROOT / ".planning" / "COMPOUND.md"
STACK_DOC = ROOT / "docs" / "AGENT_WORKFLOW_STACK.md"

JOB_DEFAULTS = {
    "throwaway": "ralph",
    "everyday": "gsd",
    "high_risk": "superpowers",
    "auditable": "speckit",
    "product_scale": "bmad",
}


def pick(
    *,
    undo_cost: str = "medium",
    multi_session: bool = False,
    repeat_correction: bool | None = None,
    one_sentence_diff: bool = False,
    job: str | None = None,
) -> dict:
    undo = undo_cost.lower()
    if repeat_correction is None:
        repeat_correction = COMPOUND.exists() and "### slug:" in COMPOUND.read_text()

    # Explicit job wins when provided
    if job:
        rec = JOB_DEFAULTS.get(job, "gsd")
        why_map = {
            "throwaway": "Throwaway job → Ralph/Quick; no ceremony",
            "everyday": "Everyday feature → open-gsd FORMAT (successor of archived get-shit-done)",
            "high_risk": "High-risk → Superpowers FORMAT (verify-complete / TDD / AFT)",
            "auditable": "Auditable/shared → Spec Kit FORMAT (constitution + converge)",
            "product_scale": "Product-scale → BMAD FORMAT (SPEC + readiness + Quick Flow)",
        }
        why = why_map.get(job, "open-gsd everyday default")
    elif one_sentence_diff and undo in {"free", "throwaway", "low"}:
        rec = "quick"
        why = "One-sentence diff + cheap undo → Quick Flow; skip ceremony"
    elif undo in {"free", "throwaway"} and not multi_session:
        rec = "ralph"
        why = "Throwaway / low undo cost → Ralph loop OK"
    elif multi_session or undo in {"high", "production", "irreversible"}:
        rec = "superpowers" if undo in {"production", "irreversible"} else "gsd"
        why = (
            "Irreversible/production → Superpowers rigor"
            if rec == "superpowers"
            else "Multi-session → open-gsd phase boundaries + goal-backward"
        )
    else:
        # Personal low-friction default = open-gsd (recommendation stack)
        rec = "gsd"
        why = "Default everyday belay = open-gsd FORMAT (not archived gsd-build)"

    cli_map = {
        "quick": "python3 scripts/bmad_readiness.py --no-append",
        "ralph": "python3 scripts/ralph_gsd_tick.py --verify",
        "gsd": (
            "python3 scripts/goal_backward_verify.py --goal harness && "
            "python3 scripts/ralph_gsd_tick.py --converge --verify-live"
        ),
        "superpowers": "python3 scripts/ralph_gsd_tick.py --verify-complete",
        "speckit": "python3 scripts/speckit_converge.py --verify-live",
        "bmad": "python3 scripts/bmad_readiness.py --verify-live",
    }
    cli = cli_map.get(rec, cli_map["gsd"])

    compound_note = None
    if repeat_correction:
        compound_note = (
            "Same correction twice — ADD Compound fourth step: "
            "python3 scripts/compound_lesson.py --slug ... "
            "(then promote into .claude/rules/)"
        )
        if "compound" not in rec:
            rec = f"{rec}+compound"

    return {
        "ok": True,
        "framework": "checkpoint_pick",
        "stolen_format": "Layered open-gsd + Spec Kit + Superpowers + BMAD (FORMAT only)",
        "stack_doc": str(STACK_DOC) if STACK_DOC.exists() else None,
        "inputs": {
            "undo_cost": undo_cost,
            "multi_session": multi_session,
            "repeat_correction": repeat_correction,
            "one_sentence_diff": one_sentence_diff,
            "job": job,
        },
        "recommend": rec,
        "why": why,
        "cli": cli,
        "compound_note": compound_note,
        "provenance": (
            "NEVER gsd-build/get-shit-done (archived 2026-06-26). "
            "USE open-gsd/gsd-core FORMAT steals in-repo. "
            "AGENTS.md/CONSTITUTION/SPEC are the invariant contract."
        ),
        "ts": datetime.now(UTC).isoformat(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--undo-cost",
        choices=["free", "throwaway", "low", "medium", "high", "production", "irreversible"],
        default="medium",
    )
    parser.add_argument("--multi-session", action="store_true")
    parser.add_argument("--repeat-correction", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--one-sentence-diff", action="store_true")
    parser.add_argument(
        "--job",
        choices=list(JOB_DEFAULTS.keys()),
        default=None,
        help="Explicit job class from AGENT_WORKFLOW_STACK.md",
    )
    args = parser.parse_args(argv)
    out = pick(
        undo_cost=args.undo_cost,
        multi_session=args.multi_session,
        repeat_correction=args.repeat_correction,
        one_sentence_diff=args.one_sentence_diff,
        job=args.job,
    )
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
