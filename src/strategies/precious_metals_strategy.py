"""
Precious Metals Strategy - GLD/SLV trading.

Created: Jan 7, 2026
Purpose: Fix missing import in autonomous_trader.py
Status: DISABLED per system_state.json (allocation = 0)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.alpaca_trader import AlpacaTrader

logger = logging.getLogger(__name__)


class PreciousMetalsStrategy:
    """Trading strategy for GLD and SLV based on gold-silver ratio."""

    def __init__(self, trader: AlpacaTrader | None = None):
        self.trader = trader
        self.tickers = ["GLD", "SLV"]
        self.enabled = False  # Disabled per system_state.json

    def analyze(self) -> dict:
        """Analyze precious metals market conditions."""
        logger.info("Precious metals strategy is DISABLED (allocation = 0)")
        return {
            "status": "disabled",
            "tickers": self.tickers,
            "recommendation": "HOLD",
            "reason": "Strategy disabled per system_state.json"
        }

    def execute(self) -> dict:
        """Execute precious metals trades (if enabled)."""
        if not self.enabled:
            logger.info("Precious metals execution skipped - strategy disabled")
            return {
                "success": True,
                "trades_executed": 0,
                "reason": "Strategy disabled"
            }

        # TODO: Implement actual trading logic when enabled
        return {"success": True, "trades_executed": 0}
