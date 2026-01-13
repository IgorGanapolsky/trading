"""
Workflow Heartbeat Monitoring - Detects when trading stops.

Created: Dec 28, 2025
Purpose: Prevent the "Dec 11-12 incident" where trading was dead for 2 days
         and nobody noticed until the CEO called it out.

This module provides:
1. Heartbeat recording - call record_heartbeat() in your workflows
2. Heartbeat checking - call check_heartbeat() to verify system is alive
3. Clear alerting when heartbeat is missed

Usage:
    # In your trading workflow:
    from src.utils.heartbeat import record_heartbeat
    record_heartbeat("trading_session")

    # In monitoring/health check:
    from src.utils.heartbeat import check_heartbeat, is_system_alive
    if not is_system_alive():
        alert("Trading system appears dead!")
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Heartbeat file location
HEARTBEAT_FILE = Path(__file__).parent.parent.parent / "data" / "heartbeat.json"

# Maximum time without heartbeat before considered dead
# Reduced from 25h to 18h (Jan 13, 2026) - ensures same-day detection of failures
MAX_HEARTBEAT_AGE_HOURS = 18  # Alert within same trading day if system goes silent


@dataclass
class HeartbeatStatus:
    """Status of the system heartbeat."""

    is_alive: bool
    last_heartbeat: str | None
    hours_since_heartbeat: float
    last_workflow: str | None
    message: str


def record_heartbeat(
    workflow_name: str,
    status: str = "success",
    details: dict | None = None,
) -> None:
    """
    Record a heartbeat for a workflow.

    Call this at the end of successful workflow runs to indicate the system is alive.

    Args:
        workflow_name: Name of the workflow (e.g., "trading_session", "market_analysis")
        status: Status of the workflow ("success", "partial", "error")
        details: Optional details about the workflow run
    """
    HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Load existing heartbeats
    try:
        if HEARTBEAT_FILE.exists():
            data = json.loads(HEARTBEAT_FILE.read_text())
        else:
            data = {"heartbeats": [], "workflows": {}}
    except (json.JSONDecodeError, Exception):
        data = {"heartbeats": [], "workflows": {}}

    now = datetime.now()
    timestamp = now.isoformat()

    # Record this heartbeat
    heartbeat = {
        "timestamp": timestamp,
        "workflow": workflow_name,
        "status": status,
        "details": details or {},
    }

    # Keep last 100 heartbeats
    data["heartbeats"] = [heartbeat] + data.get("heartbeats", [])[:99]

    # Update per-workflow last heartbeat
    data["workflows"][workflow_name] = {
        "last_heartbeat": timestamp,
        "last_status": status,
        "total_runs": data.get("workflows", {}).get(workflow_name, {}).get("total_runs", 0) + 1,
    }

    # Write atomically
    HEARTBEAT_FILE.write_text(json.dumps(data, indent=2))
    logger.info(f"💓 Heartbeat recorded: {workflow_name} ({status})")


def check_heartbeat(
    max_age_hours: float = MAX_HEARTBEAT_AGE_HOURS,
) -> HeartbeatStatus:
    """
    Check if the system has a recent heartbeat.

    Args:
        max_age_hours: Maximum allowed hours since last heartbeat

    Returns:
        HeartbeatStatus with is_alive flag and details
    """
    if not HEARTBEAT_FILE.exists():
        return HeartbeatStatus(
            is_alive=False,
            last_heartbeat=None,
            hours_since_heartbeat=float("inf"),
            last_workflow=None,
            message="⛔ NO HEARTBEAT FILE - System may never have run or file was deleted",
        )

    try:
        data = json.loads(HEARTBEAT_FILE.read_text())
    except (json.JSONDecodeError, Exception) as e:
        return HeartbeatStatus(
            is_alive=False,
            last_heartbeat=None,
            hours_since_heartbeat=float("inf"),
            last_workflow=None,
            message=f"⛔ HEARTBEAT FILE CORRUPTED: {e}",
        )

    heartbeats = data.get("heartbeats", [])
    if not heartbeats:
        return HeartbeatStatus(
            is_alive=False,
            last_heartbeat=None,
            hours_since_heartbeat=float("inf"),
            last_workflow=None,
            message="⛔ NO HEARTBEATS RECORDED - System appears dead",
        )

    # Get most recent heartbeat
    latest = heartbeats[0]
    last_heartbeat = latest.get("timestamp")
    last_workflow = latest.get("workflow")

    if not last_heartbeat:
        return HeartbeatStatus(
            is_alive=False,
            last_heartbeat=None,
            hours_since_heartbeat=float("inf"),
            last_workflow=last_workflow,
            message="⛔ INVALID HEARTBEAT - No timestamp",
        )

    # Parse and calculate age
    try:
        heartbeat_dt = datetime.fromisoformat(last_heartbeat.replace("Z", "+00:00"))
        heartbeat_dt = heartbeat_dt.replace(tzinfo=None)  # Remove tz for comparison
    except ValueError:
        return HeartbeatStatus(
            is_alive=False,
            last_heartbeat=last_heartbeat,
            hours_since_heartbeat=float("inf"),
            last_workflow=last_workflow,
            message=f"⛔ INVALID TIMESTAMP: {last_heartbeat}",
        )

    age = datetime.now() - heartbeat_dt
    hours_since = age.total_seconds() / 3600

    if hours_since > max_age_hours:
        return HeartbeatStatus(
            is_alive=False,
            last_heartbeat=last_heartbeat,
            hours_since_heartbeat=hours_since,
            last_workflow=last_workflow,
            message=f"⛔ SYSTEM APPEARS DEAD - Last heartbeat {hours_since:.1f}h ago from {last_workflow}",
        )

    return HeartbeatStatus(
        is_alive=True,
        last_heartbeat=last_heartbeat,
        hours_since_heartbeat=hours_since,
        last_workflow=last_workflow,
        message=f"💓 System alive - Last heartbeat {hours_since:.1f}h ago from {last_workflow}",
    )


def is_system_alive(max_age_hours: float = MAX_HEARTBEAT_AGE_HOURS) -> bool:
    """
    Simple check if the system is alive.

    Returns:
        True if system has heartbeat within max_age_hours
    """
    return check_heartbeat(max_age_hours).is_alive


def get_workflow_health() -> dict[str, dict]:
    """
    Get health status of all tracked workflows.

    Returns:
        Dict mapping workflow names to their last status
    """
    if not HEARTBEAT_FILE.exists():
        return {}

    try:
        data = json.loads(HEARTBEAT_FILE.read_text())
        return data.get("workflows", {})
    except (json.JSONDecodeError, Exception):
        return {}
