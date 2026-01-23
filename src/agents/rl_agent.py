"""
RL Filter - PLACEHOLDER (Not Implemented)

Status: STUB - Returns neutral decisions only
Reason: Real RL requires training infrastructure not yet built

Future implementation would use:
- Thompson Sampling for action selection (already used in RLHF feedback model)
- State: VIX level, SPY price, IV percentile, time to expiration
- Actions: enter_trade, hold, exit_trade
- Rewards: realized P/L from trades

For now, trading decisions use rule-based gates (momentum, sentiment, risk).
The RLHF feedback model (models/ml/feedback_model.json) IS actively learning
from user feedback using Thompson Sampling.
"""

import logging

logger = logging.getLogger(__name__)


class RLFilter:
    """
    Stub RLFilter for backward compatibility.

    WARNING: This is NOT a real RL agent. It passes through all signals unchanged.
    Trading decisions are made by rule-based gates, not RL.
    """

    def __init__(self):
        self.enabled = False
        self._warned = False

    def _log_stub_warning(self):
        """Log warning once that this is a stub."""
        if not self._warned:
            logger.warning(
                "RLFilter is a STUB - not performing real RL. "
                "Trading uses rule-based gates instead."
            )
            self._warned = True

    def filter(self, signal: dict) -> dict:
        """Pass through signal unchanged (stub behavior)."""
        self._log_stub_warning()
        return {"action": signal.get("action", "hold"), "confidence": 0.5}

    def get_action(self, state: dict) -> tuple:
        """Return neutral action (stub behavior)."""
        self._log_stub_warning()
        return ("hold", 0.5)

    def predict(self, state: dict) -> dict:
        """
        Predict action for given state.

        Note: Returns fixed response for health check compatibility.
        This is NOT real prediction - just a stub for backward compatibility.
        """
        return {"action": "hold", "confidence": 0.5, "is_stub": True}
