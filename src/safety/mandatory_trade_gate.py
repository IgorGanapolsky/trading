"""Mandatory Trade Gate - validates trades before execution.

This gate is called by AlpacaExecutor before every trade to ensure
compliance with risk rules, RAG lessons, and ML anomaly detection.

Currently a stub that approves all trades - to be enhanced with:
- RAG lesson blocking
- ML anomaly detection
- Position size limits
- Daily budget enforcement
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GateResult:
    """Result of mandatory trade gate validation."""

    approved: bool
    reason: str = ""
    rag_warnings: list = field(default_factory=list)
    ml_anomalies: list = field(default_factory=list)
    confidence: float = 1.0


class TradeBlockedError(Exception):
    """Exception raised when trade is blocked by mandatory gate."""

    def __init__(self, gate_result: GateResult):
        self.gate_result = gate_result
        super().__init__(gate_result.reason)


def validate_trade_mandatory(
    symbol: str,
    amount: float,
    side: str,
    strategy: str,
    context: dict[str, Any] | None = None,
) -> GateResult:
    """
    Validate trade against mandatory safety checks.

    Args:
        symbol: Trading symbol (e.g., "SPY", "SOFI260206P00024000")
        amount: Trade notional value in dollars
        side: Trade side ("BUY" or "SELL")
        strategy: Strategy name (e.g., "CSP", "momentum")
        context: Optional account context with equity, positions, etc.

    Returns:
        GateResult with approval status and any warnings
    """
    warnings = []
    anomalies = []

    # Stub implementation - approve all trades
    # TODO: Implement actual validation logic:
    # 1. Query RAG for lessons about this symbol/strategy
    # 2. Check ML model for anomaly detection
    # 3. Verify position size limits
    # 4. Check daily budget remaining

    # Basic sanity checks
    if amount <= 0:
        return GateResult(
            approved=False,
            reason=f"Invalid trade amount: ${amount:.2f}",
            rag_warnings=warnings,
            ml_anomalies=anomalies,
            confidence=1.0,
        )

    if side not in ("BUY", "SELL"):
        return GateResult(
            approved=False,
            reason=f"Invalid trade side: {side}",
            rag_warnings=warnings,
            ml_anomalies=anomalies,
            confidence=1.0,
        )

    # Check for zero equity (blind trading prevention - ll_051)
    if context:
        equity = context.get("equity", 0)
        if equity == 0:
            return GateResult(
                approved=False,
                reason="Cannot trade with $0 equity (blind trading prevention)",
                rag_warnings=["ll_051: Blind trading prevention"],
                ml_anomalies=anomalies,
                confidence=1.0,
            )

    # All checks passed - approve trade
    return GateResult(
        approved=True,
        reason="Trade approved by mandatory gate",
        rag_warnings=warnings,
        ml_anomalies=anomalies,
        confidence=1.0,
    )
