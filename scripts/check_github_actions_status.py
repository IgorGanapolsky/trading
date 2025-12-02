#!/usr/bin/env python3
"""
Check if GitHub Actions workflow already ran today.
Used by launchd daemons to avoid duplicate execution.
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Cache file to avoid too many API calls
CACHE_FILE = Path("data/github_actions_cache.json")
CACHE_TTL_SECONDS = 300  # 5 minutes cache


def check_github_cli_available() -> bool:
    """Check if GitHub CLI (gh) is available."""
    try:
        result = subprocess.run(["gh", "--version"], capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_workflow_runs(workflow_name: str, limit: int = 5) -> Optional[list]:
    """
    Get recent workflow runs using GitHub CLI.

    Args:
        workflow_name: Name of the workflow file (e.g., "daily-trading.yml")
        limit: Maximum number of runs to fetch

    Returns:
        List of workflow runs or None if error
    """
    if not check_github_cli_available():
        print("⚠️  GitHub CLI (gh) not available - cannot check GitHub Actions status")
        return None

    try:
        # Get workflow runs
        result = subprocess.run(
            [
                "gh",
                "run",
                "list",
                "--workflow",
                workflow_name,
                "--limit",
                str(limit),
                "--json",
                "conclusion,createdAt,displayTitle,status",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=Path(__file__).parent.parent,
        )

        if result.returncode != 0:
            print(f"⚠️  Failed to query GitHub Actions: {result.stderr}")
            return None

        runs = json.loads(result.stdout)
        return runs

    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        print(f"⚠️  Error checking GitHub Actions: {e}")
        return None


def check_if_ran_today(
    workflow_name: str, check_success_only: bool = True
) -> tuple[bool, Optional[str]]:
    """
    Check if workflow ran successfully today.

    Args:
        workflow_name: Name of the workflow file
        check_success_only: Only consider successful runs

    Returns:
        Tuple of (ran_today: bool, reason: str)
    """
    # Check cache first
    if CACHE_FILE.exists():
        try:
            cache_data = json.loads(CACHE_FILE.read_text())
            cache_time = datetime.fromisoformat(cache_data.get("timestamp", ""))
            now = datetime.now(timezone.utc)

            if (now - cache_time).total_seconds() < CACHE_TTL_SECONDS:
                cached_result = cache_data.get(workflow_name)
                if cached_result is not None:
                    return cached_result["ran_today"], cached_result.get("reason", "")
        except Exception:
            pass  # Cache invalid, continue to API check

    runs = get_workflow_runs(workflow_name)
    if runs is None:
        # If we can't check, assume it didn't run (safer to run backup)
        return False, "Cannot verify GitHub Actions status - will run as backup"

    if not runs:
        return False, "No recent workflow runs found"

    # Get today's date in UTC
    today = datetime.now(timezone.utc).date()

    # Check most recent run
    for run in runs:
        try:
            run_time = datetime.fromisoformat(run["createdAt"].replace("Z", "+00:00"))
            run_date = run_time.date()

            # Check if run was today
            if run_date == today:
                status = run.get("status", "").lower()
                conclusion = run.get("conclusion", "").lower()

                if check_success_only:
                    if conclusion == "success":
                        reason = (
                            f"Workflow ran successfully today at {run_time.strftime('%H:%M UTC')}"
                        )
                        # Update cache
                        _update_cache(workflow_name, True, reason)
                        return True, reason
                    elif conclusion == "failure":
                        reason = f"Workflow failed today at {run_time.strftime('%H:%M UTC')} - backup should run"
                        _update_cache(workflow_name, False, reason)
                        return False, reason
                    elif status == "in_progress":
                        reason = "Workflow currently running - backup should wait"
                        _update_cache(workflow_name, True, reason)
                        return True, reason
                else:
                    # Any run today counts
                    reason = f"Workflow ran today at {run_time.strftime('%H:%M UTC')} (status: {conclusion})"
                    _update_cache(workflow_name, True, reason)
                    return True, reason

            # If we've gone past today, no run today
            elif run_date < today:
                reason = f"Last run was on {run_date} - no run today"
                _update_cache(workflow_name, False, reason)
                return False, reason

        except (KeyError, ValueError):
            continue  # Skip malformed entries

    reason = "No workflow runs found for today"
    _update_cache(workflow_name, False, reason)
    return False, reason


def _update_cache(workflow_name: str, ran_today: bool, reason: str):
    """Update cache file."""
    try:
        cache_data = {}
        if CACHE_FILE.exists():
            cache_data = json.loads(CACHE_FILE.read_text())

        cache_data[workflow_name] = {
            "ran_today": ran_today,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        cache_data["timestamp"] = datetime.now(timezone.utc).isoformat()

        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(cache_data, indent=2))
    except Exception:
        pass  # Cache update is best-effort


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: check_github_actions_status.py <workflow-name> [--allow-failure]")
        sys.exit(1)

    workflow_name = sys.argv[1]
    check_success_only = "--allow-failure" not in sys.argv

    ran_today, reason = check_if_ran_today(workflow_name, check_success_only)

    print(f"Workflow: {workflow_name}")
    print(f"Ran today: {ran_today}")
    print(f"Reason: {reason}")

    # Exit code: 0 = ran today (skip), 1 = didn't run (should execute)
    sys.exit(0 if ran_today else 1)


if __name__ == "__main__":
    main()
