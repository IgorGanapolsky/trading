"""
Signals Module - Trading Signal Enhancement and Validation

This module provides signal enhancement capabilities including:
- Options signal enhancement with IV/expected move cross-check
- McMillan's methodology integration
- Strategy recommendation based on market conditions

Modules:
- options_signal_enhancer: Enhance sentiment signals with options analysis
"""

from src.signals.options_signal_enhancer import (
    EnhancedSignal,
    OptionsSignalEnhancer,
    get_signal_enhancer,
)

__all__ = [
    "OptionsSignalEnhancer",
    "EnhancedSignal",
    "get_signal_enhancer",
]
