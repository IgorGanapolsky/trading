"""Risk sizing logic for Gate 4 (Hybrid Funnel Pipeline).

This is a lightweight position sizer for the modular orchestrator pipeline.
It provides:
- ATR-based stop computation
- Volatility-aware sizing
- Daily budget enforcement

Note: This is distinct from src/core/risk_manager.py which provides comprehensive
risk management with circuit breakers, behavioral finance, and drawdown tracking.
Use this module for the hybrid funnel pipeline (src/orchestrator/).
Use src/core/risk_manager.py for the main trading system (src/main.py).
"""

from __future__ import annotations

import logging
import os

from src.risk.kelly import kelly_fraction

try:  # Optional at runtime; tests will provide synthetic data
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover - pandas always present in prod
    pd = None  # type: ignore

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Applies deterministic caps combined with Kelly sizing heuristics.
    """

    def __init__(
        self,
        max_position_pct: float = 0.05,
        min_notional: float = 50.0,
        use_atr_scaling: bool | None = None,
        atr_period: int = 14,
        kelly_cap: float = 0.05,
    ) -> None:
        self.max_position_pct = max_position_pct
        self.min_notional = min_notional
        self.daily_budget = float(os.getenv("DAILY_INVESTMENT", "50.0"))
        # Allow env override; default on for robustness
        if use_atr_scaling is None:
            env_flag = os.getenv("RISK_USE_ATR_SCALING", "1").lower() in {"1", "true", "yes"}
            self.use_atr_scaling = env_flag
        else:
            self.use_atr_scaling = bool(use_atr_scaling)
        self.atr_period = atr_period
        self.kelly_cap = kelly_cap

    def calculate_size(
        self,
        ticker: str,
        account_equity: float,
        signal_strength: float,
        rl_confidence: float,
        sentiment_score: float,
        multiplier: float = 1.0,
        current_price: float | None = None,
        hist: pd.DataFrame | None = None,
        market_regime: str | None = None,
        allocation_cap: float | None = None,
    ) -> float:
        if account_equity <= 0:
            logger.warning("Account equity unknown; aborting trade.")
            return 0.0

        blended_confidence = max(0.0, min(1.0, (signal_strength + rl_confidence) / 2))
        sentiment_multiplier = 1.0 + (sentiment_score * 0.25)

        baseline = self.daily_budget * blended_confidence * sentiment_multiplier * multiplier

        kelly_frac = self._estimate_kelly_fraction(
            signal_strength=signal_strength,
            rl_confidence=rl_confidence,
            sentiment_score=sentiment_score,
            regime=market_regime,
            multiplier=multiplier,
        )
        notional = account_equity * min(max(kelly_frac, 0.0), self.kelly_cap, self.max_position_pct)
        if notional < baseline:
            notional = baseline

        # Enforce the daily budget as a hard per-trade cap so a high Kelly fraction
        # cannot overshoot small-budget scenarios (e.g., paper trading).
        notional = min(notional, baseline)

        # Optional volatility-aware scaling using ATR if price history available
        scale = 1.0
        if self.use_atr_scaling and current_price and current_price > 0:
            try:
                atr_value = 0.0
                if hist is not None and pd is not None:
                    from src.utils.technical_indicators import calculate_atr

                    atr_value = float(calculate_atr(hist, period=self.atr_period))
                # If ATR known, reduce size proportionally for high volatility
                if atr_value and atr_value > 0:
                    atr_pct = atr_value / float(current_price)
                    # Linear reduction: up to 50% reduction at high ATR% levels
                    scale = max(0.5, 1.0 - min(0.5, atr_pct * 3.0))
            except Exception as exc:  # pragma: no cover - conservative fail-open
                logger.debug("ATR scaling disabled due to error: %s", exc)

        notional = notional * scale

        cap = account_equity * self.max_position_pct
        notional = min(notional, cap)
        if allocation_cap is not None:
            notional = min(notional, max(0.0, allocation_cap))

        if notional < self.min_notional:
            logger.info(
                "RiskManager rejected %s: size $%.2f below minimum $%.2f",
                ticker,
                notional,
                self.min_notional,
            )
            return 0.0

        logger.info(
            "RiskManager approved %s: size=$%.2f (cap=$%.2f)",
            ticker,
            notional,
            cap,
        )
        return round(notional, 2)

    def _estimate_kelly_fraction(
        self,
        *,
        signal_strength: float,
        rl_confidence: float,
        sentiment_score: float,
        regime: str | None,
        multiplier: float,
    ) -> float:
        win_prob = 0.45 + 0.25 * max(0.0, signal_strength) + 0.2 * max(0.0, rl_confidence)
        win_prob += 0.1 * max(0.0, sentiment_score)
        win_prob = max(0.05, min(0.95, win_prob))

        payoff_ratio = 1.0 + 0.5 * max(0.2, multiplier)
        payoff_ratio += sentiment_score * 0.4

        if regime:
            regime_lower = regime.lower()
            if "volatile" in regime_lower:
                payoff_ratio *= 0.7
                win_prob -= 0.08
            elif "bear" in regime_lower:
                payoff_ratio *= 0.8
                win_prob -= 0.05
            elif "bull" in regime_lower:
                payoff_ratio *= 1.15
                win_prob += 0.03

        payoff_ratio = max(0.2, payoff_ratio)
        return kelly_fraction(win_prob, payoff_ratio)

    def calculate_stop_loss(
        self,
        *,
        ticker: str,
        entry_price: float,
        direction: str = "long",
        atr_multiplier: float | None = None,
        hist: pd.DataFrame | None = None,
    ) -> float:
        """Compute ATR-based stop-loss price with safe fallbacks.

        If ``hist`` is provided, uses it to compute ATR; otherwise attempts a best-effort
        fetch via available data sources and falls back to a fixed 3% stop if unavailable.
        """
        if entry_price <= 0:
            return 0.0

        multiplier = atr_multiplier or float(os.getenv("ATR_STOP_MULTIPLIER", "2.0"))
        try:
            from src.utils.technical_indicators import (
                calculate_atr,
                calculate_atr_stop_loss,
            )

            atr_val = 0.0
            if hist is not None and pd is not None:
                atr_val = float(calculate_atr(hist, period=self.atr_period))
            else:
                # Best-effort: try to fetch minimal history (no network in tests)
                try:
                    from src.utils.market_data import MarketDataFetcher

                    fetcher = MarketDataFetcher()
                    res = fetcher.get_daily_bars(
                        symbol=ticker, lookback_days=max(30, self.atr_period + 5)
                    )
                    df = res.data
                    if df is not None and not df.empty:
                        atr_val = float(calculate_atr(df, period=self.atr_period))
                except Exception:
                    atr_val = 0.0

            stop_price = float(
                calculate_atr_stop_loss(
                    entry_price=entry_price, atr=atr_val, multiplier=multiplier, direction=direction
                )
            )
            return stop_price
        except Exception as exc:  # pragma: no cover
            logger.debug("ATR stop calculation failed: %s", exc)
            # Fallback 3% trailing
            return entry_price * (0.97 if direction == "long" else 1.03)
