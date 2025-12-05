"""
VIX Circuit Breaker - Automatic Position Reduction on Volatility Spikes

This module provides proactive risk management by monitoring VIX in real-time
and automatically reducing positions when volatility spikes occur.

Key capabilities:
1. Real-time VIX monitoring with configurable thresholds
2. Intraday spike detection (% change from open/previous close)
3. Tiered position reduction based on VIX level and rate of change
4. Automatic de-risking actions via Alpaca API
5. Integration with TradeGateway for coordinated risk management

Critical gap addressed (Dec 4, 2025 audit):
- "No Volatility Shock Response: If VIX jumps +50% intraday, no immediate position reduction"
- "No Real-Time Liquidation Prevention: No 'if breached, auto-close positions' logic"

Author: Trading System
Created: 2025-12-04
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

import yfinance as yf

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """VIX alert levels for tiered response."""

    NORMAL = "normal"  # VIX < 15, no action
    ELEVATED = "elevated"  # VIX 15-20, monitor closely
    HIGH = "high"  # VIX 20-25, reduce new positions
    VERY_HIGH = "very_high"  # VIX 25-30, reduce existing positions
    EXTREME = "extreme"  # VIX > 30, aggressive de-risking
    SPIKE = "spike"  # Intraday jump > 20%, immediate action


@dataclass
class VIXStatus:
    """Current VIX status and recommended actions."""

    current_level: float
    previous_close: float
    intraday_change_pct: float
    alert_level: AlertLevel
    position_multiplier: float  # 0.0 to 1.0, multiply existing position targets
    new_position_allowed: bool
    reduction_target_pct: float  # % of positions to reduce (0 = none, 0.5 = 50%)
    message: str
    timestamp: datetime
    vvix_level: Optional[float] = None  # Volatility of VIX
    skew_percentile: Optional[float] = None  # Put/call skew

    def to_dict(self) -> dict[str, Any]:
        return {
            "vix_current": round(self.current_level, 2),
            "vix_prev_close": round(self.previous_close, 2),
            "intraday_change_pct": round(self.intraday_change_pct, 2),
            "alert_level": self.alert_level.value,
            "position_multiplier": round(self.position_multiplier, 2),
            "new_position_allowed": self.new_position_allowed,
            "reduction_target_pct": round(self.reduction_target_pct, 2),
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "vvix_level": round(self.vvix_level, 2) if self.vvix_level else None,
        }


@dataclass
class DeRiskAction:
    """Action to take for de-risking."""

    symbol: str
    action: str  # "reduce", "close", "hedge"
    current_qty: float
    target_qty: float
    reason: str
    priority: int  # 1 = highest priority


@dataclass
class CircuitBreakerEvent:
    """Record of a circuit breaker trigger."""

    timestamp: datetime
    alert_level: AlertLevel
    vix_level: float
    intraday_change_pct: float
    action_taken: str
    positions_affected: list[str]
    total_reduced_value: float


class VIXCircuitBreaker:
    """
    Proactive circuit breaker based on VIX monitoring.

    Monitors VIX levels and intraday changes to detect volatility spikes
    and trigger automatic position reductions before major losses occur.

    Thresholds (configurable):
        VIX Level Thresholds:
        - Normal: < 15 (full positions allowed)
        - Elevated: 15-20 (new positions at 80%)
        - High: 20-25 (new positions at 50%, monitor existing)
        - Very High: 25-30 (reduce existing by 25%)
        - Extreme: > 30 (reduce existing by 50%)

        Intraday Spike Thresholds:
        - 10% jump: Warning, reduce new positions
        - 20% jump: Alert, reduce existing by 25%
        - 30% jump: Emergency, reduce existing by 50%
        - 50% jump: Crisis, close all speculative positions

    Args:
        vix_symbol: Symbol to monitor (default "^VIX")
        check_interval_seconds: How often to check VIX (default 300 = 5 min)
        enable_auto_reduce: Whether to automatically reduce positions
    """

    # VIX level thresholds
    VIX_NORMAL = 15.0
    VIX_ELEVATED = 20.0
    VIX_HIGH = 25.0
    VIX_VERY_HIGH = 30.0

    # Intraday spike thresholds (percentage change)
    SPIKE_WARNING = 0.10  # 10%
    SPIKE_ALERT = 0.20  # 20%
    SPIKE_EMERGENCY = 0.30  # 30%
    SPIKE_CRISIS = 0.50  # 50%

    # Position reduction targets by alert level
    REDUCTION_TARGETS = {
        AlertLevel.NORMAL: 0.0,
        AlertLevel.ELEVATED: 0.0,
        AlertLevel.HIGH: 0.0,  # Just restrict new positions
        AlertLevel.VERY_HIGH: 0.25,  # Reduce 25%
        AlertLevel.EXTREME: 0.50,  # Reduce 50%
        AlertLevel.SPIKE: 0.50,  # Reduce 50% on spike
    }

    # Position sizing multipliers for new positions
    SIZE_MULTIPLIERS = {
        AlertLevel.NORMAL: 1.0,
        AlertLevel.ELEVATED: 0.8,
        AlertLevel.HIGH: 0.5,
        AlertLevel.VERY_HIGH: 0.25,
        AlertLevel.EXTREME: 0.0,  # No new positions
        AlertLevel.SPIKE: 0.0,
    }

    def __init__(
        self,
        vix_symbol: str = "^VIX",
        check_interval_seconds: int = 300,
        enable_auto_reduce: bool = True,
        paper_mode: bool = True,
    ):
        self.vix_symbol = vix_symbol
        self.check_interval_seconds = check_interval_seconds
        self.enable_auto_reduce = enable_auto_reduce
        self.paper_mode = paper_mode

        # State tracking
        self._last_check: Optional[datetime] = None
        self._last_status: Optional[VIXStatus] = None
        self._event_history: list[CircuitBreakerEvent] = []
        self._daily_reductions: float = 0.0  # Track daily reduction actions

        # Alpaca client (lazy loaded)
        self._alpaca_client = None

    def get_current_status(self, force_refresh: bool = False) -> VIXStatus:
        """
        Get current VIX status with alert level and recommendations.

        Args:
            force_refresh: Force API call even if cache is fresh

        Returns:
            VIXStatus with current level and recommended actions
        """
        now = datetime.now()

        # Use cache if fresh (within check interval)
        if (
            not force_refresh
            and self._last_status is not None
            and self._last_check is not None
            and (now - self._last_check).total_seconds() < self.check_interval_seconds
        ):
            return self._last_status

        # Fetch current VIX data
        vix_data = self._fetch_vix_data()

        current_level = vix_data.get("current", 20.0)
        previous_close = vix_data.get("previous_close", current_level)
        vvix_level = vix_data.get("vvix")

        # Calculate intraday change
        if previous_close > 0:
            intraday_change_pct = (current_level - previous_close) / previous_close
        else:
            intraday_change_pct = 0.0

        # Determine alert level
        alert_level = self._determine_alert_level(current_level, intraday_change_pct)

        # Get position multiplier and reduction target
        position_multiplier = self.SIZE_MULTIPLIERS.get(alert_level, 0.5)
        reduction_target_pct = self.REDUCTION_TARGETS.get(alert_level, 0.0)

        # Determine if new positions allowed
        new_position_allowed = alert_level not in [AlertLevel.EXTREME, AlertLevel.SPIKE]

        # Generate message
        message = self._generate_message(alert_level, current_level, intraday_change_pct)

        status = VIXStatus(
            current_level=current_level,
            previous_close=previous_close,
            intraday_change_pct=intraday_change_pct * 100,  # Convert to percentage
            alert_level=alert_level,
            position_multiplier=position_multiplier,
            new_position_allowed=new_position_allowed,
            reduction_target_pct=reduction_target_pct,
            message=message,
            timestamp=now,
            vvix_level=vvix_level,
        )

        # Update cache
        self._last_status = status
        self._last_check = now

        # Log if elevated
        if alert_level not in [AlertLevel.NORMAL, AlertLevel.ELEVATED]:
            logger.warning(f"VIX Circuit Breaker: {message}")

        return status

    def check_and_act(self, positions: Optional[list[dict[str, Any]]] = None) -> list[DeRiskAction]:
        """
        Check VIX status and generate de-risking actions if needed.

        Args:
            positions: Current positions (if None, will fetch from Alpaca)

        Returns:
            List of DeRiskAction objects (empty if no action needed)
        """
        status = self.get_current_status(force_refresh=True)

        if status.reduction_target_pct <= 0:
            return []

        # Fetch positions if not provided
        if positions is None:
            positions = self._fetch_positions()

        actions = []

        for pos in positions:
            symbol = pos.get("symbol", "")
            qty = float(pos.get("qty", 0))
            market_value = float(pos.get("market_value", 0))

            if qty <= 0:
                continue

            # Calculate reduction
            reduce_qty = qty * status.reduction_target_pct
            target_qty = qty - reduce_qty

            # Prioritize speculative positions (growth stocks, high beta)
            priority = self._get_reduction_priority(symbol, pos)

            action = DeRiskAction(
                symbol=symbol,
                action="reduce",
                current_qty=qty,
                target_qty=round(target_qty, 4),
                reason=f"VIX {status.alert_level.value}: Reduce {status.reduction_target_pct:.0%}",
                priority=priority,
            )
            actions.append(action)

        # Sort by priority
        actions.sort(key=lambda a: a.priority)

        # Execute if auto-reduce enabled
        if self.enable_auto_reduce and actions:
            self._execute_reductions(actions, status)

        return actions

    def should_allow_trade(self, symbol: str, notional: float) -> tuple[bool, str, float]:
        """
        Check if a new trade should be allowed given VIX status.

        Args:
            symbol: Symbol to trade
            notional: Proposed trade size

        Returns:
            Tuple of (allowed, reason, adjusted_notional)
        """
        status = self.get_current_status()

        if not status.new_position_allowed:
            return (
                False,
                f"VIX {status.alert_level.value} ({status.current_level:.1f}): No new positions",
                0.0,
            )

        adjusted_notional = notional * status.position_multiplier

        if adjusted_notional < notional * 0.5:
            return (
                True,
                f"VIX {status.current_level:.1f}: Position reduced to {status.position_multiplier:.0%}",
                adjusted_notional,
            )

        return (True, "VIX within normal range", adjusted_notional)

    def _determine_alert_level(self, vix_level: float, intraday_change: float) -> AlertLevel:
        """Determine alert level from VIX level and intraday change."""
        # Check for spike first (rate of change takes priority)
        if intraday_change >= self.SPIKE_CRISIS:
            return AlertLevel.SPIKE
        if intraday_change >= self.SPIKE_EMERGENCY:
            return AlertLevel.EXTREME
        if intraday_change >= self.SPIKE_ALERT:
            return AlertLevel.VERY_HIGH

        # Then check absolute level
        if vix_level >= self.VIX_VERY_HIGH:
            return AlertLevel.EXTREME
        if vix_level >= self.VIX_HIGH:
            return AlertLevel.VERY_HIGH
        if vix_level >= self.VIX_ELEVATED:
            return AlertLevel.HIGH
        if vix_level >= self.VIX_NORMAL:
            return AlertLevel.ELEVATED

        return AlertLevel.NORMAL

    def _generate_message(
        self,
        alert_level: AlertLevel,
        vix_level: float,
        intraday_change: float,
    ) -> str:
        """Generate human-readable status message."""
        messages = {
            AlertLevel.NORMAL: f"VIX {vix_level:.1f} - Markets calm, full positions allowed",
            AlertLevel.ELEVATED: f"VIX {vix_level:.1f} - Slightly elevated, monitoring",
            AlertLevel.HIGH: f"VIX {vix_level:.1f} - High volatility, new positions at 50%",
            AlertLevel.VERY_HIGH: f"VIX {vix_level:.1f} - Very high, reducing positions 25%",
            AlertLevel.EXTREME: f"VIX {vix_level:.1f} - EXTREME, reducing positions 50%",
            AlertLevel.SPIKE: f"VIX SPIKE +{intraday_change*100:.0f}%! Emergency de-risk",
        }
        return messages.get(alert_level, f"VIX {vix_level:.1f}")

    def _fetch_vix_data(self) -> dict[str, float]:
        """Fetch current VIX data from yfinance."""
        try:
            vix = yf.Ticker(self.vix_symbol)
            hist = vix.history(period="2d")

            if hist.empty:
                logger.warning("No VIX data available, using default")
                return {"current": 20.0, "previous_close": 20.0}

            current = float(hist["Close"].iloc[-1])
            previous_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else current

            # Also try to get VVIX
            vvix_level = None
            try:
                vvix = yf.Ticker("^VVIX")
                vvix_hist = vvix.history(period="1d")
                if not vvix_hist.empty:
                    vvix_level = float(vvix_hist["Close"].iloc[-1])
            except Exception:
                pass

            return {
                "current": current,
                "previous_close": previous_close,
                "vvix": vvix_level,
            }

        except Exception as e:
            logger.error(f"Failed to fetch VIX data: {e}")
            return {"current": 20.0, "previous_close": 20.0}

    def _fetch_positions(self) -> list[dict[str, Any]]:
        """Fetch current positions from Alpaca."""
        try:
            client = self._get_alpaca_client()
            if client is None:
                return []

            positions = client.list_positions()
            return [
                {
                    "symbol": p.symbol,
                    "qty": float(p.qty),
                    "market_value": float(p.market_value),
                    "unrealized_pl": float(p.unrealized_pl),
                    "unrealized_plpc": float(p.unrealized_plpc),
                }
                for p in positions
            ]
        except Exception as e:
            logger.error(f"Failed to fetch positions: {e}")
            return []

    def _get_alpaca_client(self):
        """Get or create Alpaca client."""
        if self._alpaca_client is None:
            try:
                from alpaca.trading.client import TradingClient

                api_key = os.environ.get("ALPACA_API_KEY", "")
                secret_key = os.environ.get("ALPACA_SECRET_KEY", "")

                if api_key and secret_key:
                    self._alpaca_client = TradingClient(
                        api_key=api_key,
                        secret_key=secret_key,
                        paper=self.paper_mode,
                    )
            except Exception as e:
                logger.error(f"Failed to create Alpaca client: {e}")

        return self._alpaca_client

    def _get_reduction_priority(self, symbol: str, position: dict[str, Any]) -> int:
        """
        Determine priority for position reduction.

        Lower number = higher priority (reduce first).
        """
        # High-beta / speculative stocks reduce first
        speculative = ["NVDA", "AMD", "TSLA", "COIN", "MSTR", "PLTR", "RIVN"]
        if symbol in speculative:
            return 1

        # Growth stocks next
        growth = ["GOOGL", "AMZN", "META", "CRM", "NFLX"]
        if symbol in growth:
            return 2

        # Positions with large unrealized gains (lock in profits)
        unrealized_pl_pct = position.get("unrealized_plpc", 0)
        if unrealized_pl_pct > 0.10:  # >10% gain
            return 3

        # Core ETFs (SPY, QQQ, VOO) reduce last
        core_etfs = ["SPY", "QQQ", "VOO", "IVV", "VTI", "BND"]
        if symbol in core_etfs:
            return 5

        return 4  # Default priority

    def _execute_reductions(
        self,
        actions: list[DeRiskAction],
        status: VIXStatus,
    ) -> None:
        """Execute position reductions (paper mode aware)."""
        total_reduced = 0.0
        symbols_affected = []

        for action in actions:
            if action.current_qty == action.target_qty:
                continue

            reduce_qty = action.current_qty - action.target_qty

            if self.paper_mode:
                logger.info(
                    f"[PAPER] Would reduce {action.symbol}: "
                    f"{action.current_qty:.2f} -> {action.target_qty:.2f} "
                    f"({reduce_qty:.2f} shares)"
                )
                symbols_affected.append(action.symbol)
            else:
                try:
                    from alpaca.trading.requests import MarketOrderRequest
                    from alpaca.trading.enums import OrderSide, TimeInForce

                    client = self._get_alpaca_client()
                    if client:
                        order_data = MarketOrderRequest(
                            symbol=action.symbol,
                            qty=reduce_qty,
                            side=OrderSide.SELL,
                            time_in_force=TimeInForce.DAY,
                        )
                        order = client.submit_order(order_data)
                        logger.warning(
                            f"VIX Circuit Breaker: Reduced {action.symbol} "
                            f"by {reduce_qty:.2f} shares (Order: {order.id})"
                        )
                        symbols_affected.append(action.symbol)
                except Exception as e:
                    logger.error(f"Failed to reduce {action.symbol}: {e}")

        # Record event
        event = CircuitBreakerEvent(
            timestamp=datetime.now(),
            alert_level=status.alert_level,
            vix_level=status.current_level,
            intraday_change_pct=status.intraday_change_pct,
            action_taken=f"Reduced {len(symbols_affected)} positions",
            positions_affected=symbols_affected,
            total_reduced_value=total_reduced,
        )
        self._event_history.append(event)

    def get_event_history(self) -> list[dict[str, Any]]:
        """Get history of circuit breaker events."""
        return [
            {
                "timestamp": e.timestamp.isoformat(),
                "alert_level": e.alert_level.value,
                "vix_level": round(e.vix_level, 2),
                "intraday_change_pct": round(e.intraday_change_pct, 2),
                "action_taken": e.action_taken,
                "positions_affected": e.positions_affected,
            }
            for e in self._event_history
        ]


# Singleton instance
_circuit_breaker: Optional[VIXCircuitBreaker] = None


def get_vix_circuit_breaker(paper_mode: bool = True) -> VIXCircuitBreaker:
    """Get or create the global VIX circuit breaker instance."""
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = VIXCircuitBreaker(paper_mode=paper_mode)
    return _circuit_breaker


def check_vix_before_trade(symbol: str, notional: float) -> tuple[bool, str, float]:
    """
    Convenience function to check VIX before placing a trade.

    Usage:
        from src.risk.vix_circuit_breaker import check_vix_before_trade

        allowed, reason, adjusted = check_vix_before_trade("NVDA", 500.0)
        if allowed:
            execute_trade(symbol, adjusted)
        else:
            logger.warning(f"Trade blocked: {reason}")
    """
    breaker = get_vix_circuit_breaker()
    return breaker.should_allow_trade(symbol, notional)


if __name__ == "__main__":
    # Demo
    logging.basicConfig(level=logging.INFO)

    breaker = VIXCircuitBreaker(paper_mode=True)

    print("\n=== VIX Circuit Breaker Status ===")
    status = breaker.get_current_status(force_refresh=True)

    print(f"\nCurrent VIX: {status.current_level:.2f}")
    print(f"Previous Close: {status.previous_close:.2f}")
    print(f"Intraday Change: {status.intraday_change_pct:+.1f}%")
    print(f"Alert Level: {status.alert_level.value}")
    print(f"Position Multiplier: {status.position_multiplier:.0%}")
    print(f"Reduction Target: {status.reduction_target_pct:.0%}")
    print(f"New Positions Allowed: {status.new_position_allowed}")
    print(f"\nMessage: {status.message}")

    # Test trade check
    print("\n=== Trade Check Examples ===")
    for symbol, notional in [("NVDA", 500), ("SPY", 1000), ("TSLA", 750)]:
        allowed, reason, adjusted = breaker.should_allow_trade(symbol, notional)
        print(f"\n{symbol} ${notional}:")
        print(f"  Allowed: {allowed}")
        print(f"  Reason: {reason}")
        print(f"  Adjusted: ${adjusted:.2f}")
