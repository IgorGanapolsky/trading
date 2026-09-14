#!/usr/bin/env python3
"""Observe persistent paper-factory assets (Dagster health/freshness FORMAT).

docs.dagster.io: an asset is an object in persistent storage. Prefer
*observations* of external systems over fake materializations (those consume
Dagster+ credits; we are not on Dagster+). Health is the most elevated of
latest materialization, freshness, and asset checks.

This does **not** vendor dagster, run Dagit, or clone PR #4639's in-memory
SDA engine (Makefile / src/ops/dagster_asset_engine.py).

Usage:
  python scripts/observe_paper_assets.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_ENTRIES = ROOT / "data" / "put_credit_entries.json"
DEFAULT_STATE = ROOT / "data" / "system_state.json"
DEFAULT_KILL = ROOT / "data" / "runtime" / "strategy_kill_switch.json"
DEFAULT_OUT = ROOT / "data" / "audit" / "paper_asset_health_latest.json"

HEALTH_RANK = {"unknown": 0, "healthy": 1, "warning": 2, "degraded": 3}
FRESH_WARN = timedelta(hours=24)
FRESH_FAIL = timedelta(hours=72)
KILLED = frozenset({"ic_simple", "iron_condor"})


def _load_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _mtime(path: Path) -> datetime | None:
    if not path.is_file():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)


def _elevate(*statuses: str) -> str:
    return max(statuses, key=lambda s: HEALTH_RANK.get(s, 0))


def _freshness(as_of: datetime, last: datetime | None) -> dict[str, Any]:
    if last is None:
        return {"status": "unknown", "age_hours": None, "reason": "never_materialized"}
    age = as_of - last
    hours = round(age.total_seconds() / 3600, 3)
    if age > FRESH_FAIL:
        return {"status": "degraded", "age_hours": hours, "reason": "stale_gt_72h"}
    if age > FRESH_WARN:
        return {"status": "warning", "age_hours": hours, "reason": "stale_gt_24h"}
    return {"status": "healthy", "age_hours": hours, "reason": "fresh"}


def _check(name: str, passed: bool, *, severity: str, description: str) -> dict[str, Any]:
    return {
        "name": name,
        "passed": passed,
        "severity": severity,
        "description": description,
    }


def _checks_health(checks: list[dict[str, Any]]) -> str:
    if not checks:
        return "unknown"
    if any(not c["passed"] and c["severity"] == "ERROR" for c in checks):
        return "degraded"
    if any(not c["passed"] and c["severity"] == "WARN" for c in checks):
        return "warning"
    return "healthy"


def observe_kill_switch(payload: Any, *, as_of: datetime, path: Path) -> dict[str, Any]:
    last = _mtime(path)
    kill = payload if isinstance(payload, dict) else {}
    materialized = "healthy" if payload is not None else "unknown"
    checks = [
        _check(
            "live_blocked",
            kill.get("live_blocked") is not False,
            severity="ERROR",
            description="live capital stays blocked until EDGE_CANDIDATE",
        ),
        _check(
            "paper_only",
            kill.get("paper_only") is not False,
            severity="ERROR",
            description="paper validation only",
        ),
        _check(
            "active_family_not_killed",
            str(kill.get("active_family") or "") not in KILLED,
            severity="ERROR",
            description="iron condor / ic_simple cannot be the active family",
        ),
    ]
    fresh = _freshness(as_of, last)
    health = _elevate(materialized, fresh["status"], _checks_health(checks))
    return {
        "key": "policy/kill_switch",
        "kind": "observation",
        "health": health,
        "last_observed_at": last.isoformat() if last else None,
        "freshness": fresh,
        "checks": checks,
        "metadata": {
            "active_family": kill.get("active_family"),
            "paper_only": kill.get("paper_only"),
            "live_blocked": kill.get("live_blocked"),
        },
    }


def observe_system_state(payload: Any, *, as_of: datetime, path: Path) -> dict[str, Any]:
    state = payload if isinstance(payload, dict) else {}
    last = _parse_dt(str(state.get("last_updated") or "")) or _mtime(path)
    paper = state.get("paper_account") if isinstance(state.get("paper_account"), dict) else {}
    live = state.get("live_account") if isinstance(state.get("live_account"), dict) else {}
    positions = state.get("positions") if isinstance(state.get("positions"), list) else []
    materialized = "healthy" if payload is not None else "unknown"
    live_eq = live.get("equity")
    try:
        live_is_zero = float(live_eq or 0) == 0.0
    except (TypeError, ValueError):
        live_is_zero = False
    checks = [
        _check(
            "live_equity_zero",
            live_is_zero,
            severity="WARN",
            description="live account is $0; paper P/L is not cash",
        ),
        _check(
            "has_last_updated",
            last is not None,
            severity="ERROR",
            description="broker snapshot must carry last_updated",
        ),
    ]
    fresh = _freshness(as_of, last)
    health = _elevate(materialized, fresh["status"], _checks_health(checks))
    return {
        "key": "broker/system_state",
        "kind": "observation",
        "health": health,
        "last_observed_at": last.isoformat() if last else None,
        "freshness": fresh,
        "checks": checks,
        "metadata": {
            "paper_equity": paper.get("equity"),
            "paper_positions": paper.get("positions_count") or len(positions),
            "live_equity": live_eq,
        },
    }


def observe_journal(payload: Any, *, as_of: datetime, path: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(value, dict):
                row = dict(value)
                row.setdefault("key", key)
                rows.append(row)
    last = None
    for row in rows:
        for field in ("fill_confirmed_at", "entry_time"):
            dt = _parse_dt(str(row.get(field) or "") if row.get(field) else None)
            if dt and (last is None or dt > last):
                last = dt
    if last is None:
        last = _mtime(path)
    newest = max(rows, key=lambda r: str(r.get("entry_time") or ""), default=None)
    confirmed = [
        r
        for r in rows
        if r.get("fill_confirmed_at") or str(r.get("credit_source") or "").lower() == "broker_fill"
    ]
    unconfirmed = [r for r in rows if str(r.get("status") or "").lower() == "submitted_unconfirmed"]
    materialized = "healthy" if confirmed else ("warning" if rows else "unknown")
    checks = [
        _check(
            "newest_not_unconfirmed",
            not (
                newest is not None
                and str(newest.get("status") or "").lower() == "submitted_unconfirmed"
            ),
            severity="WARN",
            description="newest journal row is submitted_unconfirmed (not a completed fill)",
        ),
        _check(
            "has_broker_fill",
            bool(confirmed),
            severity="WARN",
            description="at least one broker_fill row exists",
        ),
    ]
    fresh = _freshness(as_of, last)
    health = _elevate(materialized, fresh["status"], _checks_health(checks))
    return {
        "key": "ledger/put_credit_journal",
        "kind": "observation",
        "health": health,
        "last_observed_at": last.isoformat() if last else None,
        "freshness": fresh,
        "checks": checks,
        "metadata": {
            "rows": len(rows),
            "confirmed_fills": len(confirmed),
            "unconfirmed": len(unconfirmed),
            "newest_key": (newest or {}).get("key"),
            "newest_status": (newest or {}).get("status"),
        },
    }


def observe_all(
    *,
    entries: Any,
    state: Any,
    kill: Any,
    entries_path: Path,
    state_path: Path,
    kill_path: Path,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    as_of = as_of or datetime.now(UTC)
    assets = [
        observe_kill_switch(kill, as_of=as_of, path=kill_path),
        observe_system_state(state, as_of=as_of, path=state_path),
        observe_journal(entries, as_of=as_of, path=entries_path),
    ]
    overall = _elevate(*(a["health"] for a in assets)) if assets else "unknown"
    error_fails = [
        f"{a['key']}:{c['name']}"
        for a in assets
        for c in a["checks"]
        if not c["passed"] and c["severity"] == "ERROR"
    ]
    return {
        "ok": overall != "degraded",
        "health": overall,
        "kind": "observation",
        "source": "docs.dagster.io-asset-health-freshness-format",
        "not": ["dagster-plus", "dagit", "openlineage", "in-memory-sda-engine"],
        "new_entry_allowed": not error_fails,
        "blocking_checks": error_fails,
        "observed_at": as_of.isoformat(),
        "assets": assets,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entries", type=Path, default=DEFAULT_ENTRIES)
    parser.add_argument("--system-state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--kill-switch", type=Path, default=DEFAULT_KILL)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--as-of",
        default=None,
        help="ISO timestamp for tests; default now UTC",
    )
    args = parser.parse_args()
    as_of = _parse_dt(args.as_of) if args.as_of else datetime.now(UTC)
    report = observe_all(
        entries=_load_json(args.entries),
        state=_load_json(args.system_state),
        kill=_load_json(args.kill_switch),
        entries_path=args.entries,
        state_path=args.system_state,
        kill_path=args.kill_switch,
        as_of=as_of,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(
            f"health={report['health']} new_entry_allowed={report['new_entry_allowed']} "
            f"blocking={report['blocking_checks']}"
        )
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
