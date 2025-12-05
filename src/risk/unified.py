"""Unified Risk Manager adapter.

Provides a single interface that exposes:
- Simple sizing for the hybrid funnel (calculate_size)
- Full safeguards for legacy/crypto flows (validate_trade, can_trade, calculate_position_size)
- Cross-strategy correlation monitoring (Dec 3, 2025 enhancement)

This allows consumers to depend on one class while the underlying implementations
remain decoupled.

Dec 3, 2025 Enhancement:
- Added correlation_check() method for pre-trade correlation validation
- Integrated CrossStrategyCorrelationMonitor to prevent hidden concentration
- Portfolio heat calculation for real-time monitoring
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    from src.core.risk_manager import RiskManager as _FullRiskManager
except Exception:  # pragma: no cover - defensive
    _FullRiskManager = None  # type: ignore

try:
    from src.risk.correlation_monitor import (
        CorrelationCheckResult,
        CrossStrategyCorrelationMonitor,
    )
except Exception:  # pragma: no cover - defensive
    CorrelationCheckResult = None  # type: ignore
    CrossStrategyCorrelationMonitor = None  # type: ignore

try:
    from src.risk.regime_aware_sizing import (
        RegimeAwareSizer,
        RegimeAwareSizeResult,
        adjust_size_for_regime,
    )
except Exception:  # pragma: no cover - defensive
    RegimeAwareSizer = None  # type: ignore
    RegimeAwareSizeResult = None  # type: ignore
    adjust_size_for_regime = None  # type: ignore

try:
    from src.risk.risk_manager import RiskManager as _SimpleRiskManager
except Exception:  # pragma: no cover - defensive
    _SimpleRiskManager = None  # type: ignore


class UnifiedRiskManager:
    """Facade over simple and full risk managers with cross-strategy correlation monitoring."""

    def __init__(
        self,
        *,
        simple_params: dict[str, Any] | None = None,
        full_params: dict[str, Any] | None = None,
        correlation_params: dict[str, Any] | None = None,
    ) -> None:
        simple_params = simple_params or {}
        full_params = full_params or {}
        correlation_params = correlation_params or {}

        self._simple = _SimpleRiskManager(**simple_params) if _SimpleRiskManager else None
        self._full = _FullRiskManager(**full_params) if _FullRiskManager else None
        self._correlation = (
            CrossStrategyCorrelationMonitor(**correlation_params)
            if CrossStrategyCorrelationMonitor
            else None
        )
        self._regime_sizer = RegimeAwareSizer() if RegimeAwareSizer else None

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
        current_price: float | None = None,
        hist: Any | None = None,
        market_regime: str | None = None,
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
            current_price=current_price,
            hist=hist,
            market_regime=market_regime,
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

    # --- Cross-strategy correlation monitoring (Dec 3, 2025) ---
    def check_correlation(
        self,
        proposed_symbol: str,
        proposed_amount: float,
        current_positions: dict[str, float],
        historical_returns: Any | None = None,
    ) -> dict[str, Any]:
        """
        Check if proposed trade would breach correlation thresholds.

        This prevents hidden concentration risk across strategy tiers.
        For example: Core tier buys SPY + Growth tier buys QQQ = high correlation.

        Args:
            proposed_symbol: Symbol to buy
            proposed_amount: Dollar amount to allocate
            current_positions: Dict of {symbol: dollar_value} for all current positions
            historical_returns: Optional DataFrame of daily returns for correlation calc

        Returns:
            Dict with:
            - approved: bool - whether trade passes correlation check
            - reason: str - explanation
            - recommendation: str - APPROVE, REDUCE, or REJECT
            - current_avg_correlation: float
            - projected_avg_correlation: float
            - sector_exposure: dict of sector -> percentage
            - high_correlation_pairs: list of problematic pairs
        """
        if not self._correlation:
            logger.warning("Correlation monitor not available - approving by default")
            return {
                "approved": True,
                "reason": "Correlation monitor not initialized",
                "recommendation": "APPROVE",
                "current_avg_correlation": 0.0,
                "projected_avg_correlation": 0.0,
                "sector_exposure": {},
                "high_correlation_pairs": [],
            }

        result = self._correlation.check_trade(
            proposed_symbol=proposed_symbol,
            proposed_amount=proposed_amount,
            current_positions=current_positions,
            historical_returns=historical_returns,
        )

        return {
            "approved": result.approved,
            "reason": result.reason,
            "recommendation": result.recommendation,
            "current_avg_correlation": result.current_avg_correlation,
            "projected_avg_correlation": result.projected_avg_correlation,
            "sector_exposure": result.sector_exposure,
            "high_correlation_pairs": result.high_correlation_pairs,
        }

    def get_portfolio_heat(self, positions: dict[str, float]) -> dict[str, Any]:
        """
        Get composite portfolio risk 'heat' score.

        Returns:
            Dict with:
            - heat_score: 0-100 (higher = more concentrated/risky)
            - sector_concentration: Herfindahl index
            - largest_position_pct: Biggest position as % of total
            - avg_correlation: Estimated average correlation
            - status: COOL, WARM, or HOT
            - sector_breakdown: Dict of sector -> percentage
        """
        if not self._correlation:
            return {
                "heat_score": 0,
                "sector_concentration": 0,
                "largest_position_pct": 0,
                "avg_correlation": 0,
                "status": "UNKNOWN",
                "sector_breakdown": {},
            }

        return self._correlation.get_portfolio_heat(positions)

    def validate_trade_with_correlation(
        self,
        *,
        symbol: str,
        amount: float,
        sentiment_score: float,
        account_value: float,
        current_positions: dict[str, float],
        trade_type: str = "BUY",
        account_info: dict[str, Any] | None = None,
        expected_return_pct: float | None = None,
        confidence: float | None = None,
        pattern_type: str | None = None,
        historical_returns: Any | None = None,
    ) -> dict[str, Any]:
        """
        Combined validation: standard risk checks + correlation check.

        This is the recommended method for production trading as it catches
        both individual trade issues AND portfolio-wide concentration.

        Returns:
            Dict with all standard validate_trade fields plus:
            - correlation_approved: bool
            - correlation_reason: str
            - correlation_recommendation: str
            - portfolio_heat: dict
        """
        # Standard validation first
        standard_result = self.validate_trade(
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

        # If standard check fails, don't bother with correlation
        if not standard_result.get("valid", True):
            standard_result["correlation_approved"] = False
            standard_result["correlation_reason"] = "Skipped - standard validation failed"
            standard_result["correlation_recommendation"] = "REJECT"
            standard_result["portfolio_heat"] = {}
            return standard_result

        # Now check correlation
        corr_result = self.check_correlation(
            proposed_symbol=symbol,
            proposed_amount=amount,
            current_positions=current_positions,
            historical_returns=historical_returns,
        )

        # Get portfolio heat
        heat = self.get_portfolio_heat(current_positions)

        # Merge results
        standard_result["correlation_approved"] = corr_result["approved"]
        standard_result["correlation_reason"] = corr_result["reason"]
        standard_result["correlation_recommendation"] = corr_result["recommendation"]
        standard_result["portfolio_heat"] = heat

        # Override validity if correlation check fails
        if not corr_result["approved"]:
            if corr_result["recommendation"] == "REJECT":
                standard_result["valid"] = False
                standard_result["reason"] = f"Correlation: {corr_result['reason']}"
            elif corr_result["recommendation"] == "REDUCE":
                # Allow but add warning
                standard_result["warnings"] = standard_result.get("warnings", [])
                standard_result["warnings"].append(
                    f"High correlation - consider 50% position: {corr_result['reason']}"
                )
                standard_result["suggested_amount"] = amount * 0.5

        return standard_result

    # --- Regime-aware position sizing (Dec 3, 2025) ---
    def adjust_size_for_regime(
        self,
        base_size: float,
        account_equity: float,
        symbol: str | None = None,
        market_features: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Adjust position size based on current market regime.

        Automatically reduces size in volatile/bear markets and allows
        full size in calm/bull markets.

        Args:
            base_size: Base position size from standard calculation
            account_equity: Total account equity
            symbol: Optional symbol for symbol-specific analysis
            market_features: Optional pre-calculated market features

        Returns:
            Dict with:
            - adjusted_size: Final position size after regime adjustment
            - original_size: Input size before adjustment
            - regime_label: Current market regime (calm/trending/volatile/spike)
            - final_multiplier: Combined multiplier applied
            - should_pause_trading: Whether trading should be paused
            - reason: Explanation of adjustment
        """
        if not self._regime_sizer:
            logger.warning("Regime sizer not available - using base size")
            return {
                "adjusted_size": base_size,
                "original_size": base_size,
                "regime_label": "unknown",
                "final_multiplier": 1.0,
                "should_pause_trading": False,
                "reason": "Regime sizer not initialized",
            }

        result = self._regime_sizer.adjust_position_size(
            base_size=base_size,
            account_equity=account_equity,
            symbol=symbol,
            market_features=market_features,
        )

        return {
            "adjusted_size": result.adjusted_size,
            "original_size": result.original_size,
            "regime_label": result.regime_label,
            "final_multiplier": result.final_multiplier,
            "regime_multiplier": result.regime_multiplier,
            "risk_bias": result.risk_bias,
            "max_position_pct": result.max_position_pct,
            "regime_confidence": result.regime_confidence,
            "vix_level": result.vix_level,
            "should_pause_trading": result.should_pause_trading,
            "reason": result.reason,
        }

    def should_pause_trading(self) -> tuple[bool, str]:
        """
        Check if trading should be paused based on current market regime.

        Uses VIX levels and regime detection to determine if markets are
        in a crisis state (VIX > 30) where new positions should be avoided.

        Returns:
            Tuple of (should_pause: bool, reason: str)
        """
        if not self._regime_sizer:
            return False, "Regime sizer not available"

        return self._regime_sizer.should_pause_trading()

    def calculate_size_with_all_adjustments(
        self,
        *,
        ticker: str,
        account_equity: float,
        signal_strength: float,
        rl_confidence: float,
        sentiment_score: float,
        current_positions: dict[str, float],
        multiplier: float = 1.0,
        current_price: float | None = None,
        hist: Any | None = None,
        market_regime: str | None = None,
    ) -> dict[str, Any]:
        """
        Complete position sizing with all risk adjustments:
        1. Base Kelly Criterion sizing
        2. Regime-aware adjustment
        3. Correlation check against existing positions

        This is the recommended method for production trading.

        Returns:
            Dict with:
            - final_size: Ultimate position size after all adjustments
            - base_size: Initial size from Kelly calculation
            - regime_adjusted_size: Size after regime adjustment
            - correlation_approved: Whether trade passes correlation check
            - should_execute: Final recommendation to execute or not
            - reasoning: Full explanation of all adjustments
        """
        result = {
            "final_size": 0.0,
            "base_size": 0.0,
            "regime_adjusted_size": 0.0,
            "correlation_approved": True,
            "should_execute": False,
            "reasoning": [],
        }

        # Step 1: Base sizing
        base_size = self.calculate_size(
            ticker=ticker,
            account_equity=account_equity,
            signal_strength=signal_strength,
            rl_confidence=rl_confidence,
            sentiment_score=sentiment_score,
            multiplier=multiplier,
            current_price=current_price,
            hist=hist,
            market_regime=market_regime,
        )
        result["base_size"] = base_size
        result["reasoning"].append(f"Base Kelly size: ${base_size:.2f}")

        if base_size <= 0:
            result["reasoning"].append("Base sizing rejected trade")
            return result

        # Step 2: Regime adjustment
        regime_result = self.adjust_size_for_regime(
            base_size=base_size,
            account_equity=account_equity,
            symbol=ticker,
        )
        result["regime_adjusted_size"] = regime_result["adjusted_size"]
        result["reasoning"].append(
            f"Regime ({regime_result['regime_label']}): "
            f"${base_size:.2f} -> ${regime_result['adjusted_size']:.2f} "
            f"({regime_result['final_multiplier']:.2f}x)"
        )

        if regime_result["should_pause_trading"]:
            result["reasoning"].append(f"BLOCKED: {regime_result['reason']}")
            return result

        adjusted_size = regime_result["adjusted_size"]
        if adjusted_size <= 0:
            result["reasoning"].append("Regime adjustment reduced size to zero")
            return result

        # Step 3: Correlation check
        corr_result = self.check_correlation(
            proposed_symbol=ticker,
            proposed_amount=adjusted_size,
            current_positions=current_positions,
        )
        result["correlation_approved"] = corr_result["approved"]

        if not corr_result["approved"]:
            if corr_result["recommendation"] == "REJECT":
                result["reasoning"].append(f"BLOCKED: Correlation - {corr_result['reason']}")
                return result
            elif corr_result["recommendation"] == "REDUCE":
                adjusted_size = adjusted_size * 0.5
                result["reasoning"].append(
                    f"Correlation warning - reduced to ${adjusted_size:.2f}: {corr_result['reason']}"
                )

        # Final result
        result["final_size"] = round(adjusted_size, 2)
        result["should_execute"] = adjusted_size > 0
        result["reasoning"].append(f"Final approved size: ${adjusted_size:.2f}")

        return result
