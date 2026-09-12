"""Decisions/Gartner universal-orchestration FORMAT steal for spy_put_credit.

Source: Decisions ebook “Universal Orchestration / Who Governs the Machines?”
(Gartner UO). We do **not** clone Decisions, BOAT, or a ThumbGate control-plane SKU.

Transfer only:
- Process state lives **outside** the agent context window
- Deterministic rules fire **before** action (“instructions are not control”)
- Observability: where the process is, what is stuck, what is next

The authoritative record is local ledgers. TRADE is not submitted here.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MAX_CONCURRENT = 2
_N30 = 30


def _load(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def build_process_record(project_root: Path | None = None) -> dict[str, Any]:
    root = Path(project_root or _REPO_ROOT).resolve()
    kill = _load(root / "data" / "runtime" / "strategy_kill_switch.json") or {}
    entries = _load(root / "data" / "put_credit_entries.json") or {}
    trades = _load(root / "data" / "trades.json") or {}
    if not isinstance(kill, dict):
        kill = {}
    if not isinstance(entries, dict):
        entries = {}
    if not isinstance(trades, dict):
        trades = {}

    open_n = sum(
        1
        for v in entries.values()
        if isinstance(v, dict) and str(v.get("status") or "").lower() == "open"
    )
    pc = ((trades.get("stats") or {}).get("by_strategy") or {}).get("spy_put_credit") or {}
    closed_n = pc.get("closed_trades", pc.get("closed"))
    try:
        closed_i = int(closed_n) if closed_n is not None else None
    except (TypeError, ValueError):
        closed_i = None
    remaining = None if closed_i is None else max(0, _N30 - closed_i)

    live_blocked = bool(kill.get("live_blocked", True))
    paper_only = bool(kill.get("paper_only", True))
    family = kill.get("active_family")
    occupancy_full = open_n >= _MAX_CONCURRENT

    stuck: str | None = None
    if family != "spy_put_credit":
        stuck = "wrong_family"
    elif occupancy_full:
        stuck = "occupancy_full"
    elif closed_i is None:
        stuck = "paired_stats_missing"
    elif remaining is not None and remaining > 0:
        stuck = "insufficient_sample"
    next_action = "do_not_live_submit"
    if stuck == "occupancy_full":
        next_action = "wait_exit_then_factory_paper"
    elif stuck == "insufficient_sample":
        next_action = "factory_paper_if_gates_pass"
    elif stuck == "paired_stats_missing":
        next_action = "repair_trades_json_stats"
    elif remaining == 0:
        next_action = "evaluate_kill_criteria_do_not_scale"

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "format": "decisions_uo_process_record",
        "process": "spy_put_credit_paper_validation",
        "ticker": "SPY",
        "state": {
            "where": "paper_lab",
            "active_family": family,
            "open_journal": open_n,
            "paired_closed": closed_i,
            "n30_remaining": remaining,
            "occupancy": f"{open_n}/{_MAX_CONCURRENT}",
        },
        "control": {
            "instructions_are_not_control": True,
            "rules_before_action": [
                "paper_only",
                "live_blocked",
                "spy_only",
                "one_lot",
                "mandatory_trade_gate",
            ],
            "paper_only": paper_only,
            "live_blocked": live_blocked,
            "human_required_for_live": True,
            "factory_may_submit_paper": stuck == "insufficient_sample"
            and paper_only
            and live_blocked,
        },
        "observability": {
            "stuck": stuck,
            "next": next_action,
            "green_cron_is_not_a_fill": True,
        },
        "trade": {"submitted": 0, "action": "record_only"},
        "forbid": (
            "clone Decisions universal orchestrator",
            "ThumbGate agent-governance SKU",
            "live --execute",
            "leave state only in an agent context window",
        ),
    }


def readiness_ok(record: dict[str, Any]) -> bool:
    ctrl = record.get("control") or {}
    st = record.get("state") or {}
    return (
        st.get("active_family") == "spy_put_credit"
        and ctrl.get("paper_only") is True
        and ctrl.get("live_blocked") is True
        and ctrl.get("instructions_are_not_control") is True
        and record.get("trade", {}).get("submitted") == 0
        and st.get("paired_closed") is not None
    )
