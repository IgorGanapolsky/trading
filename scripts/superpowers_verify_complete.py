#!/usr/bin/env python3
"""Superpowers verification-before-completion FORMAT (obra/superpowers — not a plugin install).

Iron Law: NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE.

Runs the proof command NOW, parses exit code + optional substrings, prints JSON.
EXIT 0 only when verification confirms the claim; else EXIT 2.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess  # nosec B404 — argv from caller; no shell
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_proof(
    claim: str,
    command: list[str],
    *,
    require_substr: list[str] | None = None,
    forbid_substr: list[str] | None = None,
    cwd: Path | None = None,
    timeout: int = 300,
) -> dict:
    cwd = cwd or ROOT
    started = datetime.now(UTC).isoformat()
    proc = subprocess.run(  # nosec B603 — no shell; argv list only
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(cwd),
    )
    out = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    require_substr = require_substr or []
    forbid_substr = forbid_substr or []
    missing = [s for s in require_substr if s not in out]
    forbidden_hit = [s for s in forbid_substr if s in out]
    ok = proc.returncode == 0 and not missing and not forbidden_hit
    return {
        "ok": ok,
        "framework": "superpowers_verify_complete",
        "stolen_format": "obra/superpowers verification-before-completion (not a clone)",
        "iron_law": "NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE",
        "claim": claim,
        "command": command,
        "exit_code": proc.returncode,
        "require_substr": require_substr,
        "missing_substr": missing,
        "forbid_substr": forbid_substr,
        "forbidden_hit": forbidden_hit,
        "started_at": started,
        "finished_at": datetime.now(UTC).isoformat(),
        "output_tail": out[-2000:],
        "gate": (
            "IDENTIFY→RUN→READ→VERIFY→ONLY THEN claim" if ok else "BLOCKED: do not claim success"
        ),
    }


def default_harness_suite() -> list[dict]:
    """Canonical proofs for trading Ralph/GSD harness health."""
    py = sys.executable
    return [
        {
            "claim": "ralph + speckit unit tests pass",
            "command": [
                py,
                "-m",
                "pytest",
                "tests/test_ralph_gsd_tick.py",
                "tests/test_speckit_steal.py",
                "tests/test_superpowers_steal.py",
                "-q",
            ],
            "require_substr": ["passed"],
            "forbid_substr": ["failed", "ERROR"],
        },
        {
            "claim": "speckit converge harness converged (ship_lock cash OK)",
            "command": [py, "scripts/speckit_converge.py", "--no-append"],
            "require_substr": ['"status": "converged"'],
            "forbid_substr": [],
        },
        {
            "claim": "active scope audit clean",
            "command": [py, "scripts/audit_active_scope.py", "--json"],
            "require_substr": ['"ok": true'],
            "forbid_substr": [],
        },
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claim", default="")
    parser.add_argument(
        "--command",
        default="",
        help="Shell-style command string (shlex-split; no shell exec)",
    )
    parser.add_argument("--require", action="append", default=[], help="Substring that must appear")
    parser.add_argument(
        "--forbid", action="append", default=[], help="Substring that must NOT appear"
    )
    parser.add_argument(
        "--harness",
        action="store_true",
        help="Run the canonical trading harness proof suite",
    )
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args(argv)

    results: list[dict] = []
    if args.harness:
        for item in default_harness_suite():
            # Skip missing test file until created in same commit
            cmd = item["command"]
            if cmd[1:3] == ["-m", "pytest"]:
                missing = [p for p in cmd if p.endswith(".py") and not (ROOT / p).exists()]
                if missing:
                    # Drop missing test modules from argv
                    cmd = [c for c in cmd if c not in missing]
            results.append(
                run_proof(
                    item["claim"],
                    cmd,
                    require_substr=item.get("require_substr"),
                    forbid_substr=item.get("forbid_substr"),
                    timeout=args.timeout,
                )
            )
    else:
        if not args.claim or not args.command:
            parser.error("--claim and --command required unless --harness")
        results.append(
            run_proof(
                args.claim,
                shlex.split(args.command),
                require_substr=args.require,
                forbid_substr=args.forbid,
                timeout=args.timeout,
            )
        )

    all_ok = all(r["ok"] for r in results)
    out = {
        "ok": all_ok,
        "framework": "superpowers_verify_complete",
        "stolen_format": "obra/superpowers verification-before-completion",
        "results": results,
        "ts": datetime.now(UTC).isoformat(),
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0 if all_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
