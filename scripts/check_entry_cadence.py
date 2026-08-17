#!/usr/bin/env python3
"""Fail loudly when the paper validation cohort stops growing.

The validation workflow wraps its entry step in a shell swallow, so a regime
refusal, a crash, and an expired key all render as a green check. Between
2026-07-24 and 2026-08-10 that produced twelve silent sessions followed by five
gate-blocked ones, every run reporting success, while the cohort stayed at n=2.

This check reads the committed lifecycle journal and asks the only question the
run status cannot answer: has a new *validation* structure been opened recently
enough that the loop is plausibly working? Excluded / non-validation entries
do not reset the stall clock.

Exit codes:
    0  cadence healthy, or cohort already complete
    1  stalled beyond the allowed number of trading days
    2  required ledger missing or unreadable
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
ENTRY_JOURNAL = REPO_ROOT / "data" / "put_credit_entries.json"
PAIRED_LEDGER = REPO_ROOT / "data" / "trades.json"

# Cohort target from .claude/rules/kill-criteria.md.
COHORT_TARGET = 30
# Five sessions is one full trading week with no new structure. The observed
# blackout ran twelve, so this trips well before a failure becomes historical.
DEFAULT_MAX_STALL_DAYS = 5
ACTIVE_STRATEGY = "spy_put_credit"

# NYSE full-day closures used for stall counting (extend annually).
# Counting holidays as trading days would *overstate* stall and false-alarm.
US_MARKET_HOLIDAYS: frozenset[date] = frozenset(
    {
        # 2025
        date(2025, 1, 1),
        date(2025, 1, 20),
        date(2025, 2, 17),
        date(2025, 4, 18),
        date(2025, 5, 26),
        date(2025, 6, 19),
        date(2025, 7, 4),
        date(2025, 9, 1),
        date(2025, 11, 27),
        date(2025, 12, 25),
        # 2026
        date(2026, 1, 1),
        date(2026, 1, 19),
        date(2026, 2, 16),
        date(2026, 4, 3),
        date(2026, 5, 25),  # Memorial Day
        date(2026, 6, 19),
        date(2026, 7, 3),  # Independence Day observed
        date(2026, 9, 7),
        date(2026, 11, 26),
        date(2026, 12, 25),
        # 2027
        date(2027, 1, 1),
        date(2027, 1, 18),
        date(2027, 2, 15),
        date(2027, 3, 26),
        date(2027, 5, 31),
        date(2027, 6, 18),
        date(2027, 7, 5),
        date(2027, 9, 6),
        date(2027, 11, 25),
        date(2027, 12, 24),
    }
)


def _load_json(path: Path) -> Any:
    with path.open() as fh:
        return json.load(fh)


def _is_validation_row(row: dict[str, Any]) -> bool:
    """Entries/trades explicitly marked validation_phase=false are excluded."""
    if "validation_phase" not in row:
        return True
    val = row.get("validation_phase")
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() not in {"false", "0", "no", "n"}
    return bool(val)


def _entry_rows(payload: Any) -> list[dict]:
    """The journal has been both a bare list and an {'entries': [...]} map."""
    if isinstance(payload, list):
        rows: Any = payload
    elif isinstance(payload, dict):
        inner = payload.get("entries", payload)
        rows = list(inner.values()) if isinstance(inner, dict) else inner
    else:
        rows = []
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict) and _is_validation_row(r)]


def _parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def latest_entry_time(rows: list[dict]) -> datetime | None:
    stamps = [
        ts
        for r in rows
        for ts in (_parse_ts(r.get("entry_time") or r.get("filled_at")),)
        if ts is not None
    ]
    return max(stamps) if stamps else None


def _is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d not in US_MARKET_HOLIDAYS


def trading_days_between(start: date, end: date) -> int:
    """Market-session count strictly after `start` through `end`.

    Weekends and NYSE full-day holidays are excluded so holiday-shortened weeks
    do not false-alarm at the five-day stall threshold.
    """
    if end <= start:
        return 0
    days = 0
    cursor = start + timedelta(days=1)
    while cursor <= end:
        if _is_trading_day(cursor):
            days += 1
        cursor += timedelta(days=1)
    return days


def _is_put_credit_trade(row: dict[str, Any]) -> bool:
    blob = " ".join(
        str(row.get(k) or "")
        for k in ("strategy", "strategy_family", "structure", "type", "signature", "id")
    ).lower()
    if "iron_condor" in blob and "put_credit" not in blob and "bull_put" not in blob:
        return False
    return any(
        token in blob
        for token in (
            "spy_put_credit",
            "put_credit",
            "bull_put",
            "bull put",
            "pcs_",
        )
    )


def _is_closed(row: dict[str, Any]) -> bool:
    status = str(row.get("status") or "").lower()
    if status in {"closed", "filled_closed", "done"}:
        return True
    if row.get("exit_time") or row.get("exit_date"):
        return True
    if row.get("realized_pnl") is not None and status != "open":
        return status != "open"
    return False


def _trade_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [t for t in payload if isinstance(t, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("trades", "closed_trades", "paired", "trade_history"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [t for t in rows if isinstance(t, dict)]
    return []


def cohort_size(payload: Any) -> int:
    """Closed *validation* put-credit structures only.

    Prefer physical rows with validation_phase filter. Fall back to stats
    aggregate only when no trade rows are present (legacy ledgers).
    """
    rows = _trade_rows(payload)
    if rows:
        n = 0
        for r in rows:
            if not _is_put_credit_trade(r):
                continue
            if not _is_closed(r):
                continue
            if not _is_validation_row(r):
                continue
            n += 1
        return n

    if not isinstance(payload, dict):
        return 0
    stats = payload.get("stats")
    if not isinstance(stats, dict):
        return 0
    by_strategy = stats.get("by_strategy")
    if not isinstance(by_strategy, dict):
        return 0
    active = by_strategy.get(ACTIVE_STRATEGY)
    if not isinstance(active, dict):
        return 0
    try:
        return int(active.get("closed_trades", 0) or 0)
    except (TypeError, ValueError):
        return 0


def evaluate(
    *,
    entries_payload: Any,
    trades_payload: Any,
    today: date,
    max_stall_days: int,
) -> dict:
    rows = _entry_rows(entries_payload)
    latest = latest_entry_time(rows)
    n = cohort_size(trades_payload)
    complete = n >= COHORT_TARGET

    if latest is None:
        stall_days: int | None = None
        stalled = not complete
        detail = "no validation entry has ever been journaled"
    else:
        stall_days = trading_days_between(latest.date(), today)
        stalled = stall_days >= max_stall_days and not complete
        detail = f"last validation entry {latest.date().isoformat()}"

    return {
        "stalled": stalled,
        "stall_trading_days": stall_days,
        "max_stall_days": max_stall_days,
        "last_entry_time": latest.isoformat() if latest else None,
        "journaled_entries": len(rows),
        "cohort_closed": n,
        "cohort_target": COHORT_TARGET,
        "cohort_complete": complete,
        "detail": detail,
        "as_of": today.isoformat(),
        "validation_only": True,
    }


def _render(report: dict) -> str:
    lines = [
        "Entry cadence check",
        f"  as of              : {report['as_of']}",
        f"  last entry         : {report['last_entry_time'] or 'never'}",
        f"  stall (trading dys): {report['stall_trading_days']}"
        f" (allowed {report['max_stall_days']})",
        f"  journaled entries  : {report['journaled_entries']}",
        f"  cohort closed      : {report['cohort_closed']} of {report['cohort_target']}",
    ]
    if report["cohort_complete"]:
        lines.append("  RESULT: cohort target reached - cadence no longer gating")
    elif report["stalled"]:
        lines += [
            "",
            "  RESULT: STALLED - no new structure opened within the allowed window.",
            "  A green validation run does not mean an entry happened. Inspect the",
            "  entry-run logs for the gate decision before assuming a quiet market:",
            "    gh api repos/:owner/:repo/actions/workflows/325931964/runs",
        ]
    else:
        lines.append("  RESULT: healthy")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-stall-days",
        type=int,
        default=DEFAULT_MAX_STALL_DAYS,
        help=f"trading days without an entry before failing (default {DEFAULT_MAX_STALL_DAYS})",
    )
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="always exit 0; use for dashboards rather than alarms",
    )
    args = parser.parse_args(argv)

    try:
        entries_payload = _load_json(ENTRY_JOURNAL)
        trades_payload = _load_json(PAIRED_LEDGER)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Cannot read required ledger: {exc}", file=sys.stderr)
        return 2

    report = evaluate(
        entries_payload=entries_payload,
        trades_payload=trades_payload,
        today=datetime.now(UTC).date(),
        max_stall_days=args.max_stall_days,
    )

    print(json.dumps(report, indent=2) if args.json else _render(report))

    if args.report_only:
        return 0
    return 1 if report["stalled"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
