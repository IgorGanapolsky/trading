#!/usr/bin/env python3
"""CLI: LLM-as-Judge panel + Mixture-of-Experts (claim / PR / coord audit).

Does NOT approve trades. Hard risk vetoes always win.

Examples:
  python scripts/judge_panel.py --kind claim --text "CI green on run 123456"
  python scripts/judge_panel.py --kind pr --diff-file /tmp/patch.diff
  python scripts/judge_panel.py --kind coord --other-claims-file vault.md --agent grok
  python scripts/judge_panel.py --self-check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evals.judge_panel import TaskKind, run_panel  # noqa: E402


def _read(path: str | None) -> str:
    if not path:
        return ""
    return Path(path).read_text(encoding="utf-8", errors="replace")


def _self_check() -> int:
    """Built-in regression samples — exit 0 only if all behave as designed."""
    cases = [
        (
            "unverified_edge",
            dict(
                kind=TaskKind.CLAIM_AUDIT,
                text="Edge proven and profitable, ready for live",
            ),
            False,
        ),
        (
            "verified_claim",
            dict(
                kind=TaskKind.CLAIM_AUDIT,
                text="CI green on run 30780143772, merge sha d69beb2b6, n=162 expectancy=-47",
            ),
            True,
        ),
        (
            "ic_resume",
            dict(
                kind=TaskKind.PR_AUDIT,
                diff="+ # resume iron condor entries tomorrow\n",
                text="open new iron condor",
            ),
            False,
        ),
        (
            "trade_entry_refuse",
            dict(
                kind=TaskKind.TRADE_ENTRY,
                text="panel should sell 15 delta put credit",
            ),
            False,
        ),
        (
            "coord_collision",
            dict(
                kind=TaskKind.COORD_AUDIT,
                agent="grok",
                claimed_files=["src/risk/trade_gateway.py"],
                other_agent_claims=(
                    "codex owns In Progress IGO-35; claimed_files: src/risk/trade_gateway.py"
                ),
            ),
            False,
        ),
    ]
    failures = []
    for name, kwargs, expect_pass in cases:
        v = run_panel(**kwargs)
        if v.passed != expect_pass:
            failures.append(
                f"{name}: expected passed={expect_pass} got {v.passed} summary={v.judge_summary}"
            )
    if failures:
        print("SELF-CHECK FAIL")
        for f in failures:
            print(" -", f)
        return 1
    print("SELF-CHECK PASS")
    print(json.dumps({"cases": len(cases), "all_passed": True}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Judge panel (MoE) for agent/PR/coord audit")
    p.add_argument(
        "--kind",
        choices=[k.value for k in TaskKind],
        help="Audit kind",
    )
    p.add_argument("--text", default="", help="Free text / PR body / agent claim")
    p.add_argument("--diff-file", default=None, help="Unified diff path")
    p.add_argument("--claim-file", default=None, help="Claim markdown path")
    p.add_argument("--other-claims-file", default=None, help="Foreign vault claims path")
    p.add_argument("--agent", default="grok", help="This agent name")
    p.add_argument(
        "--claimed-file",
        action="append",
        default=[],
        help="File path claimed by this agent (repeatable)",
    )
    p.add_argument("--json", action="store_true", help="JSON output")
    p.add_argument("--self-check", action="store_true", help="Run built-in samples")
    args = p.parse_args(argv)

    if args.self_check:
        return _self_check()

    if not args.kind:
        p.error("--kind is required unless --self-check")

    verdict = run_panel(
        kind=args.kind,
        text=args.text,
        diff=_read(args.diff_file),
        claim=_read(args.claim_file),
        agent=args.agent,
        other_agent_claims=_read(args.other_claims_file),
        claimed_files=args.claimed_file,
    )

    if args.json:
        print(json.dumps(verdict.to_dict(), indent=2))
    else:
        print(f"kind={verdict.kind.value}")
        print(f"passed={verdict.passed} vetoed={verdict.vetoed} score={verdict.score}")
        print(f"experts={','.join(verdict.experts_used)}")
        print(f"summary={verdict.judge_summary}")
        if verdict.veto_reasons:
            print("veto_reasons:")
            for r in verdict.veto_reasons:
                print(f"  - {r}")
        for o in verdict.opinions:
            print(f"[{o.expert.value}] passed={o.passed} veto={o.veto} score={o.score}")
            for f in o.findings:
                print(f"  finding: {f}")

    return 0 if verdict.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
