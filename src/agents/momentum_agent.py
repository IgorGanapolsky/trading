"""Momentum screening agent (Gate 1)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from src.rag.lessons_learned_rag import LessonsLearnedRAG
from src.strategies.momentum_strategy import MomentumStrategy

logger = logging.getLogger(__name__)


@dataclass
class MomentumSignal:
    is_buy: bool
    strength: float  # Normalised 0-1 confidence
    indicators: dict[str, Any]


class MomentumAgent:
    """Adapts the modern momentum strategy to the gate screening funnel."""

    def __init__(self, min_score: float = 0.0) -> None:
        self._strategy = MomentumStrategy()
        self._min_score = min_score
        self._base_config = {
            "macd_threshold": self._strategy.MACD_THRESHOLD,
            "rsi_overbought": self._strategy.RSI_OVERBOUGHT,
            "volume_min": self._strategy.VOLUME_MIN,
            "adx_threshold": self._strategy.ADX_THRESHOLD,
        }
        self.rag = LessonsLearnedRAG()  # Initialize RAG for lessons learned

    def configure_regime(
        self,
        overrides: dict[str, float] | None = None,
    ) -> None:
        """
        Apply regime-specific indicator thresholds.
        """
        config = dict(self._base_config)
        if overrides:
            for key, value in overrides.items():
                if key in config and value is not None:
                    config[key] = float(value)

        self._strategy.MACD_THRESHOLD = config["macd_threshold"]
        self._strategy.RSI_OVERBOUGHT = config["rsi_overbought"]
        self._strategy.VOLUME_MIN = config["volume_min"]
        self._strategy.ADX_THRESHOLD = config.get("adx_threshold", self._strategy.ADX_THRESHOLD)

    def analyze(self, ticker: str) -> MomentumSignal:
        """
        Analyze momentum for a ticker by fetching data and using MomentumStrategy.
        """
        try:
            from src.utils import yfinance_wrapper as yf

            stock = yf.Ticker(ticker)
            hist = stock.history(period="60d")

            # Use MomentumStrategy to generate signals
            signals = self._strategy.generate_signals({ticker: hist})

            if not signals:
                return MomentumSignal(is_buy=False, strength=0.0, indicators={"symbol": ticker})

            sig = signals[0]
            is_buy = sig.action == "buy"
            strength = sig.strength

            # Query RAG for relevant lessons
            rag_lessons = self.rag.query(f"{ticker} momentum technical analysis", top_k=3)
            critical_lessons = [
                lesson for lesson in rag_lessons if lesson.get("severity") == "CRITICAL"
            ]

            if critical_lessons:
                original_strength = strength
                strength = strength * 0.7
                logger.warning(
                    f"⚠️ {len(critical_lessons)} CRITICAL lessons found for {ticker} - "
                    f"Reducing strength from {original_strength:.2f} to {strength:.2f}"
                )

            logger.info(
                "Gate 1 (%s): Momentum Analysis | DECISION: %s (strength=%.2f) | Rationale: %s",
                ticker,
                "BUY" if is_buy else "REJECT",
                strength,
                sig.rationale,
            )

            return MomentumSignal(
                is_buy=is_buy,
                strength=strength,
                indicators={"symbol": ticker, "rationale": sig.rationale, "price": sig.price},
            )

        except Exception as e:
            logger.error(f"{ticker}: Momentum evaluation failed: {e}")
            return MomentumSignal(
                is_buy=False, strength=0.0, indicators={"symbol": ticker, "error": str(e)}
            )
