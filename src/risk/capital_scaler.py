"""
Capital Scaler with Fibonacci Scaling and Circuit Breakers

Implements the Fibonacci Compounding Strategy for scaling daily investment
based on cumulative profits. Key principle: scaling is funded ONLY by profits,
never by adding external capital.

Fibonacci Scaling Rules:
- Start at level 0: $1/day
- Scale up when cumulative_profit >= next_level * 30 days
- Example: Scale from $1 to $2 when profit >= $60 ($2 * 30)
- Sequence: 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144...

Circuit Breakers:
- Max Drawdown (15%): HALT all trading, manual review required
- Scale-Down Threshold (10%): Reduce position sizes
- Daily Loss Limit (2%): Pause trading for rest of day

This module integrates with the existing RiskManager but adds capital
scaling logic specific to the North Star goal of $100/day.

Author: Trading System
Created: 2025-12-05
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Fibonacci sequence for scaling
FIBONACCI_SEQUENCE = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987]

# Storage path
CAPITAL_SCALER_STATE_PATH = Path("data/capital_scaler_state.json")


class TradingAction(Enum):
    """Actions from circuit breaker check."""

    CONTINUE = "continue"  # Normal trading
    PAUSE_TODAY = "pause_today"  # Stop trading for today
    SCALE_DOWN = "scale_down"  # Reduce position sizes
    HALT = "halt"  # Stop all trading, manual review


@dataclass
class ScalingState:
    """Persistent state for capital scaling."""

    current_level: int = 0  # Index in Fibonacci sequence
    daily_investment: float = 1.0  # Current daily investment amount
    cumulative_profit: float = 0.0  # Total profit since start
    peak_equity: float = 0.0  # Peak equity for drawdown calculation
    current_equity: float = 0.0  # Current equity
    start_date: str = ""  # When scaling started
    last_scale_date: str = ""  # Last time we scaled up
    scale_history: list = None  # History of scaling events

    def __post_init__(self):
        if self.scale_history is None:
            self.scale_history = []
        if not self.start_date:
            self.start_date = datetime.now().strftime("%Y-%m-%d")


@dataclass
class CircuitBreakerStatus:
    """Status of circuit breaker checks."""

    action: TradingAction
    reason: str
    current_drawdown_pct: float
    daily_pnl_pct: float
    suggested_position_size_multiplier: float  # 1.0 = normal, 0.5 = half size


class CapitalScaler:
    """
    Manages capital scaling using Fibonacci sequence with circuit breakers.

    The key insight is that scaling should only use profits - never add
    external capital. This ensures sustainable growth funded by actual
    trading performance.

    Example:
        scaler = CapitalScaler(initial_equity=100000)

        # Check before trading
        status = scaler.check_circuit_breakers(daily_pnl=-500)
        if status.action == TradingAction.CONTINUE:
            # Get current daily investment
            investment = scaler.get_daily_investment()
            execute_trade(investment)

        # Update after trade
        scaler.update_equity(new_equity=100150)
        scaler.record_daily_pnl(150.0)

        # Check for scale-up
        if scaler.should_scale_up():
            scaler.scale_up()
    """

    # Circuit breaker thresholds
    MAX_DRAWDOWN_PCT = 15.0  # Halt trading
    SCALE_DOWN_DRAWDOWN_PCT = 10.0  # Reduce position sizes
    DAILY_LOSS_LIMIT_PCT = 2.0  # Pause for today

    # Scaling parameters
    DAYS_TO_FUND_NEXT_LEVEL = 30  # Profit needed = next_level * 30

    def __init__(
        self,
        initial_equity: float = 100000.0,
        starting_level: int = 0,
        state_path: Optional[Path] = None,
    ):
        """
        Initialize the capital scaler.

        Args:
            initial_equity: Starting account equity
            starting_level: Starting Fibonacci level (0 = $1/day)
            state_path: Path to persist state (default: data/capital_scaler_state.json)
        """
        self.state_path = state_path or CAPITAL_SCALER_STATE_PATH
        self.state: ScalingState = self._load_state()

        # Initialize if new
        if self.state.peak_equity == 0:
            self.state.peak_equity = initial_equity
            self.state.current_equity = initial_equity
            self.state.current_level = starting_level
            self.state.daily_investment = FIBONACCI_SEQUENCE[starting_level]
            self._save_state()

        logger.info(
            f"CapitalScaler initialized: level={self.state.current_level}, "
            f"daily=${self.state.daily_investment}, "
            f"cumulative_profit=${self.state.cumulative_profit:.2f}"
        )

    def _load_state(self) -> ScalingState:
        """Load state from disk."""
        if self.state_path.exists():
            try:
                with open(self.state_path) as f:
                    data = json.load(f)
                return ScalingState(**data)
            except Exception as e:
                logger.warning(f"Failed to load capital scaler state: {e}")
        return ScalingState()

    def _save_state(self) -> None:
        """Persist state to disk."""
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_path, "w") as f:
            json.dump(asdict(self.state), f, indent=2)

    def get_daily_investment(self) -> float:
        """Get current daily investment amount."""
        return self.state.daily_investment

    def get_current_level(self) -> int:
        """Get current Fibonacci level."""
        return self.state.current_level

    def get_drawdown_pct(self) -> float:
        """Calculate current drawdown from peak."""
        if self.state.peak_equity <= 0:
            return 0.0
        drawdown = (self.state.peak_equity - self.state.current_equity) / self.state.peak_equity
        return max(0.0, drawdown * 100)

    def update_equity(self, new_equity: float) -> None:
        """
        Update current equity and track peak.

        Args:
            new_equity: Current account equity
        """
        self.state.current_equity = new_equity

        # Update peak if new high
        if new_equity > self.state.peak_equity:
            self.state.peak_equity = new_equity
            logger.info(f"New peak equity: ${new_equity:.2f}")

        self._save_state()

    def record_daily_pnl(self, pnl: float) -> None:
        """
        Record daily P&L and update cumulative profit.

        Args:
            pnl: Today's P&L (positive or negative)
        """
        self.state.cumulative_profit += pnl
        self._save_state()

        logger.info(f"Daily P&L: ${pnl:.2f}, Cumulative: ${self.state.cumulative_profit:.2f}")

    def check_circuit_breakers(
        self, daily_pnl: float, account_value: Optional[float] = None
    ) -> CircuitBreakerStatus:
        """
        Check circuit breakers and determine trading action.

        Args:
            daily_pnl: Today's P&L so far
            account_value: Current account value (uses stored if not provided)

        Returns:
            CircuitBreakerStatus with recommended action
        """
        if account_value is not None:
            self.state.current_equity = account_value

        drawdown_pct = self.get_drawdown_pct()

        # Calculate daily P&L as percentage
        daily_pnl_pct = (
            (daily_pnl / self.state.current_equity * 100) if self.state.current_equity > 0 else 0.0
        )

        # Check circuit breakers in order of severity

        # 1. Maximum drawdown - HALT
        if drawdown_pct >= self.MAX_DRAWDOWN_PCT:
            return CircuitBreakerStatus(
                action=TradingAction.HALT,
                reason=f"Max drawdown {drawdown_pct:.1f}% >= {self.MAX_DRAWDOWN_PCT}%",
                current_drawdown_pct=drawdown_pct,
                daily_pnl_pct=daily_pnl_pct,
                suggested_position_size_multiplier=0.0,
            )

        # 2. Daily loss limit - PAUSE
        if daily_pnl_pct <= -self.DAILY_LOSS_LIMIT_PCT:
            return CircuitBreakerStatus(
                action=TradingAction.PAUSE_TODAY,
                reason=f"Daily loss {daily_pnl_pct:.1f}% >= {self.DAILY_LOSS_LIMIT_PCT}%",
                current_drawdown_pct=drawdown_pct,
                daily_pnl_pct=daily_pnl_pct,
                suggested_position_size_multiplier=0.0,
            )

        # 3. Scale-down threshold - SCALE_DOWN
        if drawdown_pct >= self.SCALE_DOWN_DRAWDOWN_PCT:
            # Reduce position sizes proportionally
            reduction = (drawdown_pct - self.SCALE_DOWN_DRAWDOWN_PCT) / (
                self.MAX_DRAWDOWN_PCT - self.SCALE_DOWN_DRAWDOWN_PCT
            )
            multiplier = max(0.3, 1.0 - reduction * 0.7)  # Min 30% of normal size

            return CircuitBreakerStatus(
                action=TradingAction.SCALE_DOWN,
                reason=f"Drawdown {drawdown_pct:.1f}% >= {self.SCALE_DOWN_DRAWDOWN_PCT}%",
                current_drawdown_pct=drawdown_pct,
                daily_pnl_pct=daily_pnl_pct,
                suggested_position_size_multiplier=multiplier,
            )

        # 4. All clear - CONTINUE
        return CircuitBreakerStatus(
            action=TradingAction.CONTINUE,
            reason="All circuit breakers clear",
            current_drawdown_pct=drawdown_pct,
            daily_pnl_pct=daily_pnl_pct,
            suggested_position_size_multiplier=1.0,
        )

    def should_scale_up(self) -> bool:
        """
        Check if ready to scale to next Fibonacci level.

        Scaling rule: cumulative_profit >= next_level * DAYS_TO_FUND_NEXT_LEVEL

        Returns:
            True if should scale up
        """
        if self.state.current_level >= len(FIBONACCI_SEQUENCE) - 1:
            return False  # Already at max level

        next_level = self.state.current_level + 1
        next_daily = FIBONACCI_SEQUENCE[next_level]
        required_profit = next_daily * self.DAYS_TO_FUND_NEXT_LEVEL

        return self.state.cumulative_profit >= required_profit

    def scale_up(self) -> bool:
        """
        Scale up to the next Fibonacci level.

        Returns:
            True if scaled up, False if not ready
        """
        if not self.should_scale_up():
            logger.warning("Not ready to scale up")
            return False

        old_level = self.state.current_level
        old_daily = self.state.daily_investment

        self.state.current_level += 1
        self.state.daily_investment = FIBONACCI_SEQUENCE[self.state.current_level]
        self.state.last_scale_date = datetime.now().strftime("%Y-%m-%d")

        # Record in history
        self.state.scale_history.append(
            {
                "date": self.state.last_scale_date,
                "from_level": old_level,
                "to_level": self.state.current_level,
                "from_daily": old_daily,
                "to_daily": self.state.daily_investment,
                "cumulative_profit_at_scale": self.state.cumulative_profit,
            }
        )

        self._save_state()

        logger.info(
            f"SCALED UP: Level {old_level} -> {self.state.current_level}, "
            f"Daily ${old_daily} -> ${self.state.daily_investment}"
        )

        return True

    def should_scale_down(self) -> bool:
        """
        Check if should scale down due to losses.

        Scale down if cumulative profit drops below funding requirement
        for current level.

        Returns:
            True if should scale down
        """
        if self.state.current_level <= 0:
            return False  # Already at minimum

        current_daily = FIBONACCI_SEQUENCE[self.state.current_level]
        required_profit = current_daily * self.DAYS_TO_FUND_NEXT_LEVEL

        # Scale down if profit drops below 50% of requirement
        return self.state.cumulative_profit < required_profit * 0.5

    def scale_down(self) -> bool:
        """
        Scale down to previous Fibonacci level.

        Returns:
            True if scaled down, False if already at minimum
        """
        if self.state.current_level <= 0:
            logger.warning("Already at minimum level")
            return False

        old_level = self.state.current_level
        old_daily = self.state.daily_investment

        self.state.current_level -= 1
        self.state.daily_investment = FIBONACCI_SEQUENCE[self.state.current_level]
        self.state.last_scale_date = datetime.now().strftime("%Y-%m-%d")

        # Record in history
        self.state.scale_history.append(
            {
                "date": self.state.last_scale_date,
                "from_level": old_level,
                "to_level": self.state.current_level,
                "from_daily": old_daily,
                "to_daily": self.state.daily_investment,
                "cumulative_profit_at_scale": self.state.cumulative_profit,
                "reason": "drawdown_scale_down",
            }
        )

        self._save_state()

        logger.warning(
            f"SCALED DOWN: Level {old_level} -> {self.state.current_level}, "
            f"Daily ${old_daily} -> ${self.state.daily_investment}"
        )

        return True

    def get_progress_to_next_level(self) -> dict[str, Any]:
        """
        Get progress towards next scaling level.

        Returns:
            Dict with progress details
        """
        if self.state.current_level >= len(FIBONACCI_SEQUENCE) - 1:
            return {
                "at_max_level": True,
                "current_level": self.state.current_level,
                "current_daily": self.state.daily_investment,
            }

        next_level = self.state.current_level + 1
        next_daily = FIBONACCI_SEQUENCE[next_level]
        required_profit = next_daily * self.DAYS_TO_FUND_NEXT_LEVEL
        current_profit = self.state.cumulative_profit

        progress_pct = (current_profit / required_profit * 100) if required_profit > 0 else 0
        remaining = max(0, required_profit - current_profit)

        return {
            "current_level": self.state.current_level,
            "current_daily": self.state.daily_investment,
            "next_level": next_level,
            "next_daily": next_daily,
            "required_profit": required_profit,
            "current_profit": current_profit,
            "remaining_profit": remaining,
            "progress_pct": min(100, progress_pct),
            "ready_to_scale": self.should_scale_up(),
        }

    def get_status(self) -> dict[str, Any]:
        """Get complete status of capital scaler."""
        drawdown = self.get_drawdown_pct()

        return {
            "current_level": self.state.current_level,
            "daily_investment": self.state.daily_investment,
            "cumulative_profit": self.state.cumulative_profit,
            "current_equity": self.state.current_equity,
            "peak_equity": self.state.peak_equity,
            "drawdown_pct": drawdown,
            "start_date": self.state.start_date,
            "last_scale_date": self.state.last_scale_date,
            "scale_history_count": len(self.state.scale_history),
            "progress": self.get_progress_to_next_level(),
            "circuit_breakers": {
                "max_drawdown_threshold": self.MAX_DRAWDOWN_PCT,
                "scale_down_threshold": self.SCALE_DOWN_DRAWDOWN_PCT,
                "daily_loss_limit": self.DAILY_LOSS_LIMIT_PCT,
                "current_status": "OK" if drawdown < self.SCALE_DOWN_DRAWDOWN_PCT else "WARNING",
            },
        }

    def reset(self, new_initial_equity: Optional[float] = None) -> None:
        """
        Reset the scaler to initial state.

        Args:
            new_initial_equity: New starting equity (optional)
        """
        equity = new_initial_equity or self.state.current_equity

        self.state = ScalingState(
            current_level=0,
            daily_investment=FIBONACCI_SEQUENCE[0],
            cumulative_profit=0.0,
            peak_equity=equity,
            current_equity=equity,
            start_date=datetime.now().strftime("%Y-%m-%d"),
        )
        self._save_state()

        logger.info(f"Capital scaler reset. Starting equity: ${equity:.2f}")


# Convenience function
def get_capital_scaler(initial_equity: float = 100000.0) -> CapitalScaler:
    """Get a capital scaler instance."""
    return CapitalScaler(initial_equity=initial_equity)
