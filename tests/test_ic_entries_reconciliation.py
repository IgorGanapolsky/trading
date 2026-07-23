"""Guard: every open option structure must have an active strategy journal.

An IC needs an ``IC_<expiry>[_suffix]`` record, while the successor bull-put
spread needs an active ``PCS_<expiry>_*`` record. Without either owner, no
strategy exit loop can evaluate profit targets or stops. The journal files are
committed by the sync workflow, so CI catches the gap within one sync cycle.
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
    pcs_path = DATA_DIR / "put_credit_entries.json"
    pcs_entries = json.loads(pcs_path.read_text()) if pcs_path.exists() else {}

    expiries = set()
    for pos in positions:
        m = OPTION_SYMBOL.match(str(pos.get("symbol", "")))
        if m:
            expiries.add(m.group(1))

    def has_owner(expiry: str) -> bool:
        ic_prefix = f"IC_{expiry}"
        if any(key == ic_prefix or key.startswith(f"{ic_prefix}_") for key in entries):
            return True
        pcs_prefix = f"PCS_{expiry}_"
        return any(
            key.startswith(pcs_prefix)
            and isinstance(entry, dict)
            and str(entry.get("status") or "open").lower()
            not in {"closed", "cancelled", "rejected"}
            for key, entry in pcs_entries.items()
        )

    missing = sorted(expiry for expiry in expiries if not has_owner(expiry))
    assert not missing, (
        f"open option positions with no active IC or PCS journal owner: {missing} — "
        "the strategy exit managers cannot evaluate profit-target or stop-loss. "
        "Backfill the journal from broker order history."
    )
