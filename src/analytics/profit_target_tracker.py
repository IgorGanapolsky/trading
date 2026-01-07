"""
Profit Target Tracker - Track daily profit goals.

Created: Jan 7, 2026
Purpose: Fix missing import in autonomous_trader.py
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.alpaca_trader import AlpacaTrader

logger = logging.getLogger(__name__)


@dataclass
class ProfitTargetResult:
    """Result of profit target tracking."""

    daily_target: float = 100.0
    current_profit: float = 0.0
    on_track: bool = False
    gap_to_target: float = 100.0


class ProfitTargetTracker:
    """Track progress towards daily profit target."""

    def __init__(self, daily_target: float = 100.0):
        self.daily_target = daily_target
        self.current_profit = 0.0

    def check_status(self, trader: AlpacaTrader) -> ProfitTargetResult:
        """Check current profit status against target."""
        try:
            account = trader.get_account_info()
            # Calculate today's P/L
            current_profit = float(account.get("unrealized_pl", 0) or 0)

            return ProfitTargetResult(
                daily_target=self.daily_target,
                current_profit=current_profit,
                on_track=current_profit >= self.daily_target * 0.5,
                gap_to_target=max(0, self.daily_target - current_profit),
            )
        except Exception as e:
            logger.warning(f"Failed to check profit target: {e}")
            return ProfitTargetResult()

    def get_recommendation(self, result: ProfitTargetResult) -> str:
        """Get trading recommendation based on progress."""
        if result.current_profit >= result.daily_target:
            return "TARGET_MET - Consider locking profits"
        elif result.on_track:
            return "ON_TRACK - Continue current strategy"
        else:
            return f"BEHIND - Need ${result.gap_to_target:.2f} more"
