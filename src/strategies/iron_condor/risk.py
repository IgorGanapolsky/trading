"""
Iron Condor Risk Layer
Role: Enforce Phil Town Rule #1 and Position Sizing.
"""

import logging
from typing import Any

from src.constants.trading_thresholds import RiskThresholds
from src.core.trading_constants import MAX_POSITIONS

logger = logging.getLogger(__name__)


class IronCondorRisk:
    """
    Risk Guardian for Iron Condors.
    """

    def __init__(self, max_positions: int | None = None):
        if max_positions is None:
            # MAX_POSITIONS is tracked in option legs; iron condors are 4-leg structures.
            max_positions = max(1, int(MAX_POSITIONS) // 4)
        self.max_positions = max_positions
        self.stop_multiplier = RiskThresholds.IRON_CONDOR_STOP_LOSS_MULTIPLIER

    def validate_exposure(self, positions: list[Any], ticker: str) -> bool:
        """
        MANDATORY FIRST STEP: Prevent race conditions and over-leverage.
        1 Iron Condor = 4 legs.
        """
        # Count option positions for this ticker
        ticker_options = [
            p
            for p in positions
            if (hasattr(p, "symbol") and p.symbol.startswith(ticker) and len(p.symbol) > 5)
            or (
                isinstance(p, dict)
                and p.get("symbol", "").startswith(ticker)
                and len(p.get("symbol", "")) > 5
            )
        ]

        total_contracts = sum(
            abs(int(float(getattr(p, "qty", 0) if hasattr(p, "qty") else p.get("qty", 0))))
            for p in ticker_options
        )

        max_contracts = self.max_positions * 4
        current_ic_count = total_contracts // 4

        if total_contracts >= max_contracts:
            logger.warning(
                f"POSITION LIMIT: Already have {current_ic_count} ICs ({total_contracts} contracts)"
            )
            return False

        logger.info(f"Position check OK: {current_ic_count}/{self.max_positions} ICs")
        return True

    def get_stop_prices(
        self, credit_received: float, short_put: float, short_call: float
    ) -> dict[str, float]:
        """
        Calculate stop prices based on 100% of credit received.
        """
        # 100% stop-loss means we allow a loss equal to the initial credit.
        # For short options, that is an adverse move of +1x credit from entry.
        stop_offset = credit_received * self.stop_multiplier
        return {"put_stop": short_put + stop_offset, "call_stop": short_call + stop_offset}
