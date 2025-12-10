"""
Kill Switch - Manual emergency stop for all trading.

Provides multiple ways to halt trading immediately:
1. File-based kill switch (create KILL_SWITCH file)
2. API endpoint for remote kill
3. CLI command
4. Automatic re-enable with timeout

When activated:
- All new trades blocked
- Existing orders cancelled
- Alert sent via all channels
- Audit log created

Author: Trading System
Created: 2025-12-08
"""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Kill switch file locations
KILL_SWITCH_FILE = Path("data/KILL_SWITCH")
KILL_SWITCH_STATE = Path("data/kill_switch_state.json")


class KillSwitch:
    """
    Emergency kill switch for halting all trading.

    Multiple activation methods:
    1. File-based: Create data/KILL_SWITCH file
    2. Programmatic: Call activate()
    3. Environment: Set TRADING_KILL_SWITCH=1

    The kill switch blocks ALL trading until explicitly deactivated.
    """

    def __init__(
        self,
        kill_file: Path = KILL_SWITCH_FILE,
        state_file: Path = KILL_SWITCH_STATE,
        auto_disable_hours: Optional[float] = None,
    ):
        """
        Initialize kill switch.

        Args:
            kill_file: Path to kill switch trigger file
            state_file: Path to state persistence file
            auto_disable_hours: Auto-disable after N hours (None = manual only)
        """
        self.kill_file = Path(kill_file)
        self.state_file = Path(state_file)
        self.auto_disable_hours = auto_disable_hours

        # Ensure directories exist
        self.kill_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Load state
        self._state = self._load_state()

    def _load_state(self) -> dict:
        """Load kill switch state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "active": False,
            "activated_at": None,
            "activated_by": None,
            "reason": None,
            "auto_disable_at": None,
            "history": [],
        }

    def _save_state(self) -> None:
        """Save kill switch state to file."""
        try:
            with open(self.state_file, "w") as f:
                json.dump(self._state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save kill switch state: {e}")

    def is_active(self) -> bool:
        """
        Check if kill switch is currently active.

        Checks in order:
        1. Environment variable TRADING_KILL_SWITCH=1
        2. Kill switch file exists
        3. Programmatic activation state

        Also checks auto-disable timeout.
        """
        # Check environment variable
        if os.environ.get("TRADING_KILL_SWITCH", "").lower() in ("1", "true", "yes"):
            return True

        # Check file-based kill switch
        if self.kill_file.exists():
            return True

        # Check programmatic state
        if self._state.get("active"):
            # Check auto-disable
            if self._state.get("auto_disable_at"):
                auto_disable = datetime.fromisoformat(self._state["auto_disable_at"])
                if datetime.now() >= auto_disable:
                    logger.info("Kill switch auto-disabled after timeout")
                    self.deactivate("system", "Auto-disabled after timeout")
                    return False
            return True

        return False

    def activate(
        self,
        activated_by: str = "unknown",
        reason: str = "Manual activation",
        auto_disable_hours: Optional[float] = None,
        send_alert: bool = True,
    ) -> dict:
        """
        Activate the kill switch.

        Args:
            activated_by: Who/what triggered the kill switch
            reason: Reason for activation
            auto_disable_hours: Auto-disable after N hours (overrides default)
            send_alert: Whether to send emergency alerts

        Returns:
            Activation status dict
        """
        now = datetime.now()
        auto_disable = auto_disable_hours or self.auto_disable_hours

        self._state["active"] = True
        self._state["activated_at"] = now.isoformat()
        self._state["activated_by"] = activated_by
        self._state["reason"] = reason

        if auto_disable:
            self._state["auto_disable_at"] = (now + timedelta(hours=auto_disable)).isoformat()
        else:
            self._state["auto_disable_at"] = None

        # Add to history
        self._state["history"].append(
            {
                "action": "activated",
                "timestamp": now.isoformat(),
                "activated_by": activated_by,
                "reason": reason,
            }
        )

        # Keep last 100 history entries
        self._state["history"] = self._state["history"][-100:]

        self._save_state()

        # Create kill switch file as backup trigger
        try:
            with open(self.kill_file, "w") as f:
                f.write("KILL SWITCH ACTIVE\n")
                f.write(f"Activated: {now.isoformat()}\n")
                f.write(f"By: {activated_by}\n")
                f.write(f"Reason: {reason}\n")
        except Exception as e:
            logger.error(f"Failed to create kill switch file: {e}")

        logger.critical(f"🛑 KILL SWITCH ACTIVATED by {activated_by}: {reason}")

        # Send alert
        if send_alert:
            try:
                from src.safety.emergency_alerts import get_alerts

                alerts = get_alerts()
                alerts.kill_switch_alert(activated_by, reason)
            except Exception as e:
                logger.error(f"Failed to send kill switch alert: {e}")

        return {
            "status": "activated",
            "activated_at": now.isoformat(),
            "activated_by": activated_by,
            "reason": reason,
            "auto_disable_at": self._state.get("auto_disable_at"),
        }

    def deactivate(
        self,
        deactivated_by: str = "unknown",
        reason: str = "Manual deactivation",
        send_alert: bool = True,
    ) -> dict:
        """
        Deactivate the kill switch.

        Args:
            deactivated_by: Who/what deactivated the kill switch
            reason: Reason for deactivation
            send_alert: Whether to send notification

        Returns:
            Deactivation status dict
        """
        if not self.is_active():
            return {"status": "already_inactive"}

        now = datetime.now()
        was_active_since = self._state.get("activated_at")

        self._state["active"] = False
        self._state["activated_at"] = None
        self._state["activated_by"] = None
        self._state["reason"] = None
        self._state["auto_disable_at"] = None

        # Add to history
        self._state["history"].append(
            {
                "action": "deactivated",
                "timestamp": now.isoformat(),
                "deactivated_by": deactivated_by,
                "reason": reason,
                "was_active_since": was_active_since,
            }
        )

        self._save_state()

        # Remove kill switch file
        try:
            if self.kill_file.exists():
                self.kill_file.unlink()
        except Exception as e:
            logger.error(f"Failed to remove kill switch file: {e}")

        logger.info(f"✅ Kill switch deactivated by {deactivated_by}: {reason}")

        # Send notification
        if send_alert:
            try:
                from src.safety.emergency_alerts import get_alerts

                alerts = get_alerts()
                alerts.send_alert(
                    title="Kill Switch Deactivated",
                    message=f"Trading resumed by {deactivated_by}: {reason}",
                    priority="medium",
                )
            except Exception:
                pass

        return {
            "status": "deactivated",
            "deactivated_at": now.isoformat(),
            "deactivated_by": deactivated_by,
            "reason": reason,
        }

    def get_status(self) -> dict:
        """Get current kill switch status."""
        return {
            "active": self.is_active(),
            "activated_at": self._state.get("activated_at"),
            "activated_by": self._state.get("activated_by"),
            "reason": self._state.get("reason"),
            "auto_disable_at": self._state.get("auto_disable_at"),
            "file_exists": self.kill_file.exists(),
            "env_var_set": os.environ.get("TRADING_KILL_SWITCH", "").lower()
            in ("1", "true", "yes"),
        }

    def check_and_block(self) -> tuple[bool, Optional[str]]:
        """
        Check if trading should be blocked.

        Returns:
            Tuple of (is_blocked, reason)
        """
        if self.is_active():
            reason = self._state.get("reason", "Kill switch active")
            return True, reason
        return False, None


# Singleton instance
_kill_switch: Optional[KillSwitch] = None


def get_kill_switch() -> KillSwitch:
    """Get or create singleton kill switch instance."""
    global _kill_switch
    if _kill_switch is None:
        _kill_switch = KillSwitch()
    return _kill_switch


def is_trading_blocked() -> tuple[bool, Optional[str]]:
    """Quick check if trading is blocked by kill switch."""
    return get_kill_switch().check_and_block()


def activate_kill_switch(reason: str = "Emergency stop", by: str = "manual") -> dict:
    """Quick function to activate kill switch."""
    return get_kill_switch().activate(activated_by=by, reason=reason)


def deactivate_kill_switch(reason: str = "Resume trading", by: str = "manual") -> dict:
    """Quick function to deactivate kill switch."""
    return get_kill_switch().deactivate(deactivated_by=by, reason=reason)


# CLI interface
if __name__ == "__main__":
    import sys

    ks = get_kill_switch()

    if len(sys.argv) < 2:
        status = ks.get_status()
        print(f"Kill Switch Status: {'🛑 ACTIVE' if status['active'] else '✅ INACTIVE'}")
        print(json.dumps(status, indent=2))
        sys.exit(0)

    command = sys.argv[1].lower()

    if command == "activate":
        reason = sys.argv[2] if len(sys.argv) > 2 else "CLI activation"
        result = ks.activate(activated_by="cli", reason=reason)
        print(f"🛑 Kill switch activated: {result}")

    elif command == "deactivate":
        reason = sys.argv[2] if len(sys.argv) > 2 else "CLI deactivation"
        result = ks.deactivate(deactivated_by="cli", reason=reason)
        print(f"✅ Kill switch deactivated: {result}")

    elif command == "status":
        status = ks.get_status()
        print(json.dumps(status, indent=2))

    else:
        print("Usage: python kill_switch.py [activate|deactivate|status] [reason]")
        sys.exit(1)
