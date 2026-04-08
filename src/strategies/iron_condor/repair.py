"""
Iron Condor Repair & Rolling Engine - Step 4 of Strategy Upgrade.
Handles challenged legs by rolling them for a credit, per Reddit strategy.
"""

import logging
from typing import Any, Optional

from .position import IronCondorPosition

logger = logging.getLogger(__name__)


class IronCondorRepair:
    """Detects and repairs challenged iron condor legs."""

    def __init__(self, challenge_threshold: float = 2.0):
        self.challenge_threshold = challenge_threshold  # Distance from strike to underlying

    def detect_challenges(self, pos: IronCondorPosition, current_price: float) -> dict[str, Any]:
        """
        Check if either the put or call side is challenged.

        A side is challenged if the underlying price is within $2 of the short strike.
        """
        put_challenged = (current_price - pos.short_put_strike) <= self.challenge_threshold
        call_challenged = (pos.short_call_strike - current_price) <= self.challenge_threshold

        return {
            "put_challenged": put_challenged,
            "call_challenged": call_challenged,
            "challenged": put_challenged or call_challenged,
            "side": "PUT" if put_challenged else "CALL" if call_challenged else None,
        }

    def find_roll_strikes(
        self, pos: IronCondorPosition, current_price: float, side: str
    ) -> Optional[dict[str, Any]]:
        """
        Find optimal strikes to roll a challenged side to for a credit.

        Reddit strategy: 'close or roll challenged side to avoid gamma risk'.
        Typically, this means rolling the challenged spread further OTM
        or to a new expiration.
        """
        # This is a structural hook for the executor to query the chain.
        # Implementation would involve calling select_strikes_by_delta for a new expiry.
        logger.info(f"Finding roll candidates for {side} side of {pos.underlying}...")

        # In a real system, we'd query the chain provider here.
        # For now, we define the requirement.
        return {
            "underlying": pos.underlying,
            "action": "ROLL",
            "side": side,
            "target_delta": 0.15,  # Roll back to safety
        }
