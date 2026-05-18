"""Time-series expiry-concentration gate.

The historical 50.7% single-expiry concentration (35/69 closed iron-condor
trades on 2026-04-02) was a sequential pattern — the trader kept re-picking
the same expiry over many weeks. The gateway's existing
``_check_expiry_concentration`` in ``src/risk/trade_gateway.py`` only handles
concurrent-position clustering and is incompatible with
``MAX_CONCURRENT_IRON_CONDORS = 2`` anyway (any two-IC setup is 50% per expiry
and would always trip a 40% threshold).

This module provides a complementary rolling-window check intended for the
entry path of every iron-condor trader script.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TRADES_LEDGER_PATH = PROJECT_ROOT / "data" / "trades.json"
RECENT_EXPIRY_LOOKBACK = 20


def check_recent_expiry_concentration(
    target_expiry: str,
    lookback: int = RECENT_EXPIRY_LOOKBACK,
    threshold: float | None = None,
    ledger_path: Path | None = None,
) -> tuple[bool, str]:
    """Return ``(True, reason)`` when the prospective entry tips rolling concentration over ``threshold``.

    Reads the last ``lookback`` closed iron-condor trades from
    ``data/trades.json``, adds the prospective new entry's expiry to the
    sample, then computes the share of the most-frequent expiry. Blocks when
    that share strictly exceeds ``threshold``.

    A sample size below 4 always returns ``(False, "")`` — too few historical
    entries to draw a concentration signal.
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

    closed_ics = [
        t
        for t in ledger.get("trades", [])
        if t.get("status") == "closed" and t.get("strategy") == "iron_condor"
    ]
    recent = closed_ics[-lookback:]
    recent_expiries = [(t.get("legs") or {}).get("expiry") for t in recent]
    sample = [e for e in recent_expiries if e] + [target_expiry]
    if len(sample) < 4:
        return False, ""

    counts = Counter(sample)
    most_expiry, most_count = counts.most_common(1)[0]
    share = most_count / len(sample)
    if share > threshold:
        return (
            True,
            f"Time-series concentration: {most_count}/{len(sample)} recent entries "
            f"on expiry {most_expiry} ({share * 100:.0f}%) "
            f"exceeds MAX_EXPIRY_CONCENTRATION_PCT={threshold * 100:.0f}%",
        )
    return False, ""
