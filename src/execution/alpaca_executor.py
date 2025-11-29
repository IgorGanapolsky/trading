"""Execution adapter for Alpaca."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.core.alpaca_trader import AlpacaTrader

logger = logging.getLogger(__name__)


class AlpacaExecutor:
    """Handles portfolio sync and order placement."""

    def __init__(self, paper: bool = True) -> None:
        self.trader = AlpacaTrader(paper=paper)
        self.account_snapshot: Dict[str, Any] = {}
        self.positions: List[Dict[str, Any]] = []

    def sync_portfolio_state(self) -> None:
        self.account_snapshot = self.trader.get_account_info()
        self.positions = self.trader.get_positions()
        logger.info(
            "Synced Alpaca state | equity=$%.2f | positions=%d",
            self.account_equity,
            len(self.positions),
        )

    @property
    def account_equity(self) -> float:
        if not self.account_snapshot:
            return 0.0
        return float(
            self.account_snapshot.get("equity")
            or self.account_snapshot.get("portfolio_value")
            or 0.0
        )

    def place_order(self, symbol: str, notional: float, side: str = "buy") -> Dict[str, Any]:
        logger.debug("Submitting %s order via AlpacaExecutor: %s for $%.2f", side, symbol, notional)
        order = self.trader.execute_order(
            symbol=symbol,
            amount_usd=notional,
            side=side,
            tier="T1_CORE",
        )
        return order

