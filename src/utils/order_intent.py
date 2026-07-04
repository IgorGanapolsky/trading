"""OPEN/CLOSE intent stamping for Alpaca `client_order_id`.

Background (LL-354)
-------------------
When the guardian closes an iron condor leg-by-leg, Alpaca returns SIMPLE
rows whose ``position_intent`` is ``None``. The paired-ledger sync then has
to reverse-lookup intent from open parent-lots, and singleton closes that
don't match any expected-close pattern are silently dropped — under-
reporting realized P/L by ~$2.6K (broker truth -$6,570 vs ledger -$3,958).

Fix: stamp our own intent on every order at submission via
``client_order_id`` (free-form, broker round-trips it). Format::

    IC-{ROLE}-{INTENT}-{LEGTAG}-{NANOS}

Examples:
    IC-OPEN-IC--1748549812345678901          (4-leg MLEG parent)
    IC-OPEN-BPS-SP-1748549812345678901       (short put leg of an open)
    IC-CLOSE-BPS-SP-1748549812345678901      (singleton close of that leg)

This module is pure-function and free of side effects so it can be imported
from `trade_gateway`, `iron_condor_trader`, `ic_simple`, `iron_condor_guardian`,
and `sync_closed_positions` without circular deps.
"""

from __future__ import annotations

import itertools
import re
import threading
import time
from typing import Final

_COUNTER = itertools.count()
_COUNTER_LOCK = threading.Lock()

# Alpaca caps client_order_id at 128 chars.
MAX_CLIENT_ORDER_ID_LEN: Final[int] = 128

VALID_ROLES: Final[frozenset[str]] = frozenset({"OPEN", "CLOSE"})
VALID_INTENTS: Final[frozenset[str]] = frozenset({"BPS", "BPL", "BCS", "BCL", "IC"})
VALID_LEG_TAGS: Final[frozenset[str]] = frozenset({"SP", "LP", "SC", "LC"})

_PATTERN = re.compile(r"^IC-(OPEN|CLOSE)-(BPS|BPL|BCS|BCL|IC)-([A-Z]{0,4})-(\d+)$")


def build_client_order_id(role: str, intent: str, leg_tag: str | None = None) -> str:
    """Build an `IC-{ROLE}-{INTENT}-{LEGTAG}-{NANOS}` client_order_id.

    ``leg_tag`` is optional (empty for the 4-leg combo parent). Guaranteed
    unique per call via ``time.time_ns()`` + monotonic counter. Result is
    <= 128 chars.
    """
    if role not in VALID_ROLES:
        raise ValueError(f"role must be one of {sorted(VALID_ROLES)}, got {role!r}")
    if intent not in VALID_INTENTS:
        raise ValueError(f"intent must be one of {sorted(VALID_INTENTS)}, got {intent!r}")
    tag = leg_tag or ""
    if tag and tag not in VALID_LEG_TAGS:
        raise ValueError(f"leg_tag must be one of {sorted(VALID_LEG_TAGS)} or None, got {tag!r}")
    # nanos suffix: time_ns()*1000 + monotonic counter. time_ns() alone has
    # microsecond resolution on macOS, so a tight loop collides; counter
    # guarantees uniqueness without changing the digits-only suffix shape.
    with _COUNTER_LOCK:
        seq = next(_COUNTER) % 1000
    cid = f"IC-{role}-{intent}-{tag}-{time.time_ns() * 1000 + seq}"
    if len(cid) > MAX_CLIENT_ORDER_ID_LEN:  # defensive; ~30 chars in practice
        raise ValueError(f"client_order_id exceeds {MAX_CLIENT_ORDER_ID_LEN} chars")
    return cid


def parse_client_order_id(value: str | None) -> dict | None:
    """Parse a stamped client_order_id back into its components.

    Returns ``{"role", "intent", "leg_tag", "nanos"}`` on success, ``None``
    when the input doesn't match our format (other broker IDs, legacy rows,
    or non-IC strategies). Never raises.
    """
    if not isinstance(value, str) or not value:
        return None
    m = _PATTERN.match(value)
    if not m:
        return None
    role, intent, leg_tag, nanos = m.groups()
    return {
        "role": role,
        "intent": intent,
        "leg_tag": leg_tag or None,
        "nanos": int(nanos),
    }
