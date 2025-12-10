"""
Automated Data Backup System

Backs up critical trading data to multiple locations:
1. Local compressed backup (data/backups/)
2. Git commit + push to backup branch
3. Optional cloud storage (S3, GCS)

Critical data backed up:
- system_state.json
- Trade logs (trades_*.json)
- Performance data
- Alert history
- Kill switch state

Author: Trading System
Created: 2025-12-08
"""

import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class DataBackup:
    """
    Automated backup system for trading data.

    Backup strategy:
    - Hourly: Incremental backup of changed files
    - Daily: Full compressed backup
    - Weekly: Archive to backup branch
    """

    # Critical files to always backup
    CRITICAL_FILES = [
        "data/system_state.json",
        "data/kill_switch_state.json",
        "data/emergency_alerts.json",
        "data/circuit_breaker_state.json",
        "data/emergency_liquidator_state.json",
    ]

    # Patterns for trade logs
    TRADE_LOG_PATTERNS = [
        "data/trades_*.json",
        "data/trade_logs/*.json",
        "data/performance_log.json",
    ]

    def __init__(
        self,
        backup_dir: str = "data/backups",
        max_backups: int = 30,
        s3_bucket: Optional[str] = None,
        gcs_bucket: Optional[str] = None,
    ):
        """
        Initialize backup system.

        Args:
            backup_dir: Local backup directory
            max_backups: Maximum number of backups to keep
            s3_bucket: Optional S3 bucket for cloud backup
            gcs_bucket: Optional GCS bucket for cloud backup
        """
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.max_backups = max_backups
        self.s3_bucket = s3_bucket or os.environ.get("BACKUP_S3_BUCKET")
        self.gcs_bucket = gcs_bucket or os.environ.get("BACKUP_GCS_BUCKET")

    def _get_files_to_backup(self) -> list[Path]:
        """Get list of all files to backup."""
        files = []

        # Add critical files
        for file_path in self.CRITICAL_FILES:
            path = Path(file_path)
            if path.exists():
                files.append(path)

        # Add trade logs with glob patterns
        import glob

        for pattern in self.TRADE_LOG_PATTERNS:
            for match in glob.glob(pattern):
                path = Path(match)
                if path.exists() and path not in files:
                    files.append(path)

        return files

    def create_backup(self, backup_type: str = "manual") -> dict:
        """
        Create a backup of all critical data.

        Args:
            backup_type: Type of backup (manual, hourly, daily, weekly)

        Returns:
            Backup result dict
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{backup_type}_{timestamp}"
        backup_path = self.backup_dir / f"{backup_name}.tar.gz"

        files_to_backup = self._get_files_to_backup()

        if not files_to_backup:
            logger.warning("No files to backup")
            return {"status": "no_files", "files_count": 0}

        try:
            # Create temporary directory for backup
            temp_dir = self.backup_dir / f"temp_{timestamp}"
            temp_dir.mkdir(exist_ok=True)

            # Copy files to temp directory
            for file_path in files_to_backup:
                dest = temp_dir / file_path.name
                shutil.copy2(file_path, dest)

            # Add backup metadata
            metadata = {
                "backup_type": backup_type,
                "timestamp": timestamp,
                "files": [str(f) for f in files_to_backup],
                "created_at": datetime.now().isoformat(),
            }
            with open(temp_dir / "backup_metadata.json", "w") as f:
                json.dump(metadata, f, indent=2)

            # Create compressed archive
            import tarfile

            with tarfile.open(backup_path, "w:gz") as tar:
                for file in temp_dir.iterdir():
                    tar.add(file, arcname=file.name)

            # Clean up temp directory
            shutil.rmtree(temp_dir)

            # Get backup size
            backup_size = backup_path.stat().st_size

            logger.info(f"✅ Backup created: {backup_path} ({backup_size / 1024:.1f} KB)")

            # Clean up old backups
            self._cleanup_old_backups()

            # Upload to cloud if configured
            cloud_results = {}
            if self.s3_bucket:
                cloud_results["s3"] = self._upload_to_s3(backup_path)
            if self.gcs_bucket:
                cloud_results["gcs"] = self._upload_to_gcs(backup_path)

            return {
                "status": "success",
                "backup_path": str(backup_path),
                "files_count": len(files_to_backup),
                "size_bytes": backup_size,
                "cloud_uploads": cloud_results,
            }

        except Exception as e:
            logger.error(f"❌ Backup failed: {e}")
            return {"status": "error", "error": str(e)}

    def _cleanup_old_backups(self) -> int:
        """Remove old backups beyond max_backups limit."""
        backups = sorted(
            self.backup_dir.glob("backup_*.tar.gz"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        removed = 0
        for backup in backups[self.max_backups :]:
            try:
                backup.unlink()
                removed += 1
                logger.debug(f"Removed old backup: {backup}")
            except Exception as e:
                logger.error(f"Failed to remove {backup}: {e}")

        if removed:
            logger.info(f"Cleaned up {removed} old backups")

        return removed

    def _upload_to_s3(self, backup_path: Path) -> dict:
        """Upload backup to S3."""
        try:
            import boto3

            s3 = boto3.client("s3")
            key = f"trading-backups/{backup_path.name}"

            s3.upload_file(str(backup_path), self.s3_bucket, key)

            logger.info(f"✅ Uploaded to S3: s3://{self.s3_bucket}/{key}")
            return {"status": "success", "key": key}

        except ImportError:
            logger.debug("boto3 not installed, skipping S3 upload")
            return {"status": "skipped", "reason": "boto3 not installed"}
        except Exception as e:
            logger.error(f"S3 upload failed: {e}")
            return {"status": "error", "error": str(e)}

    def _upload_to_gcs(self, backup_path: Path) -> dict:
        """Upload backup to Google Cloud Storage."""
        try:
            from google.cloud import storage

            client = storage.Client()
            bucket = client.bucket(self.gcs_bucket)
            blob = bucket.blob(f"trading-backups/{backup_path.name}")

            blob.upload_from_filename(str(backup_path))

            logger.info(f"✅ Uploaded to GCS: gs://{self.gcs_bucket}/{blob.name}")
            return {"status": "success", "blob": blob.name}

        except ImportError:
            logger.debug("google-cloud-storage not installed, skipping GCS upload")
            return {"status": "skipped", "reason": "google-cloud-storage not installed"}
        except Exception as e:
            logger.error(f"GCS upload failed: {e}")
            return {"status": "error", "error": str(e)}

    def restore_backup(self, backup_name: str, restore_dir: str = "data/restored") -> dict:
        """
        Restore from a backup.

        Args:
            backup_name: Name of backup file (or "latest")
            restore_dir: Directory to restore files to

        Returns:
            Restore result dict
        """
        restore_path = Path(restore_dir)
        restore_path.mkdir(parents=True, exist_ok=True)

        # Find backup file
        if backup_name == "latest":
            backups = sorted(
                self.backup_dir.glob("backup_*.tar.gz"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if not backups:
                return {"status": "error", "error": "No backups found"}
            backup_file = backups[0]
        else:
            backup_file = self.backup_dir / backup_name
            if not backup_file.exists():
                return {"status": "error", "error": f"Backup not found: {backup_name}"}

        try:
            import tarfile

            with tarfile.open(backup_file, "r:gz") as tar:
                # Secure extraction preventing Zip Slip
                def is_safe_member(member, path):
                    member_path = os.path.join(path, member.name)
                    abs_directory = os.path.abspath(path)
                    abs_target = os.path.abspath(member_path)
                    prefix = os.path.commonprefix([abs_directory, abs_target])
                    return prefix == abs_directory

                for member in tar.getmembers():
                    if is_safe_member(member, str(restore_path)):
                        tar.extract(member, restore_path)
                    else:
                        logger.warning(f"Skipping unsafe file in backup: {member.name}")

            logger.info(f"✅ Restored backup to: {restore_path}")

            return {
                "status": "success",
                "backup_file": str(backup_file),
                "restore_dir": str(restore_path),
                "files": list(restore_path.iterdir()),
            }

        except Exception as e:
            logger.error(f"❌ Restore failed: {e}")
            return {"status": "error", "error": str(e)}

    def list_backups(self) -> list[dict]:
        """List all available backups."""
        backups = []
        for backup_file in sorted(
            self.backup_dir.glob("backup_*.tar.gz"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            stat = backup_file.stat()
            backups.append(
                {
                    "name": backup_file.name,
                    "size_bytes": stat.st_size,
                    "size_kb": f"{stat.st_size / 1024:.1f} KB",
                    "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )

        return backups

    def git_backup(self, commit_message: Optional[str] = None) -> dict:
        """
        Commit current data state to git backup branch.

        This creates a commit on a 'data-backup' branch with all critical files.
        """
        import subprocess

        try:
            # Get current branch
            current_branch = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
            ).stdout.strip()

            # Create/checkout backup branch
            subprocess.run(
                ["git", "checkout", "-B", "data-backup"],
                capture_output=True,
            )

            # Add critical files
            files_to_add = self._get_files_to_backup()
            for file_path in files_to_add:
                subprocess.run(["git", "add", str(file_path)], capture_output=True)

            # Commit
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            message = commit_message or f"Data backup: {timestamp}"
            subprocess.run(
                ["git", "commit", "-m", message],
                capture_output=True,
            )

            # Switch back to original branch
            subprocess.run(
                ["git", "checkout", current_branch],
                capture_output=True,
            )

            logger.info("✅ Git backup committed to data-backup branch")

            return {
                "status": "success",
                "branch": "data-backup",
                "message": message,
                "files_count": len(files_to_add),
            }

        except Exception as e:
            logger.error(f"❌ Git backup failed: {e}")
            # Try to switch back to original branch
            try:
                subprocess.run(["git", "checkout", current_branch], capture_output=True)
            except Exception:
                pass
            return {"status": "error", "error": str(e)}


# Singleton instance
_backup_instance: Optional[DataBackup] = None


def get_backup() -> DataBackup:
    """Get or create singleton backup instance."""
    global _backup_instance
    if _backup_instance is None:
        _backup_instance = DataBackup()
    return _backup_instance


def create_backup(backup_type: str = "manual") -> dict:
    """Quick function to create backup."""
    return get_backup().create_backup(backup_type)


# CLI interface
if __name__ == "__main__":
    import sys

    backup = get_backup()

    if len(sys.argv) < 2:
        print("Usage: python data_backup.py [create|list|restore] [options]")
        sys.exit(0)

    command = sys.argv[1].lower()

    if command == "create":
        backup_type = sys.argv[2] if len(sys.argv) > 2 else "manual"
        result = backup.create_backup(backup_type)
        print(json.dumps(result, indent=2))

    elif command == "list":
        backups = backup.list_backups()
        print(f"Found {len(backups)} backups:")
        for b in backups[:10]:
            print(f"  {b['name']} - {b['size_kb']} - {b['created']}")

    elif command == "restore":
        backup_name = sys.argv[2] if len(sys.argv) > 2 else "latest"
        result = backup.restore_backup(backup_name)
        print(json.dumps(result, indent=2, default=str))

    elif command == "git":
        result = backup.git_backup()
        print(json.dumps(result, indent=2))

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
