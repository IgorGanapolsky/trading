"""Momentum screening agent (Gate 1)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from src.rag.lessons_learned_rag import LessonsLearnedRAG
from src.strategies.legacy_momentum import LegacyMomentumCalculator

logger = logging.getLogger(__name__)


@dataclass
class MomentumSignal:
    is_buy: bool
    strength: float  # Normalised 0-1 confidence
    indicators: dict[str, Any]


class MomentumAgent:
    """Adapts the legacy deterministic momentum logic to the new funnel."""

    def __init__(self, min_score: float = 0.0) -> None:
        self._calculator = LegacyMomentumCalculator()
        self._min_score = min_score
        self._base_config = {
            "macd_threshold": self._calculator.macd_threshold,
            "rsi_overbought": self._calculator.rsi_overbought,
            "volume_min": self._calculator.volume_min,
        }
        self.rag = LessonsLearnedRAG()  # Initialize RAG for lessons learned

    def configure_regime(
        self,
        overrides: dict[str, float] | None = None,
    ) -> None:
        """
        Apply regime-specific indicator thresholds.

        Args:
            overrides: Optional dict with macd_threshold, rsi_overbought, volume_min.
                       Passing an empty dict resets to defaults captured at init time.
        """
        config = dict(self._base_config)
        if overrides:
            for key, value in overrides.items():
                if key in config and value is not None:
                    config[key] = float(value)

        self._calculator.macd_threshold = config["macd_threshold"]
        self._calculator.rsi_overbought = config["rsi_overbought"]
        self._calculator.volume_min = config["volume_min"]

    def analyze(self, ticker: str) -> MomentumSignal:
        payload = self._calculator.evaluate(ticker)
        score = payload.score
        ind = payload.indicators

        is_buy = score > self._min_score
        strength = self._normalise_score(score)

        # Query RAG for relevant lessons BEFORE finalizing decision
        rag_lessons = self.rag.query(f"{ticker} momentum technical analysis", top_k=3)
        critical_lessons = [lesson for lesson in rag_lessons if lesson.get("severity") == "CRITICAL"]

        # If CRITICAL lessons found, reduce strength/confidence
        if critical_lessons:
            original_strength = strength
            strength = strength * 0.7  # Reduce strength by 30% when CRITICAL lessons exist
            logger.warning(
                f"⚠️ {len(critical_lessons)} CRITICAL lessons found for {ticker} - "
                f"Reducing strength from {original_strength:.2f} to {strength:.2f}"
            )
            for lesson in critical_lessons:
                logger.warning(f"  - {lesson['id']}: {lesson['snippet'][:150]}...")

        # Detailed logging - show ALL indicator values vs thresholds
        adx = ind.get("adx", 0)
        macd = ind.get("macd_hist", ind.get("macd", 0))
        rsi = ind.get("rsi", 50)
        vol_ratio = ind.get("volume_ratio", 1.0)

        # Thresholds (from calculator)
        adx_thresh = getattr(self._calculator, "adx_threshold", 10.0)
        macd_thresh = self._calculator.macd_threshold
        rsi_thresh = self._calculator.rsi_overbought
        vol_thresh = self._calculator.volume_min

        # Build detailed analysis log
        checks = []
        checks.append(
            f"ADX: {adx:.1f} >= {adx_thresh} {'✓' if adx >= adx_thresh else '✗ (weak trend)'}"
        )
        checks.append(
            f"MACD: {macd:.3f} >= {macd_thresh} {'✓' if macd >= macd_thresh else '✗ (bearish)'}"
        )
        checks.append(
            f"RSI: {rsi:.1f} <= {rsi_thresh} {'✓' if rsi <= rsi_thresh else '✗ (overbought)'}"
        )
        checks.append(
            f"Volume: {vol_ratio:.2f}x >= {vol_thresh}x {'✓' if vol_ratio >= vol_thresh else '✗ (low volume)'}"
        )
        checks.append(f"Score: {score:.2f} > {self._min_score} {'✓' if is_buy else '✗'}")

        decision = "BUY" if is_buy else "REJECT"
        logger.info(
            "Gate 1 (%s): Momentum Analysis\n  %s\n  DECISION: %s (strength=%.2f)",
            ticker,
            "\n  ".join(checks),
            decision,
            strength,
        )

        payload.indicators.setdefault("symbol", ticker)
        payload.indicators["momentum_strength"] = strength
        payload.indicators["raw_score"] = score

        return MomentumSignal(
            is_buy=is_buy,
            strength=strength,
            indicators=payload.indicators,
        )

    @staticmethod
    def _normalise_score(score: float) -> float:
        """Convert raw technical score to 0-1 band."""
        if score <= 0:
            return 0.0
        # Damp extremely large values (>100) to 1.0 asymptotically
        return min(1.0, score / (score + 100.0))
