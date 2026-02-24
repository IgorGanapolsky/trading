from __future__ import annotations

import logging
from typing import Any

from src.strategies.core_strategy import BaseStrategy, Signal
from src.utils.technical_indicators import (
    calculate_adx,
    calculate_macd,
    calculate_rsi,
    calculate_volume_ratio,
)

logger = logging.getLogger(__name__)


class MomentumStrategy(BaseStrategy):
    """
    Modernized Momentum Strategy based on LegacyMomentumCalculator.

    Uses MACD, RSI, Volume Ratio, and ADX for trend and momentum confirmation.
    """

    DEFAULT_UNIVERSE = ["SPY", "QQQ", "IWM"]

    # Thresholds (Permissive by default per ll_019)
    MACD_THRESHOLD = 0.0
    RSI_OVERBOUGHT = 85.0
    VOLUME_MIN = 0.5
    ADX_THRESHOLD = 0.0

    # Risk parameters
    STOP_LOSS_PCT = 0.02
    TAKE_PROFIT_PCT = 0.06
    MAX_POSITION_SIZE = 0.02

    def __init__(
        self,
        universe: list[str] | None = None,
        paper: bool = True,
        config: dict[str, Any] | None = None,
    ):
        self.universe = universe or self.DEFAULT_UNIVERSE
        self.paper = paper
        self._config = config or {}

        # Apply config overrides
        self.MACD_THRESHOLD = self._config.get("macd_threshold", self.MACD_THRESHOLD)
        self.RSI_OVERBOUGHT = self._config.get("rsi_overbought", self.RSI_OVERBOUGHT)
        self.VOLUME_MIN = self._config.get("volume_min", self.VOLUME_MIN)
        self.ADX_THRESHOLD = self._config.get("adx_threshold", self.ADX_THRESHOLD)

    @property
    def name(self) -> str:
        return "momentum_strategy"

    def get_config(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "universe": self.universe,
            "thresholds": {
                "macd": self.MACD_THRESHOLD,
                "rsi_overbought": self.RSI_OVERBOUGHT,
                "volume_min": self.VOLUME_MIN,
                "adx": self.ADX_THRESHOLD,
            },
            "risk": {
                "stop_loss_pct": self.STOP_LOSS_PCT,
                "take_profit_pct": self.TAKE_PROFIT_PCT,
                "max_position_size": self.MAX_POSITION_SIZE,
            },
        }

    def generate_signals(self, data: Any) -> list[Signal]:
        """
        Generate momentum signals from market data.

        Args:
            data: Dict mapping symbol to history DataFrame
        """
        signals = []

        if not isinstance(data, dict):
            logger.warning("MomentumStrategy: data must be a dict of DataFrames")
            return signals

        for symbol in self.universe:
            try:
                hist = data.get(symbol)
                if hist is None or hist.empty or len(hist) < 26:
                    continue

                close = hist["Close"]
                current_price = float(close.iloc[-1])

                # Calculate indicators using centralized utils
                macd_val, macd_signal, macd_hist = calculate_macd(close)
                rsi = calculate_rsi(close)
                vol_ratio = calculate_volume_ratio(hist)
                adx, _, _ = calculate_adx(hist)

                # Signal Logic
                action = "hold"
                strength = 0.5
                rationale_parts = []

                # Screening filters
                passed = True
                if macd_hist < self.MACD_THRESHOLD:
                    passed = False
                    rationale_parts.append(f"MACD Hist ({macd_hist:.3f}) < {self.MACD_THRESHOLD}")

                if rsi > self.RSI_OVERBOUGHT:
                    passed = False
                    rationale_parts.append(f"RSI ({rsi:.1f}) > {self.RSI_OVERBOUGHT}")

                if vol_ratio < self.VOLUME_MIN:
                    passed = False
                    rationale_parts.append(f"Vol Ratio ({vol_ratio:.2f}) < {self.VOLUME_MIN}")

                if self.ADX_THRESHOLD > 0 and adx < self.ADX_THRESHOLD:
                    passed = False
                    rationale_parts.append(f"ADX ({adx:.1f}) < {self.ADX_THRESHOLD}")

                if passed:
                    action = "buy"
                    # Calculate composite score (same as legacy)
                    score = (
                        current_price * (1 + macd_hist / 10) * (1 + (70 - rsi) / 100) * vol_ratio
                    )
                    # Normalise to 0-1
                    strength = min(1.0, score / (score + 100.0))
                    rationale_parts.append(f"Strong momentum score: {score:.2f}")

                signals.append(
                    Signal(
                        symbol=symbol,
                        action=action,
                        strength=strength,
                        price=current_price,
                        stop_loss=current_price * (1 - self.STOP_LOSS_PCT),
                        take_profit=current_price * (1 + self.TAKE_PROFIT_PCT),
                        rationale=" | ".join(rationale_parts),
                    )
                )

            except Exception as e:
                logger.error(f"Error generating momentum signal for {symbol}: {e}")

        return signals
