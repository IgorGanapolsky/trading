#!/usr/bin/env python3
"""Checkpoint / rope-length picker (AI Engineer: Superpowers vs GSD vs Compound).

Three questions:
1. How expensive to undo?
2. Does the run outgrow one context window?
3. Are you making the same correction twice?

Outputs a recommended belay: ralph | superpowers | gsd | compound | quick
plus the concrete trading CLI to run. Not a product install.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOUND = ROOT / ".planning" / "COMPOUND.md"


def pick(
    *,
    undo_cost: str,
    multi_session: bool,
    repeat_correction: bool | None = None,
    one_sentence_diff: bool = False,
) -> dict:
    undo = undo_cost.lower()
    if repeat_correction is None:
        repeat_correction = COMPOUND.exists() and "### slug:" in COMPOUND.read_text()

    # Article decision tree
    if one_sentence_diff and undo in {"free", "throwaway", "low"}:
        rec = "quick"
        why = "One-sentence diff + cheap undo → bare prompt / Quick Flow; skip ceremony"
        cli = "python3 scripts/bmad_readiness.py --no-append  # confirm Quick Flow still ok"
    elif undo in {"free", "throwaway"} and not multi_session:
        rec = "ralph"
        why = "Throwaway / low undo cost → Ralph loop OK; no plan gate required"
        cli = "python3 scripts/ralph_gsd_tick.py --verify"
    elif multi_session or undo in {"high", "production", "irreversible"}:
        rec = "gsd"
        why = "Multi-session or expensive undo → phase boundaries + goal-backward (open-gsd FORMAT)"
        cli = (
            "python3 scripts/goal_backward_verify.py --goal harness && "
            "python3 scripts/ralph_gsd_tick.py --converge --verify-live"
        )
    else:
        rec = "superpowers"
        why = "Default operator belay: plan/TDD/verify-before-claim without GSD ceremony"
        cli = "python3 scripts/ralph_gsd_tick.py --verify-complete"

    compound_note = None
    if repeat_correction:
        compound_note = (
            "Same correction twice detected — ADD Compound Engineering fourth step "
            "(python3 scripts/compound_lesson.py ...) on top of the chosen belay"
        )
        if rec != "compound":
            rec = f"{rec}+compound"

    return {
        "ok": True,
        "framework": "checkpoint_pick",
        "stolen_format": "AI Engineer Superpowers vs GSD vs Compound Engineering",
        "inputs": {
            "undo_cost": undo_cost,
            "multi_session": multi_session,
            "repeat_correction": repeat_correction,
            "one_sentence_diff": one_sentence_diff,
        },
        "recommend": rec,
        "why": why,
        "cli": cli,
        "compound_note": compound_note,
        "provenance": (
            "Prefer open-gsd FORMAT (never original GSD supply chain). "
            "Prefer Superpowers FORMAT steal over plugin if trading lab."
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
    args = parser.parse_args(argv)
    out = pick(
        undo_cost=args.undo_cost,
        multi_session=args.multi_session,
        repeat_correction=args.repeat_correction,
        one_sentence_diff=args.one_sentence_diff,
    )
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
