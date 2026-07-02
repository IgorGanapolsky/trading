"""Guard: every open option structure must have an ic_entries.json record.

The exit loop in scripts/ic_simple.py holds a position blind (no
profit-target, no stop evaluation — only the 7-DTE failsafe) when
IC_<expiry> is missing from data/ic_entries.json. The SPY 2026-07-31 IC
sat unmanaged from Jun 24 to Jul 2 2026 this way. Both files are
committed by the sync workflows, so CI can catch the gap within one
sync cycle.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
OPTION_SYMBOL = re.compile(r"^SPY(\d{6})[CP]\d{8}$")


def test_open_option_positions_have_entry_records() -> None:
    state_path = DATA_DIR / "system_state.json"
    entries_path = DATA_DIR / "ic_entries.json"
    if not state_path.exists() or not entries_path.exists():
        return

    positions = json.loads(state_path.read_text()).get("positions", [])
    entries = json.loads(entries_path.read_text())

    expiries = set()
    for pos in positions:
        m = OPTION_SYMBOL.match(str(pos.get("symbol", "")))
        if m:
            expiries.add(m.group(1))

    missing = sorted(e for e in expiries if f"IC_{e}" not in entries)
    assert not missing, (
        f"open option positions with no ic_entries.json record: {missing} — "
        "the ic_simple exit loop cannot evaluate profit-target or stop-loss "
        "for these (holds blind until 7-DTE failsafe). Backfill from broker "
        "order history (see IC_260731 backfill, 2026-07-02)."
    )
