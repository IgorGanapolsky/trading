"""
Staleness Guard - Prevents trading decisions on stale data.

Created: Dec 28, 2025
Purpose: Prevent the "Dec 23 lying incident" where system claimed no trades
         while stale local data hid 9 actual live orders.

This guard BLOCKS trading if:
- system_state.json is more than 24 hours old on a market day
- system_state.json doesn't exist or can't be read
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Maximum allowed staleness before blocking trading decisions
MAX_STALE_HOURS = 24

# Path to system state file
SYSTEM_STATE_PATH = Path(__file__).parent.parent.parent / "data" / "system_state.json"


@dataclass
class StalenessResult:
    """Result of staleness check."""

    is_stale: bool
    hours_old: float
    last_updated: str | None
    reason: str
    blocking: bool  # True if this should block trading


def check_data_staleness(
    state_path: Path = SYSTEM_STATE_PATH,
    max_stale_hours: float = MAX_STALE_HOURS,
    is_market_day: bool = True,
) -> StalenessResult:
    """
    Check if trading data is too stale to use.

    Args:
        state_path: Path to system_state.json
        max_stale_hours: Maximum allowed hours before data is stale
        is_market_day: Whether today is a trading day

    Returns:
        StalenessResult with is_stale flag and details
    """
    try:
        if not state_path.exists():
            return StalenessResult(
                is_stale=True,
                hours_old=float("inf"),
                last_updated=None,
                reason="system_state.json does not exist",
                blocking=is_market_day,  # Only block on market days
            )

        with open(state_path) as f:
            state = json.load(f)

        # Check both meta.last_updated (preferred) and top-level last_updated (fallback)
        # Fix for Jan 15 crisis: top-level timestamp was being ignored
        last_updated = state.get("meta", {}).get("last_updated") or state.get("last_updated")

        if not last_updated:
            return StalenessResult(
                is_stale=True,
                hours_old=float("inf"),
                last_updated=None,
                reason="system_state.json has no last_updated timestamp",
                blocking=is_market_day,
            )

        # Parse timestamp
        if "T" in last_updated:
            updated_dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
            # Remove timezone for comparison
            updated_dt = updated_dt.replace(tzinfo=None)
        else:
            updated_dt = datetime.strptime(last_updated, "%Y-%m-%d %H:%M:%S")

        # Calculate age
        age = datetime.now() - updated_dt
        hours_old = age.total_seconds() / 3600

        if hours_old > max_stale_hours:
            return StalenessResult(
                is_stale=True,
                hours_old=hours_old,
                last_updated=last_updated,
                reason=f"Data is {hours_old:.1f} hours old (max allowed: {max_stale_hours}h)",
                blocking=is_market_day,
            )

        return StalenessResult(
            is_stale=False,
            hours_old=hours_old,
            last_updated=last_updated,
            reason=f"Data is fresh ({hours_old:.1f} hours old)",
            blocking=False,
        )

    except json.JSONDecodeError as e:
        return StalenessResult(
            is_stale=True,
            hours_old=float("inf"),
            last_updated=None,
            reason=f"system_state.json is invalid JSON: {e}",
            blocking=is_market_day,
        )
    except Exception as e:
        return StalenessResult(
            is_stale=True,
            hours_old=float("inf"),
            last_updated=None,
            reason=f"Failed to check staleness: {e}",
            blocking=is_market_day,
        )


def require_fresh_data(is_market_day: bool = True) -> bool:
    """
    Check staleness and raise if data is too stale to trade.

    This is a simple function to call at the start of trading logic.

    Returns:
        True if data is fresh enough to proceed

    Raises:
        RuntimeError if data is stale and would block trading
    """
    result = check_data_staleness(is_market_day=is_market_day)

    if result.is_stale:
        msg = f"⛔ STALE DATA GUARD: {result.reason}"
        logger.warning(msg)

        if result.blocking:
            error_msg = (
                f"Trading blocked due to stale data: {result.reason}. "
                f"Last update: {result.last_updated or 'unknown'}. "
                f"Run 'python scripts/sync_alpaca_state.py' to refresh."
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)

    else:
        logger.info(f"✅ Data freshness check passed: {result.reason}")

    return True


def get_staleness_warning() -> str | None:
    """
    Get a warning message if data is stale, or None if fresh.

    Use this for non-blocking warnings (e.g., in status displays).
    """
    result = check_data_staleness(is_market_day=False)  # Non-blocking check

    if result.is_stale:
        return f"⚠️ DATA STALE: {result.reason}"

    return None


@dataclass
class DataIntegrityResult:
    """Result of data integrity validation."""

    is_valid: bool
    errors: list[str]
    warnings: list[str]


def validate_system_state(state_path: Path = SYSTEM_STATE_PATH) -> DataIntegrityResult:
    """
    Validate system_state.json data integrity.

    Checks:
    - Required fields exist
    - Equity and cash are positive
    - Positions count matches positions array
    - No impossible values (negative prices, etc.)

    Returns:
        DataIntegrityResult with validation status
    """
    errors = []
    warnings = []

    try:
        if not state_path.exists():
            return DataIntegrityResult(
                is_valid=False,
                errors=["system_state.json does not exist"],
                warnings=[],
            )

        with open(state_path) as f:
            state = json.load(f)

        # Check required top-level fields
        required_fields = ["portfolio", "paper_account", "positions"]
        for field in required_fields:
            if field not in state:
                errors.append(f"Missing required field: {field}")

        if errors:
            return DataIntegrityResult(is_valid=False, errors=errors, warnings=warnings)

        # Validate portfolio values
        portfolio = state.get("portfolio", {})
        equity = portfolio.get("equity", 0)
        cash = portfolio.get("cash", 0)

        if equity <= 0:
            errors.append(f"Invalid equity: {equity} (must be > 0)")
        if cash < 0:
            errors.append(f"Invalid cash: {cash} (must be >= 0)")

        # Validate positions count consistency
        paper_account = state.get("paper_account", {})
        positions = state.get("positions", [])
        positions_count = paper_account.get("positions_count", 0)

        if positions_count != len(positions):
            warnings.append(
                f"Position count mismatch: positions_count={positions_count}, "
                f"actual positions={len(positions)}"
            )

        # Validate each position
        for i, pos in enumerate(positions):
            if "symbol" not in pos:
                errors.append(f"Position {i}: missing symbol")
            if pos.get("price", 0) < 0:
                errors.append(f"Position {i} ({pos.get('symbol', '?')}): negative price")

        # Check for data drift (equity changed dramatically)
        # This would compare against previous sync, but we need history for that
        # For now, just warn if equity is suspiciously different from initial $5000
        initial_equity = 5000.0
        drift_pct = abs(equity - initial_equity) / initial_equity * 100
        if drift_pct > 20:  # More than 20% change from initial
            warnings.append(
                f"Large equity drift: {drift_pct:.1f}% from initial ${initial_equity}"
            )

        return DataIntegrityResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    except json.JSONDecodeError as e:
        return DataIntegrityResult(
            is_valid=False,
            errors=[f"Invalid JSON: {e}"],
            warnings=[],
        )
    except Exception as e:
        return DataIntegrityResult(
            is_valid=False,
            errors=[f"Validation failed: {e}"],
            warnings=[],
        )


def check_data_integrity() -> bool:
    """
    Run data integrity check and log results.

    Returns:
        True if data is valid, False otherwise
    """
    result = validate_system_state()

    if result.errors:
        for error in result.errors:
            logger.error(f"❌ Data integrity error: {error}")

    if result.warnings:
        for warning in result.warnings:
            logger.warning(f"⚠️ Data integrity warning: {warning}")

    if result.is_valid:
        logger.info("✅ Data integrity check passed")

    return result.is_valid
