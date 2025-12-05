"""
Risk Management Module (Lightweight Pipeline Version)

This module provides lightweight risk tools for the hybrid funnel pipeline:
- RiskManager: Position sizing with ATR-based scaling (Gate 4)
- SlippageModel: Execution cost modeling
- VaRCalculator: Value at Risk calculations
- RiskMonitor: Real-time risk monitoring with alerts
- TargetAlignedSizer: Position sizing aligned with $100/day target
- DailyLossLimiter: Circuit breakers for daily loss limits

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

with contextlib.suppress(ImportError):
    from src.risk.target_aligned_sizing import (
        DailyLossLimiter,
        PositionSizeResult,
        TargetAlignedSizer,
        create_target_aligned_sizer,
    )

with contextlib.suppress(ImportError):
    from src.risk.vix_circuit_breaker import (
        AlertLevel,
        VIXCircuitBreaker,
        VIXStatus,
        check_vix_before_trade,
        get_vix_circuit_breaker,
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
    "TargetAlignedSizer",
    "DailyLossLimiter",
    "PositionSizeResult",
    "create_target_aligned_sizer",
    "VIXCircuitBreaker",
    "VIXStatus",
    "AlertLevel",
    "check_vix_before_trade",
    "get_vix_circuit_breaker",
]
