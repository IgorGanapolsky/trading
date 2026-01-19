#!/usr/bin/env python3
"""
Position Compliance Self-Healing Script (LL-249)

Automatically detects and queues remediation for position limit violations:
1. MAX_POSITIONS = 4 (1 iron condor = 4 legs per CLAUDE.md)
2. MAX_POSITION_PCT = 5% per position

When violations are detected:
- Calculates which positions to close
- Adds to remediation_queue in system_state.json
- On market open, daily-trading workflow executes the queue

This is a SELF-HEALING mechanism - no manual intervention required.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Constants per CLAUDE.md
MAX_POSITIONS = 4
MAX_POSITION_PCT = 0.05  # 5%


def load_system_state(path: Path) -> dict:
    """Load system state from JSON file."""
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def save_system_state(path: Path, state: dict) -> bool:
    """Save system state to JSON file."""
    try:
        with open(path, "w") as f:
            json.dump(state, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to save system_state.json: {e}")
        return False


def detect_violations(state: dict) -> dict:
    """
    Detect position limit violations.

    Returns:
        dict with violation details and remediation plan
    """
    paper_account = state.get("paper_account", {})
    positions = state.get("positions", [])
    equity = paper_account.get("equity", 5000.0)

    violations = {
        "position_count": None,
        "position_size": [],
        "total_violations": 0,
        "remediation_queue": [],
    }

    # Check 1: Position count violation
    position_count = len(positions)
    if position_count > MAX_POSITIONS:
        excess = position_count - MAX_POSITIONS
        violations["position_count"] = {
            "current": position_count,
            "max": MAX_POSITIONS,
            "excess": excess,
        }
        violations["total_violations"] += 1
        logger.warning(
            f"POSITION COUNT VIOLATION: {position_count} positions > {MAX_POSITIONS} max"
        )

    # Check 2: Position size violations
    max_value = equity * MAX_POSITION_PCT
    for pos in positions:
        symbol = pos.get("symbol", "UNKNOWN")
        value = abs(pos.get("value", 0))

        if value > max_value:
            violations["position_size"].append(
                {
                    "symbol": symbol,
                    "value": value,
                    "max_allowed": max_value,
                    "excess_pct": ((value / max_value) - 1) * 100,
                }
            )
            violations["total_violations"] += 1
            logger.warning(
                f"POSITION SIZE VIOLATION: {symbol} ${value:.2f} > ${max_value:.2f} (5% of ${equity:.2f})"
            )

    # Create remediation plan
    if violations["total_violations"] > 0:
        violations["remediation_queue"] = create_remediation_plan(
            positions, equity, violations
        )

    return violations


def create_remediation_plan(
    positions: list, equity: float, violations: dict
) -> list:
    """
    Create a plan to remediate violations.

    Strategy:
    - For position count: Close smallest absolute value positions first
    - For position size: Close partial position to bring under limit

    Returns:
        list of remediation actions
    """
    plan = []
    max_value = equity * MAX_POSITION_PCT

    # Handle position size violations first (reduce size)
    for violation in violations.get("position_size", []):
        symbol = violation["symbol"]
        current_value = violation["value"]

        # Find the position
        for pos in positions:
            if pos.get("symbol") == symbol:
                qty = abs(pos.get("qty", 1))
                # Close 1 contract to reduce size
                if qty > 1:
                    plan.append(
                        {
                            "action": "REDUCE",
                            "symbol": symbol,
                            "contracts_to_close": 1,
                            "reason": f"Position ${current_value:.2f} exceeds 5% limit (${max_value:.2f})",
                            "priority": "HIGH",
                        }
                    )
                else:
                    # Can't reduce further - flag for review
                    plan.append(
                        {
                            "action": "REVIEW",
                            "symbol": symbol,
                            "reason": f"Single contract exceeds 5% limit - strategy mismatch",
                            "priority": "CRITICAL",
                        }
                    )
                break

    # Handle position count violations (close smallest positions)
    if violations.get("position_count"):
        excess = violations["position_count"]["excess"]

        # Sort positions by absolute value (close smallest first)
        sorted_positions = sorted(
            positions, key=lambda p: abs(p.get("value", 0))
        )

        # Plan to close excess positions
        for i, pos in enumerate(sorted_positions):
            if i >= excess:
                break
            symbol = pos.get("symbol", "UNKNOWN")
            value = pos.get("value", 0)
            plan.append(
                {
                    "action": "CLOSE",
                    "symbol": symbol,
                    "reason": f"Excess position (count violation). Value: ${value:.2f}",
                    "priority": "MEDIUM",
                }
            )

    return plan


def heal_positions(state_path: Path) -> dict:
    """
    Main self-healing function.

    Returns:
        dict with healing status and actions taken
    """
    logger.info("=" * 60)
    logger.info("POSITION COMPLIANCE SELF-HEALING")
    logger.info("=" * 60)

    state = load_system_state(state_path)
    if not state:
        return {"status": "ERROR", "message": "Cannot load system_state.json"}

    # Detect violations
    violations = detect_violations(state)

    if violations["total_violations"] == 0:
        logger.info("✅ No position violations detected")
        return {"status": "HEALTHY", "violations": 0}

    logger.info(f"\n🚨 DETECTED {violations['total_violations']} VIOLATION(S)")

    # Add remediation queue to system state
    if violations["remediation_queue"]:
        state["remediation_queue"] = {
            "created_at": datetime.now().isoformat(),
            "reason": "Position compliance self-healing",
            "actions": violations["remediation_queue"],
            "status": "PENDING",
        }

        if save_system_state(state_path, state):
            logger.info("\n✅ Remediation queue saved to system_state.json")
            logger.info("   Actions will execute on next market open")
        else:
            logger.error("❌ Failed to save remediation queue")
            return {"status": "ERROR", "message": "Failed to save queue"}

    # Print remediation plan
    logger.info("\n📋 REMEDIATION PLAN:")
    for i, action in enumerate(violations["remediation_queue"], 1):
        logger.info(
            f"   {i}. [{action['priority']}] {action['action']} {action['symbol']}"
        )
        logger.info(f"      Reason: {action['reason']}")

    return {
        "status": "QUEUED",
        "violations": violations["total_violations"],
        "actions_queued": len(violations["remediation_queue"]),
        "details": violations,
    }


def main() -> int:
    """Main entry point."""
    repo_root = Path(__file__).parent.parent
    state_path = repo_root / "data" / "system_state.json"

    result = heal_positions(state_path)

    if result["status"] == "ERROR":
        logger.error(f"❌ Self-healing failed: {result.get('message')}")
        return 1
    elif result["status"] == "QUEUED":
        logger.info(
            f"\n⚠️  {result['actions_queued']} remediation actions queued for market open"
        )
        return 0
    else:
        logger.info("✅ System healthy - no remediation needed")
        return 0


if __name__ == "__main__":
    exit(main())
