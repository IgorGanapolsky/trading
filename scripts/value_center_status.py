#!/usr/bin/env python3
"""Value-center status (InfoQ / Simon Rohrer — Viable Systems five questions).

FORMAT steal from:
https://www.infoq.com/news/2026/09/autonomous-software-teams/

Not a clone of any org framework. Answers agency+coherence questions from LIVE
evidence (scorecard, open PRs, cash residual, dial card). Fail-closed: refuses
to report commercial value as A+/profitable while cash fee-yes unmet.

EXIT 0 always unless --strict (then 2 when coherence gaps).
"""

from __future__ import annotations

import argparse
import json
import subprocess  # nosec B404 — fixed argv only
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RE_LANE = Path.home() / "workspace/git/igor/RealEstate-lane-grok"
DIAL_CARD = RE_LANE / "outreach" / "DIAL_CARD_NOW.md"
CALL_SHEET = RE_LANE / "outreach" / "CALL_SHEET_VERIFIED.md"
DRAFTS = RE_LANE / "outreach" / "drafts"
SCORECARD = Path.home() / ".grok" / "skills" / "fleet-a-plus" / "scripts" / "scorecard.py"
GSD_STATE = RE_LANE / "data" / "ralph" / "GSD_STATE.json"


def _sh(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(  # nosec B603
        args, capture_output=True, text=True, timeout=timeout
    )


def _scorecard() -> dict:
    if not SCORECARD.exists():
        return {"error": "scorecard_missing"}
    r = _sh([sys.executable, str(SCORECARD), "--json"], timeout=120)
    try:
        return json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return {"error": "scorecard_parse", "stderr": (r.stderr or "")[:300]}


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
            "number,title,mergeStateStatus",
        ]
    )
    try:
        return json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        return []


def _cash_funnel() -> dict:
    if not GSD_STATE.exists():
        return {"fee_yes_count": None, "live_cash_usd": None}
    try:
        d = json.loads(GSD_STATE.read_text())
    except json.JSONDecodeError:
        return {"fee_yes_count": None, "live_cash_usd": None}
    fun = d.get("funnel") or {}
    return {
        "fee_yes_count": fun.get("fee_yes_count"),
        "live_cash_usd": d.get("live_cash_usd"),
        "cold_email_freeze": fun.get("cold_email_freeze"),
        "inbound_buyer_replies": fun.get("inbound_buyer_replies"),
    }


def _draft_count() -> int:
    if not DRAFTS.exists():
        return 0
    return len(list(DRAFTS.glob("prepaid_*.json")))


