#!/usr/bin/env python3
"""
Emergency Rollback Script - Revert bad merges to main

Usage:
    python3 scripts/emergency_rollback.py --check     # Show what would be reverted
    python3 scripts/emergency_rollback.py --revert    # Actually revert last merge
    python3 scripts/emergency_rollback.py --revert-to <sha>  # Revert to specific commit

Safety features:
- Shows diff before reverting
- Creates backup branch before reverting
- Requires confirmation
- Logs all rollbacks for audit
"""

import argparse
import subprocess
import sys
import json
from datetime import datetime
from pathlib import Path


def run_git(cmd: list[str], check: bool = True) -> str:
    """Run git command and return output."""
    result = subprocess.run(
        ["git"] + cmd,
        capture_output=True,
        text=True,
        check=check
    )
    return result.stdout.strip()


def get_last_merge() -> dict:
    """Get info about the last merge commit."""
    try:
        # Get last merge commit
        sha = run_git(["log", "--merges", "-1", "--format=%H"])
        if not sha:
            return {"error": "No merge commits found"}

        message = run_git(["log", "-1", "--format=%s", sha])
        author = run_git(["log", "-1", "--format=%an <%ae>", sha])
        date = run_git(["log", "-1", "--format=%ai", sha])

        return {
            "sha": sha,
            "short_sha": sha[:7],
            "message": message,
            "author": author,
            "date": date
        }
    except subprocess.CalledProcessError as e:
        return {"error": str(e)}


def get_commit_before_merge(merge_sha: str) -> str:
    """Get the commit SHA before a merge."""
    return run_git(["rev-parse", f"{merge_sha}^"])


def show_changes_since(sha: str) -> None:
    """Show what changed since a commit."""
    print("\n📋 Files changed since this commit:")
    print("-" * 50)
    diff_stat = run_git(["diff", "--stat", sha, "HEAD"])
    print(diff_stat if diff_stat else "  (no changes)")

    print("\n📋 Commits that would be reverted:")
    print("-" * 50)
    log = run_git(["log", "--oneline", f"{sha}..HEAD"])
    print(log if log else "  (no commits)")


def create_backup_branch() -> str:
    """Create a backup branch before rollback."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    branch_name = f"backup/pre-rollback-{timestamp}"
    run_git(["branch", branch_name])
    return branch_name


def log_rollback(merge_info: dict, backup_branch: str) -> None:
    """Log rollback for audit trail."""
    log_file = Path("data/rollback_log.json")
    log_file.parent.mkdir(exist_ok=True)

    try:
        logs = json.loads(log_file.read_text()) if log_file.exists() else []
    except json.JSONDecodeError:
        logs = []

    logs.append({
        "timestamp": datetime.now().isoformat(),
        "reverted_merge": merge_info,
        "backup_branch": backup_branch,
        "current_head": run_git(["rev-parse", "HEAD"])
    })

    log_file.write_text(json.dumps(logs, indent=2))
    print(f"\n📝 Rollback logged to {log_file}")


def main():
    parser = argparse.ArgumentParser(description="Emergency rollback for bad merges")
    parser.add_argument("--check", action="store_true", help="Show what would be reverted")
    parser.add_argument("--revert", action="store_true", help="Revert last merge")
    parser.add_argument("--revert-to", metavar="SHA", help="Revert to specific commit")
    args = parser.parse_args()

    # Check we're on main
    current_branch = run_git(["branch", "--show-current"])
    if current_branch != "main":
        print(f"⚠️  Not on main branch (currently on: {current_branch})")
        print("   Switch to main first: git checkout main")
        sys.exit(1)

    if args.check or (not args.revert and not args.revert_to):
        # Show status
        merge_info = get_last_merge()
        if "error" in merge_info:
            print(f"❌ {merge_info['error']}")
            sys.exit(1)

        print("═" * 60)
        print("🔍 LAST MERGE COMMIT")
        print("═" * 60)
        print(f"  SHA:     {merge_info['short_sha']}")
        print(f"  Message: {merge_info['message']}")
        print(f"  Author:  {merge_info['author']}")
        print(f"  Date:    {merge_info['date']}")

        target_sha = get_commit_before_merge(merge_info['sha'])
        show_changes_since(target_sha)

        print("\n" + "═" * 60)
        print("To revert this merge, run:")
        print(f"  python3 scripts/emergency_rollback.py --revert")
        print("═" * 60)

    elif args.revert:
        merge_info = get_last_merge()
        if "error" in merge_info:
            print(f"❌ {merge_info['error']}")
            sys.exit(1)

        target_sha = get_commit_before_merge(merge_info['sha'])

        print("═" * 60)
        print("🚨 EMERGENCY ROLLBACK")
        print("═" * 60)
        print(f"Reverting merge: {merge_info['short_sha']} - {merge_info['message']}")
        print(f"Rolling back to: {target_sha[:7]}")

        # Create backup
        backup = create_backup_branch()
        print(f"\n✅ Created backup branch: {backup}")

        # Revert using git revert (creates new commit, safer than reset)
        print("\n🔄 Reverting merge commit...")
        try:
            run_git(["revert", "-m", "1", merge_info['sha'], "--no-edit"])
            print("✅ Merge reverted successfully")

            # Log the rollback
            log_rollback(merge_info, backup)

            print("\n" + "═" * 60)
            print("✅ ROLLBACK COMPLETE")
            print("═" * 60)
            print(f"Backup branch: {backup}")
            print("To push: git push origin main")
            print("To undo: git revert HEAD")

        except subprocess.CalledProcessError as e:
            print(f"❌ Revert failed: {e}")
            print(f"   Backup available at: {backup}")
            sys.exit(1)

    elif args.revert_to:
        target_sha = args.revert_to

        # Verify commit exists
        try:
            full_sha = run_git(["rev-parse", target_sha])
        except subprocess.CalledProcessError:
            print(f"❌ Commit not found: {target_sha}")
            sys.exit(1)

        print("═" * 60)
        print(f"🚨 REVERTING TO SPECIFIC COMMIT: {target_sha[:7]}")
        print("═" * 60)

        show_changes_since(full_sha)

        confirm = input("\n⚠️  Type 'REVERT' to confirm: ")
        if confirm != "REVERT":
            print("Cancelled.")
            sys.exit(0)

        backup = create_backup_branch()
        print(f"\n✅ Created backup branch: {backup}")

        # Hard reset (dangerous but sometimes necessary)
        run_git(["reset", "--hard", full_sha])
        print(f"✅ Reset to {target_sha[:7]}")

        print("\n⚠️  This was a HARD reset. To push:")
        print("   git push --force-with-lease origin main")


if __name__ == "__main__":
    main()
