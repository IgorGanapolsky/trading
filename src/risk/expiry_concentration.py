"""Time-series expiry-concentration gate.

The historical 50.7% single-expiry concentration (35/69 closed iron-condor
trades on 2026-04-02) was a sequential pattern — the trader kept re-picking
the same expiry over many weeks. The gateway's existing
``_check_expiry_concentration`` in ``src/risk/trade_gateway.py`` only handles
concurrent-position clustering and is incompatible with
``MAX_CONCURRENT_IRON_CONDORS = 2`` anyway (any two-IC setup is 50% per expiry
and would always trip a 40% threshold).

This module provides a complementary rolling-window check intended for the
entry path of every iron-condor trader script. The window is *calendar-time*
(entries within the last ``lookback_days``), not row-count: that way, if the
gate ever blocks every fresh entry, the historical cohort ages out naturally
instead of deadlocking the system.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TRADES_LEDGER_PATH = PROJECT_ROOT / "data" / "trades.json"

# Calendar-day window. Chosen to match the controlled-experiment cohort size
# (30 trades) — at one trade per day, 60 days yields ~30 entries even with
# weekends and FOMC blackouts removed. The 30-day version of this constant
# was rejected because at the moment of writing the entire 69-trade ledger
# is within 33 days, so a 30-day window would gate too aggressively right
# after the historical concentration ages out.
LOOKBACK_DAYS = 60


def _parse_iso(value: str | None) -> datetime | None:
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
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def check_recent_expiry_concentration(
    target_expiry: str,
    lookback_days: int = LOOKBACK_DAYS,
    threshold: float | None = None,
    ledger_path: Path | None = None,
    *,
    now: datetime | None = None,
) -> tuple[bool, str]:
    """Return ``(True, reason)`` when the prospective entry tips rolling concentration over ``threshold``.

    Considers closed iron-condor trades whose ``entry_time`` is within the
    last ``lookback_days`` of ``now``. Adds the prospective new entry's
    expiry, then computes the share of the most-frequent expiry. Blocks when
    that share strictly exceeds ``threshold``.

    A sample size below 4 always returns ``(False, "")`` — too few historical
    entries to draw a concentration signal. This is also the
    self-unblocking property: as historical entries age past
    ``lookback_days``, they leave the window and the gate naturally relaxes.
    """
    if threshold is None:
        try:
            from src.core.trading_constants import MAX_EXPIRY_CONCENTRATION_PCT

            threshold = MAX_EXPIRY_CONCENTRATION_PCT
        except ImportError:
            threshold = 0.40

    ledger_path = ledger_path or TRADES_LEDGER_PATH
    if not ledger_path.exists():
        return False, ""

    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False, ""

    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=lookback_days)

    recent_expiries: list[str] = []
    for t in ledger.get("trades", []):
        if t.get("status") != "closed" or t.get("strategy") != "iron_condor":
            continue
        entry_dt = _parse_iso(t.get("entry_time")) or _parse_iso(t.get("entry_date"))
        if entry_dt is None or entry_dt < cutoff:
            continue
        expiry = (t.get("legs") or {}).get("expiry")
        if expiry:
            recent_expiries.append(expiry)

    sample = recent_expiries + [target_expiry]
    if len(sample) < 4:
        return False, ""

    counts = Counter(sample)
    most_expiry, most_count = counts.most_common(1)[0]
    share = most_count / len(sample)
    if share > threshold:
        return (
            True,
            f"Time-series concentration: {most_count}/{len(sample)} entries in last "
            f"{lookback_days}d on expiry {most_expiry} ({share * 100:.0f}%) "
            f"exceeds MAX_EXPIRY_CONCENTRATION_PCT={threshold * 100:.0f}%",
        )
    return False, ""