def build_value_center(score: dict, prs: list[dict], funnel: dict) -> dict:
    """Five Rohrer questions → evidence-backed answers."""
    overall = (score.get("overall") or {}) if "error" not in score else {}
    cash = (score.get("cash_fee_yes") or {}) if "error" not in score else {}
    letter = overall.get("letter")
    cash_ok = bool(cash.get("ok")) if cash else False
    fee_yes = funnel.get("fee_yes_count")
    live_cash = funnel.get("live_cash_usd")
    open_n = len(prs)
    drafts = _draft_count()
    dial = DIAL_CARD.exists()
    sheet = CALL_SHEET.exists()

    # Purpose = what the system DOES (Stacey/Beer), not aspirations
    purpose_does = {
        "paper_lab": True,
        "live_trading_deployed": False,
        "cleared_non_owner_cash": (live_cash or 0) > 0 or (fee_yes or 0) > 0,
        "overall_letter": letter,
        "cash_ok": cash_ok,
    }

    # Coherence gaps: autonomy without coordination / false value claims
    gaps: list[dict] = []
    if letter in {"A", "A+", "A-"} and not cash_ok:
        gaps.append(
            {
                "id": "false_commercial_value",
                "detail": "overall A* while cash fee-yes unmet — autonomy theater",
            }
        )
    if open_n > 5:
        gaps.append(
            {
                "id": "coordination_debt",
                "detail": f"{open_n} open PRs — coherence under agency pressure",
            }
        )
    if not dial and not sheet and not cash_ok:
        gaps.append(
            {
                "id": "value_path_missing",
                "detail": "no dial card/call sheet while cash unmet",
            }
        )

    residual = "cash_fee_yes" if not cash_ok else "maintain"
    if any((p.get("mergeStateStatus") == "BLOCKED") and "fail" in str(p).lower() for p in prs):
        # Prefer CI heal only when we know required fails — keep cash primary
        pass

    questions = {
        "what_value_am_i_delivering": {
            "answer": (
                "Cleared prepaid Miramar research-packet / AHLS fee-yes"
                if cash_ok
                else "Paper Buffett lab + staged dial/draft rails (NOT cleared cash)"
            ),
            "evidence": {
                "overall_letter": letter,
                "cash_ok": cash_ok,
                "fee_yes_count": fee_yes,
                "live_cash_usd": live_cash,
                "drafts_prepaid": drafts,
            },
        },
        "how_do_we_coordinate": {
            "answer": "Linear claim + Obsidian vault + GitHub PR/worktree (three-bus)",
            "evidence": {
                "open_prs": open_n,
                "prs": [
                    {
                        "n": p.get("number"),
                        "mss": p.get("mergeStateStatus"),
                        "title": (p.get("title") or "")[:60],
                    }
                    for p in prs[:8]
                ],
                "skills": [
                    "/trading-ralph-gsd-24-7",
                    "/agent-workflow-stack",
                    "/multi-agent-coord",
                ],
            },
        },
        "how_do_we_fit_together": {
            "answer": (
                "Nested value centers: trading=paper lab; RealEstate=cash packet; "
                "agency=AHLS; Resume=FT. Coherence = cash truth binds grades."
            ),
            "evidence": {
                "dial_card": dial,
                "call_sheet": sheet,
                "constitution": str(ROOT / "docs" / "CONSTITUTION.md"),
                "value_doc": str(ROOT / "docs" / "VALUE_CENTER.md"),
            },
        },
        "whats_out_there_for_us": {
            "answer": (
                "Outside scope / future: ThumbGate paid (ECI pause), live trading "
                "(blocked), OnCore clerk spend (CEO auth), Parallel research credit"
            ),
            "evidence": {
                "eci_pause": True,
                "live_blocked": True,
                "residual_pick": residual,
            },
        },
        "who_are_we": {
            "answer": (
                "Grok value center in a nested fleet: purpose TODAY is what we do — "
                "heal CI, stage dials/drafts, refuse A+ without fee-yes"
            ),
            "evidence": purpose_does,
        },
    }

    coherent = len(gaps) == 0
    return {
        "ok": True,
        "framework": "value_center",
        "stolen_format": (
            "InfoQ autonomous teams / Rohrer value-center five questions "
            "(Viable Systems Model FORMAT; not a clone)"
        ),
        "ts": datetime.now(UTC).isoformat(),
        "agency_coherence": {
            "prefer": "coherence_over_pure_autonomy",
            "coherent": coherent,
            "gaps": gaps,
        },
        "purpose_is_what_we_do": purpose_does,
        "questions": questions,
        "next_act": (
            "Dial DIAL_CARD_NOW / TOP_5 research-packet (human); keep PR wall drained"
            if not cash_ok
            else "Maintain paper lab; do not invent new product theater"
        ),
        "residual": residual,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument(
        "--write-planning",
        action="store_true",
        help="Append snapshot to .planning/VALUE_CENTER.md",
    )
    args = parser.parse_args(argv)
    score = _scorecard()
    prs = _open_prs()
    funnel = _cash_funnel()
    out = build_value_center(score, prs, funnel)

    if args.write_planning:
        plan = ROOT / ".planning"
        plan.mkdir(parents=True, exist_ok=True)
        path = plan / "VALUE_CENTER.md"
        q = out["questions"]
        body = [
            f"# Value center snapshot — {out['ts']}",
            "",
            "Stolen format: InfoQ / Rohrer five questions (not a clone).",
            "",
            f"**Coherent:** {out['agency_coherence']['coherent']}",
            f"**Residual:** `{out['residual']}`",
            f"**Next act:** {out['next_act']}",
            "",
            "## 1. What value am I delivering?",
            q["what_value_am_i_delivering"]["answer"],
            "",
            "## 2. How do we coordinate?",
            q["how_do_we_coordinate"]["answer"],
            "",
            "## 3. How do we fit together?",
            q["how_do_we_fit_together"]["answer"],
            "",
            "## 4. What's out there for us?",
            q["whats_out_there_for_us"]["answer"],
            "",
            "## 5. Who are we?",
            q["who_are_we"]["answer"],
            "",
        ]
        prior = path.read_text() if path.exists() else ""
        path.write_text(prior.rstrip() + "\n\n" + "\n".join(body) if prior else "\n".join(body))
        out["planning_path"] = str(path)

    print(json.dumps(out, indent=2, sort_keys=True))
    if args.strict and not out["agency_coherence"]["coherent"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
