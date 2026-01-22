"""Crisis Monitor - Automatic TRADING_HALTED Trigger.

CRITICAL SAFETY COMPONENT - Jan 22, 2026 (LL-281)

This module automatically triggers TRADING_HALTED when crisis conditions detected:
1. Position count exceeds MAX_POSITIONS (4)
2. Unrealized loss exceeds CRISIS_LOSS_PCT (25%)
3. Single position loss exceeds 50% of premium

Root Cause of Crisis:
- TRADING_HALTED was only created manually
- System kept accumulating positions despite dangerous conditions
- No automated circuit breaker for position count

Solution:
- Continuous monitoring of position count and P/L
- Automatic creation of TRADING_HALTED when thresholds exceeded
- Clear logging of crisis conditions for post-mortem

Author: AI Trading System
Date: January 22, 2026
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Import from single source of truth
try:
    from src.core.trading_constants import (
        CRISIS_LOSS_PCT,
        CRISIS_POSITION_COUNT,
        MAX_POSITIONS,
    )
except ImportError:
    # Fallback values
    CRISIS_LOSS_PCT = 0.25
    CRISIS_POSITION_COUNT = 4
    MAX_POSITIONS = 4

# File paths
TRADING_HALTED_FILE = Path("data/TRADING_HALTED")
CRISIS_LOG_FILE = Path("data/crisis_log.json")


class CrisisCondition:
    """Represents a detected crisis condition."""

    def __init__(
        self,
        condition_type: str,
        current_value: float | int,
        threshold: float | int,
        details: str = "",
    ):
        self.condition_type = condition_type
        self.current_value = current_value
        self.threshold = threshold
        self.details = details
        self.detected_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.condition_type,
            "current_value": self.current_value,
            "threshold": self.threshold,
            "details": self.details,
            "detected_at": self.detected_at.isoformat(),
        }


def check_crisis_conditions(
    positions: list[dict[str, Any]],
    account_equity: float,
) -> list[CrisisCondition]:
    """
    Check for crisis conditions.

    Args:
        positions: List of current positions
        account_equity: Current account equity

    Returns:
        List of detected crisis conditions (empty if none)
    """
    conditions = []

    # Condition 1: Too many positions
    option_positions = [p for p in positions if len(p.get("symbol", "")) > 10]
    if len(option_positions) > MAX_POSITIONS:
        conditions.append(
            CrisisCondition(
                condition_type="EXCESS_POSITIONS",
                current_value=len(option_positions),
                threshold=MAX_POSITIONS,
                details=f"Option positions: {[p.get('symbol') for p in option_positions]}",
            )
        )

    # Condition 2: Total unrealized loss exceeds threshold
    total_unrealized_loss = sum(
        float(p.get("unrealized_pl", 0)) for p in positions if float(p.get("unrealized_pl", 0)) < 0
    )
    loss_pct = abs(total_unrealized_loss) / account_equity if account_equity > 0 else 0

    if loss_pct > CRISIS_LOSS_PCT:
        conditions.append(
            CrisisCondition(
                condition_type="EXCESS_UNREALIZED_LOSS",
                current_value=loss_pct,
                threshold=CRISIS_LOSS_PCT,
                details=f"Unrealized loss: ${abs(total_unrealized_loss):.2f} ({loss_pct*100:.1f}% of equity)",
            )
        )

    # Condition 3: Single position losing > 50%
    for pos in positions:
        cost_basis = float(pos.get("cost_basis", 0))
        unrealized_pl = float(pos.get("unrealized_pl", 0))
        if cost_basis > 0 and unrealized_pl < 0:
            loss_ratio = abs(unrealized_pl) / cost_basis
            if loss_ratio > 0.50:
                conditions.append(
                    CrisisCondition(
                        condition_type="SINGLE_POSITION_CRISIS",
                        current_value=loss_ratio,
                        threshold=0.50,
                        details=f"{pos.get('symbol')}: Lost {loss_ratio*100:.0f}% (${abs(unrealized_pl):.2f})",
                    )
                )

    return conditions


def trigger_trading_halt(
    conditions: list[CrisisCondition],
    auto_close_note: str = "",
) -> bool:
    """
    Create TRADING_HALTED file and log crisis.

    Args:
        conditions: List of crisis conditions that triggered halt
        auto_close_note: Optional note about auto-close actions

    Returns:
        True if halt was triggered, False if already halted
    """
    if TRADING_HALTED_FILE.exists():
        logger.warning("🚨 TRADING_HALTED already exists - not overwriting")
        return False

    # Create TRADING_HALTED file
    today = datetime.now()
    content = f"""CRISIS MODE - {today.strftime('%b %d, %Y')}
