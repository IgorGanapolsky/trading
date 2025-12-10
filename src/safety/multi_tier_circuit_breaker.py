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
7. AUTOMATIC RE-ENGAGEMENT: Time-based recovery with progressive tier reduction

Tiers:
- TIER_1 (CAUTION): 1% daily loss - Log warning, reduce position sizes by 50%
- TIER_2 (WARNING): 2% daily loss - Soft pause (no new entries)
- TIER_3 (CRITICAL): 3% daily loss OR VIX spike - Hard stop, liquidation review
- TIER_4 (HALT): 5% daily loss OR market circuit breaker - Full halt, auto-recovery after timeout

Author: Trading System
Created: 2025-12-02
Updated: 2025-12-04 - Added automatic re-engagement with timeout
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any

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
    last_trigger_event: CircuitBreakerEvent | None
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

    # AUTOMATIC RE-ENGAGEMENT CONFIGURATION (new Dec 2025)
    # Time-based recovery: automatically re-engage after timeout if conditions normalize
    AUTO_RECOVERY_ENABLED = os.getenv("CB_AUTO_RECOVERY", "true").lower() == "true"
    HALT_RECOVERY_TIMEOUT_HOURS = float(os.getenv("CB_HALT_TIMEOUT_HOURS", "4.0"))  # 4 hours
    CRITICAL_RECOVERY_TIMEOUT_HOURS = float(
        os.getenv("CB_CRITICAL_TIMEOUT_HOURS", "2.0")
    )  # 2 hours
    WARNING_RECOVERY_TIMEOUT_HOURS = float(os.getenv("CB_WARNING_TIMEOUT_HOURS", "1.0"))  # 1 hour

    # Recovery conditions: must be met for automatic re-engagement
    RECOVERY_LOSS_THRESHOLD_PCT = float(os.getenv("CB_RECOVERY_LOSS_PCT", "0.005"))  # <0.5% loss
    RECOVERY_VIX_THRESHOLD = float(os.getenv("CB_RECOVERY_VIX", "22.0"))  # VIX < 22

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
        vix_level: float | None = None,
        spy_daily_change: float | None = None,
        rolling_volatility: float | None = None,
        historical_volatility: float | None = None,
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

        # Calculate daily loss percentage (needed for recovery check)
        daily_loss_pct = abs(daily_pnl) / portfolio_value if portfolio_value > 0 else 0
        is_loss = daily_pnl < 0
        daily_pnl_pct = -daily_loss_pct if is_loss else daily_loss_pct

        # Attempt automatic recovery before evaluating new conditions
        # This allows the system to recover from HALT/CRITICAL/WARNING if conditions normalize
        self._attempt_automatic_recovery(
            daily_pnl_pct=daily_pnl_pct,
            vix_level=vix_level,
        )

        active_triggers = []
        tier = CircuitBreakerTier.NORMAL
        action = CircuitBreakerAction.ALLOW
        position_multiplier = 1.0
        trigger_events = []

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

    def _attempt_automatic_recovery(
        self,
        daily_pnl_pct: float = 0.0,
        vix_level: float | None = None,
    ) -> bool:
        """
        Attempt automatic recovery from circuit breaker states.

        Recovery happens when:
        1. Timeout has elapsed since trigger
        2. Conditions have normalized (low loss, low VIX)

        Returns:
            True if recovery occurred, False otherwise
        """
        if not self.AUTO_RECOVERY_ENABLED:
            return False

        now = datetime.now()
        recovered = False

        # Check HALT recovery (Tier 4 → Tier 3 or Normal)
        if self.state.get("is_halted", False):
            halt_time_str = self.state.get("halt_triggered_at")
            if halt_time_str:
                halt_time = datetime.fromisoformat(halt_time_str)
                hours_since_halt = (now - halt_time).total_seconds() / 3600

                if hours_since_halt >= self.HALT_RECOVERY_TIMEOUT_HOURS:
                    # Check if conditions have normalized
                    conditions_normalized = self._check_recovery_conditions(
                        daily_pnl_pct, vix_level
                    )
                    if conditions_normalized:
                        # Recover to CRITICAL tier (progressive recovery)
                        self.state["is_halted"] = False
                        self.current_tier = CircuitBreakerTier.CRITICAL
                        self.current_action = CircuitBreakerAction.HARD_STOP
                        self.state["critical_triggered_at"] = now.isoformat()
                        self.state["auto_recovery"] = {
                            "timestamp": now.isoformat(),
                            "from_tier": "HALT",
                            "to_tier": "CRITICAL",
                            "hours_since_halt": hours_since_halt,
                        }
                        self._save_state()

                        event = self._create_event(
                            tier="CRITICAL",
                            action="auto_recovery",
                            reason=f"Auto-recovery from HALT after {hours_since_halt:.1f}h",
                            value=daily_pnl_pct,
                            threshold=self.RECOVERY_LOSS_THRESHOLD_PCT,
                        )
                        self._log_event(event)

                        logger.warning(
                            f"AUTO-RECOVERY: HALT → CRITICAL after {hours_since_halt:.1f}h "
                            f"(loss={daily_pnl_pct:.2%}, VIX={vix_level or 'N/A'})"
                        )
                        recovered = True

        # Check CRITICAL recovery (Tier 3 → Tier 2)
        if self.current_tier == CircuitBreakerTier.CRITICAL and not self.state.get(
            "is_halted", False
        ):
            critical_time_str = self.state.get("critical_triggered_at")
            if critical_time_str:
                critical_time = datetime.fromisoformat(critical_time_str)
                hours_since_critical = (now - critical_time).total_seconds() / 3600

                if hours_since_critical >= self.CRITICAL_RECOVERY_TIMEOUT_HOURS:
                    if self._check_recovery_conditions(daily_pnl_pct, vix_level):
                        self.current_tier = CircuitBreakerTier.WARNING
                        self.current_action = CircuitBreakerAction.SOFT_PAUSE
                        self.state["warning_triggered_at"] = now.isoformat()
                        self._save_state()

                        logger.info(
                            f"AUTO-RECOVERY: CRITICAL → WARNING after {hours_since_critical:.1f}h"
                        )
                        recovered = True

        # Check WARNING recovery (Tier 2 → Tier 1 or Normal)
        if self.current_tier == CircuitBreakerTier.WARNING:
            warning_time_str = self.state.get("warning_triggered_at")
            if warning_time_str:
                warning_time = datetime.fromisoformat(warning_time_str)
                hours_since_warning = (now - warning_time).total_seconds() / 3600

                if hours_since_warning >= self.WARNING_RECOVERY_TIMEOUT_HOURS:
                    if self._check_recovery_conditions(daily_pnl_pct, vix_level):
                        # Recover to CAUTION (reduced sizing) for safety
                        self.current_tier = CircuitBreakerTier.CAUTION
                        self.current_action = CircuitBreakerAction.REDUCE_SIZE
                        self._save_state()

                        logger.info(
                            f"AUTO-RECOVERY: WARNING → CAUTION after {hours_since_warning:.1f}h"
                        )
                        recovered = True

        return recovered

    def _check_recovery_conditions(
        self,
        daily_pnl_pct: float,
        vix_level: float | None,
    ) -> bool:
        """
        Check if conditions are favorable for automatic recovery.

        Returns:
            True if conditions are normalized enough for recovery
        """
        # Condition 1: Daily loss is within acceptable range
        loss_ok = daily_pnl_pct >= -self.RECOVERY_LOSS_THRESHOLD_PCT

        # Condition 2: VIX is below recovery threshold (or not available)
        vix_ok = vix_level is None or vix_level < self.RECOVERY_VIX_THRESHOLD

        return loss_ok and vix_ok

    def _reset_daily_if_needed(self) -> None:
        """Reset daily counters if it's a new day."""
        today = date.today().isoformat()
        last_reset = self.state.get("last_reset", "")

        if last_reset != today:
            # Reset daily state but preserve halt status and trigger timestamps
            is_halted = self.state.get("is_halted", False)
            halt_triggered_at = self.state.get("halt_triggered_at")
            critical_triggered_at = self.state.get("critical_triggered_at")
            warning_triggered_at = self.state.get("warning_triggered_at")

            self.state = {
                "last_reset": today,
                "is_halted": is_halted,
                "halt_triggered_at": halt_triggered_at,
                "critical_triggered_at": critical_triggered_at,
                "warning_triggered_at": warning_triggered_at,
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
            # Track when halt was triggered for automatic recovery timeout
            self.state["halt_triggered_at"] = datetime.now().isoformat()
            logger.warning(
                f"HALT triggered at {self.state['halt_triggered_at']} - "
                f"auto-recovery after {self.HALT_RECOVERY_TIMEOUT_HOURS}h if conditions normalize"
            )
        elif action == CircuitBreakerAction.HARD_STOP:
            # Track critical tier trigger time
            self.state["critical_triggered_at"] = datetime.now().isoformat()
        elif action == CircuitBreakerAction.SOFT_PAUSE:
            # Track warning tier trigger time
            self.state["warning_triggered_at"] = datetime.now().isoformat()

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
def get_vix_level() -> float | None:
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


def get_spy_daily_change() -> float | None:
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
_GLOBAL_CIRCUIT_BREAKER: MultiTierCircuitBreaker | None = None


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
