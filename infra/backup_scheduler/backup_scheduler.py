#!/usr/bin/env python3
"""
Backup Scheduler - Fallback when GitHub Actions is unavailable.

This script provides scheduler redundancy by:
1. Checking if GitHub Actions ran recently
2. Running trading if GitHub Actions missed the schedule
3. Supporting local cron, systemd timer, or Cloud Run

Usage:
    # Local cron (every 30 mins during market hours)
    */30 9-16 * * 1-5 /path/to/venv/bin/python backup_scheduler.py

    # Manual run
    python backup_scheduler.py --force

    # Cloud Run / Cloud Scheduler (set via GCP console or Terraform)
    # Endpoint: POST /run

Author: Trading System
Created: December 2025
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configuration
BASE_DIR = Path(__file__).resolve().parent.parent.parent
HEARTBEAT_FILE = BASE_DIR / "data" / "scheduler_heartbeat.json"
TRADING_SCRIPT = BASE_DIR / "scripts" / "daily_trading.py"
STALE_THRESHOLD_MINUTES = 45  # Consider GitHub Actions stale after 45 mins


def load_heartbeat() -> dict:
    """Load the last heartbeat from GitHub Actions."""
    if not HEARTBEAT_FILE.exists():
        return {"last_run": None, "source": None}
    try:
        with open(HEARTBEAT_FILE) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load heartbeat: {e}")
        return {"last_run": None, "source": None}


def save_heartbeat(source: str) -> None:
    """Save heartbeat after running."""
    HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "last_run": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "hostname": os.uname().nodename,
    }
    with open(HEARTBEAT_FILE, "w") as f:
        json.dump(data, f, indent=2)


def is_github_actions_stale() -> bool:
    """Check if GitHub Actions hasn't run recently."""
    heartbeat = load_heartbeat()
    last_run_str = heartbeat.get("last_run")

    if not last_run_str:
        logger.info("No heartbeat found - GitHub Actions never ran")
        return True

    try:
        last_run = datetime.fromisoformat(last_run_str.replace("Z", "+00:00"))
        age = datetime.now(timezone.utc) - last_run
        age_minutes = age.total_seconds() / 60

        if age_minutes > STALE_THRESHOLD_MINUTES:
            logger.warning(
                f"GitHub Actions stale: last run {age_minutes:.1f} mins ago "
                f"(threshold: {STALE_THRESHOLD_MINUTES} mins)"
            )
            return True

        logger.info(f"GitHub Actions healthy: last run {age_minutes:.1f} mins ago")
        return False

    except Exception as e:
        logger.warning(f"Failed to parse heartbeat timestamp: {e}")
        return True


def is_trading_hours() -> bool:
    """Check if we're in trading hours (9:30 AM - 4:00 PM ET, Mon-Fri)."""

    now_utc = datetime.now(timezone.utc)
    # Convert to ET (UTC-5 or UTC-4 depending on DST)
    et_offset = timedelta(hours=-5)  # Simplified - use pytz for production
    now_et = now_utc + et_offset

    # Check weekend
    if now_et.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False  # No trading on weekends

    # Check market hours (9:30 AM - 4:00 PM ET)
    market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)

    return market_open <= now_et <= market_close


def run_trading(dry_run: bool = False) -> bool:
    """Execute the trading script."""
    if not TRADING_SCRIPT.exists():
        logger.error(f"Trading script not found: {TRADING_SCRIPT}")
        return False

    cmd = [sys.executable, str(TRADING_SCRIPT)]
    if dry_run:
        cmd.append("--dry-run")

    logger.info(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            cwd=str(BASE_DIR),
        )

        if result.returncode == 0:
            logger.info("Trading completed successfully")
            save_heartbeat(source="backup_scheduler")
            return True
        else:
            logger.error(f"Trading failed: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("Trading script timed out")
        return False
    except Exception as e:
        logger.error(f"Failed to run trading: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Backup scheduler for trading system")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force run even if GitHub Actions is healthy",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode (no actual trades)",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check GitHub Actions status, don't run",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("BACKUP SCHEDULER CHECK")
    logger.info("=" * 60)

    # Check GitHub Actions status
    stale = is_github_actions_stale()

    if args.check_only:
        status = "STALE" if stale else "HEALTHY"
        logger.info(f"GitHub Actions status: {status}")
        sys.exit(0 if not stale else 1)

    # Decide whether to run
    should_run = args.force or stale

    if not should_run:
        logger.info("GitHub Actions is healthy - no backup run needed")
        sys.exit(0)

    if not is_trading_hours() and not args.force:
        logger.info("Outside trading hours - skipping")
        sys.exit(0)

    # Run trading
    logger.info("Running backup trading session...")
    success = run_trading(dry_run=args.dry_run)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
