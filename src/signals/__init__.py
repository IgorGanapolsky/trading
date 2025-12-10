"""
Signals Module - Trading Signal Enhancement and Validation

This module provides signal enhancement capabilities including:
- Options signal enhancement with IV/expected move cross-check
- McMillan's methodology integration
- Strategy recommendation based on market conditions
- Kalshi prediction market oracle for cross-asset signals

Modules:
- options_signal_enhancer: Enhance sentiment signals with options analysis
- kalshi_oracle: Use prediction market odds as leading indicators
"""

from src.signals.kalshi_oracle import (
    AssetClass,
    KalshiOracle,
    KalshiSignal,
    SignalDirection,
    get_kalshi_oracle,
    get_kalshi_signals,
)
from src.signals.options_signal_enhancer import (
    EnhancedSignal,
    OptionsSignalEnhancer,
    get_signal_enhancer,
)

__all__ = [
    # Options signal enhancer
    "OptionsSignalEnhancer",
    "EnhancedSignal",
    "get_signal_enhancer",
    # Kalshi oracle
    "KalshiOracle",
    "KalshiSignal",
    "SignalDirection",
    "AssetClass",
    "get_kalshi_oracle",
    "get_kalshi_signals",
]
