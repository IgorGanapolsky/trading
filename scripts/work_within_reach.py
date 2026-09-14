#!/usr/bin/env python3
"""Completed-task receipt for the paper put-credit factory (Astra FORMAT).

OpenAI GPT-6 Astra / Friar: the result that matters is the *completed task*,
with fewer retries and no unsupported conclusions. This script does **not**
subscribe to Astra or add OpenAI as a primary model.

Completed paper work = a broker-filled 1-lot SPY put-credit (journal
``status=open`` and ``credit_source=broker_fill`` / ``fill_confirmed_at``).
Dry-run plans, ``submitted_unconfirmed`` rows, and ``success: true`` JSON
without a fill are not completed tasks.

Usage:
  python scripts/work_within_reach.py --from-journal --json
  python scripts/work_within_reach.py --from-journal --execute-rc 0 --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_ENTRIES = ROOT / "data" / "put_credit_entries.json"
DEFAULT_KILL = ROOT / "data" / "runtime" / "strategy_kill_switch.json"
DEFAULT_OUT = ROOT / "data" / "audit" / "work_within_reach_latest.json"

KILLED_FAMILIES = frozenset({"ic_simple", "iron_condor"})
OPENAI_PRIMARY_FLAGS = frozenset({"1", "true", "yes", "astra", "gpt-6", "gpt6"})


def _load_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _entry_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        rows: list[dict[str, Any]] = []
        for key, value in payload.items():
            if isinstance(value, dict):
                row = dict(value)
                row.setdefault("key", key)
                rows.append(row)
        return rows
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def is_completed_paper_fill(entry: dict[str, Any]) -> bool:
    """True only when the journal row is a confirmed paper fill."""

    status = str(entry.get("status") or "").strip().lower()
    if status not in {"open", "filled"}:
        return False
    if entry.get("fill_confirmed_at") or entry.get("fill_confirmed") is True:
        return True
    return str(entry.get("credit_source") or "").strip().lower() == "broker_fill"


def _newest(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None

    def _ts(row: dict[str, Any]) -> str:
        return str(row.get("fill_confirmed_at") or row.get("entry_time") or "")

    return max(rows, key=_ts)


def evaluate_completed_task(
    entries: Any,
    *,
    execute_rc: int | None = None,
) -> dict[str, Any]:
    rows = _entry_rows(entries)
    completed = [row for row in rows if is_completed_paper_fill(row)]
    unconfirmed = [
        row
        for row in rows
        if str(row.get("status") or "").strip().lower() == "submitted_unconfirmed"
    ]
    newest = _newest(rows)
    reason = "has_confirmed_fill" if completed else "no_confirmed_fill_in_journal"

    ok = True
    if execute_rc == 0:
        ok = bool(newest) and is_completed_paper_fill(newest)
        reason = "execute_rc_0_fill_confirmed" if ok else "execute_rc_0_without_broker_fill"
    elif execute_rc in {1, 2}:
        ok = True
        reason = f"honest_skip_or_block_rc_{execute_rc}"
    elif execute_rc == 3:
        ok = False
        reason = "fatal_gate_rc_3"

    return {
        "ok": ok,
        "metric": "completed_task",
        "completed_n": len(completed),
        "unconfirmed_n": len(unconfirmed),
        "newest_key": (newest or {}).get("key"),
        "newest_status": (newest or {}).get("status"),
        "newest_credit_source": (newest or {}).get("credit_source"),
        "execute_rc": execute_rc,
        "reason": reason,
    }


def evaluate_attempt_efficiency(attempts: int, completed: int) -> dict[str, Any]:
    """Fewer retries is reported, not a license to invent fills."""

    ok = attempts >= 0 and completed >= 0 and completed <= attempts
    rate = (completed / attempts) if attempts else None
    return {
        "ok": ok,
        "metric": "attempt_efficiency",
        "attempts": attempts,
        "completed": completed,
        "rate": rate,
        "reason": "completed_le_attempts" if ok else "invalid_attempt_counts",
    }


def evaluate_capital_discipline(
    kill: dict[str, Any] | None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """No live, no IC revival, no GPT-6 / OpenAI primary for this lab."""

    kill = kill or {}
    env = env if env is not None else dict(os.environ)
    blockers: list[str] = []
    if kill.get("paper_only") is False:
        blockers.append("paper_only=false")
    if kill.get("live_blocked") is False:
        blockers.append("live_blocked=false")
    family = str(kill.get("active_family") or "")
    if family in KILLED_FAMILIES:
        blockers.append(f"killed_family_active={family}")
    primary = str(env.get("TRADING_OPENAI_PRIMARY") or env.get("OPENAI_PRIMARY") or "").lower()
    if primary in OPENAI_PRIMARY_FLAGS:
        blockers.append("openai_primary")
    for key, value in env.items():
        kl = key.upper()
        if not value:
            continue
        if "GPT6" in kl or "GPT_6" in kl or "ASTRA" in kl:
            blockers.append(f"env_{key}")
            break
    return {
        "ok": not blockers,
        "metric": "capital_discipline",
        "blockers": blockers,
        "reason": "paper_only_live_blocked" if not blockers else "capital_gate",
    }


def evaluate_unsupported_assertion(honesty: dict[str, Any] | None) -> dict[str, Any]:
    """Refuse profitable/live-ready claims the ledger does not support (n<30)."""

    honesty = honesty or {}
    n = honesty.get("n_closed")
    if n is None:
        n = honesty.get("closed_n")
    try:
        n_closed = int(n or 0)
    except (TypeError, ValueError):
        n_closed = 0
    claims = [
        key
        for key in ("claim_profitable", "live_deposit_ready", "edge_claim_allowed")
        if honesty.get(key) is True
    ]
    ok = not (n_closed < 30 and claims)
    return {
        "ok": ok,
        "metric": "unsupported_assertion",
        "n_closed": n_closed,
        "claims": claims,
        "reason": "no_premature_edge_claim" if ok else "premature_edge_or_live_claim",
    }


def evaluate_all(
    *,
    entries: Any,
    kill: dict[str, Any] | None,
    honesty: dict[str, Any] | None,
    execute_rc: int | None,
    attempts: int | None,
    completed: int | None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    completed_task = evaluate_completed_task(entries, execute_rc=execute_rc)
    if attempts is None:
        attempts = int(completed_task["completed_n"]) + int(completed_task["unconfirmed_n"])
    if completed is None:
        completed = int(completed_task["completed_n"])
    metrics = [
        completed_task,
        evaluate_attempt_efficiency(attempts, completed),
        evaluate_capital_discipline(kill, env=env),
        evaluate_unsupported_assertion(honesty),
    ]
    ok = all(bool(item.get("ok")) for item in metrics)
    return {
        "ok": ok,
        "source": "openai-astra-friar-completed-task-format",
        "not": ["gpt-6-astra-product", "openai-api-primary", "chatgpt-work"],
        "evaluated_at": datetime.now(UTC).isoformat(),
        "metrics": metrics,
    }


def _honesty_from_scorecard(path: Path | None) -> dict[str, Any]:
    if path is None:
        try:
            from scripts.put_credit_cohort_scorecard import build_scorecard

            card = build_scorecard()
        except Exception:  # noqa: BLE001
            return {}
    else:
        card = _load_json(path)
        if not isinstance(card, dict):
            return {}
    closed = card.get("closed") if isinstance(card.get("closed"), dict) else {}
    kill = card.get("kill_criteria") if isinstance(card.get("kill_criteria"), dict) else {}
    n = closed.get("closed_n")
    if n is None:
        n = kill.get("n_closed")
    honesty = card.get("honesty") if isinstance(card.get("honesty"), dict) else {}
    return {
        "n_closed": n or 0,
        "claim_profitable": honesty.get("claim_profitable", False),
        "live_deposit_ready": honesty.get("live_deposit_ready", False),
        "edge_claim_allowed": honesty.get("edge_claim_allowed", False),
    }


def _parse_execute_rc(raw: str | None, rc_file: Path | None) -> int | None:
    if rc_file is not None and rc_file.is_file():
        text = rc_file.read_text(encoding="utf-8").strip().splitlines()
        raw = text[0] if text else raw
    if raw is None or raw == "" or raw == "dry":
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-journal", action="store_true")
    parser.add_argument("--entries", type=Path, default=DEFAULT_ENTRIES)
    parser.add_argument("--kill-switch", type=Path, default=DEFAULT_KILL)
    parser.add_argument("--scorecard", type=Path, default=None)
    parser.add_argument("--execute-rc", default=None)
    parser.add_argument("--execute-rc-file", type=Path, default=None)
    parser.add_argument("--attempts", type=int, default=None)
    parser.add_argument("--completed", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    if not args.from_journal:
        parser.error("--from-journal is required (this is not a model router)")

    entries = _load_json(args.entries) or {}
    kill = _load_json(args.kill_switch) or {}
    honesty = _honesty_from_scorecard(args.scorecard)
    execute_rc = _parse_execute_rc(args.execute_rc, args.execute_rc_file)
    report = evaluate_all(
        entries=entries,
        kill=kill if isinstance(kill, dict) else {},
        honesty=honesty,
        execute_rc=execute_rc,
        attempts=args.attempts,
        completed=args.completed,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(
            f"ok={report['ok']} metrics={[m['metric'] + ':' + str(m['ok']) for m in report['metrics']]}"
        )
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
