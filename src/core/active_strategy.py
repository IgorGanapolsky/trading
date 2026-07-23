"""Active strategy selector — kill dead families without pretending they still have edge.

IC Simple (4-leg iron condor) is KILLED as a North Star candidate after the lifetime
paired ledger failed (WR ~17%, PF 0.70, negative expectancy over 170+ closed trades).
Successor validation family: spy_put_credit (2-leg SPY bull put, 1-lot, paper only).

This module is the single switch operators and entry scripts consult before opening
new risk. Exit/management of already-open legs remains allowed.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = REPO_ROOT / "data" / "runtime"
KILL_FILE = RUNTIME_DIR / "strategy_kill_switch.json"
HYPOTHESIS_FILE = RUNTIME_DIR / "strategy_validation_hypothesis.json"

# Default if kill-switch file missing: IC is dead; put-credit is the only entry path.
DEFAULT_ACTIVE_FAMILY = "spy_put_credit"
DEFAULT_KILLED_FAMILIES = ("ic_simple", "iron_condor")


@dataclass(frozen=True)
class StrategyKillState:
    active_family: str
    killed_families: tuple[str, ...]
    reason: str
    successor: str
    paper_only: bool
    live_blocked: bool

    def is_killed(self, family: str) -> bool:
        return str(family or "").strip().lower() in {f.lower() for f in self.killed_families}

    def allows_new_entries(self, family: str) -> bool:
        fam = str(family or "").strip().lower()
        if self.is_killed(fam):
            return False
        return fam == self.active_family.lower()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def load_kill_state() -> StrategyKillState:
    """Load kill switch + hypothesis; env ACTIVE_STRATEGY_FAMILY can override active."""
    payload = _load_json(KILL_FILE)
    hypothesis = _load_json(HYPOTHESIS_FILE)

    killed = payload.get("killed_families") or list(DEFAULT_KILLED_FAMILIES)
    if isinstance(killed, str):
        killed = [killed]
    killed_t = tuple(str(x).strip().lower() for x in killed if str(x).strip())

    active = (
        os.getenv("ACTIVE_STRATEGY_FAMILY")
        or payload.get("active_family")
        or (hypothesis.get("strategy_family") if hypothesis.get("enabled") is True else None)
        or DEFAULT_ACTIVE_FAMILY
    )
    active = str(active).strip().lower()

    reason = str(
        payload.get("reason")
        or "IC Simple killed: lifetime negative expectancy / PF<1 on paired ledger"
    )
    successor = str(payload.get("successor_family") or DEFAULT_ACTIVE_FAMILY).strip().lower()
    paper_only = bool(payload.get("paper_only", True))
    live_blocked = bool(payload.get("live_blocked", True))

    # Never allow a killed family to be "active" even via env typo.
    if active in killed_t:
        active = successor if successor not in killed_t else DEFAULT_ACTIVE_FAMILY

    return StrategyKillState(
        active_family=active,
        killed_families=killed_t or DEFAULT_KILLED_FAMILIES,
        reason=reason,
        successor=successor,
        paper_only=paper_only,
        live_blocked=live_blocked,
    )


def assert_entry_allowed(family: str) -> None:
    """Raise RuntimeError if family may not open new risk."""
    state = load_kill_state()
    fam = str(family or "").strip().lower()
    if state.is_killed(fam):
        raise RuntimeError(
            f"STRATEGY_KILLED: {fam} may not open new risk. {state.reason} "
            f"Successor: {state.successor}. Manage existing positions only."
        )
    if not state.allows_new_entries(fam):
        raise RuntimeError(
            f"STRATEGY_NOT_ACTIVE: {fam} is not the active validation family "
            f"(active={state.active_family})."
        )


def entry_block_message(family: str) -> str | None:
    """Return a human block reason, or None if entries are allowed."""
    try:
        assert_entry_allowed(family)
    except RuntimeError as exc:
        return str(exc)
    return None
