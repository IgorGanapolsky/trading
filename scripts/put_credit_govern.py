#!/usr/bin/env python3
"""Decisions UO FORMAT steal for spy_put_credit — not a Decisions/BOAT clone.

Process state lives OUTSIDE the agent (journal + system_state + gate modules).
Instructions / prompts are NOT control. Rules run before action
(``mandatory_trade_gate``). The record answers where / stuck / next.

Paper factory when occupancy < max_concurrent. Never live ``--execute``.

Source FORMAT: Decisions *Who Governs the Machines?* (Gartner UO).
Linear: AGENT-606.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SCHEMA_VERSION = 1
WE_ARE_NOT = (
    "Decisions universal orchestrator product",
    "Gartner BOAT platform",
    "ThumbGate UO SKU / control-plane clone",
)


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _occupancy_from_entries(entries: dict[str, Any]) -> dict[str, Any]:
    """Reuse spy_put_credit concurrency semantics without submitting orders."""
    from scripts.spy_put_credit import evaluate_entry_limits

    return evaluate_entry_limits(entries)


def _regime_snapshot() -> dict[str, Any]:
    try:
        from src.risk.put_credit_regime import capture_regime_snapshot, evaluate_regime_gate

        snap = capture_regime_snapshot()
        gate = evaluate_regime_gate(snap)
        return {
            "allowed": bool(gate.get("allowed")),
            "blockers": list(gate.get("blockers") or []),
            "soft_flags": list(gate.get("soft_flags") or []),
        }
    except Exception as exc:  # noqa: BLE001 — doctor must stay fail-closed readable
        return {"allowed": False, "blockers": [f"regime_unavailable:{exc}"], "soft_flags": []}


def _kill_switch() -> dict[str, Any]:
    try:
        from src.core.active_strategy import load_kill_state

        state = load_kill_state()
        return {
            "live_blocked": bool(getattr(state, "live_blocked", True)),
            "entry_allowed": True,
        }
    except Exception as exc:  # noqa: BLE001
        return {"live_blocked": True, "entry_allowed": False, "error": str(exc)}


def _mandatory_gate_present() -> bool:
    path = ROOT / "src" / "safety" / "mandatory_trade_gate.py"
    return path.is_file()


def build_process_record(
    *,
    root: Path | None = None,
    entries: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Authoritative put-credit process record (UO FORMAT: state outside agent)."""
    base = Path(root) if root else ROOT
    entries_path = base / "data" / "put_credit_entries.json"
    system_state_path = base / "data" / "system_state.json"
    loaded = entries if entries is not None else _load_json(entries_path, {})
    if not isinstance(loaded, dict):
        loaded = {}

    limits = _occupancy_from_entries(loaded)
    occupancy = int(limits.get("active_count") or 0)
    max_concurrent = int(limits.get("max_concurrent") or 2)
    regime = _regime_snapshot()
    kill = _kill_switch()
    gate_present = _mandatory_gate_present()

    stuck: list[str] = []
    stuck.extend(str(b) for b in (limits.get("blockers") or []))
    if not regime.get("allowed"):
        stuck.extend(str(b) for b in (regime.get("blockers") or ["regime_blocked"]))
    if not gate_present:
        stuck.append("mandatory_trade_gate_missing")
    if kill.get("live_blocked") is False:
        # Live capital would be allowed — still never expose live execute here.
        pass

    next_actions: list[str] = []
    if occupancy < max_concurrent and regime.get("allowed") and not limits.get("blockers"):
        next_actions.append(
            ".venv/bin/python scripts/spy_put_credit.py --execute-paper  # paper factory"
        )
    elif occupancy < max_concurrent and not regime.get("allowed"):
        next_actions.append(
            ".venv/bin/python scripts/spy_put_credit.py --regime-only  # clear regime blockers"
        )
    elif occupancy >= max_concurrent:
        next_actions.append(
            ".venv/bin/python scripts/spy_put_credit.py --manage-exits  # book full; manage"
        )
    else:
        next_actions.append(
            ".venv/bin/python scripts/spy_put_credit.py --status  # inspect before acting"
        )

    next_actions.append(
        ".venv/bin/python scripts/put_credit_govern.py --check-ready  # rules before action"
    )

    where = {
        "strategy": "spy_put_credit",
        "occupancy": occupancy,
        "max_concurrent": max_concurrent,
        "today_count": int(limits.get("today_count") or 0),
        "max_daily": int(limits.get("max_daily") or 0),
        "regime_allowed": bool(regime.get("allowed")),
        "live_blocked": bool(kill.get("live_blocked", True)),
        "mandatory_trade_gate": gate_present,
        "entries_path": str(entries_path),
        "system_state_path": str(system_state_path),
        "as_of": (now or datetime.now(UTC)).isoformat(),
    }

    return {
        "schemaVersion": SCHEMA_VERSION,
        "format": "decisions_uo_process_record",
        "weAreNot": list(WE_ARE_NOT),
        "instructionsAreNotControl": True,
        "rulesBeforeAction": gate_present,
        "liveExecuteAllowed": False,
        "where": where,
        "stuck": stuck,
        "next": next_actions,
        "paperFactoryEligible": occupancy < max_concurrent
        and bool(regime.get("allowed"))
        and not list(limits.get("blockers") or []),
        "claimBoundary": (
            "Local process record for paper put-credit governance. "
            "Not Decisions, not BOAT, not a ThumbGate universal-orchestrator SKU."
        ),
    }


def check_ready(record: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    """Exit 0 when paper path is governable; 2 when stuck or misconfigured."""
    rec = record or build_process_record()
    issues: list[str] = []
    if not rec.get("rulesBeforeAction"):
        issues.append("mandatory_trade_gate_missing")
    if rec.get("liveExecuteAllowed"):
        issues.append("live_execute_must_stay_false")
    if not rec.get("instructionsAreNotControl"):
        issues.append("instructions_must_not_be_control")
    # Stuck on missing gate is hard fail; regime/occupancy stuck is informative
    if "mandatory_trade_gate_missing" in (rec.get("stuck") or []):
        issues.append("mandatory_trade_gate_missing")

    ok = not issues
    payload = {
        **rec,
        "checkReady": {"ok": ok, "issues": issues},
    }
    return (0 if ok else 2), payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="UO FORMAT process record for spy_put_credit (not a Decisions clone)",
    )
    parser.add_argument(
        "--check-ready",
        action="store_true",
        help="Exit 0 if rules-before-action rail is present; print record JSON",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="REFUSED — live execute is never allowed on this doctor",
    )
    parser.add_argument(
        "--execute-live",
        action="store_true",
        help="REFUSED — live execute is never allowed on this doctor",
    )
    args = parser.parse_args(argv)

    if args.execute or args.execute_live:
        denied = {
            "schemaVersion": SCHEMA_VERSION,
            "decision": "deny",
            "issues": ["live_execute_refused"],
            "claimBoundary": "put_credit_govern never live-executes. Use spy_put_credit --execute-paper.",
            "weAreNot": list(WE_ARE_NOT),
        }
        print(json.dumps(denied, indent=2, sort_keys=True))
        return 2

    if args.check_ready:
        code, payload = check_ready()
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return code

    record = build_process_record()
    print(json.dumps(record, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
