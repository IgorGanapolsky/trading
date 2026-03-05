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
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Maximum allowed staleness before blocking trading decisions
MAX_STALE_HOURS = 24

# Path to system state file
SYSTEM_STATE_PATH = Path(__file__).parent.parent.parent / "data" / "system_state.json"
RAG_QUERY_INDEX_PATH = Path(__file__).parent.parent.parent / "data" / "rag" / "lessons_query.json"
CONTEXT_INDEX_PATH = (
    Path(__file__).parent.parent.parent / "data" / "context_engine" / "context_index.json"
)


@dataclass
class StalenessResult:
    """Result of staleness check."""

    is_stale: bool
    hours_old: float
    last_updated: str | None
    reason: str
    blocking: bool  # True if this should block trading


@dataclass
class ContextFreshnessSource:
    """Freshness details for a single context source."""

    source: str
    path: str
    last_sync: str | None
    age_minutes: float
    max_age_minutes: float
    is_stale: bool
    reason: str


@dataclass
class ContextFreshnessResult:
    """Aggregated freshness status for RAG/context sources."""

    is_stale: bool
    blocking: bool
    checked_at: str
    stale_sources: list[str]
    sources: list[ContextFreshnessSource]
    reason: str


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
            updated_dt = _parse_iso_datetime(last_updated)
            if not updated_dt:
                return StalenessResult(
                    is_stale=True,
                    hours_old=float("inf"),
                    last_updated=last_updated,
                    reason=f"Invalid timestamp format: {last_updated}",
                    blocking=is_market_day,
                )
        else:
            updated_dt = datetime.strptime(last_updated, "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )

        # Calculate age
        age = _utc_now() - updated_dt
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


def _env_max_age_minutes(name: str, default_minutes: float) -> float:
    raw = os.getenv(name, str(default_minutes)).strip()
    try:
        value = float(raw)
        if value <= 0:
            raise ValueError("must be > 0")
        return value
    except ValueError:
        logger.warning("Invalid %s=%r, using default %.1f", name, raw, default_minutes)
        return default_minutes


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    candidate = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _extract_rag_query_index_last_sync(path: Path) -> str | None:
    try:
        lessons = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    timestamps: list[datetime] = []
    if isinstance(lessons, list):
        for entry in lessons:
            if not isinstance(entry, dict):
                continue
            for field in ("indexed_at_utc", "event_timestamp_utc", "source_mtime_utc"):
                parsed = _parse_iso_datetime(str(entry.get(field) or ""))
                if parsed:
                    timestamps.append(parsed)
                    break

    if not timestamps:
        return None
    latest = max(timestamps)
    return _to_utc_iso(latest)


def _extract_context_index_last_sync(path: Path) -> str | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    if not isinstance(payload, dict):
        return None
    built_at = payload.get("built_at")
    if not isinstance(built_at, str):
        return None
    parsed = _parse_iso_datetime(built_at)
    if not parsed:
        return None
    return _to_utc_iso(parsed)


def _build_context_source(
    *,
    source: str,
    path: Path,
    max_age_minutes: float,
    extractor: Callable[[Path], str | None] | None = None,
) -> ContextFreshnessSource:
    now = _utc_now()
    if not path.exists():
        return ContextFreshnessSource(
            source=source,
            path=str(path),
            last_sync=None,
            age_minutes=float("inf"),
            max_age_minutes=max_age_minutes,
            is_stale=True,
            reason=f"{source} index is missing",
        )

    last_sync = extractor(path) if extractor else None
    last_dt = _parse_iso_datetime(last_sync) if last_sync else None
    if not last_dt:
        file_dt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        last_sync = _to_utc_iso(file_dt)
        last_dt = file_dt

    age_minutes = (now - last_dt).total_seconds() / 60
    is_stale = age_minutes > max_age_minutes
    reason = (
        f"{source} stale ({age_minutes:.1f}m > max {max_age_minutes:.1f}m)"
        if is_stale
        else f"{source} fresh ({age_minutes:.1f}m <= max {max_age_minutes:.1f}m)"
    )
    return ContextFreshnessSource(
        source=source,
        path=str(path),
        last_sync=last_sync,
        age_minutes=age_minutes,
        max_age_minutes=max_age_minutes,
        is_stale=is_stale,
        reason=reason,
    )


def check_context_freshness(is_market_day: bool = True) -> ContextFreshnessResult:
    """
    Validate context indexes freshness using explicit SLO thresholds.

    SLOs can be overridden through:
    - RAG_QUERY_INDEX_MAX_AGE_MINUTES
    - CONTEXT_INDEX_MAX_AGE_MINUTES
    """
    rag_max = _env_max_age_minutes("RAG_QUERY_INDEX_MAX_AGE_MINUTES", 7 * 24 * 60)
    context_max = _env_max_age_minutes("CONTEXT_INDEX_MAX_AGE_MINUTES", 7 * 24 * 60)

    sources = [
        _build_context_source(
            source="rag_query_index",
            path=RAG_QUERY_INDEX_PATH,
            max_age_minutes=rag_max,
            extractor=_extract_rag_query_index_last_sync,
        ),
        _build_context_source(
            source="context_engine_index",
            path=CONTEXT_INDEX_PATH,
            max_age_minutes=context_max,
            extractor=_extract_context_index_last_sync,
        ),
    ]
    stale_sources = [src.source for src in sources if src.is_stale]
    is_stale = bool(stale_sources)
    blocking = bool(is_stale and is_market_day)
    reason = (
        "Context freshness check passed"
        if not is_stale
        else f"Stale context indexes detected: {', '.join(stale_sources)}"
    )

    return ContextFreshnessResult(
        is_stale=is_stale,
        blocking=blocking,
        checked_at=_to_utc_iso(_utc_now()),
        stale_sources=stale_sources,
        sources=sources,
        reason=reason,
    )


def require_fresh_context(is_market_day: bool = True) -> bool:
    """Raise when context freshness SLOs are violated on a market day."""
    result = check_context_freshness(is_market_day=is_market_day)
    if result.is_stale:
        if result.blocking:
            details = "; ".join(f"{source.source}: {source.reason}" for source in result.sources)
            raise RuntimeError(
                "Trading blocked due to stale context. "
                f"{details}. Refresh with "
                "'python scripts/build_rag_query_index.py' and "
                "'python scripts/build_context_engine_index.py'."
            )
        logger.warning("Context stale but non-blocking check: %s", result.reason)
    return True


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
        # Note: positions are under paper_account.positions, not top-level
        required_fields = ["portfolio", "paper_account"]
        for field in required_fields:
            if field not in state:
                errors.append(f"Missing required field: {field}")

        if errors:
            return DataIntegrityResult(is_valid=False, errors=errors, warnings=warnings)

        # Validate portfolio values (may be strings from Alpaca API)
        portfolio = state.get("portfolio", {})
        try:
            equity = float(portfolio.get("equity", 0))
        except (TypeError, ValueError):
            equity = 0
        try:
            cash = float(portfolio.get("cash", 0))
        except (TypeError, ValueError):
            cash = 0

        if equity <= 0:
            errors.append(f"Invalid equity: {equity} (must be > 0)")
        if cash < 0:
            errors.append(f"Invalid cash: {cash} (must be >= 0)")

        # Validate positions count consistency
        # Positions can be at top level OR under paper_account (check both for resilience)
        paper_account = state.get("paper_account", {})
        positions = state.get("positions", []) or paper_account.get("positions", [])
        positions_count = paper_account.get("positions_count", 0) or state.get("account", {}).get(
            "positions_count", 0
        )

        if positions_count != len(positions):
            warnings.append(
                f"Position count mismatch: positions_count={positions_count}, "
                f"actual positions={len(positions)}"
            )

        # Validate each position (prices may be strings from Alpaca API)
        for i, pos in enumerate(positions):
            if "symbol" not in pos:
                errors.append(f"Position {i}: missing symbol")
            try:
                price = float(pos.get("price", 0) or 0)
                if price < 0:
                    errors.append(f"Position {i} ({pos.get('symbol', '?')}): negative price")
            except (TypeError, ValueError):
                pass  # Skip price validation if not a valid number

        # Check for data drift (equity changed dramatically)
        # This would compare against previous sync, but we need history for that
        # Warn if equity is suspiciously different from initial $100,000 (PA3C5AG0CECQ)
        initial_equity = 100000.0
        drift_pct = abs(equity - initial_equity) / initial_equity * 100
        if drift_pct > 20:  # More than 20% change from initial
            warnings.append(f"Large equity drift: {drift_pct:.1f}% from initial ${initial_equity}")

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
