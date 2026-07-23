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
INACTIVE = {"closed", "cancelled", "rejected"}


def _pcs_expiries(pcs: dict) -> set[str]:
    out: set[str] = set()
    for key, entry in pcs.items():
        if not isinstance(entry, dict):
            continue
        if str(entry.get("status") or "open").strip().lower() in INACTIVE:
            continue
        exp = str(entry.get("expiry") or "")
        if len(exp) >= 10 and exp[4] == "-":
            y, m, d = exp[:10].split("-")
            out.add(f"{y[2:]}{m}{d}")
            continue
        m = re.search(r"(\d{6})", key)
        if m:
            out.add(m.group(1))
    return out


def _ic_expiries(entries: dict) -> set[str]:
    out: set[str] = set()
    for key in entries:
        if not str(key).startswith("IC_"):
            continue
        m = re.match(r"IC_(\d{6})", str(key))
        if m:
            out.add(m.group(1))
    return out


def test_open_option_positions_have_entry_records() -> None:
    state_path = DATA_DIR / "system_state.json"
    entries_path = DATA_DIR / "ic_entries.json"
    pcs_path = DATA_DIR / "put_credit_entries.json"
    if not state_path.exists() or not entries_path.exists():
        return

    positions = json.loads(state_path.read_text()).get("positions", [])
    entries = json.loads(entries_path.read_text())
    pcs = json.loads(pcs_path.read_text()) if pcs_path.exists() else {}
    covered = _ic_expiries(entries) | _pcs_expiries(pcs if isinstance(pcs, dict) else {})

    expiries: set[str] = set()
    for pos in positions:
        m = OPTION_SYMBOL.match(str(pos.get("symbol", "")))
        if m:
            expiries.add(m.group(1))

    missing = sorted(e for e in expiries if e not in covered)
    assert not missing, (
        f"open option positions with no active IC or PCS journal owner: {missing} — "
        "exit managers cannot evaluate profit-target/stop without a journal map. "
        "Backfill ic_entries.json (IC_*) or put_credit_entries.json (PCS)."
    )
