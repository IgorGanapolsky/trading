"""Two-ceiling honesty stolen from Claude Code /limit-reset FORMAT.

Session/daily structure cap ≠ cohort/weekly gate. Resetting the daily cap does
not increase cohort n, does not clear the kill switch, and does not unblock live.
`/reset-weekly` and `/reset-kill-switch` do not exist. Do not invent them.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Mapping

from src.core.active_strategy import StrategyKillState, load_kill_state
from src.core.trading_profiles import PutCreditProfile, get_put_credit_profile

COHORT_GATE_N = 30
ACTIVE_FAMILY = "spy_put_credit"
FORBIDDEN_RESETS = (
    "reset-weekly",
    "reset-kill-switch",
    "reset-live-block",
    "no-limits",
)


def _parse_dt(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def count_entries_on_date(
    entries: Mapping[str, Any] | None,
    *,
    day: datetime,
) -> int:
    if not isinstance(entries, Mapping):
        return 0
    target = day.astimezone(UTC).date()
    count = 0
    for row in entries.values():
        if not isinstance(row, Mapping):
            continue
        stamp = _parse_dt(row.get("entry_time") or row.get("filled_at"))
        if stamp is not None and stamp.date() == target:
            count += 1
    return count


def count_open_entries(entries: Mapping[str, Any] | None) -> int:
    if not isinstance(entries, Mapping):
        return 0
    open_count = 0
    for row in entries.values():
        if not isinstance(row, Mapping):
            continue
        if (
            row.get("exit_time")
            or row.get("closed_at")
            or str(row.get("status") or "").lower()
            in {
                "closed",
                "exited",
            }
        ):
            continue
        open_count += 1
    return open_count


def count_put_credit_cohort(trades: list[Any] | None) -> int:
    """Paired closed spy_put_credit rows only. Never use trades.json.stats.closed_trades."""

    if not isinstance(trades, list):
        return 0
    count = 0
    for row in trades:
        if not isinstance(row, Mapping):
            continue
        family = str(row.get("strategy") or row.get("strategy_family") or "").strip().lower()
        if family != ACTIVE_FAMILY:
            continue
        status = str(row.get("status") or "closed").strip().lower()
        if status and status not in {"closed", "exited", "done"}:
            continue
        count += 1
    return count


def build_ceiling_report(
    *,
    profile: PutCreditProfile | None = None,
    kill_state: StrategyKillState | None = None,
    entries: Mapping[str, Any] | None = None,
    trades: list[Any] | None = None,
    now: datetime | None = None,
    entries_present: bool = True,
    trades_present: bool = True,
) -> dict[str, Any]:
    """JSON report. Missing files stay missing — never fill with invented zeros-as-proof."""

    resolved_profile = profile or get_put_credit_profile()
    resolved_kill = kill_state or load_kill_state()
    stamp = now or datetime.now(UTC)

    daily_used = count_entries_on_date(entries, day=stamp) if entries_present else None
    concurrent_used = count_open_entries(entries) if entries_present else None
    cohort_used = count_put_credit_cohort(trades) if trades_present else None

    daily_cap = int(resolved_profile.max_daily_structures)
    concurrent_cap = int(resolved_profile.max_concurrent_positions)

    daily_remaining = None if daily_used is None else max(0, daily_cap - daily_used)
    concurrent_remaining = (
        None if concurrent_used is None else max(0, concurrent_cap - concurrent_used)
    )
    cohort_remaining = None if cohort_used is None else max(0, COHORT_GATE_N - cohort_used)

    return {
        "schema": "two-ceiling-honesty/1",
        "source": "explainx.ai /limit-reset FORMAT; not Claude Code; not a usage reset",
        "as_of": stamp.isoformat(),
        "family": ACTIVE_FAMILY,
        "paper_only": bool(resolved_kill.paper_only),
        "live_blocked": bool(resolved_kill.live_blocked),
        "session_analog": {
            "name": "max_daily_structures",
            "cap": daily_cap,
            "used": daily_used,
            "remaining": daily_remaining,
            "note": "Like a 5-hour session cap: a daily reset is a scheduling unlock, not more risk budget.",
        },
        "concurrent_ceiling": {
            "name": "max_concurrent_positions",
            "cap": concurrent_cap,
            "used": concurrent_used,
            "remaining": concurrent_remaining,
        },
        "weekly_analog": {
            "name": "put_credit_cohort_n",
            "cap": COHORT_GATE_N,
            "used": cohort_used,
            "remaining": cohort_remaining,
            "counts_strategy": ACTIVE_FAMILY,
            "excludes": "trades.json.stats.closed_trades (includes killed iron_condor)",
            "note": "Resetting the daily cap does not increase cohort n or unblock live.",
        },
        "resetting_session_increases_weekly": False,
        "forbidden_resets": list(FORBIDDEN_RESETS),
        "invented_commands_do_not_exist": True,
        "live_unblocked": False,
    }
