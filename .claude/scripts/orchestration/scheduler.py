#!/usr/bin/env python3
"""
Cron-style Scheduler for Trading System Automation.

Schedules and triggers swarm operations based on time:
- 9:25 AM ET: Pre-market analysis swarm (5 agents)
- 9:35 AM ET: Trading execution (if signals align)
- 3:45 PM ET: EOD position review
- 8:00 PM ET: Daily cleanup
- Weekends: Research swarm (Sunday 8 AM)

Usage:
    # Run scheduler daemon
    python scheduler.py --daemon

    # Check next scheduled task
    python scheduler.py --next

    # Manually trigger a task
    python scheduler.py --trigger analysis
"""

import argparse
import asyncio
import json
import os
import signal
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

# Project paths
PROJECT_DIR = Path(__file__).parent.parent.parent.parent
SCRIPT_DIR = Path(__file__).parent
STATE_FILE = PROJECT_DIR / ".claude" / "scheduler_state.json"

# Eastern Time
ET = ZoneInfo("America/New_York")


class ScheduledTask:
    """Represents a scheduled task."""

    def __init__(
        self,
        name: str,
        mode: str,
        hour: int,
        minute: int,
        days: list[int] | None = None,  # None = weekdays, [6,7] = weekends
        enabled: bool = True,
    ):
        self.name = name
        self.mode = mode
        self.hour = hour
        self.minute = minute
        self.days = days  # 1=Mon, 7=Sun; None means Mon-Fri
        self.enabled = enabled
        self.last_run: datetime | None = None

    def should_run(self, now: datetime) -> bool:
        """Check if this task should run now."""
        if not self.enabled:
            return False

        # Check day of week
        dow = now.isoweekday()  # 1=Mon, 7=Sun
        if self.days is None:
            # Weekdays only
            if dow > 5:
                return False
        else:
            if dow not in self.days:
                return False

        # Check time (within 1-minute window)
        if now.hour != self.hour or now.minute != self.minute:
            return False

        # Don't run twice in same minute
        if self.last_run:
            if (now - self.last_run).total_seconds() < 60:
                return False

        return True

    def next_run(self, now: datetime) -> datetime:
        """Calculate next run time."""
        target = now.replace(hour=self.hour, minute=self.minute, second=0, microsecond=0)

        # If past today's target, start from tomorrow
        if now >= target:
            target += timedelta(days=1)

        # Find next valid day
        while True:
            dow = target.isoweekday()
            if self.days is None:
                if dow <= 5:
                    break
            else:
                if dow in self.days:
                    break
            target += timedelta(days=1)

        return target

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "mode": self.mode,
            "schedule": f"{self.hour:02d}:{self.minute:02d}",
            "days": "weekdays" if self.days is None else self.days,
            "enabled": self.enabled,
            "last_run": self.last_run.isoformat() if self.last_run else None,
        }


