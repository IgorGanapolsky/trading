"""RL filter stub used as Gate 2."""

from __future__ import annotations

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class RLFilter:
    """
    Placeholder for the upcoming PPO/LSTM policy.

    The interface matches the spec so we can drop in an ONNX/PyTorch model
    later without touching the orchestrator.
    """

    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = model_path
        # Future: load model weights from `model_path`

    def predict(self, market_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Args:
            market_state: Dict of indicators from Gate 1.

        Returns:
            Dict with action/confidence/multiplier.
        """
        logger.debug("RLFilter received market_state: %s", market_state)

        # Stub behaviour: gently pass trades through with moderate confidence.
        return {
            "action": "long",
            "confidence": 0.65,
            "suggested_multiplier": 0.8,
        }