===========================

Trading halted automatically due to crisis conditions:
"""

    for condition in conditions:
        content += f"\n- {condition.condition_type}: {condition.current_value} (threshold: {condition.threshold})"
        if condition.details:
            content += f"\n  Details: {condition.details}"

    content += """

DO NOT REMOVE THIS FILE until:
1. All bleeding positions are closed
2. Portfolio returns to normal state
3. CEO explicitly approves resuming trading

To resume trading: rm data/TRADING_HALTED
"""

    if auto_close_note:
        content += f"\nAuto-close status: {auto_close_note}\n"

    # Ensure directory exists
    TRADING_HALTED_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Write halt file
    TRADING_HALTED_FILE.write_text(content)
    logger.critical("🚨🚨🚨 TRADING HALTED - Crisis detected! 🚨🚨🚨")
    logger.critical(f"Halt file created: {TRADING_HALTED_FILE}")

    # Log crisis details
    _log_crisis(conditions)

    return True


def _log_crisis(conditions: list[CrisisCondition]) -> None:
    """Log crisis to JSON file for analysis."""
    try:
        # Load existing log
        if CRISIS_LOG_FILE.exists():
            with open(CRISIS_LOG_FILE) as f:
                log = json.load(f)
        else:
            log = {"crises": []}

        # Add new crisis
        crisis_entry = {
            "timestamp": datetime.now().isoformat(),
            "conditions": [c.to_dict() for c in conditions],
        }
        log["crises"].append(crisis_entry)

        # Keep last 100 entries
        log["crises"] = log["crises"][-100:]

        # Write back
        CRISIS_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CRISIS_LOG_FILE, "w") as f:
            json.dump(log, f, indent=2)

        logger.info(f"Crisis logged to {CRISIS_LOG_FILE}")

    except Exception as e:
        logger.error(f"Failed to log crisis: {e}")


def monitor_and_halt_if_needed(
    positions: list[dict[str, Any]],
    account_equity: float,
) -> tuple[bool, list[CrisisCondition]]:
    """
    Main entry point: Check conditions and trigger halt if needed.

    Args:
        positions: List of current positions
        account_equity: Current account equity

    Returns:
        (was_halted, conditions)
    """
    conditions = check_crisis_conditions(positions, account_equity)

    if conditions:
        logger.warning(f"🚨 {len(conditions)} crisis condition(s) detected!")
        for c in conditions:
            logger.warning(f"  - {c.condition_type}: {c.details}")

        halted = trigger_trading_halt(conditions)
        return halted, conditions

    return False, []


def is_in_crisis_mode() -> bool:
    """Check if system is currently in crisis mode."""
    return TRADING_HALTED_FILE.exists()


def clear_crisis_mode(reason: str = "Manual clear") -> bool:
    """
    Clear crisis mode (remove TRADING_HALTED file).

    WARNING: Only use after positions are closed and CEO approves.

    Args:
        reason: Reason for clearing (logged)

    Returns:
        True if cleared, False if not in crisis mode
    """
    if not TRADING_HALTED_FILE.exists():
        return False

    try:
        # Log the clear action
        logger.warning(f"⚠️ Clearing crisis mode: {reason}")

        # Backup halt file content
        content = TRADING_HALTED_FILE.read_text()
        backup_path = Path(f"data/crisis_cleared_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        backup_path.write_text(f"Cleared: {reason}\n\nOriginal content:\n{content}")

        # Remove halt file
        TRADING_HALTED_FILE.unlink()
        logger.info("✅ Crisis mode cleared - trading can resume")

        return True

    except Exception as e:
        logger.error(f"Failed to clear crisis mode: {e}")
        return False
