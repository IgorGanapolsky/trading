#!/usr/bin/env python3
"""Spec Kit bug assess→fix→test FORMAT (github/spec-kit bug extension — not a clone).

Writes `.planning/bugs/<slug>/{ASSESS,FIX,TEST}.md` and prints JSON.
Does not apply patches itself — documents the evidence ladder agents must follow
before claiming a CI/harness defect fixed.

EXIT 0 always unless --strict and TEST not marked pass.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUGS = ROOT / ".planning" / "bugs"


def _slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")[:64] or "bug"


def assess(slug: str, report: str, root_cause: str, evidence: str) -> Path:
    """Phase 1 systematic-debugging (obra/superpowers) before any fix."""
    d = BUGS / slug
    d.mkdir(parents=True, exist_ok=True)
    path = d / "ASSESS.md"
    path.write_text(
        f"""# ASSESS — {slug}

Updated: {datetime.now(UTC).isoformat()}

Iron law (obra/superpowers systematic-debugging): **NO FIXES WITHOUT ROOT CAUSE FIRST.**

## Phase 1 — Root Cause Investigation

### Report

{report.strip()}

### Root cause (must be disprovable)

{root_cause.strip()}

### Evidence preserved before remediate

{evidence.strip()}

## Phases 2–4 (after assess)

2. **Pattern analysis** — why this class of bug exists; related sites
3. **Hypothesis + minimal fix** — document in FIX.md
4. **Verification** — TEST.md with fresh command output (superpowers verify-complete)

## Gate

Do not write FIX.md until Phase 1 is evidenced. Do not claim TEST pass without fresh output.
"""
    )
    return path


def fix(slug: str, change: str, files: list[str]) -> Path:
    d = BUGS / slug
    d.mkdir(parents=True, exist_ok=True)
    assess_path = d / "ASSESS.md"
    if not assess_path.exists():
        raise FileNotFoundError(f"ASSESS.md missing for {slug} — run assess first")
    path = d / "FIX.md"
    path.write_text(
        f"""# FIX — {slug}

Updated: {datetime.now(UTC).isoformat()}

## Change

{change.strip()}

## Files

{chr(10).join(f"- `{f}`" for f in files) or "- (none listed)"}

## Linked assess

See ASSESS.md in this directory.
"""
    )
    return path


def test_step(slug: str, command: str, output: str, passed: bool) -> Path:
    d = BUGS / slug
    d.mkdir(parents=True, exist_ok=True)
    if not (d / "FIX.md").exists():
        raise FileNotFoundError(f"FIX.md missing for {slug} — run fix first")
    path = d / "TEST.md"
    status = "pass" if passed else "fail"
    path.write_text(
        f"""# TEST — {slug}

Updated: {datetime.now(UTC).isoformat()}
Status: **{status}**

## Command

```bash
{command.strip()}
```

## Output (evidence)

```text
{output.strip()[:4000]}
```
"""
    )
    return path


def status(slug: str) -> dict:
    d = BUGS / slug
    stages = {
        "assess": (d / "ASSESS.md").exists(),
        "fix": (d / "FIX.md").exists(),
        "test": (d / "TEST.md").exists(),
    }
    test_pass = False
    if stages["test"]:
        text = (d / "TEST.md").read_text()
        test_pass = "Status: **pass**" in text
    complete = all(stages.values()) and test_pass
    return {
        "slug": slug,
        "stages": stages,
        "test_pass": test_pass,
        "complete": complete,
        "dir": str(d),
        "stolen_format": "github/spec-kit bug assess→fix→test",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_a = sub.add_parser("assess")
    p_a.add_argument("--slug", required=True)
    p_a.add_argument("--report", required=True)
    p_a.add_argument("--root-cause", required=True)
    p_a.add_argument("--evidence", required=True)

    p_f = sub.add_parser("fix")
    p_f.add_argument("--slug", required=True)
    p_f.add_argument("--change", required=True)
    p_f.add_argument("--file", action="append", default=[])

    p_t = sub.add_parser("test")
    p_t.add_argument("--slug", required=True)
    p_t.add_argument("--command", required=True)
    p_t.add_argument("--output", required=True)
    p_t.add_argument("--pass", dest="passed", action="store_true")
    p_t.add_argument("--fail", dest="failed", action="store_true")

    p_s = sub.add_parser("status")
    p_s.add_argument("--slug", required=True)
    p_s.add_argument("--strict", action="store_true")

    args = parser.parse_args(argv)
    if args.cmd == "assess":
        slug = _slugify(args.slug)
        path = assess(slug, args.report, args.root_cause, args.evidence)
        print(
            json.dumps({"ok": True, "stage": "assess", "path": str(path), **status(slug)}, indent=2)
        )
        return 0
    if args.cmd == "fix":
        slug = _slugify(args.slug)
        path = fix(slug, args.change, args.file)
        print(json.dumps({"ok": True, "stage": "fix", "path": str(path), **status(slug)}, indent=2))
        return 0
    if args.cmd == "test":
        slug = _slugify(args.slug)
        if args.failed and args.passed:
            print("choose --pass or --fail", file=sys.stderr)
            return 2
        passed = bool(args.passed) and not bool(args.failed)
        path = test_step(slug, args.command, args.output, passed)
        st = status(slug)
        print(json.dumps({"ok": True, "stage": "test", "path": str(path), **st}, indent=2))
        return 0 if passed else 1
    if args.cmd == "status":
        slug = _slugify(args.slug)
        st = status(slug)
        print(json.dumps({"ok": True, **st}, indent=2))
        if args.strict and not st["complete"]:
            return 2
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
