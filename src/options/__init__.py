"""
Options Trading Module

This module provides options trading capabilities including:
- VIX monitoring and volatility regime detection (vix_monitor.py)
- Integration with Alpaca Options API

Author: Claude (CTO)
Created: 2025-12-10
"""

__all__ = []

# VIX Monitor imports (optional)
try:
    from src.options.vix_monitor import (  # noqa: F401
        TermStructureState,
        VIXMonitor,
        VIXSignals,
        VolatilityRegime,
        get_vix_monitor,
        get_vix_signals,
    )

    __all__.extend(
        [
            "VIXMonitor",
            "VIXSignals",
            "VolatilityRegime",
            "TermStructureState",
            "get_vix_monitor",
            "get_vix_signals",
        ]
    )
except ImportError:
    pass

__version__ = "1.0.0"