class Scheduler:
    """Cron-style scheduler for trading operations."""

    # Default schedule
    TASKS = [
        ScheduledTask("Pre-market Analysis", "analysis", 9, 25),
        ScheduledTask("Trading Execution", "trade", 9, 35),
        ScheduledTask("EOD Review", "eod_review", 15, 45),
        ScheduledTask("Daily Cleanup", "cleanup", 20, 0),
        ScheduledTask("Weekend Research", "research", 8, 0, days=[7]),  # Sunday
    ]

    def __init__(self):
        self.running = False
        self.tasks = self.TASKS.copy()
        self._load_state()

    def _load_state(self):
        """Load scheduler state from file."""
        if STATE_FILE.exists():
            try:
                state = json.loads(STATE_FILE.read_text())
                for task in self.tasks:
                    if task.name in state.get("last_runs", {}):
                        task.last_run = datetime.fromisoformat(
                            state["last_runs"][task.name]
                        )
            except (json.JSONDecodeError, KeyError):
                pass

    def _save_state(self):
        """Save scheduler state to file."""
        state = {
            "last_runs": {
                task.name: task.last_run.isoformat()
                for task in self.tasks
                if task.last_run
            },
            "updated": datetime.now(ET).isoformat(),
        }
        STATE_FILE.write_text(json.dumps(state, indent=2))

    async def run_task(self, task: ScheduledTask) -> dict[str, Any]:
        """Execute a scheduled task."""
        print(f"[Scheduler] Running task: {task.name} (mode: {task.mode})")

        task.last_run = datetime.now(ET)
        self._save_state()

        # Import and run swarm
        try:
            # Run swarm_runner.py
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                str(SCRIPT_DIR / "swarm_runner.py"),
                "--mode",
                task.mode,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await proc.communicate()

            result = {
                "task": task.name,
                "mode": task.mode,
                "status": "completed" if proc.returncode == 0 else "failed",
                "returncode": proc.returncode,
                "output": stdout.decode()[:1000] if stdout else "",
                "errors": stderr.decode()[:500] if stderr else "",
                "timestamp": datetime.now(ET).isoformat(),
            }

            print(f"[Scheduler] Task {task.name} completed with status: {result['status']}")
            return result

        except Exception as e:
            print(f"[Scheduler] Task {task.name} failed: {e}")
            return {
                "task": task.name,
                "mode": task.mode,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(ET).isoformat(),
            }

    def get_next_task(self) -> tuple[ScheduledTask | None, datetime | None]:
        """Get the next scheduled task and its run time."""
        now = datetime.now(ET)
        next_task = None
        next_time = None

        for task in self.tasks:
            if not task.enabled:
                continue
            task_next = task.next_run(now)
            if next_time is None or task_next < next_time:
                next_time = task_next
                next_task = task

        return next_task, next_time

    async def check_and_run(self) -> list[dict[str, Any]]:
        """Check for tasks to run and execute them."""
        now = datetime.now(ET)
        results = []

        for task in self.tasks:
            if task.should_run(now):
                result = await self.run_task(task)
                results.append(result)

        return results

    async def run_daemon(self, check_interval: int = 30):
        """Run scheduler as a daemon process."""
        self.running = True
        print(f"[Scheduler] Starting daemon (check every {check_interval}s)")
        print(f"[Scheduler] Timezone: America/New_York")
        print(f"[Scheduler] Tasks: {len(self.tasks)}")

        # Print schedule
        for task in self.tasks:
            print(f"  - {task.name}: {task.hour:02d}:{task.minute:02d} ({task.mode})")

        while self.running:
            try:
                results = await self.check_and_run()

                if results:
                    for r in results:
                        print(f"[Scheduler] Result: {r['task']} -> {r['status']}")

                await asyncio.sleep(check_interval)

            except asyncio.CancelledError:
                print("[Scheduler] Daemon cancelled")
                break
            except Exception as e:
                print(f"[Scheduler] Error in daemon loop: {e}")
                await asyncio.sleep(check_interval)

        print("[Scheduler] Daemon stopped")

    def stop(self):
        """Stop the scheduler daemon."""
        self.running = False

    def get_status(self) -> dict[str, Any]:
        """Get scheduler status."""
        now = datetime.now(ET)
        next_task, next_time = self.get_next_task()

        return {
            "current_time": now.isoformat(),
            "timezone": "America/New_York",
            "tasks": [task.to_dict() for task in self.tasks],
            "next_task": next_task.to_dict() if next_task else None,
            "next_run": next_time.isoformat() if next_time else None,
            "time_until_next": str(next_time - now) if next_time else None,
        }


def handle_signal(signum, frame):
    """Handle shutdown signals."""
    print(f"\n[Scheduler] Received signal {signum}, shutting down...")
    sys.exit(0)


async def main():
    parser = argparse.ArgumentParser(description="Trading System Scheduler")
    parser.add_argument(
        "--daemon", action="store_true", help="Run as daemon"
    )
    parser.add_argument(
        "--next", action="store_true", help="Show next scheduled task"
    )
    parser.add_argument(
        "--status", action="store_true", help="Show scheduler status"
    )
    parser.add_argument(
        "--trigger", type=str, help="Manually trigger a mode"
    )
    parser.add_argument(
        "--interval", type=int, default=30, help="Check interval in seconds"
    )

    args = parser.parse_args()

    scheduler = Scheduler()

    if args.daemon:
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
        await scheduler.run_daemon(args.interval)

    elif args.next:
        next_task, next_time = scheduler.get_next_task()
        if next_task:
            print(f"Next task: {next_task.name}")
            print(f"Mode: {next_task.mode}")
            print(f"Scheduled: {next_time}")
            print(f"Time until: {next_time - datetime.now(ET)}")
        else:
            print("No tasks scheduled")

    elif args.status:
        status = scheduler.get_status()
        print(json.dumps(status, indent=2))

    elif args.trigger:
        # Find matching task or create ad-hoc
        mode = args.trigger
        task = next((t for t in scheduler.tasks if t.mode == mode), None)

        if not task:
            task = ScheduledTask(f"Manual: {mode}", mode, 0, 0)

        result = await scheduler.run_task(task)
        print(json.dumps(result, indent=2))

    else:
        # Default: show status
        status = scheduler.get_status()
        print(json.dumps(status, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
