#!/usr/bin/env python3
"""Eval-first ledger for agent alerts/residuals (always-on assistant FORMAT).

Episode thesis (YT Music Xa1jm2VWEHk): the product heart is the eval/improvement
loop — log every candidate alert, user action, correction, dismissal, outcome.
Optimize precision by *workflow*, not generic agent quality.

EXIT 0 always for report. EXIT 2 with --strict if precision below floor.
"""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "data" / "runtime" / "eval_first_ledger.jsonl"

# Narrow workflows only (priority 1 from episode)
WORKFLOWS = frozenset(
    {
        "cash_fee_yes",
        "dial_path",
        "pr_ci_block",
        "inventory_hygiene",
        "fanout_memory",
        "trading_halt",
        "ops_brief",
    }
)

TERMINAL_ACTIONS = frozenset(
    {"approved", "dismissed", "corrected", "outcome_yes", "outcome_no", "expired"}
)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def append_event(row: dict, *, path: Path = LEDGER) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = dict(row)
    row.setdefault("id", str(uuid.uuid4())[:12])
    row.setdefault("ts", _now())
    if row.get("workflow") not in WORKFLOWS:
        raise ValueError(f"workflow must be one of {sorted(WORKFLOWS)}")
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def load_events(*, path: Path = LEDGER) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def precision_by_workflow(events: list[dict] | None = None) -> dict:
    """Precision = approved+outcome_yes / (approved+dismissed+outcome_*), per workflow."""
    events = events if events is not None else load_events()
    by_wf: dict[str, dict] = {}
    for e in events:
        wf = e.get("workflow") or "unknown"
        bucket = by_wf.setdefault(
            wf, {"candidates": 0, "approved": 0, "dismissed": 0, "corrected": 0, "outcomes": 0}
        )
        kind = e.get("kind")
        if kind == "candidate":
            bucket["candidates"] += 1
        elif kind == "action":
            act = e.get("action")
            if act == "approved":
                bucket["approved"] += 1
            elif act == "dismissed":
                bucket["dismissed"] += 1
            elif act == "corrected":
                bucket["corrected"] += 1
            elif act in {"outcome_yes", "outcome_no"}:
                bucket["outcomes"] += 1
                if act == "outcome_yes":
                    bucket["approved"] += 0  # already counted separately
                    bucket["outcome_yes"] = bucket.get("outcome_yes", 0) + 1
                else:
                    bucket["outcome_no"] = bucket.get("outcome_no", 0) + 1

    report = {}
    for wf, b in by_wf.items():
        judged = b["approved"] + b["dismissed"]
        precision = (b["approved"] / judged) if judged else None
        report[wf] = {
            **b,
            "precision": round(precision, 4) if precision is not None else None,
            "judged": judged,
        }
    return report


def summary(*, path: Path = LEDGER, min_precision: float = 0.5) -> dict:
    events = load_events(path=path)
    by_wf = precision_by_workflow(events)
    breaches = []
    for wf, stats in by_wf.items():
        p = stats.get("precision")
        if p is not None and stats.get("judged", 0) >= 5 and p < min_precision:
            breaches.append(
                {
                    "workflow": wf,
                    "precision": p,
                    "threshold": min_precision,
                    "why": "Episode: prioritize alert precision over coverage — mute risk",
                }
            )
    return {
        "ok": len(breaches) == 0,
        "framework": "eval_first_ledger",
        "stolen_format": (
            "Always-on consumer AI assistant episode — eval/improvement loop is the "
            "product heart (YT Xa1jm2VWEHk); not a family-assistant SKU"
        ),
        "source": {"youtube_music": "https://music.youtube.com/watch?v=Xa1jm2VWEHk"},
        "ledger": str(path),
        "events": len(events),
        "by_workflow": by_wf,
        "breaches": breaches,
        "kpis": [
            "actionable_alert_precision",
            "correction_rate",
            "cost_per_retained_outcome",
            "weekly_retained_workflows",
        ],
        "ts": _now(),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("candidate", help="log a candidate alert")
    c.add_argument("--workflow", required=True, choices=sorted(WORKFLOWS))
    c.add_argument("--title", required=True)
    c.add_argument("--provenance", required=True, help="source path or URL")
    c.add_argument("--confidence", type=float, default=0.5)
    c.add_argument("--tier", default="rules", help="rules|cheap|extract|premium")

    a = sub.add_parser("action", help="log approve/dismiss/correct/outcome")
    a.add_argument("--workflow", required=True, choices=sorted(WORKFLOWS))
    a.add_argument("--action", required=True, choices=sorted(TERMINAL_ACTIONS))
    a.add_argument("--candidate-id", default="")
    a.add_argument("--note", default="")

    s = sub.add_parser("summary", help="precision by workflow")
    s.add_argument("--min-precision", type=float, default=0.5)
    s.add_argument("--strict", action="store_true")

    args = p.parse_args(argv)
    if args.cmd == "candidate":
        row = append_event(
            {
                "kind": "candidate",
                "workflow": args.workflow,
                "title": args.title,
                "provenance": args.provenance,
                "confidence": args.confidence,
                "tier": args.tier,
                "status": "open",
            }
        )
        print(json.dumps(row, indent=2, sort_keys=True))
        return 0
    if args.cmd == "action":
        row = append_event(
            {
                "kind": "action",
                "workflow": args.workflow,
                "action": args.action,
                "candidate_id": args.candidate_id,
                "note": args.note,
            }
        )
        print(json.dumps(row, indent=2, sort_keys=True))
        return 0
    if args.cmd == "summary":
        out = summary(min_precision=args.min_precision)
        print(json.dumps(out, indent=2, sort_keys=True))
        if args.strict and not out["ok"]:
            return 2
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
