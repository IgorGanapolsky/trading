#!/usr/bin/env python3
"""Superpowers writing-plans FORMAT (obra/superpowers — not a plugin install).

Bite-sized tasks (2–5 min): exact paths + verification steps, junior-proof.
Writes/appends `.planning/plan.md`. EXIT 0.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / ".planning" / "plan.md"


def write_plan(
    title: str,
    tasks: list[dict],
    *,
    append: bool = False,
) -> Path:
    """tasks: [{id, title, files:[...], steps:[...], verify:str}]"""
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).isoformat()
    lines = [
        f"# Plan — {title}",
        "",
        f"Updated: {ts}",
        "Stolen format: obra/superpowers writing-plans (bite-sized, paths + verify).",
        "Audience: enthusiastic junior with poor taste — be explicit.",
        "",
    ]
    for t in tasks:
        tid = t.get("id") or "T?"
        lines.append(f"## {tid}: {t.get('title', '')}")
        lines.append("")
        files = t.get("files") or []
        lines.append("### Files")
        lines.extend(f"- `{f}`" for f in files) if files else lines.append("- (none)")
        lines.append("")
        lines.append("### Steps")
        for i, step in enumerate(t.get("steps") or [], 1):
            lines.append(f"{i}. {step}")
        lines.append("")
        lines.append("### Verify")
        lines.append(f"```bash\n{t.get('verify', 'echo missing-verify')}\n```")
        lines.append("")
        lines.append("YAGNI: do not add extras. RED→GREEN before expand.")
        lines.append("")
    body = "\n".join(lines)
    if append and PLAN.exists():
        with PLAN.open("a", encoding="utf-8") as fh:
            fh.write("\n" + body)
    else:
        PLAN.write_text(body)
    return PLAN


def harness_default_tasks() -> list[dict]:
    return [
        {
            "id": "T1",
            "title": "Run Superpowers verify-complete harness suite",
            "files": ["scripts/superpowers_verify_complete.py"],
            "steps": [
                "Execute python3 scripts/superpowers_verify_complete.py --harness",
                "Confirm JSON ok=true before any completion claim",
            ],
            "verify": "python3 scripts/superpowers_verify_complete.py --harness",
        },
        {
            "id": "T2",
            "title": "Converge Spec Kit + constitution",
            "files": ["scripts/speckit_converge.py", "docs/CONSTITUTION.md"],
            "steps": [
                "Run converge --verify-live",
                "Treat ship_lock cash as standing; do not invent A+",
            ],
            "verify": "python3 scripts/speckit_converge.py --verify-live --no-append",
        },
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", default="trading-ralph-harness")
    parser.add_argument("--harness-defaults", action="store_true")
    parser.add_argument("--append", action="store_true")
    parser.add_argument(
        "--task-json",
        default="",
        help="JSON list of tasks [{id,title,files,steps,verify}]",
    )
    args = parser.parse_args(argv)
    if args.harness_defaults:
        tasks = harness_default_tasks()
    elif args.task_json:
        tasks = json.loads(args.task_json)
    else:
        parser.error("pass --harness-defaults or --task-json")
    path = write_plan(args.title, tasks, append=args.append)
    print(
        json.dumps(
            {
                "ok": True,
                "path": str(path),
                "n_tasks": len(tasks),
                "stolen_format": "obra/superpowers writing-plans",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
