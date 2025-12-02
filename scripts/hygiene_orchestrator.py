#!/usr/bin/env python3
"""
Autonomous Hygiene Orchestrator
Automatically cleans up garbage, organizes repository, and maintains code quality
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()


class HygieneOrchestrator:
    """Autonomous hygiene and garbage cleanup system"""

    def __init__(self, dry_run: bool = False):
        """Initialize hygiene orchestrator"""
        self.dry_run = dry_run
        self.project_root = Path(__file__).parent.parent
        self.garbage_cache_dir = self.project_root / ".claude" / "cache" / "garbage-detection"
        self.reports_dir = self.project_root / ".claude" / "reports"
        self.logs_dir = self.project_root / "logs"
        self.data_cache_dir = self.project_root / "data" / "cache"

    def cleanup_garbage_detection_cache(self, max_age_days: int = 7) -> dict[str, Any]:
        """
        Clean up old garbage detection cache files

        Args:
            max_age_days: Maximum age in days for cache files

        Returns:
            Dict with cleanup results
        """
        try:
            if not self.garbage_cache_dir.exists():
                return {
                    "success": True,
                    "files_deleted": 0,
                    "message": "Cache directory does not exist",
                }

            deleted_count = 0
            deleted_files = []
            total_size = 0
            cutoff_date = datetime.now() - timedelta(days=max_age_days)

            for cache_file in self.garbage_cache_dir.glob("*.json"):
                try:
                    file_mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
                    file_size = cache_file.stat().st_size

                    if file_mtime < cutoff_date:
                        if not self.dry_run:
                            cache_file.unlink()
                        deleted_count += 1
                        deleted_files.append(str(cache_file.name))
                        total_size += file_size
                except Exception as e:
                    print(f"Warning: Could not process {cache_file}: {e}")

            # Clean up text files (dead_imports.txt, etc.)
            for txt_file in self.garbage_cache_dir.glob("*.txt"):
                try:
                    file_mtime = datetime.fromtimestamp(txt_file.stat().st_mtime)
                    if file_mtime < cutoff_date:
                        if not self.dry_run:
                            txt_file.unlink()
                        deleted_count += 1
                        deleted_files.append(str(txt_file.name))
                except Exception:
                    pass

            return {
                "success": True,
                "files_deleted": deleted_count,
                "deleted_files": deleted_files[:10],  # Limit to first 10
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "dry_run": self.dry_run,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def cleanup_old_reports(self, max_age_days: int = 30) -> dict[str, Any]:
        """
        Clean up old hygiene reports

        Args:
            max_age_days: Maximum age in days for reports

        Returns:
            Dict with cleanup results
        """
        try:
            if not self.reports_dir.exists():
                return {"success": True, "files_deleted": 0}

            deleted_count = 0
            cutoff_date = datetime.now() - timedelta(days=max_age_days)

            for report_file in self.reports_dir.glob("*.txt"):
                try:
                    file_mtime = datetime.fromtimestamp(report_file.stat().st_mtime)
                    if file_mtime < cutoff_date:
                        if not self.dry_run:
                            report_file.unlink()
                        deleted_count += 1
                except Exception:
                    pass

            return {
                "success": True,
                "files_deleted": deleted_count,
                "dry_run": self.dry_run,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def cleanup_old_logs(self, max_age_days: int = 7) -> dict[str, Any]:
        """
        Clean up old log files

        Args:
            max_age_days: Maximum age in days for logs

        Returns:
            Dict with cleanup results
        """
        try:
            if not self.logs_dir.exists():
                return {"success": True, "files_deleted": 0}

            deleted_count = 0
            total_size = 0
            cutoff_date = datetime.now() - timedelta(days=max_age_days)

            for log_file in self.logs_dir.glob("*.log"):
                try:
                    file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                    file_size = log_file.stat().st_size

                    if file_mtime < cutoff_date:
                        if not self.dry_run:
                            log_file.unlink()
                        deleted_count += 1
                        total_size += file_size
                except Exception:
                    pass

            return {
                "success": True,
                "files_deleted": deleted_count,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "dry_run": self.dry_run,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def cleanup_old_cache_files(self, max_age_days: int = 3) -> dict[str, Any]:
        """
        Clean up old data cache files

        Args:
            max_age_days: Maximum age in days for cache files

        Returns:
            Dict with cleanup results
        """
        try:
            if not self.data_cache_dir.exists():
                return {"success": True, "files_deleted": 0}

            deleted_count = 0
            total_size = 0
            cutoff_date = datetime.now() - timedelta(days=max_age_days)

            # Clean CSV cache files
            for cache_file in self.data_cache_dir.rglob("*.csv"):
                try:
                    file_mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
                    file_size = cache_file.stat().st_size

                    if file_mtime < cutoff_date:
                        if not self.dry_run:
                            cache_file.unlink()
                        deleted_count += 1
                        total_size += file_size
                except Exception:
                    pass

            return {
                "success": True,
                "files_deleted": deleted_count,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "dry_run": self.dry_run,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_all_cleanup(self) -> dict[str, Any]:
        """
        Run all cleanup operations

        Returns:
            Dict with all cleanup results
        """
        results = {
            "timestamp": datetime.now().isoformat(),
            "dry_run": self.dry_run,
            "cleanup_results": {},
        }

        # Cleanup garbage detection cache
        results["cleanup_results"]["garbage_cache"] = self.cleanup_garbage_detection_cache(
            max_age_days=7
        )

        # Cleanup old reports
        results["cleanup_results"]["reports"] = self.cleanup_old_reports(max_age_days=30)

        # Cleanup old logs
        results["cleanup_results"]["logs"] = self.cleanup_old_logs(max_age_days=7)

        # Cleanup old cache files
        results["cleanup_results"]["data_cache"] = self.cleanup_old_cache_files(max_age_days=3)

        # Calculate totals
        total_files = sum(
            r.get("files_deleted", 0)
            for r in results["cleanup_results"].values()
            if isinstance(r, dict)
        )
        total_size = sum(
            r.get("total_size_mb", 0)
            for r in results["cleanup_results"].values()
            if isinstance(r, dict)
        )

        results["summary"] = {
            "total_files_deleted": total_files,
            "total_space_freed_mb": round(total_size, 2),
        }

        return results

    def check_repository_hygiene(self) -> dict[str, Any]:
        """
        Check repository hygiene status

        Returns:
            Dict with hygiene status
        """
        try:
            # Check for large files
            large_files = []
            for file_path in self.project_root.rglob("*"):
                if file_path.is_file() and file_path.stat().st_size > 10 * 1024 * 1024:  # 10MB
                    large_files.append(
                        {
                            "path": str(file_path.relative_to(self.project_root)),
                            "size_mb": round(file_path.stat().st_size / (1024 * 1024), 2),
                        }
                    )

            # Check garbage cache size
            garbage_cache_size = 0
            if self.garbage_cache_dir.exists():
                for cache_file in self.garbage_cache_dir.glob("*.json"):
                    garbage_cache_size += cache_file.stat().st_size

            # Check for __pycache__ directories
            pycache_dirs = [
                str(d.relative_to(self.project_root))
                for d in self.project_root.rglob("__pycache__")
            ]

            return {
                "success": True,
                "hygiene_status": {
                    "large_files": large_files[:10],  # Limit to first 10
                    "garbage_cache_size_mb": round(garbage_cache_size / (1024 * 1024), 2),
                    "pycache_dirs_count": len(pycache_dirs),
                    "issues_found": len(large_files)
                    + (1 if garbage_cache_size > 100 * 1024 * 1024 else 0),
                },
                "recommendations": [
                    "Run cleanup if garbage cache > 100MB",
                    "Remove large files if not needed",
                    "Clean __pycache__ directories",
                ],
            }

        except Exception as e:
            return {"success": False, "error": str(e)}


def main():
    """CLI interface for hygiene orchestrator"""
    parser = argparse.ArgumentParser(description="Autonomous Hygiene Orchestrator")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    parser.add_argument("--check-only", action="store_true", help="Only check hygiene status")
    parser.add_argument(
        "--cleanup-garbage",
        action="store_true",
        help="Clean up garbage detection cache",
    )
    parser.add_argument("--cleanup-reports", action="store_true", help="Clean up old reports")
    parser.add_argument("--cleanup-logs", action="store_true", help="Clean up old logs")
    parser.add_argument("--cleanup-cache", action="store_true", help="Clean up data cache")
    parser.add_argument("--all", action="store_true", help="Run all cleanup operations")

    args = parser.parse_args()

    orchestrator = HygieneOrchestrator(dry_run=args.dry_run)

    if args.check_only:
        result = orchestrator.check_repository_hygiene()
        print(json.dumps(result, indent=2))
        return

    if args.all:
        result = orchestrator.run_all_cleanup()
        print(json.dumps(result, indent=2))
        return

    results = {}
    if args.cleanup_garbage:
        results["garbage_cache"] = orchestrator.cleanup_garbage_detection_cache()
    if args.cleanup_reports:
        results["reports"] = orchestrator.cleanup_old_reports()
    if args.cleanup_logs:
        results["logs"] = orchestrator.cleanup_old_logs()
    if args.cleanup_cache:
        results["data_cache"] = orchestrator.cleanup_old_cache_files()

    if not results:
        # Default: run all cleanup
        result = orchestrator.run_all_cleanup()
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
