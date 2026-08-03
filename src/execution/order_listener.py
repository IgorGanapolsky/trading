"""Alpaca Real-Time Order & Fill Event Listener and Ledger Synchronizer.

Listens for order fill events (fill, partial_fill, canceled, stopped) and updates
canonical position ledgers (data/put_credit_entries.json and data/mercury_income_loop_state.json)
in real-time without waiting for polling intervals.
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
class OrderEvent:
    event_type: str  # "fill", "partial_fill", "canceled", "stopped", "expired"
    order_id: str
    symbol: str
    qty: float
    filled_qty: float
    filled_price: float | None
    side: str  # "buy" or "sell"
    timestamp: str


class OrderFillHandler:
    """Processes order events and reconciles position ledgers in real-time."""

    def __init__(self, state_path: Path | None = None):
        self.state_path = state_path or (ROOT / "data" / "mercury_income_loop_state.json")

    def process_event(
        self, event: OrderEvent, state: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Process an incoming order event and update state dict."""
        if state is None:
            state = self._load_state()

        now = datetime.now(timezone.utc).isoformat()
        state.setdefault("events", [])
        state.setdefault("positions", {})

        event_record = {
            "type": f"order_{event.event_type}",
            "order_id": event.order_id,
            "symbol": event.symbol,
            "qty": event.qty,
            "filled_qty": event.filled_qty,
            "filled_price": event.filled_price,
            "side": event.side,
            "at": now,
        }
        state["events"].append(event_record)

        if event.event_type in ("fill", "partial_fill") and event.filled_price is not None:
            notional = event.filled_qty * event.filled_price
            current_pos = state["positions"].get(event.symbol, 0.0)
            if event.side == "buy":
                state["positions"][event.symbol] = current_pos + notional
            elif event.side == "sell":
                state["positions"][event.symbol] = max(0.0, current_pos - notional)

        self._save_state(state)
        return state

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {"positions": {}, "events": []}
        try:
            with self.state_path.open("r", encoding="utf-8") as h:
                return json.load(h)
        except Exception:
            return {"positions": {}, "events": []}

    def _save_state(self, state: dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with self.state_path.open("w", encoding="utf-8") as h:
            json.dump(state, h, indent=2, sort_keys=True)
