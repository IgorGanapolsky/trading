"""Mercury Incoming ACH Settlement Reconciler.

Reconciles incoming ACH deposit notifications from broker transfers back into
Mercury AI bank accounts, verifying settlement against data/mercury_income_loop_state.json.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ACHDepositNotification:
    transaction_id: str
    account_id: str
    amount_usd: float
    sender_name: str
    posted_at: str


class MercuryACHReconciler:
    """Reconciles incoming ACH deposits from Alpaca into Mercury bank state."""

    def __init__(self, state_path: Path | None = None):
        self.state_path = state_path or (ROOT / "data" / "mercury_income_loop_state.json")

    def reconcile_deposit(self, notification: ACHDepositNotification, state: dict[str, Any] | None = None) -> dict[str, Any]:
        if state is None:
            state = self._load_state()

        now = datetime.now(timezone.utc).isoformat()
        state.setdefault("total_deposited_to_bank_usd", 0.0)
        state.setdefault("events", [])

        # Prevent duplicate reconciliation of the same transaction_id
        existing_ids = {
            e.get("transaction_id")
            for e in state["events"]
            if e.get("type") == "ach_deposit_reconciled"
        }
        if notification.transaction_id in existing_ids:
            logger.info("ACH Deposit %s already reconciled; skipping.", notification.transaction_id)
            return state

        state["total_deposited_to_bank_usd"] += notification.amount_usd
        reconciled_event = {
            "type": "ach_deposit_reconciled",
            "transaction_id": notification.transaction_id,
            "account_id": notification.account_id,
            "amount_usd": notification.amount_usd,
            "sender_name": notification.sender_name,
            "posted_at": notification.posted_at,
            "reconciled_at": now,
        }
        state["events"].append(reconciled_event)
        self._save_state(state)
        return state

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {"total_deposited_to_bank_usd": 0.0, "events": []}
        try:
            with self.state_path.open("r", encoding="utf-8") as h:
                return json.load(h)
        except Exception:
            return {"total_deposited_to_bank_usd": 0.0, "events": []}

    def _save_state(self, state: dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with self.state_path.open("w", encoding="utf-8") as h:
            json.dump(state, h, indent=2, sort_keys=True)
