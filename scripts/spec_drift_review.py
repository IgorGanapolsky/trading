#!/usr/bin/env python3
"""Attributed drift review against docs/SPEC.md named invariants (InfoQ SDD).

Key finding from InfoQ study: specs don't raise bug recall — they raise
**attribution** (findings cite named clauses). This CLI emits a drift log where
every finding cites an INV_* id.

EXIT 0 if no drifts; EXIT 2 if drifts found (--strict default for CI optional).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess  # nosec B404
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "SPEC.md"
SCORECARD = Path.home() / ".grok" / "skills" / "fleet-a-plus" / "scripts" / "scorecard.py"
RE_LANE = Path.home() / "workspace/git/igor/RealEstate-lane-grok"
GSD_STATE = RE_LANE / "data" / "ralph" / "GSD_STATE.json"
DIAL_CARD = RE_LANE / "outreach" / "DIAL_CARD_NOW.md"
CALL_SHEET = RE_LANE / "outreach" / "CALL_SHEET_VERIFIED.md"
PLANNING = ROOT / ".planning"
DRIFT_LOG = PLANNING / "DRIFT_LOG.md"

INV_ROW = re.compile(r"\|\s*(INV_[A-Za-z0-9_]+)\s*\|\s*([^|]+)\|\s*([^|]+)\|")


def _sh(args: list[str], timeout: int = 90) -> subprocess.CompletedProcess:
    return subprocess.run(  # nosec B603
        args, capture_output=True, text=True, timeout=timeout
    )


def parse_invariants(text: str) -> list[dict]:
    rows = []
    for m in INV_ROW.finditer(text):
        rows.append(
            {
                "id": m.group(1).strip(),
                "invariant": m.group(2).strip(),
                "probe": m.group(3).strip(),
            }
        )
    return rows


def _scorecard() -> dict:
    if not SCORECARD.exists():
        return {"error": "missing"}
    r = _sh([sys.executable, str(SCORECARD), "--json"], timeout=120)
    try:
        return json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return {"error": "parse"}


def _funnel() -> dict:
    if not GSD_STATE.exists():
        return {}
    try:
        d = json.loads(GSD_STATE.read_text())
    except json.JSONDecodeError:
        return {}
    return d.get("funnel") or {}


def _active_scope_ok() -> bool | None:
    script = ROOT / "scripts" / "audit_active_scope.py"
    if not script.exists():
        return None
    r = _sh([sys.executable, str(script), "--json"], timeout=60)
    try:
        data = json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return None
    return bool(data.get("ok"))


def check_invariant(inv: dict, score: dict, funnel: dict) -> dict | None:
    """Return a drift finding (with attribution) or None if ok/skip."""
    iid = inv["id"]
    overall = (score.get("overall") or {}) if "error" not in score else {}
    cash = (score.get("cash_fee_yes") or {}) if "error" not in score else {}
    letter = overall.get("letter")
    cash_ok = bool(cash.get("ok")) if isinstance(cash, dict) and "ok" in cash else False

    if iid == "INV_cash_grade_honesty":
        if letter in {"A", "A+", "A-"} and not cash_ok:
            return {
                "invariant_id": iid,
                "severity": "error",
                "detail": f"overall={letter} while cash_fee_yes unmet",
                "attribution": inv["invariant"],
            }
        return None

    if iid == "INV_cash_ship_lock":
        fee = funnel.get("fee_yes_count")
        live = None
        # live_cash may be on parent GSD_STATE
        if GSD_STATE.exists():
            try:
                live = json.loads(GSD_STATE.read_text()).get("live_cash_usd")
            except json.JSONDecodeError:
                live = None
        # No drift if we honestly stay non-A+; drift only if claiming cleared cash wrongly
        if cash_ok and not ((fee or 0) > 0 or (live or 0) > 0):
            return {
                "invariant_id": iid,
                "severity": "error",
                "detail": "cash_ok true but fee_yes/live_cash show no clear funds",
                "attribution": inv["invariant"],
            }
        return None

    if iid == "INV_live_blocked":
        # Soft: if scorecard exposes live flag later; for now SPEC constraint presence
        if "live_blocked" not in SPEC.read_text().lower() and "Paper only" not in SPEC.read_text():
            return {
                "invariant_id": iid,
                "severity": "error",
                "detail": "SPEC missing live_blocked / paper-only constraint",
                "attribution": inv["invariant"],
            }
        return None

    if iid == "INV_no_autosend":
        freeze = funnel.get("cold_email_freeze")
        if freeze is False:
            return {
                "invariant_id": iid,
                "severity": "error",
                "detail": "cold_email_freeze is False while SPEC requires freeze",
                "attribution": inv["invariant"],
            }
        return None

    if iid == "INV_dial_path":
        if not cash_ok and not DIAL_CARD.exists() and not CALL_SHEET.exists():
            return {
                "invariant_id": iid,
                "severity": "error",
                "detail": "cash unmet and neither dial card nor call sheet exists",
                "attribution": inv["invariant"],
            }
        return None

    if iid == "INV_ic_killed":
        ok = _active_scope_ok()
        if ok is False:
            return {
                "invariant_id": iid,
                "severity": "error",
                "detail": "audit_active_scope reported not ok",
                "attribution": inv["invariant"],
            }
        return None

    if iid in {"INV_sdd_targeting", "INV_attribution"}:
        # Meta-invariants about process — satisfied by this tool existing
        return None

    return None


def review(*, write_log: bool = True) -> dict:
    if not SPEC.exists():
        return {
            "ok": False,
            "error": f"missing {SPEC}",
            "drifts": [],
            "attribution_rate": None,
        }
    text = SPEC.read_text()
    invs = parse_invariants(text)
    score = _scorecard()
    funnel = _funnel()
    drifts = []
    for inv in invs:
        finding = check_invariant(inv, score, funnel)
        if finding:
            drifts.append(finding)

    attributed = sum(1 for d in drifts if d.get("invariant_id"))
    attribution_rate = 1.0 if not drifts else attributed / len(drifts)

    out = {
        "ok": len(drifts) == 0,
        "framework": "spec_drift_review",
        "stolen_format": (
            "InfoQ SDD pays-off: attribution-first drift review "
            "(recall may not rise; findings must cite INV_*)"
        ),
        "ts": datetime.now(UTC).isoformat(),
        "invariants_checked": len(invs),
        "drifts": drifts,
        "drift_count": len(drifts),
        "attribution_rate": attribution_rate,
        "raci": {
            "model_responsible": "generation / propose",
            "human_accountable": "reconcile each drift (never the model)",
        },
        "spec": str(SPEC),
    }

    if write_log:
        PLANNING.mkdir(parents=True, exist_ok=True)
        lines = [
            f"## Drift review — {out['ts']}",
            f"invariants={len(invs)} drifts={len(drifts)} attribution_rate={attribution_rate}",
            "",
        ]
        if not drifts:
            lines.append("- none (all checked INV_* held)")
        for d in drifts:
            lines.append(
                f"- **{d['invariant_id']}** ({d['severity']}): {d['detail']} "
                f"— attribution: {d['attribution']}"
            )
        lines.append("")
        prior = (
            DRIFT_LOG.read_text() if DRIFT_LOG.exists() else "# DRIFT_LOG — attributed findings\n\n"
        )
        DRIFT_LOG.write_text(prior.rstrip() + "\n" + "\n".join(lines))
        out["drift_log"] = str(DRIFT_LOG)

    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--strict", action="store_true")
    p.add_argument("--no-log", action="store_true")
    args = p.parse_args(argv)
    out = review(write_log=not args.no_log)
    print(json.dumps(out, indent=2, sort_keys=True))
    if args.strict and not out.get("ok"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
