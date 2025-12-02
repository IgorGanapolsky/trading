"""
Multi-Tier Circuit Breaker System

Implements a sophisticated circuit breaker system with multiple tiers and
distinct soft/hard stop behaviors. Borrows ideas from market-wide circuit
breaker design used by major exchanges.

Key Features:
1. Multi-tier thresholds (CAUTION → WARNING → CRITICAL → HALT)
2. Soft pause: Stop new entries, manage exits only
3. Hard stop: Shut down all trading immediately
4. Detailed logging of which tier triggered and why
5. Market-wide index monitoring (SPY, VIX)
6. Rolling drawdown and volatility tracking

Tiers:
- TIER_1 (CAUTION): 1% daily loss - Log warning, reduce position sizes by 50%
- TIER_2 (WARNING): 2% daily loss - Soft pause (no new entries)
- TIER_3 (CRITICAL): 3% daily loss OR VIX spike - Hard stop, liquidation review
- TIER_4 (HALT): 5% daily loss OR market circuit breaker - Full halt, manual reset

Author: Trading System
Created: 2025-12-02
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CircuitBreakerTier(Enum):
    """Circuit breaker severity tiers."""

    NORMAL = auto()  # No breaker triggered
    CAUTION = auto()  # Tier 1: Reduce risk
    WARNING = auto()  # Tier 2: Soft pause
    CRITICAL = auto()  # Tier 3: Hard stop
    HALT = auto()  # Tier 4: Full halt


class CircuitBreakerAction(Enum):
    """Actions that can be taken by circuit breaker."""

    ALLOW = "allow"  # Normal trading allowed
    REDUCE_SIZE = "reduce_size"  # Reduce position sizes
    SOFT_PAUSE = "soft_pause"  # No new entries, manage exits only
    HARD_STOP = "hard_stop"  # Stop all trading, review positions
    FULL_HALT = "full_halt"  # Emergency halt, manual reset required


@dataclass
class CircuitBreakerEvent:
    """Record of a circuit breaker event."""

    timestamp: str
    tier: str
    action: str
    trigger_reason: str
    trigger_value: float
    threshold: float
    details: dict


@dataclass
class CircuitBreakerStatus:
    """Current status of the circuit breaker system."""

    current_tier: CircuitBreakerTier
    current_action: CircuitBreakerAction
    is_trading_allowed: bool
    is_new_entries_allowed: bool
    position_size_multiplier: float
    active_triggers: list[str]
    last_trigger_event: Optional[CircuitBreakerEvent]
    tier_history: list[CircuitBreakerEvent]


class MultiTierCircuitBreaker:
    """
    Multi-tier circuit breaker system with soft/hard stop distinction.

    Implements exchange-style circuit breakers adapted for individual trading:
    - Tier 1 (CAUTION): Reduce risk exposure
    - Tier 2 (WARNING): Soft pause - no new entries
    - Tier 3 (CRITICAL): Hard stop - halt trading, review positions
    - Tier 4 (HALT): Full halt - manual reset required

    Each tier logs exactly what triggered it and why.
    """

    # Tier thresholds (configurable via environment)
    TIER1_DAILY_LOSS_PCT = float(os.getenv("CB_TIER1_LOSS_PCT", "0.01"))  # 1%
    TIER2_DAILY_LOSS_PCT = float(os.getenv("CB_TIER2_LOSS_PCT", "0.02"))  # 2%
    TIER3_DAILY_LOSS_PCT = float(os.getenv("CB_TIER3_LOSS_PCT", "0.03"))  # 3%
    TIER4_DAILY_LOSS_PCT = float(os.getenv("CB_TIER4_LOSS_PCT", "0.05"))  # 5%

    # Volatility thresholds (VIX-based)
    VIX_CAUTION_LEVEL = float(os.getenv("CB_VIX_CAUTION", "25.0"))
    VIX_WARNING_LEVEL = float(os.getenv("CB_VIX_WARNING", "30.0"))
    VIX_CRITICAL_LEVEL = float(os.getenv("CB_VIX_CRITICAL", "40.0"))

    # Rolling volatility thresholds
    VOL_SPIKE_MULTIPLIER = float(os.getenv("CB_VOL_SPIKE_MULT", "2.0"))

    # Consecutive loss thresholds
    TIER1_CONSEC_LOSSES = int(os.getenv("CB_TIER1_CONSEC", "2"))
    TIER2_CONSEC_LOSSES = int(os.getenv("CB_TIER2_CONSEC", "3"))
    TIER3_CONSEC_LOSSES = int(os.getenv("CB_TIER3_CONSEC", "5"))

    # Market index thresholds (SPY daily move)
    MARKET_CAUTION_PCT = float(os.getenv("CB_MARKET_CAUTION", "0.02"))  # 2%
    MARKET_WARNING_PCT = float(os.getenv("CB_MARKET_WARNING", "0.03"))  # 3%
    MARKET_HALT_PCT = float(os.getenv("CB_MARKET_HALT", "0.07"))  # 7% (market-wide CB)

    def __init__(
        self,
        state_file: str = "data/multi_tier_circuit_breaker_state.json",
        event_log_file: str = "data/circuit_breaker_events.jsonl",
    ):
        self.state_file = Path(state_file)
        self.event_log_file = Path(event_log_file)
        self.state = self._load_state()
        self.current_tier = CircuitBreakerTier.NORMAL
        self.current_action = CircuitBreakerAction.ALLOW

        # Initialize from saved state
        if self.state.get("is_halted", False):
            self.current_tier = CircuitBreakerTier.HALT
            self.current_action = CircuitBreakerAction.FULL_HALT

        logger.info(
            f"MultiTierCircuitBreaker initialized: "
            f"tier={self.current_tier.name}, action={self.current_action.value}"
        )

    def evaluate(
        self,
        portfolio_value: float,
        daily_pnl: float,
        consecutive_losses: int = 0,
        vix_level: Optional[float] = None,
        spy_daily_change: Optional[float] = None,
        rolling_volatility: Optional[float] = None,
        historical_volatility: Optional[float] = None,
    ) -> CircuitBreakerStatus:
        """
        Evaluate all circuit breaker conditions and return current status.

        Args:
            portfolio_value: Current portfolio value
            daily_pnl: Today's P/L (negative = loss)
            consecutive_losses: Number of consecutive losing trades
            vix_level: Current VIX level (optional)
            spy_daily_change: SPY daily percentage change (optional)
            rolling_volatility: Recent realized volatility (optional)
            historical_volatility: Historical baseline volatility (optional)

        Returns:
            CircuitBreakerStatus with current tier, action, and details
        """
        # Reset daily if needed
        self._reset_daily_if_needed()

        active_triggers = []
        tier = CircuitBreakerTier.NORMAL
        action = CircuitBreakerAction.ALLOW
        position_multiplier = 1.0
        trigger_events = []

        # Calculate daily loss percentage
        daily_loss_pct = abs(daily_pnl) / portfolio_value if portfolio_value > 0 else 0
        is_loss = daily_pnl < 0

        # --- TIER 4: FULL HALT ---
        # Check for catastrophic conditions
        if is_loss and daily_loss_pct >= self.TIER4_DAILY_LOSS_PCT:
            tier = CircuitBreakerTier.HALT
            action = CircuitBreakerAction.FULL_HALT
            active_triggers.append(
                f"TIER4: Daily loss {daily_loss_pct:.2%} >= {self.TIER4_DAILY_LOSS_PCT:.2%}"
            )
            trigger_events.append(
                self._create_event(
                    tier="HALT",
                    action="full_halt",
                    reason="daily_loss_catastrophic",
                    value=daily_loss_pct,
                    threshold=self.TIER4_DAILY_LOSS_PCT,
                )
            )

        if spy_daily_change is not None and abs(spy_daily_change) >= self.MARKET_HALT_PCT:
            tier = CircuitBreakerTier.HALT
            action = CircuitBreakerAction.FULL_HALT
            active_triggers.append(
                f"TIER4: Market move {abs(spy_daily_change):.2%} >= {self.MARKET_HALT_PCT:.2%}"
            )
            trigger_events.append(
                self._create_event(
                    tier="HALT",
                    action="full_halt",
                    reason="market_circuit_breaker",
                    value=abs(spy_daily_change),
                    threshold=self.MARKET_HALT_PCT,
                )
            )

        # --- TIER 3: CRITICAL (HARD STOP) ---
        if tier == CircuitBreakerTier.NORMAL:
            if is_loss and daily_loss_pct >= self.TIER3_DAILY_LOSS_PCT:
                tier = CircuitBreakerTier.CRITICAL
                action = CircuitBreakerAction.HARD_STOP
                active_triggers.append(
                    f"TIER3: Daily loss {daily_loss_pct:.2%} >= {self.TIER3_DAILY_LOSS_PCT:.2%}"
                )
                trigger_events.append(
                    self._create_event(
                        tier="CRITICAL",
                        action="hard_stop",
                        reason="daily_loss_critical",
                        value=daily_loss_pct,
                        threshold=self.TIER3_DAILY_LOSS_PCT,
                    )
                )

            if vix_level is not None and vix_level >= self.VIX_CRITICAL_LEVEL:
                tier = CircuitBreakerTier.CRITICAL
                action = CircuitBreakerAction.HARD_STOP
                active_triggers.append(
                    f"TIER3: VIX {vix_level:.1f} >= {self.VIX_CRITICAL_LEVEL:.1f}"
                )
                trigger_events.append(
                    self._create_event(
                        tier="CRITICAL",
                        action="hard_stop",
                        reason="vix_critical",
                        value=vix_level,
                        threshold=self.VIX_CRITICAL_LEVEL,
                    )
                )

            if consecutive_losses >= self.TIER3_CONSEC_LOSSES:
                tier = CircuitBreakerTier.CRITICAL
                action = CircuitBreakerAction.HARD_STOP
                active_triggers.append(
                    f"TIER3: {consecutive_losses} consecutive losses >= {self.TIER3_CONSEC_LOSSES}"
                )
                trigger_events.append(
                    self._create_event(
                        tier="CRITICAL",
                        action="hard_stop",
                        reason="consecutive_losses_critical",
                        value=consecutive_losses,
                        threshold=self.TIER3_CONSEC_LOSSES,
                    )
                )

        # --- TIER 2: WARNING (SOFT PAUSE) ---
        if tier == CircuitBreakerTier.NORMAL:
            if is_loss and daily_loss_pct >= self.TIER2_DAILY_LOSS_PCT:
                tier = CircuitBreakerTier.WARNING
                action = CircuitBreakerAction.SOFT_PAUSE
                active_triggers.append(
                    f"TIER2: Daily loss {daily_loss_pct:.2%} >= {self.TIER2_DAILY_LOSS_PCT:.2%}"
                )
                trigger_events.append(
                    self._create_event(
                        tier="WARNING",
                        action="soft_pause",
                        reason="daily_loss_warning",
                        value=daily_loss_pct,
                        threshold=self.TIER2_DAILY_LOSS_PCT,
                    )
                )

            if vix_level is not None and vix_level >= self.VIX_WARNING_LEVEL:
                tier = CircuitBreakerTier.WARNING
                action = CircuitBreakerAction.SOFT_PAUSE
                active_triggers.append(
                    f"TIER2: VIX {vix_level:.1f} >= {self.VIX_WARNING_LEVEL:.1f}"
                )
                trigger_events.append(
                    self._create_event(
                        tier="WARNING",
                        action="soft_pause",
                        reason="vix_warning",
                        value=vix_level,
                        threshold=self.VIX_WARNING_LEVEL,
                    )
                )

            if consecutive_losses >= self.TIER2_CONSEC_LOSSES:
                tier = CircuitBreakerTier.WARNING
                action = CircuitBreakerAction.SOFT_PAUSE
                active_triggers.append(
                    f"TIER2: {consecutive_losses} consecutive losses >= {self.TIER2_CONSEC_LOSSES}"
                )
                trigger_events.append(
                    self._create_event(
                        tier="WARNING",
                        action="soft_pause",
                        reason="consecutive_losses_warning",
                        value=consecutive_losses,
                        threshold=self.TIER2_CONSEC_LOSSES,
                    )
                )

            if spy_daily_change is not None and abs(spy_daily_change) >= self.MARKET_WARNING_PCT:
                tier = CircuitBreakerTier.WARNING
                action = CircuitBreakerAction.SOFT_PAUSE
                active_triggers.append(
                    f"TIER2: Market move {abs(spy_daily_change):.2%} >= {self.MARKET_WARNING_PCT:.2%}"
                )
                trigger_events.append(
                    self._create_event(
                        tier="WARNING",
                        action="soft_pause",
                        reason="market_volatile",
                        value=abs(spy_daily_change),
                        threshold=self.MARKET_WARNING_PCT,
                    )
                )

        # --- TIER 1: CAUTION (REDUCE SIZE) ---
        if tier == CircuitBreakerTier.NORMAL:
            if is_loss and daily_loss_pct >= self.TIER1_DAILY_LOSS_PCT:
                tier = CircuitBreakerTier.CAUTION
                action = CircuitBreakerAction.REDUCE_SIZE
                position_multiplier = 0.5
                active_triggers.append(
                    f"TIER1: Daily loss {daily_loss_pct:.2%} >= {self.TIER1_DAILY_LOSS_PCT:.2%}"
                )
                trigger_events.append(
                    self._create_event(
                        tier="CAUTION",
                        action="reduce_size",
                        reason="daily_loss_caution",
                        value=daily_loss_pct,
                        threshold=self.TIER1_DAILY_LOSS_PCT,
                    )
                )

            if vix_level is not None and vix_level >= self.VIX_CAUTION_LEVEL:
                tier = CircuitBreakerTier.CAUTION
                action = CircuitBreakerAction.REDUCE_SIZE
                position_multiplier = 0.5
                active_triggers.append(
                    f"TIER1: VIX {vix_level:.1f} >= {self.VIX_CAUTION_LEVEL:.1f}"
                )
                trigger_events.append(
                    self._create_event(
                        tier="CAUTION",
                        action="reduce_size",
                        reason="vix_elevated",
                        value=vix_level,
                        threshold=self.VIX_CAUTION_LEVEL,
                    )
                )

            if consecutive_losses >= self.TIER1_CONSEC_LOSSES:
                tier = CircuitBreakerTier.CAUTION
                action = CircuitBreakerAction.REDUCE_SIZE
                position_multiplier = 0.5
                active_triggers.append(
                    f"TIER1: {consecutive_losses} consecutive losses >= {self.TIER1_CONSEC_LOSSES}"
                )
                trigger_events.append(
                    self._create_event(
                        tier="CAUTION",
                        action="reduce_size",
                        reason="consecutive_losses",
                        value=consecutive_losses,
                        threshold=self.TIER1_CONSEC_LOSSES,
                    )
                )

            if spy_daily_change is not None and abs(spy_daily_change) >= self.MARKET_CAUTION_PCT:
                tier = CircuitBreakerTier.CAUTION
                action = CircuitBreakerAction.REDUCE_SIZE
                position_multiplier = 0.7
                active_triggers.append(
                    f"TIER1: Market move {abs(spy_daily_change):.2%} >= {self.MARKET_CAUTION_PCT:.2%}"
                )
                trigger_events.append(
                    self._create_event(
                        tier="CAUTION",
                        action="reduce_size",
                        reason="market_move",
                        value=abs(spy_daily_change),
                        threshold=self.MARKET_CAUTION_PCT,
                    )
                )

            # Volatility spike check
            if (
                rolling_volatility is not None
                and historical_volatility is not None
                and historical_volatility > 0
            ):
                vol_ratio = rolling_volatility / historical_volatility
                if vol_ratio >= self.VOL_SPIKE_MULTIPLIER:
                    tier = CircuitBreakerTier.CAUTION
                    action = CircuitBreakerAction.REDUCE_SIZE
                    position_multiplier = 0.5
                    active_triggers.append(
                        f"TIER1: Volatility spike {vol_ratio:.1f}x >= {self.VOL_SPIKE_MULTIPLIER:.1f}x"
                    )
                    trigger_events.append(
                        self._create_event(
                            tier="CAUTION",
                            action="reduce_size",
                            reason="volatility_spike",
                            value=vol_ratio,
                            threshold=self.VOL_SPIKE_MULTIPLIER,
                        )
                    )

        # Update state and log events
        self.current_tier = tier
        self.current_action = action

        for event in trigger_events:
            self._log_event(event)

        if tier != CircuitBreakerTier.NORMAL:
            self._update_state(tier, action, active_triggers)
            logger.warning(
                f"Circuit breaker triggered: {tier.name} -> {action.value} | {active_triggers}"
            )

        # Determine trading permissions
        is_trading_allowed = action not in [
            CircuitBreakerAction.HARD_STOP,
            CircuitBreakerAction.FULL_HALT,
        ]
        is_new_entries_allowed = action not in [
            CircuitBreakerAction.SOFT_PAUSE,
            CircuitBreakerAction.HARD_STOP,
            CircuitBreakerAction.FULL_HALT,
        ]

        return CircuitBreakerStatus(
            current_tier=tier,
            current_action=action,
            is_trading_allowed=is_trading_allowed,
            is_new_entries_allowed=is_new_entries_allowed,
            position_size_multiplier=position_multiplier,
            active_triggers=active_triggers,
            last_trigger_event=trigger_events[-1] if trigger_events else None,
            tier_history=self.state.get("tier_history", [])[-10:],
        )

    def check_before_trade(
        self,
        trade_type: str = "entry",  # "entry" or "exit"
    ) -> dict[str, Any]:
        """
        Quick check before executing a trade.

        Args:
            trade_type: Type of trade ("entry" for new positions, "exit" for closing)

        Returns:
            Dict with 'allowed', 'reason', 'action'
        """
        if self.current_action == CircuitBreakerAction.FULL_HALT:
            return {
                "allowed": False,
                "reason": "🚨 FULL HALT - Manual reset required",
                "action": "full_halt",
                "tier": "HALT",
            }

        if self.current_action == CircuitBreakerAction.HARD_STOP:
            if trade_type == "entry":
                return {
                    "allowed": False,
                    "reason": "⛔ HARD STOP - No new entries, reviewing positions",
                    "action": "hard_stop",
                    "tier": "CRITICAL",
                }
            else:
                return {
                    "allowed": True,
                    "reason": "⚠️ HARD STOP - Exits allowed for risk management",
                    "action": "hard_stop_exit_allowed",
                    "tier": "CRITICAL",
                }

        if self.current_action == CircuitBreakerAction.SOFT_PAUSE:
            if trade_type == "entry":
                return {
                    "allowed": False,
                    "reason": "⏸️ SOFT PAUSE - No new entries, managing exits only",
                    "action": "soft_pause",
                    "tier": "WARNING",
                }
            else:
                return {
                    "allowed": True,
                    "reason": "⏸️ SOFT PAUSE - Exit management allowed",
                    "action": "soft_pause_exit_allowed",
                    "tier": "WARNING",
                }

        if self.current_action == CircuitBreakerAction.REDUCE_SIZE:
            return {
                "allowed": True,
                "reason": "⚠️ CAUTION - Trading allowed with reduced position sizes",
                "action": "reduce_size",
                "tier": "CAUTION",
                "position_multiplier": 0.5,
            }

        return {
            "allowed": True,
            "reason": "✅ Normal trading allowed",
            "action": "allow",
            "tier": "NORMAL",
        }

    def manual_reset(self, reason: str = "Manual reset by operator") -> bool:
        """
        Manually reset circuit breaker (requires human intervention).

        Args:
            reason: Reason for manual reset

        Returns:
            True if reset successful
        """
        self.current_tier = CircuitBreakerTier.NORMAL
        self.current_action = CircuitBreakerAction.ALLOW
        self.state["is_halted"] = False
        self.state["manual_reset"] = {
            "timestamp": datetime.now().isoformat(),
            "reason": reason,
        }
        self._save_state()

        event = self._create_event(
            tier="NORMAL",
            action="manual_reset",
            reason=reason,
            value=0,
            threshold=0,
        )
        self._log_event(event)

        logger.warning(f"Circuit breaker manually reset: {reason}")
        return True

    def get_status_report(self) -> dict[str, Any]:
        """Get comprehensive status report."""
        return {
            "current_tier": self.current_tier.name,
            "current_action": self.current_action.value,
            "is_halted": self.state.get("is_halted", False),
            "last_reset": self.state.get("last_reset"),
            "recent_events": self._get_recent_events(10),
            "thresholds": {
                "tier1_loss": self.TIER1_DAILY_LOSS_PCT,
                "tier2_loss": self.TIER2_DAILY_LOSS_PCT,
                "tier3_loss": self.TIER3_DAILY_LOSS_PCT,
                "tier4_loss": self.TIER4_DAILY_LOSS_PCT,
                "vix_caution": self.VIX_CAUTION_LEVEL,
                "vix_warning": self.VIX_WARNING_LEVEL,
                "vix_critical": self.VIX_CRITICAL_LEVEL,
            },
        }

    def _create_event(
        self,
        tier: str,
        action: str,
        reason: str,
        value: float,
        threshold: float,
    ) -> CircuitBreakerEvent:
        """Create a circuit breaker event record."""
        return CircuitBreakerEvent(
            timestamp=datetime.now().isoformat(),
            tier=tier,
            action=action,
            trigger_reason=reason,
            trigger_value=value,
            threshold=threshold,
            details={},
        )

    def _log_event(self, event: CircuitBreakerEvent) -> None:
        """Log event to JSONL file."""
        try:
            self.event_log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.event_log_file, "a") as f:
                f.write(
                    json.dumps(
                        {
                            "timestamp": event.timestamp,
                            "tier": event.tier,
                            "action": event.action,
                            "trigger_reason": event.trigger_reason,
                            "trigger_value": event.trigger_value,
                            "threshold": event.threshold,
                        }
                    )
                    + "\n"
                )
        except Exception as e:
            logger.error(f"Error logging circuit breaker event: {e}")

    def _get_recent_events(self, count: int = 10) -> list[dict]:
        """Get recent circuit breaker events."""
        events = []
        try:
            if self.event_log_file.exists():
                with open(self.event_log_file) as f:
                    for line in f:
                        try:
                            events.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"Error reading circuit breaker events: {e}")

        return events[-count:]

    def _reset_daily_if_needed(self) -> None:
        """Reset daily counters if it's a new day."""
        today = date.today().isoformat()
        last_reset = self.state.get("last_reset", "")

        if last_reset != today:
            # Reset daily state but preserve halt status
            is_halted = self.state.get("is_halted", False)
            self.state = {
                "last_reset": today,
                "is_halted": is_halted,
                "tier_history": self.state.get("tier_history", [])[-100:],
            }
            if not is_halted:
                self.current_tier = CircuitBreakerTier.NORMAL
                self.current_action = CircuitBreakerAction.ALLOW
            self._save_state()
            logger.info(f"Daily circuit breaker reset for {today}")

    def _update_state(
        self, tier: CircuitBreakerTier, action: CircuitBreakerAction, triggers: list[str]
    ) -> None:
        """Update circuit breaker state."""
        self.state["current_tier"] = tier.name
        self.state["current_action"] = action.value
        self.state["active_triggers"] = triggers
        self.state["last_trigger_time"] = datetime.now().isoformat()

        if action == CircuitBreakerAction.FULL_HALT:
            self.state["is_halted"] = True

        # Append to tier history
        if "tier_history" not in self.state:
            self.state["tier_history"] = []
        self.state["tier_history"].append(
            {
                "timestamp": datetime.now().isoformat(),
                "tier": tier.name,
                "action": action.value,
                "triggers": triggers,
            }
        )

        self._save_state()

    def _load_state(self) -> dict:
        """Load state from disk."""
        if not self.state_file.exists():
            return {"last_reset": date.today().isoformat(), "is_halted": False}
        try:
            with open(self.state_file) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading circuit breaker state: {e}")
            return {"last_reset": date.today().isoformat(), "is_halted": False}

    def _save_state(self) -> None:
        """Save state to disk."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, "w") as f:
                json.dump(self.state, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving circuit breaker state: {e}")


# Convenience functions
def get_vix_level() -> Optional[float]:
    """Fetch current VIX level."""
    try:
        import yfinance as yf

        vix = yf.Ticker("^VIX")
        hist = vix.history(period="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception as e:
        logger.debug(f"Error fetching VIX: {e}")
    return None


def get_spy_daily_change() -> Optional[float]:
    """Fetch SPY daily percentage change."""
    try:
        import yfinance as yf

        spy = yf.Ticker("SPY")
        hist = spy.history(period="2d")
        if len(hist) >= 2:
            prev_close = hist["Close"].iloc[-2]
            curr_close = hist["Close"].iloc[-1]
            return (curr_close - prev_close) / prev_close
    except Exception as e:
        logger.debug(f"Error fetching SPY change: {e}")
    return None


# Global instance
_GLOBAL_CIRCUIT_BREAKER: Optional[MultiTierCircuitBreaker] = None


def get_circuit_breaker() -> MultiTierCircuitBreaker:
    """Get or create global multi-tier circuit breaker."""
    global _GLOBAL_CIRCUIT_BREAKER
    if _GLOBAL_CIRCUIT_BREAKER is None:
        _GLOBAL_CIRCUIT_BREAKER = MultiTierCircuitBreaker()
    return _GLOBAL_CIRCUIT_BREAKER


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("=" * 80)
    print("MULTI-TIER CIRCUIT BREAKER TEST")
    print("=" * 80)

    cb = MultiTierCircuitBreaker()

    # Test normal conditions
    status = cb.evaluate(
        portfolio_value=100000,
        daily_pnl=0,
        consecutive_losses=0,
    )
    print(f"\nNormal conditions: {status.current_tier.name} -> {status.current_action.value}")

    # Test Tier 1 (CAUTION)
    status = cb.evaluate(
        portfolio_value=100000,
        daily_pnl=-1100,  # 1.1% loss
        consecutive_losses=0,
    )
    print(f"Tier 1 loss: {status.current_tier.name} -> {status.current_action.value}")

    # Test Tier 2 (WARNING - soft pause)
    status = cb.evaluate(
        portfolio_value=100000,
        daily_pnl=-2100,  # 2.1% loss
        consecutive_losses=0,
    )
    print(f"Tier 2 loss: {status.current_tier.name} -> {status.current_action.value}")

    # Test trade check
    trade_check = cb.check_before_trade(trade_type="entry")
    print(f"Entry allowed: {trade_check['allowed']} - {trade_check['reason']}")

    trade_check = cb.check_before_trade(trade_type="exit")
    print(f"Exit allowed: {trade_check['allowed']} - {trade_check['reason']}")

    print("\n" + "=" * 80)
