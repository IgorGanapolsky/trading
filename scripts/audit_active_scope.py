#!/usr/bin/env python3
"""Fail closed when trading scope drifts into cash-theater or live risk."""

from __future__ import annotations

import argparse
import json
import re
import subprocess  # nosec B404
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCOPE_DOC = "docs/TRADING_ACTIVE_SCOPE.md"
KILL_SWITCH = "data/runtime/strategy_kill_switch.json"

REMOVED_IC_WORKFLOWS = (
    ".github/workflows/force-iron-condor.yml",
    ".github/workflows/iron-condor-autonomous.yml",
    ".github/workflows/iron-condor-scan.yml",
    ".github/workflows/execute-credit-spread.yml",
    ".github/workflows/iron-condor-guardian.yml",
)

# Filename theater from CEO scrap 2026-09-14 (AGENT-615). Allow tests/docs that
# mention the ban; block new product modules under scripts/src/.github.
FORBIDDEN_THEATER = re.compile(
    r"(?i)("
    r"ralph.?gsd.?24.?7|"
    r"desk.?grade.?quant|"
    r"institutional.?desk|"
    r"dagster.?sda|"
    r"gpt.?6.?astra|"
    r"astra.?work.?harness|"
    r"pi.?dev.?agent.?integration"
    r")"
)

ALLOW_THEATER_PATH_PREFIXES = (
    "docs/",
    "tests/",
    "rag_knowledge/",
    ".claude/rules/",
    "skills/",
)


def _git_ls_files(repo: Path) -> list[str]:
    completed = subprocess.run(  # nosec B603 B607
        ["git", "ls-files", "-z"],
        cwd=repo,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        return []
    return [item.decode() for item in completed.stdout.split(b"\0") if item]


def audit(repo: Path) -> dict:
    findings: list[dict] = []

    if not (repo / SCOPE_DOC).is_file():
        findings.append(
            {
                "severity": "error",
                "kind": "missing-scope-doc",
                "path": SCOPE_DOC,
                "detail": "active scope freeze doc missing",
            }
        )

    kill_path = repo / KILL_SWITCH
    if not kill_path.is_file():
        findings.append(
            {
                "severity": "error",
                "kind": "missing-kill-switch",
                "path": KILL_SWITCH,
                "detail": "strategy kill switch missing",
            }
        )
    else:
        try:
            kill = json.loads(kill_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            findings.append(
                {
                    "severity": "error",
                    "kind": "kill-switch-invalid-json",
                    "path": KILL_SWITCH,
                    "detail": str(exc),
                }
            )
            kill = {}
        if kill.get("active_family") != "spy_put_credit":
            findings.append(
                {
                    "severity": "error",
                    "kind": "wrong-active-family",
                    "path": KILL_SWITCH,
                    "detail": f"active_family={kill.get('active_family')!r}",
                }
            )
        if kill.get("paper_only") is not True:
            findings.append(
                {
                    "severity": "error",
                    "kind": "paper-only-required",
                    "path": KILL_SWITCH,
                    "detail": f"paper_only={kill.get('paper_only')!r}",
                }
            )
        if kill.get("live_blocked") is not True:
            findings.append(
                {
                    "severity": "error",
                    "kind": "live-blocked-required",
                    "path": KILL_SWITCH,
                    "detail": f"live_blocked={kill.get('live_blocked')!r}",
                }
            )
        killed = set(kill.get("killed_families") or [])
        for family in ("iron_condor", "ic_simple"):
            if family not in killed:
                findings.append(
                    {
                        "severity": "error",
                        "kind": "killed-family-missing",
                        "path": KILL_SWITCH,
                        "detail": f"{family} must remain in killed_families",
                    }
                )

    for rel in REMOVED_IC_WORKFLOWS:
        if (repo / rel).exists():
            findings.append(
                {
                    "severity": "error",
                    "kind": "revived-ic-workflow",
                    "path": rel,
                    "detail": "killed IC entry workflow must stay deleted",
                }
            )

    for rel in _git_ls_files(repo):
        if any(rel.startswith(prefix) for prefix in ALLOW_THEATER_PATH_PREFIXES):
            continue
        name = Path(rel).name
        hay = f"{rel} {name}"
        if FORBIDDEN_THEATER.search(hay):
            findings.append(
                {
                    "severity": "error",
                    "kind": "forbidden-theater-path",
                    "path": rel,
                    "detail": "matches scrap-frozen theater pattern (AGENT-615)",
                }
            )

    errors = sum(1 for f in findings if f["severity"] == "error")
    return {"errors": errors, "findings": findings, "ok": errors == 0}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = audit(args.repo.resolve())
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        if report["ok"]:
            print("active scope audit OK")
        else:
            print("active scope audit FAILED", file=sys.stderr)
            for finding in report["findings"]:
                print(
                    f"{finding['severity']}: {finding['kind']}: "
                    f"{finding['path']}: {finding['detail']}",
                    file=sys.stderr,
                )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
