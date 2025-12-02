"""
Risk Management Module (Lightweight Pipeline Version)

This module provides lightweight risk tools for the hybrid funnel pipeline:
- RiskManager: Position sizing with ATR-based scaling (Gate 4)
- SlippageModel: Execution cost modeling
- VaRCalculator: Value at Risk calculations
- RiskMonitor: Real-time risk monitoring with alerts

Note: For comprehensive risk management with circuit breakers, behavioral
finance, and drawdown tracking, use src/core/risk_manager.RiskManager instead.
This module is optimized for the modular orchestrator (src/orchestrator/).
"""

import contextlib

from src.risk.risk_manager import RiskManager

# Import new risk components
with contextlib.suppress(ImportError):
    from src.risk.slippage_model import (
        SlippageModel,
        SlippageModelType,
        SlippageResult,
        apply_slippage,
        get_default_slippage_model,
    )

with contextlib.suppress(ImportError):
    from src.risk.var_metrics import (
        RiskAlert,
        RiskMonitor,
        VaRCalculator,
        VaRMethod,
        VaRResult,
        calculate_portfolio_var,
        get_risk_monitor,
    )

__all__ = [
    "RiskManager",
    "SlippageModel",
    "SlippageModelType",
    "SlippageResult",
    "VaRCalculator",
    "VaRMethod",
    "VaRResult",
    "RiskMonitor",
    "RiskAlert",
]
