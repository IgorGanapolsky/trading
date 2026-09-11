"""Parallel Basis FORMAT steal for spy_put_credit SEARCH.

Parallel.ai (https://parallel.ai/) attaches provenance + calibrated confidence
to every claim ("Basis"). We do **not** vendor Parallel APIs, FindAll, Monitor
webhooks, or copy untracked `parallel_ai_features.py` theater.

This module cites **local ledgers** for SEARCH → EVALUATE → TRADE. Discover
does not mean "find all tickers": the controlled experiment is SPY put-credit.
TRADE is receipt-only (submitted=0). Live stays blocked.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class BasisClaim:
    """One cited claim. confidence is high|medium|low, never a fake 0-1 model score."""

    claim: str
    value: Any
    source: str
    confidence: str  # high | medium | low

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load_json(path: Path) -> tuple[Any | None, str]:
    if not path.is_file():
        return None, "missing"
    try:
        return json.loads(path.read_text(encoding="utf-8")), "ok"
    except (OSError, json.JSONDecodeError):
        return None, "unreadable"


def _conf(ok: bool) -> str:
    return "high" if ok else "low"


def build_basis(project_root: Path | None = None) -> dict[str, Any]:
    """Return SEARCH/EVALUATE/TRADE receipt with Basis citations."""
    root = Path(project_root or _REPO_ROOT).resolve()
    kill_path = root / "data" / "runtime" / "strategy_kill_switch.json"
    entries_path = root / "data" / "put_credit_entries.json"
    trades_path = root / "data" / "trades.json"
    state_path = root / "data" / "system_state.json"

    kill, kill_st = _load_json(kill_path)
    entries, ent_st = _load_json(entries_path)
    trades, tr_st = _load_json(trades_path)
    state, st_st = _load_json(state_path)

    kill = kill if isinstance(kill, dict) else {}
    entries = entries if isinstance(entries, dict) else {}
    trades = trades if isinstance(trades, dict) else {}
    state = state if isinstance(state, dict) else {}

    open_n = sum(
        1
        for v in entries.values()
        if isinstance(v, dict) and str(v.get("status") or "").lower() == "open"
    )
    pc_stats = ((trades.get("stats") or {}).get("by_strategy") or {}).get("spy_put_credit") or {}
    closed_n = pc_stats.get("closed")
    paper = (
        (state.get("paper_account") or {}) if isinstance(state.get("paper_account"), dict) else {}
    )

    claims = [
        BasisClaim(
            "active_family",
            kill.get("active_family"),
            "data/runtime/strategy_kill_switch.json",
            _conf(kill_st == "ok" and bool(kill.get("active_family"))),
        ),
        BasisClaim(
            "live_blocked",
            kill.get("live_blocked"),
            "data/runtime/strategy_kill_switch.json",
            _conf(kill_st == "ok" and "live_blocked" in kill),
        ),
        BasisClaim(
            "paper_only",
            kill.get("paper_only"),
            "data/runtime/strategy_kill_switch.json",
            _conf(kill_st == "ok" and "paper_only" in kill),
        ),
        BasisClaim(
            "open_put_credit_journal",
            open_n,
            "data/put_credit_entries.json",
            "medium" if ent_st == "ok" else "low",
        ),
        BasisClaim(
            "paired_put_credit_closed",
            closed_n,
            "data/trades.json.stats.by_strategy.spy_put_credit",
            _conf(tr_st == "ok" and closed_n is not None),
        ),
        BasisClaim(
            "paper_equity",
            paper.get("equity"),
            "data/system_state.json.paper_account.equity",
            _conf(st_st == "ok" and paper.get("equity") is not None),
        ),
    ]

    search = {
        "active_family": kill.get("active_family"),
        "live_blocked": kill.get("live_blocked"),
        "paper_only": kill.get("paper_only"),
    }
    evaluate = {
        "open_journal": open_n,
        "paired_closed": closed_n,
        "n30_remaining": None if closed_n is None else max(0, 30 - int(closed_n)),
    }
    trade = {
        "submitted": 0,
        "action": "receipt_only",
        "live_execute": False,
        "findall_other_tickers": False,
        "parallel_api_called": False,
    }

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "format": "parallel_basis_local_ledgers",
        "ticker": "SPY",
        "search": search,
        "evaluate": evaluate,
        "trade": trade,
        "basis": [c.to_dict() for c in claims],
        "forbid": (
            "Parallel FindAll of other tickers",
            "paid Parallel Task/Monitor in the hot path",
            "copy untracked parallel_ai_features.py theater",
            "live --execute",
            "claim green cron as a fill",
        ),
    }


def readiness_ok(receipt: dict[str, Any]) -> bool:
    """Ready when kill switch cites spy_put_credit paper-only live-blocked."""
    search = receipt.get("search") or {}
    return (
        search.get("active_family") == "spy_put_credit"
        and search.get("paper_only") is True
        and search.get("live_blocked") is True
        and receipt.get("trade", {}).get("submitted") == 0
    )
