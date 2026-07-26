"""
Mercury Bank MCP Server - read-only bank visibility

Provides tools for:
- Account balances and status
- Recent transaction history
- Bank connectivity health checks

Every tool is read-only: the underlying MercuryReadOnlyClient
(src/adapters/mercury_readonly.py) is GET-only by construction. Money
movement is deliberately NOT exposed here - it stays behind
MercuryBankAdapter's MERCURY_LIVE_TRANSFERS_ENABLED hard stop.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from src.adapters.mercury_readonly import MercuryReadOnlyClient

logger = logging.getLogger(__name__)

_client: MercuryReadOnlyClient | None = None


def _get_client() -> MercuryReadOnlyClient:
    global _client
    if _client is None:
        _client = MercuryReadOnlyClient.from_env()
    return _client


def _reset_client() -> None:
    """Test hook: drop the cached client so from_env runs again."""
    global _client
    _client = None


def get_bank_status() -> dict[str, Any]:
    """
    Masked snapshot of all Mercury accounts with total available balance.

    Returns:
        Snapshot dict with accounts, total_available_usd, read_only flag.
    """
    try:
        snapshot = _get_client().snapshot()
        return {"success": True, **snapshot}
    except Exception as e:  # noqa: BLE001 - MCP tools report errors, never raise
        logger.error("Mercury bank status failed: %s", e)
        return {"success": False, "error": str(e)}


def get_bank_transactions(account: str = "checking", limit: int = 20) -> dict[str, Any]:
    """
    Recent transactions for one account.

    Args:
        account: "checking", "savings", or a raw Mercury account id.
        limit: Maximum rows to return (1-500).

    Returns:
        Masked transaction summaries plus the account alias queried.
    """
    try:
        result = _get_client().get_transactions(account, limit=limit)
        return {
            "success": True,
            "account": account,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **result,
        }
    except Exception as e:  # noqa: BLE001
        logger.error("Mercury transactions failed: %s", e)
        return {"success": False, "account": account, "error": str(e)}


def get_bank_health() -> dict[str, Any]:
    """
    Connectivity check: token resolves and the accounts endpoint answers.

    Returns:
        Health dict with reachable flag, account count, and latency.
    """
    start = time.perf_counter()
    try:
        accounts = _get_client().list_accounts()
        return {
            "success": True,
            "reachable": True,
            "accounts": len(accounts),
            "latency_ms": round((time.perf_counter() - start) * 1000, 1),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:  # noqa: BLE001
        return {
            "success": False,
            "reachable": False,
            "error": str(e),
            "latency_ms": round((time.perf_counter() - start) * 1000, 1),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
