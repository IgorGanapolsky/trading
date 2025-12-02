#!/usr/bin/env python3
"""
Continuous Training Monitor & Dashboard Updater
Uses Claude Skills and Vertex MCP to monitor training status and update Progress Dashboard.
"""

import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/training_monitor.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Import Claude Skills
try:
    sys.path.insert(
        0,
        str(
            Path(__file__).parent.parent / ".claude" / "skills" / "performance_monitor" / "scripts"
        ),
    )
    from performance_monitor import PerformanceMonitor

    PERFORMANCE_MONITOR_AVAILABLE = True
except ImportError:
    logger.warning("Performance Monitor skill not available")
    PERFORMANCE_MONITOR_AVAILABLE = False

# Import LangSmith Monitor
try:
    sys.path.insert(
        0,
        str(Path(__file__).parent.parent / ".claude" / "skills" / "langsmith_monitor" / "scripts"),
    )
    from langsmith_monitor import LangSmithMonitor

    LANGSMITH_MONITOR_AVAILABLE = True
except ImportError:
    logger.warning("LangSmith Monitor skill not available")
    LANGSMITH_MONITOR_AVAILABLE = False

# Import training status checker
from scripts.continuous_training import ContinuousTrainer


class TrainingMonitor:
    """Monitors RL training status and updates dashboard."""

    def __init__(self):
        """Initialize monitor."""
        self.trainer = ContinuousTrainer()
        self.performance_monitor = None
        self.langsmith_monitor = None

        if PERFORMANCE_MONITOR_AVAILABLE:
            try:
                self.performance_monitor = PerformanceMonitor()
                logger.info("✅ Performance Monitor skill initialized")
            except Exception as e:
                logger.warning(f"⚠️  Performance Monitor initialization failed: {e}")

        if LANGSMITH_MONITOR_AVAILABLE:
            try:
                self.langsmith_monitor = LangSmithMonitor()
                logger.info("✅ LangSmith Monitor skill initialized")
            except Exception as e:
                logger.warning(f"⚠️  LangSmith Monitor initialization failed: {e}")

    def check_training_status(self) -> dict[str, Any]:
        """Check current training status."""
        logger.info("🔍 Checking training status...")

        status = self.trainer.get_status()

        # Get cloud job statuses
        cloud_jobs = status.get("cloud_jobs", {})
        active_jobs = []
        completed_jobs = []

        for job_id, job_info in cloud_jobs.items():
            job_status = job_info.get("status", "unknown")
            if job_status in ["submitted", "running", "in_progress"]:
                active_jobs.append(
                    {
                        "job_id": job_id,
                        "symbol": job_info.get("symbol"),
                        "status": job_status,
                        "submitted_at": job_info.get("submitted_at"),
                    }
                )
            elif job_status in ["completed", "success"]:
                completed_jobs.append(
                    {
                        "job_id": job_id,
                        "symbol": job_info.get("symbol"),
                        "status": job_status,
                    }
                )

        return {
            "timestamp": datetime.now().isoformat(),
            "last_training": status.get("last_training", {}),
            "next_retrain": status.get("next_retrain", {}),
            "active_jobs": active_jobs,
            "completed_jobs": completed_jobs,
            "total_jobs": len(cloud_jobs),
        }

    def check_vertex_ai_jobs(self) -> dict[str, Any]:
        """Check Vertex AI RL job statuses using MCP."""
        logger.info("☁️  Checking Vertex AI RL jobs...")

        try:
            from src.ml.rl_service_client import RLServiceClient

            client = RLServiceClient(provider="vertex_ai")
            status = self.check_training_status()

            # Check each active job
            job_statuses = {}
            for job in status.get("active_jobs", []):
                job_id = job["job_id"]
                try:
                    job_status = client.get_job_status(job_id)
                    job_statuses[job_id] = job_status
                    logger.info(
                        f"   {job['symbol']} ({job_id}): {job_status.get('status', 'unknown')}"
                    )
                except Exception as e:
                    logger.warning(f"   Failed to check {job_id}: {e}")
                    job_statuses[job_id] = {"status": "unknown", "error": str(e)}

            return {"checked_at": datetime.now().isoformat(), "jobs": job_statuses}

        except Exception as e:
            logger.error(f"❌ Failed to check Vertex AI jobs: {e}")
            return {"error": str(e)}

    def update_dashboard(self) -> bool:
        """Update Progress Dashboard with training status."""
        logger.info("📊 Updating Progress Dashboard...")

        try:
            # Import dashboard generator
            from scripts.generate_progress_dashboard import (
                main as generate_dashboard_main,
            )

            # Generate dashboard (this saves to wiki/Progress-Dashboard.md)
            generate_dashboard_main()

            dashboard_path = Path("wiki/Progress-Dashboard.md")

            if dashboard_path.exists():
                logger.info(f"✅ Dashboard generated: {dashboard_path}")

                # Also update training status section
                self._add_training_status_to_dashboard(dashboard_path)

                return True
            else:
                logger.warning("⚠️  Dashboard file not found after generation")
                return False

        except Exception as e:
            logger.error(f"❌ Failed to update dashboard: {e}")
            import traceback

            traceback.print_exc()
            return False

    def _add_training_status_to_dashboard(self, dashboard_path: Path):
        """Add RL training status section to dashboard."""
        try:
            status = self.check_training_status()
            self.check_vertex_ai_jobs()

            # Read current dashboard
            with open(dashboard_path) as f:
                content = f.read()

            # Create training status section
            training_section = f"""
---

## 🤖 RL Training Status

**Last Updated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

### Cloud RL Jobs

**Active Jobs**: {len(status.get("active_jobs", []))}
**Completed Jobs**: {len(status.get("completed_jobs", []))}
**Total Jobs**: {status.get("total_jobs", 0)}

#### Active Training Jobs

"""

            for job in status.get("active_jobs", [])[:10]:  # Show top 10
                training_section += (
                    f"- **{job['symbol']}**: {job['status']} (Job ID: `{job['job_id']}`)\n"
                )
                training_section += f"  - Submitted: {job.get('submitted_at', 'Unknown')}\n"

            training_section += "\n#### Last Training Times\n\n"
            for symbol, last_time in list(status.get("last_training", {}).items())[:10]:
                training_section += f"- **{symbol}**: {last_time}\n"

            training_section += "\n#### Next Retrain Schedule\n\n"
            for symbol, next_time in list(status.get("next_retrain", {}).items())[:10]:
                training_section += f"- **{symbol}**: {next_time}\n"

            # Add LangSmith monitoring section
            if self.langsmith_monitor:
                try:
                    langsmith_stats = self.langsmith_monitor.get_project_stats(
                        "trading-rl-training", days=7
                    )
                    if langsmith_stats.get("success"):
                        stats = langsmith_stats
                        training_section += "\n### LangSmith Monitoring\n\n"
                        training_section += "**Project**: trading-rl-training\n"
                        training_section += (
                            f"**Total Runs** (7 days): {stats.get('total_runs', 0)}\n"
                        )
                        training_section += (
                            f"**Success Rate**: {stats.get('success_rate', 0):.1f}%\n"
                        )
                        training_section += f"**Average Duration**: {stats.get('average_duration_seconds', 0):.1f}s\n"
                        training_section += "\n**View Dashboard**: https://smith.langchain.com\n"
                except Exception as e:
                    logger.debug(f"Failed to add LangSmith stats: {e}")

            # Append to dashboard (before final ---)
            if "---" in content:
                parts = content.rsplit("---", 1)
                content = parts[0] + training_section + "\n---" + parts[1]
            else:
                content += training_section

            # Write back
            with open(dashboard_path, "w") as f:
                f.write(content)

            logger.info("✅ Training status added to dashboard")

        except Exception as e:
            logger.warning(f"⚠️  Failed to add training status to dashboard: {e}")

    def monitor_loop(self, interval_minutes: int = 60, max_iterations: int = None):
        """
        Run continuous monitoring loop.

        Args:
            interval_minutes: Minutes between checks
            max_iterations: Maximum iterations (None = infinite)
        """
        logger.info("=" * 80)
        logger.info("🚀 STARTING CONTINUOUS TRAINING MONITOR")
        logger.info("=" * 80)
        logger.info(f"Check interval: {interval_minutes} minutes")
        logger.info(f"Max iterations: {max_iterations or 'infinite'}")
        logger.info("")

        iteration = 0

        while True:
            iteration += 1
            logger.info(f"\n{'=' * 80}")
            logger.info(
                f"📊 MONITORING CYCLE #{iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            logger.info(f"{'=' * 80}\n")

            try:
                # Check training status
                status = self.check_training_status()
                logger.info("✅ Training status checked")
                logger.info(f"   Active jobs: {len(status.get('active_jobs', []))}")
                logger.info(f"   Completed jobs: {len(status.get('completed_jobs', []))}")

                # Check Vertex AI jobs
                vertex_status = self.check_vertex_ai_jobs()
                if "error" not in vertex_status:
                    logger.info("✅ Vertex AI jobs checked")

                # Check LangSmith status
                if self.langsmith_monitor:
                    langsmith_health = self.langsmith_monitor.monitor_health()
                    if langsmith_health.get("success"):
                        logger.info(
                            f"✅ LangSmith health checked: {langsmith_health.get('status')}"
                        )

                    langsmith_stats = self.langsmith_monitor.get_project_stats(
                        "trading-rl-training", days=7
                    )
                    if langsmith_stats.get("success"):
                        stats = langsmith_stats
                        logger.info(
                            f"✅ LangSmith stats: {stats.get('total_runs', 0)} runs, "
                            f"{stats.get('success_rate', 0):.1f}% success rate"
                        )

                # Update dashboard
                if self.update_dashboard():
                    logger.info("✅ Dashboard updated")
                else:
                    logger.warning("⚠️  Dashboard update failed")

                # Check if we should stop
                if max_iterations and iteration >= max_iterations:
                    logger.info(f"\n🏁 Reached max iterations ({max_iterations}), stopping...")
                    break

                # Wait for next check
                logger.info(f"\n⏳ Waiting {interval_minutes} minutes until next check...")
                time.sleep(interval_minutes * 60)

            except KeyboardInterrupt:
                logger.info("\n🛑 Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"❌ Error in monitoring cycle: {e}")
                import traceback

                traceback.print_exc()
                logger.info(f"⏳ Waiting {interval_minutes} minutes before retry...")
                time.sleep(interval_minutes * 60)


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Monitor RL Training & Update Dashboard")
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Check interval in minutes (default: 60)",
    )
    parser.add_argument("--once", action="store_true", help="Run once and exit (don't loop)")
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum iterations (default: infinite)",
    )
    parser.add_argument(
        "--status-only",
        action="store_true",
        help="Only check status, don't update dashboard",
    )

    args = parser.parse_args()

    monitor = TrainingMonitor()

    if args.once:
        # Run once
        logger.info("🔍 Running single check...")
        status = monitor.check_training_status()
        print(json.dumps(status, indent=2, default=str))

        if not args.status_only:
            monitor.update_dashboard()

        return 0

    # Run continuous monitoring
    monitor.monitor_loop(interval_minutes=args.interval, max_iterations=args.max_iterations)

    return 0


if __name__ == "__main__":
    sys.exit(main())
