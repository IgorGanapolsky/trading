"""Senpi 5-phase FORMAT steal for spy_put_credit.

Senpi (https://senpi.ai) runs Discover → Decide → Execute → Manage → Exit
on Hyperliquid with a scanner that proposes and a runtime that disposes.

We do **not** clone Hyperliquid, fund a wallet, buy credits, or copy-trade
260+ perps. This module emits a local ledger receipt with those five names
mapped onto paper SPY put-credit gates and exits.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
PHASES = ("discover", "decide", "execute", "manage", "exit")


def _load_json(path: Path) -> tuple[Any | None, str]:
    if not path.is_file():
        return None, "missing"
    try:
        return json.loads(path.read_text(encoding="utf-8")), "ok"
    except (OSError, json.JSONDecodeError):
        return None, "unreadable"


def build_lifecycle(project_root: Path | None = None) -> dict[str, Any]:
    """Return Discover/Decide/Execute/Manage/Exit receipt from local ledgers."""
    root = Path(project_root or _REPO_ROOT).resolve()
    kill, kill_st = _load_json(root / "data" / "runtime" / "strategy_kill_switch.json")
    entries, ent_st = _load_json(root / "data" / "put_credit_entries.json")
    trades, tr_st = _load_json(root / "data" / "trades.json")
    state, st_st = _load_json(root / "data" / "system_state.json")

    kill = kill if isinstance(kill, dict) else {}
    entries = entries if isinstance(entries, dict) else {}
    trades = trades if isinstance(trades, dict) else {}
    state = state if isinstance(state, dict) else {}

    statuses: dict[str, int] = {}
    for row in entries.values():
        if not isinstance(row, dict):
            continue
        key = str(row.get("status") or "unknown").lower()
        statuses[key] = statuses.get(key, 0) + 1

    pc_stats = ((trades.get("stats") or {}).get("by_strategy") or {}).get("spy_put_credit") or {}
    closed_n = pc_stats.get("closed_trades", pc_stats.get("closed"))
    live = state.get("live_account") if isinstance(state.get("live_account"), dict) else {}
    live_eq = live.get("equity", live.get("current_equity"))

    family_ok = kill.get("active_family") == "spy_put_credit"
    paper_ok = kill.get("paper_only") is True
    blocked_ok = kill.get("live_blocked") is True
    decide_ok = family_ok and paper_ok and blocked_ok and kill_st == "ok"

    n30_remaining = None if closed_n is None else max(0, 30 - int(closed_n))
    edge_claim = False  # n>=30 + expectancy>0 is a later gate; never true from this receipt

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "format": "senpi_five_phase_local_ledgers",
        "ticker": "SPY",
        "vendor_senpi": False,
        "hyperliquid": False,
        "wallet_funded": False,
        "phases": list(PHASES),
        "discover": {
            "universe": 1,
            "ticker": "SPY",
            "source": "local_ledgers_not_hyperfeed",
            "kill_switch_status": kill_st,
        },
        "decide": {
            "scanner_proposes": True,
            "runtime_disposes": True,
            "confluence_cleared": decide_ok,
            "gates": {
                "active_family": kill.get("active_family"),
                "paper_only": kill.get("paper_only"),
                "live_blocked": kill.get("live_blocked"),
            },
        },
        "execute": {
            "submitted": 0,
            "live_execute": False,
            "action": "receipt_only",
            "live_equity": live_eq,
            "state_status": st_st,
        },
        "manage": {
            "journal_status_counts": statuses,
            "open": int(statuses.get("open") or 0),
            "exit_pending": int(statuses.get("exit_pending") or 0),
            "phase1_defense": "stop_200pct_of_credit",
            "phase2_lock": "take_profit_50pct_buffett_profile",
            "time_exit": "exit_dte_30_buffett",
            "dsl_ratchet_not_cloned": True,
            "entries_status": ent_st,
        },
        "exit": {
            "paired_closed": closed_n,
            "n30_remaining": n30_remaining,
            "edge_claim_allowed": edge_claim,
            "learn": "paired_ledger_only",
            "trades_status": tr_st,
        },
        "forbid": (
            "Hyperliquid perps / copy-trade 260+ markets",
            "fund a Senpi or crypto wallet",
            "buy Senpi credits or Subscribe",
            "clone @senpi-ai/runtime",
            "treat $10 trial credits as trading capital",
            "live --execute from this receipt",
        ),
    }


def readiness_ok(receipt: dict[str, Any]) -> bool:
    """Ready when paper SPY put-credit is gated and this receipt does not submit."""
    decide = receipt.get("decide") or {}
    execute = receipt.get("execute") or {}
    return (
        receipt.get("ticker") == "SPY"
        and receipt.get("hyperliquid") is False
        and decide.get("confluence_cleared") is True
        and execute.get("submitted") == 0
        and execute.get("live_execute") is False
    )
