#!/usr/bin/env python3
"""One Ralph/GSD observe→act tick for trading + cash residuals (AGENT-616+).

Does not send email, spend money, or merge without green required checks.
Prints JSON residual pick + evidence paths. EXIT 0 always unless --strict.
"""

from __future__ import annotations

import argparse
import json
import subprocess  # nosec B404 — fixed argv only (gh + local scorecard)
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RE_LANE = Path.home() / "workspace/git/igor/RealEstate-lane-grok"
CALL_SHEET = RE_LANE / "outreach/CALL_SHEET_VERIFIED.md"
SCORECARD = Path.home() / ".grok/skills/fleet-a-plus/scripts/scorecard.py"


def _sh(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(  # nosec B603 — no shell; argv list only
        args, capture_output=True, text=True, timeout=timeout
    )


def _scorecard() -> dict:
    if not SCORECARD.exists():
        return {"error": "scorecard missing"}
    r = _sh([sys.executable, str(SCORECARD), "--json"], timeout=120)
    try:
        return json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return {"error": "scorecard_parse", "stderr": (r.stderr or "")[:400]}


def _open_prs() -> list[dict]:
    r = _sh(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            "IgorGanapolsky/trading",
            "--state",
            "open",
            "--limit",
            "20",
            "--json",
            "number,title,headRefName,mergeStateStatus,statusCheckRollup",
        ]
    )
    try:
        return json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        return []


def _pick(score: dict, prs: list[dict]) -> dict:
    cash = score.get("cash_fee_yes") or {}
    overall = score.get("overall") or {}
    failing = []
    for pr in prs:
        for c in pr.get("statusCheckRollup") or []:
            if (c.get("conclusion") or "") == "FAILURE" and (c.get("name") or "") in {
                "Run All Tests",
                "Validate issue, claim, and branch metadata",
                "Agent PR required review",
                "grep-guard",
            }:
                failing.append(
                    {"pr": pr.get("number"), "check": c.get("name"), "title": pr.get("title")}
                )
    if failing:
        return {
            "residual": "fix_required_ci",
            "priority": 1,
            "detail": failing[:5],
            "act": "Heal failing required check in isolated worktree; push; re-arm auto-merge",
        }
    if not cash.get("ok"):
        return {
            "residual": "cash_fee_yes",
            "priority": 3,
            "detail": {
                "letter": cash.get("letter"),
                "call_sheet": str(CALL_SHEET),
                "call_sheet_exists": CALL_SHEET.exists(),
                "overall": overall.get("letter"),
            },
            "act": "Expand CALL_SHEET_VERIFIED + drafts; verify Stripe checkout; do not auto-send",
        }
    return {
        "residual": "maintain",
        "priority": 99,
        "detail": {"overall": overall.get("letter")},
        "act": "Scorecard green path — run dry-run / Buffett status; keep live blocked until cohort gates",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true", default=True)
    args = parser.parse_args(argv)
    score = _scorecard()
    prs = _open_prs()
    pick = _pick(score if "error" not in score else {}, prs)
    out = {
        "ok": True,
        "framework": "ralph_gsd",
        "skill": "/trading-ralph-gsd-24-7",
        "ts": datetime.now(UTC).isoformat(),
        "repo": str(ROOT),
        "pick": pick,
        "open_pr_count": len(prs),
        "cash_ok": bool((score.get("cash_fee_yes") or {}).get("ok")),
        "overall_letter": (score.get("overall") or {}).get("letter"),
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    if args.strict and pick.get("residual") in {"fix_required_ci"}:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
