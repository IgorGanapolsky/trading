"""
Input Validation Layer (Pydantic)

Validates all MCP requests before execution.
Implements allowlist-based security for trading operations.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional, TypeVar

from pydantic import BaseModel, Field, field_validator

# Allowlist of tradeable symbols - UPDATED Jan 19, 2026 (LL-244)
# Per CLAUDE.md: SPY/SPX/XSP for index options
# SPY = equity option, SPX/XSP = index options with Section 1256 tax treatment
ALLOWED_SYMBOLS = frozenset({"SPY", "SPX", "XSP", "QQQ", "IWM"})  # liquid ETFs per CLAUDE.md

# Maximum values to prevent resource exhaustion
MAX_LOOKBACK_DAYS = 365
MAX_ORDER_AMOUNT_USD = 5000.0  # 5% of $100K account
MAX_POSITION_RISK = 5000.0
MIN_CLOSED_TRADES_FOR_LIVE = 30
SYSTEM_STATE_PATH = Path(__file__).resolve().parents[2] / "data" / "system_state.json"


T = TypeVar("T", bound=BaseModel)


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _load_system_state(path: Path = SYSTEM_STATE_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _live_trading_unlocked() -> tuple[bool, str]:
    """Allow live orders only after sufficient closed-trade evidence."""
    state = _load_system_state()
    paper_account = state.get("paper_account", {}) if isinstance(state, dict) else {}
    weekly_gate = state.get("north_star_weekly_gate", {}) if isinstance(state, dict) else {}
    scaling_gate = weekly_gate.get("scaling_sample_gate", {}) if isinstance(weekly_gate, dict) else {}

    paper_samples = _as_int(paper_account.get("win_rate_sample_size"), 0)
    scaling_samples = _as_int(scaling_gate.get("closed_trades_observed"), 0)
    closed_trades = max(paper_samples, scaling_samples)

    if closed_trades < MIN_CLOSED_TRADES_FOR_LIVE:
        return False, f"{closed_trades}/{MIN_CLOSED_TRADES_FOR_LIVE} closed trades"

    total_pl = _as_float(paper_account.get("total_pl"), 0.0)
    expectancy = total_pl / paper_samples if paper_samples > 0 else 0.0
    if expectancy <= 0:
        return False, f"expectancy {expectancy:.2f}/trade is non-positive"

    return True, "evidence threshold satisfied"


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
    tier: Optional[str] = Field(default=None)
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
        # Safety: keep live disabled until evidence threshold is met.
        if not v:
            unlocked, reason = _live_trading_unlocked()
            if not unlocked:
                raise ValueError(
                    f"Live trading locked. Continue paper trading until validation passes ({reason})."
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
