"""
Risk Management Module

Provides comprehensive risk management tools for the trading system:
- Position sizing with ATR-based scaling
- Slippage modeling for realistic backtests
- VaR/CVaR risk metrics for real-time monitoring
- Circuit breakers and risk alerts

Components:
- RiskManager: Position sizing and stop-loss calculation
- SlippageModel: Execution cost modeling
- VaRCalculator: Value at Risk calculations
- RiskMonitor: Real-time risk monitoring with alerts
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
