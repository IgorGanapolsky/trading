"""
Options Trading Module

This module provides comprehensive options trading capabilities including:
- VIX monitoring and volatility regime detection (vix_monitor.py)
- Real-time IV data integration (iv_data_integration.py)
- Volatility surface modeling
- IV alerts and regime detection
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

# IV Data Integration imports (optional - requires numpy, scipy, alpaca-py)
try:
    from src.options.iv_data_integration import (  # noqa: F401
        IVAlerts,
        IVDataFetcher,
        IVMetrics,
        IVRegime,
        VolatilitySurface,
        VolatilitySurfacePoint,
    )

    __all__.extend(
        [
            "IVDataFetcher",
            "IVAlerts",
            "VolatilitySurface",
            "IVRegime",
            "IVMetrics",
            "VolatilitySurfacePoint",
        ]
    )
except ImportError:
    pass

__version__ = "1.0.0"
