#!/usr/bin/env python3
"""
LangSmith Monitor Skill - Continuous monitoring of LangSmith traces and runs
Provides insights into LLM usage, RL training performance, and system health.
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Any

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def error_response(error_msg: str, error_code: str = "ERROR") -> dict[str, Any]:
    """Standard error response format"""
    return {"success": False, "error": error_msg, "error_code": error_code}


def success_response(data: Any) -> dict[str, Any]:
    """Standard success response format"""
    return {"success": True, **data}


class LangSmithMonitor:
    """Monitor LangSmith traces, runs, and performance metrics."""

    def __init__(self):
        """Initialize LangSmith monitor."""
        self.api_key = os.getenv("LANGCHAIN_API_KEY")
        self.client = None

        if self.api_key:
            try:
                from langsmith import Client

                self.client = Client(api_key=self.api_key)
                logger.info("✅ LangSmith client initialized")
            except ImportError:
                logger.warning("⚠️  langsmith package not installed")
            except Exception as e:
                logger.warning(f"⚠️  Failed to initialize LangSmith client: {e}")
        else:
            logger.warning("⚠️  LANGCHAIN_API_KEY not configured")

    def get_recent_runs(
        self,
        project_name: str = "trading-rl-training",
        limit: int = 50,
        hours: int = 24,
    ) -> dict[str, Any]:
        """
        Get recent LangSmith runs.

        Args:
            project_name: Project name to query
            limit: Maximum number of runs to return
            hours: Hours of history to query

        Returns:
            Dict with recent runs and statistics
        """
        if not self.client:
            return error_response("LangSmith client not initialized")

        try:
            # Calculate start time
            start_time = datetime.now() - timedelta(hours=hours)

            # Query runs
            runs = list(
                self.client.list_runs(project_name=project_name, start_time=start_time, limit=limit)
            )

            # Analyze runs
            total_runs = len(runs)
            successful_runs = sum(1 for r in runs if r.status == "success")
            failed_runs = sum(1 for r in runs if r.status == "error")
            total_tokens = sum(
                getattr(r, "total_tokens", 0) or 0 for r in runs if hasattr(r, "total_tokens")
            )

            # Group by run type
            run_types = {}
            for run in runs:
                run_type = getattr(run, "run_type", "unknown")
                if run_type not in run_types:
                    run_types[run_type] = 0
                run_types[run_type] += 1

            return success_response(
                {
                    "project": project_name,
                    "period_hours": hours,
                    "total_runs": total_runs,
                    "successful_runs": successful_runs,
                    "failed_runs": failed_runs,
                    "success_rate": ((successful_runs / total_runs * 100) if total_runs > 0 else 0),
                    "total_tokens": total_tokens,
                    "run_types": run_types,
                    "recent_runs": [
                        {
                            "id": str(run.id),
                            "name": run.name,
                            "status": run.status,
                            "run_type": getattr(run, "run_type", "unknown"),
                            "start_time": (run.start_time.isoformat() if run.start_time else None),
                            "end_time": (run.end_time.isoformat() if run.end_time else None),
                            "error": run.error if hasattr(run, "error") else None,
                        }
                        for run in runs[:20]  # Return top 20
                    ],
                }
            )

        except Exception as e:
            logger.error(f"Failed to get recent runs: {e}")
            return error_response(str(e))

    def get_project_stats(
        self, project_name: str = "trading-rl-training", days: int = 7
    ) -> dict[str, Any]:
        """
        Get project statistics.

        Args:
            project_name: Project name
            days: Days of history

        Returns:
            Project statistics
        """
        if not self.client:
            return error_response("LangSmith client not initialized")

        try:
            start_time = datetime.now() - timedelta(days=days)

            runs = list(
                self.client.list_runs(project_name=project_name, start_time=start_time, limit=1000)
            )

            if not runs:
                return success_response(
                    {
                        "project": project_name,
                        "period_days": days,
                        "total_runs": 0,
                        "message": "No runs found in this period",
                    }
                )

            # Calculate statistics
            total_runs = len(runs)
            successful = sum(1 for r in runs if r.status == "success")
            failed = sum(1 for r in runs if r.status == "error")

            # Calculate average duration
            durations = []
            for run in runs:
                if run.start_time and run.end_time:
                    duration = (run.end_time - run.start_time).total_seconds()
                    durations.append(duration)

            avg_duration = sum(durations) / len(durations) if durations else 0

            # Group by day
            daily_stats = {}
            for run in runs:
                if run.start_time:
                    day = run.start_time.date().isoformat()
                    if day not in daily_stats:
                        daily_stats[day] = {"total": 0, "success": 0, "failed": 0}
                    daily_stats[day]["total"] += 1
                    if run.status == "success":
                        daily_stats[day]["success"] += 1
                    elif run.status == "error":
                        daily_stats[day]["failed"] += 1

            return success_response(
                {
                    "project": project_name,
                    "period_days": days,
                    "total_runs": total_runs,
                    "successful_runs": successful,
                    "failed_runs": failed,
                    "success_rate": ((successful / total_runs * 100) if total_runs > 0 else 0),
                    "average_duration_seconds": avg_duration,
                    "daily_stats": daily_stats,
                }
            )

        except Exception as e:
            logger.error(f"Failed to get project stats: {e}")
            return error_response(str(e))

    def get_trace_details(self, run_id: str) -> dict[str, Any]:
        """
        Get detailed trace information for a specific run.

        Args:
            run_id: LangSmith run ID

        Returns:
            Detailed trace information
        """
        if not self.client:
            return error_response("LangSmith client not initialized")

        try:
            run = self.client.read_run(run_id)

            return success_response(
                {
                    "id": str(run.id),
                    "name": run.name,
                    "status": run.status,
                    "run_type": getattr(run, "run_type", "unknown"),
                    "start_time": (run.start_time.isoformat() if run.start_time else None),
                    "end_time": run.end_time.isoformat() if run.end_time else None,
                    "inputs": run.inputs if hasattr(run, "inputs") else {},
                    "outputs": run.outputs if hasattr(run, "outputs") else {},
                    "error": run.error if hasattr(run, "error") else None,
                    "total_tokens": getattr(run, "total_tokens", 0),
                }
            )

        except Exception as e:
            logger.error(f"Failed to get trace details: {e}")
            return error_response(str(e))

    def monitor_health(self) -> dict[str, Any]:
        """
        Monitor LangSmith service health and connectivity.

        Returns:
            Health status
        """
        if not self.api_key:
            return error_response("LANGCHAIN_API_KEY not configured")

        if not self.client:
            return error_response("LangSmith client not initialized")

        try:
            # Try to list projects as health check
            list(self.client.list_projects(limit=1))

            return success_response(
                {
                    "status": "healthy",
                    "api_key_configured": True,
                    "client_initialized": True,
                    "projects_accessible": True,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        except Exception as e:
            return error_response(f"Health check failed: {e}")


def main():
    """CLI entry point for testing."""
    import argparse

    parser = argparse.ArgumentParser(description="LangSmith Monitor Skill")
    parser.add_argument(
        "--project",
        default="trading-rl-training",
        help="Project name (default: trading-rl-training)",
    )
    parser.add_argument("--hours", type=int, default=24, help="Hours of history (default: 24)")
    parser.add_argument("--health", action="store_true", help="Check health status")
    parser.add_argument("--stats", action="store_true", help="Get project statistics")

    args = parser.parse_args()

    monitor = LangSmithMonitor()

    if args.health:
        result = monitor.monitor_health()
        print(json.dumps(result, indent=2))
    elif args.stats:
        result = monitor.get_project_stats(args.project, days=7)
        print(json.dumps(result, indent=2))
    else:
        result = monitor.get_recent_runs(args.project, hours=args.hours)
        print(json.dumps(result, indent=2))

    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
