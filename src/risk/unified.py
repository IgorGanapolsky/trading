"""Unified Risk Manager adapter.

Provides a single interface that exposes:
- Simple sizing for the hybrid funnel (calculate_size)
- Full safeguards for legacy/crypto flows (validate_trade, can_trade, calculate_position_size)

This allows consumers to depend on one class while the underlying implementations
remain decoupled.
"""

from __future__ import annotations

from typing import Any

try:
    from src.risk.risk_manager import RiskManager as _SimpleRiskManager
except Exception:  # pragma: no cover - defensive
    _SimpleRiskManager = None  # type: ignore

try:
    from src.core.risk_manager import RiskManager as _FullRiskManager
except Exception:  # pragma: no cover - defensive
    _FullRiskManager = None  # type: ignore


class UnifiedRiskManager:
    """Facade over simple and full risk managers."""

    def __init__(
        self,
        *,
        simple_params: dict[str, Any] | None = None,
        full_params: dict[str, Any] | None = None,
    ) -> None:
        simple_params = simple_params or {}
        full_params = full_params or {}

        self._simple = _SimpleRiskManager(**simple_params) if _SimpleRiskManager else None
        self._full = _FullRiskManager(**full_params) if _FullRiskManager else None

    # --- Simple sizing used by hybrid funnel ---
    def calculate_size(
        self,
        *,
        ticker: str,
        account_equity: float,
        signal_strength: float,
        rl_confidence: float,
        sentiment_score: float,
        multiplier: float = 1.0,
    ) -> float:
        if not self._simple:
            return 0.0
        return self._simple.calculate_size(
            ticker=ticker,
            account_equity=account_equity,
            signal_strength=signal_strength,
            rl_confidence=rl_confidence,
            sentiment_score=sentiment_score,
            multiplier=multiplier,
        )

    # --- Full safeguards used by legacy/crypto flows ---
    def can_trade(
        self,
        account_value: float,
        daily_pl: float,
        account_info: dict[str, Any] | None = None,
    ) -> bool:
        if not self._full:
            return True
        return self._full.can_trade(account_value, daily_pl, account_info)

    def calculate_position_size(
        self,
        account_value: float,
        risk_per_trade_pct: float = 1.0,
        price_per_share: float | None = None,
    ) -> float:
        if not self._full:
            return 0.0
        return self._full.calculate_position_size(
            account_value, risk_per_trade_pct, price_per_share
        )

    def validate_trade(
        self,
        *,
        symbol: str,
        amount: float,
        sentiment_score: float,
        account_value: float,
        trade_type: str = "BUY",
        account_info: dict[str, Any] | None = None,
        expected_return_pct: float | None = None,
        confidence: float | None = None,
        pattern_type: str | None = None,
    ) -> dict[str, Any]:
        if not self._full:
            return {
                "valid": True,
                "symbol": symbol,
                "amount": amount,
                "trade_type": trade_type,
                "warnings": [],
                "reason": None,
            }
        return self._full.validate_trade(
            symbol=symbol,
            amount=amount,
            sentiment_score=sentiment_score,
            account_value=account_value,
            trade_type=trade_type,
            account_info=account_info,
            expected_return_pct=expected_return_pct,
            confidence=confidence,
            pattern_type=pattern_type,
        )
