"""Risk sizing logic for Gate 4."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Applies deterministic caps:
        - Max 5% of account equity per trade
        - Scale position by blended confidence
    """

    def __init__(
        self,
        max_position_pct: float = 0.05,
        min_notional: float = 3.0,
    ) -> None:
        self.max_position_pct = max_position_pct
        self.min_notional = min_notional
        self.daily_budget = float(os.getenv("DAILY_INVESTMENT", "10.0"))

    def calculate_size(
        self,
        ticker: str,
        account_equity: float,
        signal_strength: float,
        rl_confidence: float,
        sentiment_score: float,
        multiplier: float = 1.0,
    ) -> float:
        if account_equity <= 0:
            logger.warning("Account equity unknown; aborting trade.")
            return 0.0

        blended_confidence = max(0.0, min(1.0, (signal_strength + rl_confidence) / 2))
        sentiment_multiplier = 1.0 + (sentiment_score * 0.25)

        notional = (
            self.daily_budget
            * blended_confidence
            * sentiment_multiplier
            * multiplier
        )

        cap = account_equity * self.max_position_pct
        notional = min(notional, cap)

        if notional < self.min_notional:
            logger.info(
                "RiskManager rejected %s: size $%.2f below minimum $%.2f",
                ticker,
                notional,
                self.min_notional,
            )
            return 0.0

        logger.info(
            "RiskManager approved %s: size=$%.2f (cap=$%.2f)",
            ticker,
            notional,
            cap,
        )
        return round(notional, 2)

