#!/usr/bin/env python3
"""Ops daily brief — narrow high-frequency workflows (episode FORMAT).

Not a family assistant. Maps YT Xa1jm2VWEHk bets onto trading+cash:

1. Narrow workflows only (cash, dials, PR/CI, inventory, fanout, halt)
2. Eval-first: every alert logged as candidate with provenance
3. Tiered ladder: rules → cheap signals → premium only if flagged
4. Recommend-first / read-only (never auto-send)
5. Alert budget + precision over coverage
6. Provenance on every item

EXIT 0 always. EXIT 2 with --strict if critical alerts exceed budget unresolved.
"""

from __future__ import annotations

import argparse
import json
import subprocess  # nosec B404
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_ALERT_BUDGET = 5  # episode: prioritize precision over coverage


def _eval_mod():
    """Lazy-load sibling script (avoids trunk E402 on non-package imports)."""
    if str(ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(ROOT / "scripts"))
    import eval_first_ledger as m

    return m


def _run_json(script: str, *args: str) -> dict | None:
    py = ROOT / ".venv" / "bin" / "python"
    exe = str(py) if py.exists() else sys.executable
    cmd = [exe, str(ROOT / "scripts" / script), *args]
    try:
        r = subprocess.run(  # nosec B603
            cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=120, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (r.stdout or "").strip()
    if not text.startswith("{"):
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _item(
    *,
    workflow: str,
    title: str,
    provenance: str,
    confidence: float,
    tier: str,
    recommend: str,
    severity: str = "info",
) -> dict:
    return {
        "workflow": workflow,
        "title": title,
        "provenance": provenance,
        "confidence": confidence,
        "tier": tier,  # rules | cheap | extract | premium
        "recommend": recommend,  # never auto-execute
        "severity": severity,
        "autonomy": "recommend_only",
    }


def collect_alerts(*, log_candidates: bool = True) -> list[dict]:
    """Rules-first collection — premium models not required for the brief itself."""
    alerts: list[dict] = []

    # --- cash fee-yes (rules / scorecard if present) ---
    scorecard = ROOT / "data" / "runtime" / "fleet_scorecard.json"
    cash_ok = None
    if scorecard.exists():
        try:
            sc = json.loads(scorecard.read_text())
            cash_ok = (sc.get("cash_fee_yes") or {}).get("ok")
            letter = (sc.get("overall") or {}).get("letter")
            if cash_ok is False:
                alerts.append(
                    _item(
                        workflow="cash_fee_yes",
                        title=f"Commercial grade unmet (overall={letter})",
                        provenance=str(scorecard),
                        confidence=0.95,
                        tier="rules",
                        recommend=(
                            "Agent-owned cash residual only: advance drafts/checkout/"
                            "ledger rails; never assign dials to Igor (LL-638); no auto-send"
                        ),
                        severity="critical",
                    )
                )
        except (OSError, json.JSONDecodeError):
            pass
    if cash_ok is None:
        # cheap path: GSD / RE lane dial card presence (agent inventory — never Igor homework)
        dial = Path.home() / "workspace/git/igor/RealEstate-lane-grok/outreach/DIAL_CARD_NOW.md"
        if dial.exists():
            alerts.append(
                _item(
                    workflow="dial_path",
                    title="Dial card present — agent inventory only (never assign to Igor)",
                    provenance=str(dial),
                    confidence=0.8,
                    tier="rules",
                    recommend=(
                        "Agents advance automated residual / drafts; log attempts "
                        "themselves — do not tell Igor to dial (LL-638)"
                    ),
                    severity="high",
                )
            )
        else:
            alerts.append(
                _item(
                    workflow="dial_path",
                    title="No dial card found in RealEstate-lane-grok",
                    provenance="~/workspace/git/igor/RealEstate-lane-grok/outreach/",
                    confidence=0.7,
                    tier="rules",
                    recommend=(
                        "Agent refreshes research-packet inventory for automation; "
                        "never hand dial lists to Igor (LL-638)"
                    ),
                    severity="high",
                )
            )

    # --- fanout memory (rules) ---
    fanout = _run_json("agent_fanout_memory.py")
    if fanout and not fanout.get("ok"):
        alerts.append(
            _item(
                workflow="fanout_memory",
                title=(
                    f"Fan-out over budget: sandboxes={fanout.get('sandboxes')} "
                    f"rec_max={fanout.get('budget', {}).get('recommended_max_sandboxes')}"
                ),
                provenance="scripts/agent_fanout_memory.py",
                confidence=0.9,
                tier="rules",
                recommend="Prune stale .worktrees before spawning more agents",
                severity="high",
            )
        )

    # --- trading halt (rules) ---
    for halt in ("data/TRADING_HALTED", "data/SYSTEM_HALTED", "data/trading_halt.txt"):
        hp = ROOT / halt
        if hp.exists():
            alerts.append(
                _item(
                    workflow="trading_halt",
                    title=f"Halt file present: {halt}",
                    provenance=str(hp),
                    confidence=1.0,
                    tier="rules",
                    recommend="Do not clear halt; verify open inventory == 0 via crisis path",
                    severity="critical",
                )
            )

    # --- hydrafusion suggest for open high-risk residual ---
    if any(a["severity"] == "critical" for a in alerts):
        alerts.append(
            _item(
                workflow="ops_brief",
                title="Critical alerts present — use Critique route (tool-less critic)",
                provenance="scripts/hydrafusion_route.py --high-risk",
                confidence=0.75,
                tier="cheap",
                recommend="ralph --hydrafusion-route --high-risk before acting",
                severity="info",
            )
        )

    if log_candidates:
        append_event = _eval_mod().append_event
        for a in alerts:
            try:
                append_event(
                    {
                        "kind": "candidate",
                        "workflow": a["workflow"],
                        "title": a["title"],
                        "provenance": a["provenance"],
                        "confidence": a["confidence"],
                        "tier": a["tier"],
                        "status": "open",
                    }
                )
            except ValueError:
                continue

    # Alert budget: keep highest severity first
    sev_rank = {"critical": 0, "high": 1, "info": 2}
    alerts.sort(key=lambda x: (sev_rank.get(x["severity"], 9), -x["confidence"]))
    return alerts


def build_brief(*, alert_budget: int = DEFAULT_ALERT_BUDGET, log_candidates: bool = True) -> dict:
    alerts = collect_alerts(log_candidates=log_candidates)
    shown = alerts[:alert_budget]
    suppressed = max(0, len(alerts) - len(shown))
    eval_s = _eval_mod().summary()
    return {
        "ok": True,
        "framework": "ops_daily_brief",
        "stolen_format": (
            "Always-on assistant episode — narrow workflows, eval-first, tiered "
            "inference, recommend-first, precision>coverage (YT Xa1jm2VWEHk)"
        ),
        "source": {"youtube_music": "https://music.youtube.com/watch?v=Xa1jm2VWEHk"},
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "habit": "ops_daily_brief",
        "decision_ladder": [
            "rules_and_source_metadata",
            "cheap_classification",
            "structured_extraction",
            "premium_reasoning_only_if_material",
            "user_confirmation_for_external_actions",
        ],
        "alert_budget": alert_budget,
        "alerts_shown": shown,
        "alerts_suppressed": suppressed,
        "autonomy_default": "recommend_only",
        "never": [
            "auto-send email/WhatsApp",
            "alter calendars/purchases",
            "general-purpose do-anything chat as the product",
            "unbounded context instead of compact provenance-linked memory",
        ],
        "eval": {
            "events": eval_s.get("events"),
            "by_workflow": eval_s.get("by_workflow"),
        },
        "kpis": [
            "weekly_retained_ops_habit",
            "actionable_alert_precision",
            "correction_rate",
            "cost_per_fee_yes_outcome",
            "pct_users_granting_higher_autonomy",  # here: agent classes with approve
        ],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--alert-budget", type=int, default=DEFAULT_ALERT_BUDGET)
    p.add_argument("--no-log", action="store_true", help="do not append eval candidates")
    p.add_argument("--strict", action="store_true")
    args = p.parse_args(argv)
    out = build_brief(alert_budget=args.alert_budget, log_candidates=not args.no_log)
    print(json.dumps(out, indent=2, sort_keys=True))
    if args.strict and any(a["severity"] == "critical" for a in out["alerts_shown"]):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
