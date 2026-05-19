"""
Iron Condor Risk Layer
Role: Enforce Phil Town Rule #1 and Position Sizing.
"""

import logging
from typing import Any

from src.constants.trading_thresholds import RiskThresholds
from src.core.trading_constants import (
    MAX_CONTRACTS_PER_TRADE,
    MAX_POSITION_PCT,
    MAX_POSITIONS,
)

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

    def calculate_quantity(
        self,
        equity: float,
        wing_width: float,
        credit_per_contract: float,
        max_risk_pct: float | None = None,
        hard_cap: int | None = None,
    ) -> int:
        """Compute the largest legal iron-condor quantity.

        Caps quantity by the strictest of three constraints:
        1. max_risk_pct of equity per trade (default: MAX_POSITION_PCT from
           trading_constants)
        2. hard_cap (default: MAX_CONTRACTS_PER_TRADE from active profile;
           controlled-experiment.md currently mandates 1)
        3. >= 0 (returns 0 on invalid inputs rather than negative)

        Per-IC max loss = (wing_width * 100 - credit_per_contract * 100).
        That assumes equal-width wings on both sides; the risk surface is
        symmetric so we size against one side.

        Returns 0 if equity <= 0, wing_width <= 0, or credit >= wing_width
        (would imply zero or negative max loss, which is non-physical).
        """
        if equity <= 0 or wing_width <= 0:
            return 0
        per_contract_max_loss = (wing_width - credit_per_contract) * 100
        if per_contract_max_loss <= 0:
            return 0

        risk_pct = max_risk_pct if max_risk_pct is not None else MAX_POSITION_PCT
        risk_dollars = equity * risk_pct
        qty_from_risk = int(risk_dollars // per_contract_max_loss)

        cap = hard_cap if hard_cap is not None else MAX_CONTRACTS_PER_TRADE
        qty = min(qty_from_risk, cap)
        return max(0, qty)

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
