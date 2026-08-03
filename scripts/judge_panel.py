#!/usr/bin/env python3
"""CLI: LLM-as-Judge panel + Mixture-of-Experts (claim / PR / coord audit).

Does NOT approve trades. Hard risk vetoes always win.

Examples:
  python scripts/judge_panel.py --kind claim_audit --text "CI green on run 123456"
  python scripts/judge_panel.py --kind pr_audit --diff-file ./patch.diff
  python scripts/judge_panel.py --kind coord_audit --other-claims-file vault.md --agent grok
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

# Paths may only be read under these roots (absolute after resolve).
# Do NOT include /tmp — Bandit B108 flags hardcoded temp-dir allowlists.
_ALLOWED_READ_ROOTS: tuple[Path, ...] = (
    ROOT,
    Path.home() / "Documents" / "AI-Agent-Sync",
)


def safe_read_text(path: str | None, *, roots: tuple[Path, ...] | None = None) -> str:
    """Read a UTF-8 text file only if it resolves under an allowed root.

    Prevents path traversal / arbitrary FS reads from CLI args (Sonar S8707).
    """
    if not path:
        return ""
    allowed = roots if roots is not None else _ALLOWED_READ_ROOTS
    try:
        candidate = Path(path).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise SystemExit(f"error: cannot resolve path {path!r}: {exc}") from exc

    if not candidate.is_file():
        raise SystemExit(f"error: not a file: {path!r}")

    for root in allowed:
        try:
            root_resolved = root.expanduser().resolve()
        except (OSError, RuntimeError):
            continue
        try:
            candidate.relative_to(root_resolved)
            return candidate.read_text(encoding="utf-8", errors="replace")
        except ValueError:
            continue

    roots_disp = ", ".join(str(r) for r in allowed)
    raise SystemExit(f"error: path outside allowed roots ({roots_disp}): {path!r}")


def _self_check() -> int:
    """Built-in regression samples — exit 0 only if all behave as designed."""
    cases = [
        (
            "unverified_edge",
            {
                "kind": TaskKind.CLAIM_AUDIT,
                "text": "Edge proven and profitable, ready for live",
            },
            False,
        ),
        (
            "verified_claim",
            {
                "kind": TaskKind.CLAIM_AUDIT,
                "text": ("CI green on run 30780143772, merge sha d69beb2b6, n=162 expectancy=-47"),
            },
            True,
        ),
        (
            "ic_resume",
            {
                "kind": TaskKind.PR_AUDIT,
                "diff": "+ # resume iron condor entries tomorrow\n",
                "text": "open new iron condor",
            },
            False,
        ),
        (
            "trade_entry_refuse",
            {
                "kind": TaskKind.TRADE_ENTRY,
                "text": "panel should sell 15 delta put credit",
            },
            False,
        ),
        (
            "coord_collision",
            {
                "kind": TaskKind.COORD_AUDIT,
                "agent": "grok",
                "claimed_files": ["src/risk/trade_gateway.py"],
                "other_agent_claims": (
                    "codex owns In Progress IGO-35; claimed_files: src/risk/trade_gateway.py"
                ),
            },
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


def _print_human(verdict) -> None:
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
        diff=safe_read_text(args.diff_file),
        claim=safe_read_text(args.claim_file),
        agent=args.agent,
        other_agent_claims=safe_read_text(args.other_claims_file),
        claimed_files=args.claimed_file,
    )

    if args.json:
        print(json.dumps(verdict.to_dict(), indent=2))
    else:
        _print_human(verdict)

    return 0 if verdict.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
