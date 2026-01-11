#!/usr/bin/env python3
"""
Cleanup old JSON files to prevent accumulation.
Retention: 7 days for backups, 30 days for trading plans.
"""
import os
from pathlib import Path
from datetime import datetime, timedelta

RETENTION_POLICIES = {
    "data/backups": 7,           # Keep 7 days of backups
    "data/trading_plans": 30,    # Keep 30 days of trading plans
    "data/options_signals": 14,  # Keep 14 days of signals
    "data/sentiment": 7,         # Keep 7 days of sentiment
    "data/agent_context/memories": 14,  # Keep 14 days of memories
}

def cleanup_directory(dir_path: str, retention_days: int) -> int:
    """Delete files older than retention_days. Returns count deleted."""
    deleted = 0
    cutoff = datetime.now() - timedelta(days=retention_days)
    
    path = Path(dir_path)
    if not path.exists():
        return 0
    
    for file in path.glob("*.json"):
        if file.stat().st_mtime < cutoff.timestamp():
            file.unlink()
            deleted += 1
            print(f"  Deleted: {file.name}")
    
    return deleted

def main():
    print("=" * 50)
    print("FILE CLEANUP - Retention Policy Enforcement")
    print("=" * 50)
    
    total_deleted = 0
    for dir_path, days in RETENTION_POLICIES.items():
        print(f"\n{dir_path} (keep {days} days):")
        deleted = cleanup_directory(dir_path, days)
        total_deleted += deleted
        if deleted == 0:
            print("  No old files to delete")
    
    print(f"\n{'=' * 50}")
    print(f"Total deleted: {total_deleted} files")

if __name__ == "__main__":
    main()
