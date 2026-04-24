"""Signals module for trading signals."""

from src.signals.ath_breakout_signal import (
    ATHBreakoutSignal,
    generate_ath_breakout_signal,
)

__all__ = ["ATHBreakoutSignal", "generate_ath_breakout_signal"]
