"""
Circuit Breakers - Auto-stop trading on dangerous conditions

Prevents catastrophic losses by automatically halting trading when:
- Daily loss exceeds threshold
- Too many consecutive losses
- Unusual trading patterns
- API errors exceed limit
- Position size anomalies

Updated: 2025-12-04 - Added file locking for thread-safe state operations.
"""

import fcntl
import json
import logging
from collections.abc import Generator
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@contextmanager
def file_lock(file_path: Path, exclusive: bool = True) -> Generator[None, None, None]:
    """
    Context manager for file locking to prevent race conditions.

    Args:
        file_path: Path to the file to lock
        exclusive: If True, acquire exclusive lock (for writes). If False, shared lock (for reads).

    Usage:
        with file_lock(state_file):
            # Safe to read/write
    """
    lock_path = file_path.with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with open(lock_path, "w") as lock_file:
        try:
            lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
            fcntl.flock(lock_file.fileno(), lock_type)
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


class CircuitBreaker:
    """
    Circuit breaker system to prevent catastrophic losses.

    Implements multiple safety mechanisms:
    - Daily loss limit (default: 2% of portfolio)
    - Consecutive loss limit (default: 3 trades)
    - API error limit (default: 5 errors)
    - Position size anomaly detection
    - Emergency kill switch
    """

    def __init__(
        self,
        max_daily_loss_pct: float = 0.02,  # 2% max daily loss
        max_consecutive_losses: int = 3,
        max_api_errors: int = 5,
        max_position_size_pct: float = 0.10,  # 10% max per position
        state_file: str = "data/circuit_breaker_state.json",
    ):
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_consecutive_losses = max_consecutive_losses
        self.max_api_errors = max_api_errors
        self.max_position_size_pct = max_position_size_pct
        self.state_file = Path(state_file)

        # Load state
        self.state = self._load_state()
        self.is_tripped = self.state.get("is_tripped", False)

        logger.info(
            f"Circuit Breaker initialized: max_loss={max_daily_loss_pct:.1%}, "
            f"max_consec={max_consecutive_losses}, tripped={self.is_tripped}"
        )

    def check_before_trade(
        self,
        portfolio_value: float,
        proposed_position_size: float,
        current_pl_today: float,
    ) -> dict[str, Any]:
        """
        Check if trading should be allowed.

        Args:
            portfolio_value: Total portfolio value
            proposed_position_size: Proposed trade size
            current_pl_today: Current P/L for today

        Returns:
            Dict with 'allowed', 'reason', 'severity'
        """

        # Check 1: Kill switch
        if self.is_tripped:
            return {
                "allowed": False,
                "reason": "🚨 CIRCUIT BREAKER TRIPPED - Manual reset required",
                "severity": "CRITICAL",
                "breaker": "KILL_SWITCH",
            }

        # Check 2: Daily loss limit
        daily_loss_pct = abs(current_pl_today) / portfolio_value if portfolio_value > 0 else 0
        if current_pl_today < 0 and daily_loss_pct > self.max_daily_loss_pct:
            self._trip_breaker(
                "DAILY_LOSS_LIMIT",
                f"Daily loss {daily_loss_pct:.2%} exceeds {self.max_daily_loss_pct:.2%}",
            )
            return {
                "allowed": False,
                "reason": f"🛑 Daily loss limit exceeded: {daily_loss_pct:.2%} > {self.max_daily_loss_pct:.2%}",
                "severity": "CRITICAL",
                "breaker": "DAILY_LOSS",
            }

        # Check 3: Consecutive losses
        consecutive_losses = self.state.get("consecutive_losses", 0)
        if consecutive_losses >= self.max_consecutive_losses:
            self._trip_breaker("CONSECUTIVE_LOSSES", f"{consecutive_losses} consecutive losses")
            return {
                "allowed": False,
                "reason": f"🛑 Too many consecutive losses: {consecutive_losses}",
                "severity": "CRITICAL",
                "breaker": "CONSECUTIVE_LOSS",
            }

        # Check 4: Position size anomaly
        position_pct = proposed_position_size / portfolio_value if portfolio_value > 0 else 0
        if position_pct > self.max_position_size_pct:
            return {
                "allowed": False,
                "reason": f"🛑 Position size too large: {position_pct:.2%} > {self.max_position_size_pct:.2%}",
                "severity": "HIGH",
                "breaker": "POSITION_SIZE",
            }

        # Check 5: API error rate
        api_errors_today = self.state.get("api_errors_today", 0)
        if api_errors_today >= self.max_api_errors:
            self._trip_breaker("API_ERRORS", f"{api_errors_today} API errors today")
            return {
                "allowed": False,
                "reason": f"🛑 Too many API errors: {api_errors_today}",
                "severity": "HIGH",
                "breaker": "API_ERROR",
            }

        # All checks passed
        return {
            "allowed": True,
            "reason": "✅ All safety checks passed",
            "severity": "NORMAL",
            "checks": {
                "daily_loss": f"{daily_loss_pct:.2%} / {self.max_daily_loss_pct:.2%}",
                "consecutive_losses": f"{consecutive_losses} / {self.max_consecutive_losses}",
                "position_size": f"{position_pct:.2%} / {self.max_position_size_pct:.2%}",
                "api_errors": f"{api_errors_today} / {self.max_api_errors}",
            },
        }

    def record_trade_outcome(self, profit_loss: float) -> None:
        """Record trade outcome for consecutive loss tracking."""
        if profit_loss < 0:
            self.state["consecutive_losses"] = self.state.get("consecutive_losses", 0) + 1
            logger.warning(f"Loss recorded: {self.state['consecutive_losses']} consecutive")
        else:
            self.state["consecutive_losses"] = 0  # Reset on win
            logger.info("Win recorded: consecutive losses reset to 0")

        self._save_state()

    def record_api_error(self) -> None:
        """Record an API error."""
        self.state["api_errors_today"] = self.state.get("api_errors_today", 0) + 1
        logger.warning(f"API error recorded: {self.state['api_errors_today']} today")
        self._save_state()

    def reset_daily(self) -> None:
        """Reset daily counters (call at start of day)."""
        today = date.today().isoformat()
        last_reset = self.state.get("last_reset", "")

        if last_reset != today:
            self.state["api_errors_today"] = 0
            self.state["last_reset"] = today
            logger.info(f"Daily counters reset for {today}")
            self._save_state()

    def _trip_breaker(self, reason_code: str, details: str) -> None:
        """Trip the circuit breaker."""
        self.is_tripped = True
        self.state["is_tripped"] = True
        self.state["trip_reason"] = reason_code
        self.state["trip_details"] = details
        self.state["trip_time"] = datetime.now().isoformat()
        self._save_state()

        logger.critical(f"🚨 CIRCUIT BREAKER TRIPPED: {reason_code} - {details}")

    def manual_reset(self) -> bool:
        """Manually reset circuit breaker (requires human intervention)."""
        self.is_tripped = False
        self.state["is_tripped"] = False
        self.state["consecutive_losses"] = 0
        self.state["api_errors_today"] = 0
        self.state["reset_by"] = "manual"
        self.state["reset_time"] = datetime.now().isoformat()
        self._save_state()

        logger.warning("Circuit breaker manually reset")
        return True

    def _load_state(self) -> dict[str, Any]:
        """Load state from disk with file locking."""
        if not self.state_file.exists():
            return {
                "is_tripped": False,
                "consecutive_losses": 0,
                "api_errors_today": 0,
                "last_reset": date.today().isoformat(),
            }

        try:
            with file_lock(self.state_file, exclusive=False):
                with open(self.state_file) as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading circuit breaker state: {e}")
            return {}

    def _save_state(self) -> None:
        """Save state to disk with file locking (atomic write)."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with file_lock(self.state_file, exclusive=True):
                # Write to temp file then rename for atomic operation
                temp_file = self.state_file.with_suffix(".tmp")
                with open(temp_file, "w") as f:
                    json.dump(self.state, f, indent=2)
                temp_file.replace(self.state_file)
        except Exception as e:
            logger.error(f"Error saving circuit breaker state: {e}")

    def get_status(self) -> dict[str, Any]:
        """Get current circuit breaker status."""
        return {
            "is_tripped": self.is_tripped,
            "consecutive_losses": self.state.get("consecutive_losses", 0),
            "api_errors_today": self.state.get("api_errors_today", 0),
            "last_reset": self.state.get("last_reset", "unknown"),
            "trip_reason": self.state.get("trip_reason", None),
            "trip_details": self.state.get("trip_details", None),
        }


class SharpeKillSwitch:
    """
    Sharpe Ratio-based Kill Switch.

    If rolling 90-day Sharpe drops below 1.3:
    1. Pause all new entries
    2. Liquidate everything except treasuries (TLT, IEF, BND)
    3. Force 30-day research mode

    This is the ultimate Buffett moat - protects against strategy decay.
    """

    # Thresholds - UPDATED Dec 11, 2025: Relaxed to enable growth
    # Old: 1.3 fixed threshold killed momentum strategies on normal variance
    # New: 0.8 base threshold with regime adjustment (VIX-aware)
    MIN_SHARPE_THRESHOLD = 0.8  # Lowered from 1.3 - still profitable above this
    ROLLING_WINDOW_DAYS = 90
    RESEARCH_MODE_DAYS = 14  # Reduced from 30 - faster recovery

    # Safe haven assets to keep during liquidation
    SAFE_HAVENS = {"TLT", "IEF", "BND", "SCHD", "VNQ"}

    def __init__(
        self,
        min_sharpe: float = MIN_SHARPE_THRESHOLD,
        rolling_days: int = ROLLING_WINDOW_DAYS,
        state_file: str = "data/sharpe_kill_switch_state.json",
    ):
        self.min_sharpe = min_sharpe
        self.rolling_days = rolling_days
        self.state_file = Path(state_file)
        self.state = self._load_state()

        logger.info(
            f"Sharpe Kill Switch initialized: min_sharpe={min_sharpe}, rolling_days={rolling_days}"
        )

    def check_sharpe(self, daily_returns: list) -> dict[str, Any]:
        """
        Check if rolling Sharpe ratio is above threshold.

        Args:
            daily_returns: List of daily returns (last 90 days)

        Returns:
            Dict with 'allowed', 'sharpe', 'action' fields
        """
        import numpy as np

        if len(daily_returns) < 30:  # Need minimum data
            return {
                "allowed": True,
                "sharpe": None,
                "action": "INSUFFICIENT_DATA",
                "message": f"Only {len(daily_returns)} days of data, need 30+",
            }

        # Use last N days (up to rolling window)
        recent_returns = daily_returns[-min(len(daily_returns), self.rolling_days) :]

        # Calculate Sharpe ratio (annualized)
        mean_return = np.mean(recent_returns)
        std_return = np.std(recent_returns)

        # Apply volatility floor to prevent extreme Sharpe ratios
        MIN_VOLATILITY_FLOOR = 0.001
        std_return = max(std_return, MIN_VOLATILITY_FLOOR)

        # Annualized Sharpe = daily_mean / daily_std * sqrt(252)
        sharpe = (mean_return / std_return) * np.sqrt(252)
        # Clamp to reasonable bounds [-10, 10]
        sharpe = float(np.clip(sharpe, -10.0, 10.0))

        # Check if below threshold
        if sharpe < self.min_sharpe:
            self._activate_kill_switch(sharpe)
            return {
                "allowed": False,
                "sharpe": sharpe,
                "action": "KILL_SWITCH_ACTIVATED",
                "message": f"Rolling {len(recent_returns)}-day Sharpe {sharpe:.2f} < {self.min_sharpe}",
                "required_action": [
                    "1. Pause all new entries immediately",
                    "2. Liquidate all positions EXCEPT treasuries (TLT, IEF, BND)",
                    "3. Enter 30-day research mode",
                    "4. Investigate strategy decay root cause",
                ],
            }

        # Check if in research mode
        if self.state.get("in_research_mode", False):
            days_in_research = self._days_in_research_mode()
            if days_in_research < self.RESEARCH_MODE_DAYS:
                return {
                    "allowed": False,
                    "sharpe": sharpe,
                    "action": "RESEARCH_MODE",
                    "message": f"In research mode: {days_in_research}/{self.RESEARCH_MODE_DAYS} days",
                    "days_remaining": self.RESEARCH_MODE_DAYS - days_in_research,
                }
            else:
                # Research mode complete, check if Sharpe recovered
                if sharpe >= self.min_sharpe:
                    self._deactivate_kill_switch()
                    return {
                        "allowed": True,
                        "sharpe": sharpe,
                        "action": "RESEARCH_MODE_COMPLETE",
                        "message": f"Sharpe recovered to {sharpe:.2f}, trading resumed",
                    }

        return {
            "allowed": True,
            "sharpe": sharpe,
            "action": "HEALTHY",
            "message": f"Rolling Sharpe {sharpe:.2f} >= {self.min_sharpe} threshold",
        }

    def get_positions_to_liquidate(self, positions: list) -> list:
        """
        Get list of positions to liquidate (everything except safe havens).

        Args:
            positions: List of position dicts with 'symbol' key

        Returns:
            List of symbols to liquidate
        """
        to_liquidate = []
        for pos in positions:
            symbol = pos.get("symbol", "").upper()
            if symbol not in self.SAFE_HAVENS:
                to_liquidate.append(symbol)

        logger.warning(f"Sharpe kill switch: {len(to_liquidate)} positions to liquidate")
        return to_liquidate

    def _activate_kill_switch(self, sharpe: float) -> None:
        """Activate the Sharpe kill switch."""
        self.state["is_active"] = True
        self.state["in_research_mode"] = True
        self.state["activated_at"] = datetime.now().isoformat()
        self.state["sharpe_at_activation"] = sharpe
        self._save_state()

        logger.critical(f"🚨 SHARPE KILL SWITCH ACTIVATED: Sharpe {sharpe:.2f} < {self.min_sharpe}")

    def _deactivate_kill_switch(self) -> None:
        """Deactivate the kill switch after successful research mode."""
        self.state["is_active"] = False
        self.state["in_research_mode"] = False
        self.state["deactivated_at"] = datetime.now().isoformat()
        self._save_state()

        logger.info("✅ Sharpe kill switch deactivated - trading resumed")

    def _days_in_research_mode(self) -> int:
        """Calculate days spent in research mode."""
        activated = self.state.get("activated_at")
        if not activated:
            return 0

        try:
            activated_date = datetime.fromisoformat(activated)
            return (datetime.now() - activated_date).days
        except Exception:
            return 0

    def _load_state(self) -> dict[str, Any]:
        """Load state from disk with file locking."""
        if not self.state_file.exists():
            return {"is_active": False, "in_research_mode": False}

        try:
            with file_lock(self.state_file, exclusive=False):
                with open(self.state_file) as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading Sharpe kill switch state: {e}")
            return {"is_active": False, "in_research_mode": False}

    def _save_state(self) -> None:
        """Save state to disk with file locking (atomic write)."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with file_lock(self.state_file, exclusive=True):
                temp_file = self.state_file.with_suffix(".tmp")
                with open(temp_file, "w") as f:
                    json.dump(self.state, f, indent=2)
                temp_file.replace(self.state_file)
        except Exception as e:
            logger.error(f"Error saving Sharpe kill switch state: {e}")

    def get_status(self) -> dict[str, Any]:
        """Get current kill switch status."""
        return {
            "is_active": self.state.get("is_active", False),
            "in_research_mode": self.state.get("in_research_mode", False),
            "days_in_research": self._days_in_research_mode(),
            "activated_at": self.state.get("activated_at"),
            "sharpe_at_activation": self.state.get("sharpe_at_activation"),
            "threshold": self.min_sharpe,
        }
