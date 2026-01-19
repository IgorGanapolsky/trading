"""
Input Validation Layer (Pydantic)

Validates all MCP requests before execution.
Implements allowlist-based security for trading operations.
"""

from __future__ import annotations

import re
from typing import Any, TypeVar

from pydantic import BaseModel, Field, field_validator

# Allowlist of tradeable symbols - UPDATED Jan 19, 2026 (LL-244)
# Per CLAUDE.md: "SPY ONLY - best liquidity, tightest spreads"
ALLOWED_SYMBOLS = frozenset({"SPY"})  # SPY ONLY per CLAUDE.md Jan 19, 2026

# Maximum values to prevent resource exhaustion
MAX_LOOKBACK_DAYS = 365
MAX_ORDER_AMOUNT_USD = 248.0  # 5% of $4,959 account (from CLAUDE.md)
MAX_POSITION_RISK = 248.0


T = TypeVar("T", bound=BaseModel)


class StockAnalysisRequest(BaseModel):
    """Validated request for stock analysis."""

    symbol: str = Field(..., min_length=1, max_length=10)
    lookback_days: int = Field(default=60, ge=1, le=MAX_LOOKBACK_DAYS)

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        v = v.upper().strip()
        if not re.match(r"^[A-Z]{1,5}$", v):
            raise ValueError(f"Invalid symbol format: {v}")
        if v not in ALLOWED_SYMBOLS:
            raise ValueError(f"Symbol {v} not in allowlist. Allowed: {sorted(ALLOWED_SYMBOLS)}")
        return v


class PositionSizeRequest(BaseModel):
    """Validated request for position sizing."""

    symbol: str = Field(..., min_length=1, max_length=10)
    entry_price: float = Field(..., gt=0)
    stop_loss: float = Field(..., gt=0)
    risk_dollars: float = Field(..., gt=0, le=MAX_POSITION_RISK)

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        v = v.upper().strip()
        if not re.match(r"^[A-Z]{1,5}$", v):
            raise ValueError(f"Invalid symbol format: {v}")
        if v not in ALLOWED_SYMBOLS:
            raise ValueError(f"Symbol {v} not in allowlist. Allowed: {sorted(ALLOWED_SYMBOLS)}")
        return v

    @field_validator("stop_loss")
    @classmethod
    def validate_stop_loss(cls, v: float, info) -> float:
        entry_price = info.data.get("entry_price")
        if entry_price and v >= entry_price:
            raise ValueError("Stop loss must be below entry price for long positions")
        return v


class OrderRequest(BaseModel):
    """Validated request for order submission."""

    symbol: str = Field(..., min_length=1, max_length=10)
    amount_usd: float = Field(..., gt=0, le=MAX_ORDER_AMOUNT_USD)
    side: str = Field(default="buy")
    tier: str | None = Field(default=None)
    paper: bool = Field(default=True)

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        v = v.upper().strip()
        if not re.match(r"^[A-Z]{1,5}$", v):
            raise ValueError(f"Invalid symbol format: {v}")
        if v not in ALLOWED_SYMBOLS:
            raise ValueError(f"Symbol {v} not in allowlist. Allowed: {sorted(ALLOWED_SYMBOLS)}")
        return v

    @field_validator("side")
    @classmethod
    def validate_side(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in {"buy", "sell"}:
            raise ValueError(f"Invalid side: {v}. Must be 'buy' or 'sell'")
        return v

    @field_validator("paper")
    @classmethod
    def enforce_paper_trading(cls, v: bool) -> bool:
        # Safety: Always enforce paper trading until validated
        if not v:
            raise ValueError(
                "Live trading disabled. Paper trading required during validation phase."
            )
        return v


def validate_request(request_type: type[T], data: dict[str, Any]) -> T:
    """
    Validate incoming MCP request data against Pydantic model.

    Args:
        request_type: The Pydantic model class to validate against
        data: Raw request data from MCP client

    Returns:
        Validated request object

    Raises:
        ValueError: If validation fails
    """
    return request_type.model_validate(data)
