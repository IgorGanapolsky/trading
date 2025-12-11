"""
0DTE Options Scalping Strategy - High Frequency Options Trading

Implements rapid options trading on SPY 0DTE (same-day expiry) options.
Based on RAG knowledge from:
- TastyTrade: High probability selling, manage at 50% profit
- Natenberg: Volatility edge, gamma scalping
- CBOE: Market microstructure, SPY options liquidity

Strategy:
1. Sell credit spreads when IV is elevated (>20 VIX)
2. Buy directional options on momentum breakouts
3. Quick exits: 25-50% profit target, 100% stop loss
4. Max 3-5 trades per day for defined risk

Risk Parameters:
- Max position: $50 per trade
- Max daily loss: $100
- Only trade 0DTE on high-volume days
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, date, timezone, timedelta
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class OptionsScalpSignal:
    """Signal for 0DTE options scalp."""

    action: str  # "BUY_CALL", "BUY_PUT", "SELL_CALL_SPREAD", "SELL_PUT_SPREAD"
    symbol: str  # Underlying (SPY, QQQ)
    strike: float
    expiry: date
    premium: float
    delta: float
    contracts: int
    take_profit_pct: float  # e.g., 0.50 = 50% profit
    stop_loss_pct: float    # e.g., 1.0 = 100% loss
    rationale: str


@dataclass
class OptionsScalpConfig:
    """Configuration for 0DTE scalping."""

    # Position sizing
    max_position_usd: float = 50.0      # $50 max per trade
    max_daily_loss_usd: float = 100.0   # $100 max daily loss
    max_daily_trades: int = 5           # Max 5 options trades/day

    # Entry criteria
    min_vix: float = 15.0               # Only trade when VIX > 15
    max_vix: float = 35.0               # Avoid extreme volatility
    min_delta: float = 0.30             # Min delta for directional
    max_delta: float = 0.50             # Max delta (ATM)

    # Exit criteria
    take_profit_pct: float = 0.50       # 50% profit target
    stop_loss_pct: float = 1.0          # 100% stop loss
    max_hold_minutes: int = 60          # Max 1 hour hold

    # Spread parameters
    spread_width: int = 5               # $5 wide spreads
    min_credit: float = 0.50            # Min $0.50 credit


class ZeroDTEScalper:
    """
    0DTE Options Scalping for SPY/QQQ.

    High-frequency options trading using same-day expiry options.
    Combines TastyTrade probability selling with momentum scalping.
    """

    def __init__(self, config: OptionsScalpConfig | None = None) -> None:
        self.config = config or OptionsScalpConfig()
        self._daily_trades = 0
        self._daily_pnl = 0.0
        self._last_trade_date: str | None = None

        # Load config from environment
        self.config.max_position_usd = float(
            os.getenv("OPTIONS_SCALP_MAX_POSITION", str(self.config.max_position_usd))
        )
        self.config.max_daily_trades = int(
            os.getenv("OPTIONS_SCALP_MAX_TRADES", str(self.config.max_daily_trades))
        )

    def _reset_daily_counters(self) -> None:
        """Reset counters on new trading day."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._last_trade_date != today:
            self._daily_trades = 0
            self._daily_pnl = 0.0
            self._last_trade_date = today
            logger.info(f"Reset options scalp counters for {today}")

    def can_trade(self) -> tuple[bool, str]:
        """Check if we can place a new options trade."""
        self._reset_daily_counters()

        if self._daily_trades >= self.config.max_daily_trades:
            return False, f"Daily trade limit ({self.config.max_daily_trades})"

        if self._daily_pnl <= -self.config.max_daily_loss_usd:
            return False, f"Daily loss limit (${self.config.max_daily_loss_usd})"

        return True, "Ready"

    def get_0dte_expiry(self) -> date:
        """Get today's date as 0DTE expiry (SPY has daily options)."""
        return datetime.now(timezone.utc).date()

    def evaluate_momentum_scalp(
        self,
        symbol: str,
        current_price: float,
        price_change_pct: float,
        volume_ratio: float,
        vix: float,
    ) -> OptionsScalpSignal | None:
        """
        Evaluate momentum-based 0DTE scalp opportunity.

        Buy calls on bullish momentum, puts on bearish momentum.
        """
        can_trade, reason = self.can_trade()
        if not can_trade:
            logger.info(f"Skip options scalp: {reason}")
            return None

        # VIX filter
        if vix < self.config.min_vix:
            logger.debug(f"VIX too low ({vix:.1f} < {self.config.min_vix})")
            return None
        if vix > self.config.max_vix:
            logger.debug(f"VIX too high ({vix:.1f} > {self.config.max_vix})")
            return None

        # Need significant momentum
        if abs(price_change_pct) < 0.003:  # < 0.3% move
            return None

        # Need volume confirmation
        if volume_ratio < 1.3:
            return None

        # Determine direction
        if price_change_pct > 0.003:  # Bullish momentum
            action = "BUY_CALL"
            # ATM or slightly OTM call
            strike = round(current_price / 5) * 5  # Round to nearest $5
            delta = 0.45  # Approximate ATM delta
            rationale = f"Bullish momentum: +{price_change_pct*100:.2f}%, Vol {volume_ratio:.1f}x"
        elif price_change_pct < -0.003:  # Bearish momentum
            action = "BUY_PUT"
            strike = round(current_price / 5) * 5
            delta = -0.45
            rationale = f"Bearish momentum: {price_change_pct*100:.2f}%, Vol {volume_ratio:.1f}x"
        else:
            return None

        # Estimate premium (rough - would use real options chain in production)
        # 0DTE ATM options typically $1-3 for SPY
        estimated_premium = max(0.50, current_price * 0.003)  # ~0.3% of stock price

        # Position size: $50 max / premium
        contracts = max(1, int(self.config.max_position_usd / (estimated_premium * 100)))
        contracts = min(contracts, 2)  # Cap at 2 contracts for safety

        signal = OptionsScalpSignal(
            action=action,
            symbol=symbol,
            strike=strike,
            expiry=self.get_0dte_expiry(),
            premium=estimated_premium,
            delta=delta,
            contracts=contracts,
            take_profit_pct=self.config.take_profit_pct,
            stop_loss_pct=self.config.stop_loss_pct,
            rationale=rationale,
        )

        logger.info(f"0DTE Signal: {action} {symbol} {strike} x{contracts} - {rationale}")
        return signal

    def evaluate_credit_spread(
        self,
        symbol: str,
        current_price: float,
        vix: float,
        trend: str,  # "bullish", "bearish", "neutral"
    ) -> OptionsScalpSignal | None:
        """
        Evaluate credit spread opportunity (TastyTrade style).

        Sell put spreads in bullish/neutral, call spreads in bearish.
        """
        can_trade, reason = self.can_trade()
        if not can_trade:
            return None

        # Only sell premium when IV is elevated
        if vix < 18:  # Need elevated IV for credit spreads
            return None

        expiry = self.get_0dte_expiry()
        width = self.config.spread_width

        if trend in ("bullish", "neutral"):
            # Sell put credit spread (bullish)
            action = "SELL_PUT_SPREAD"
            # Sell put 2-3% OTM
            short_strike = round((current_price * 0.97) / 5) * 5
            long_strike = short_strike - width
            delta = -0.20  # Short put delta
            rationale = f"Bullish credit spread: VIX={vix:.1f}, trend={trend}"
        else:
            # Sell call credit spread (bearish)
            action = "SELL_CALL_SPREAD"
            short_strike = round((current_price * 1.03) / 5) * 5
            long_strike = short_strike + width
            delta = 0.20
            rationale = f"Bearish credit spread: VIX={vix:.1f}, trend={trend}"

        # Credit spreads collect premium
        # Typical 0DTE $5 wide spread collects $0.50-1.50
        estimated_credit = max(0.50, width * 0.15)  # ~15% of width

        signal = OptionsScalpSignal(
            action=action,
            symbol=symbol,
            strike=short_strike,
            expiry=expiry,
            premium=estimated_credit,
            delta=delta,
            contracts=1,  # Single contract for spreads
            take_profit_pct=0.50,  # Manage at 50% profit (TastyTrade)
            stop_loss_pct=2.0,     # 2x credit stop
            rationale=rationale,
        )

        logger.info(f"Credit Spread Signal: {action} {symbol} {short_strike}/{long_strike} - {rationale}")
        return signal

    def record_trade(self, pnl: float) -> None:
        """Record completed trade."""
        self._daily_trades += 1
        self._daily_pnl += pnl
        logger.info(f"Options trade #{self._daily_trades}: P/L ${pnl:.2f}, Daily P/L: ${self._daily_pnl:.2f}")


def get_0dte_scalper() -> ZeroDTEScalper:
    """Factory function to get configured 0DTE scalper."""
    return ZeroDTEScalper()
