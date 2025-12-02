"""Execution adapter for Alpaca."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from typing import Any

from src.core.alpaca_trader import AlpacaTrader, AlpacaTraderError

logger = logging.getLogger(__name__)


class AlpacaExecutor:
    """Handles portfolio sync and order placement."""

    def __init__(self, paper: bool = True, allow_simulator: bool = True) -> None:
        self.simulated_orders: list[dict[str, Any]] = []
        self.account_snapshot: dict[str, Any] = {}
        self.positions: list[dict[str, Any]] = []
        self.simulated = os.getenv("ALPACA_SIMULATED", "false").lower() in {"1", "true"}
        self.paper = paper

        if not self.simulated:
            try:
                self.trader = AlpacaTrader(paper=paper)
            except AlpacaTraderError as exc:
                if not allow_simulator:
                    raise
                logger.warning(
                    "Alpaca credentials unavailable (%s); falling back to simulator.",
                    exc,
                )
                self.trader = None
                self.simulated = True
        else:
            self.trader = None

    def sync_portfolio_state(self) -> None:
        if self.simulated:
            equity = float(os.getenv("SIMULATED_EQUITY", "100000"))
            self.account_snapshot = {"equity": equity, "mode": "simulated"}
            self.positions = []
        else:
            self.account_snapshot = self.trader.get_account_info()
            self.positions = self.trader.get_positions()

        logger.info(
            "Synced %s Alpaca state | equity=$%.2f | positions=%d",
            "simulated" if self.simulated else ("paper" if self.paper else "live"),
            self.account_equity,
            len(self.positions),
        )

    @property
    def account_equity(self) -> float:
        if not self.account_snapshot:
            return float(os.getenv("SIMULATED_EQUITY", "100000")) if self.simulated else 0.0
        return float(
            self.account_snapshot.get("equity")
            or self.account_snapshot.get("portfolio_value")
            or 0.0
        )

    def place_order(self, symbol: str, notional: float, side: str = "buy") -> dict[str, Any]:
        logger.debug(
            "Submitting %s order via AlpacaExecutor: %s for $%.2f",
            side,
            symbol,
            notional,
        )
        if self.simulated:
            order = {
                "id": str(uuid.uuid4()),
                "symbol": symbol,
                "side": side,
                "notional": round(notional, 2),
                "status": "filled",
                "filled_at": datetime.utcnow().isoformat(),
                "mode": "simulated",
            }
            self.simulated_orders.append(order)
            return order

        order = self.trader.execute_order(
            symbol=symbol,
            amount_usd=notional,
            side=side,
            tier="T1_CORE",
        )
        return order

    def set_stop_loss(self, symbol: str, qty: float, stop_price: float) -> dict[str, Any]:
        """Place or simulate a stop-loss order.

        In simulated mode, records a synthetic stop order entry.
        """
        if qty <= 0 or stop_price <= 0:
            raise ValueError("qty and stop_price must be positive")

        if self.simulated:
            order = {
                "id": str(uuid.uuid4()),
                "symbol": symbol,
                "side": "sell",
                "type": "stop",
                "qty": float(qty),
                "stop_price": float(stop_price),
                "status": "accepted",
                "submitted_at": datetime.utcnow().isoformat(),
                "mode": "simulated",
            }
            self.simulated_orders.append(order)
            return order

        return self.trader.set_stop_loss(symbol=symbol, qty=qty, stop_price=stop_price)
