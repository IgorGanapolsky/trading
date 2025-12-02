#!/usr/bin/env python3
"""Fix shell issue and commit pending changes."""

import subprocess
import sys


def run_git_command(cmd):
    """Run git command and return result."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd="/Users/igorganapolsky/workspace/git/apps/trading",
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def main():
    print("🔧 Fixing shell issue and committing changes...")

    # Check git status
    success, stdout, stderr = run_git_command("git status --short")
    if not success:
        print(f"❌ Git status failed: {stderr}")
        return 1

    if not stdout.strip():
        print("✅ No changes to commit")
        return 0

    print(f"📋 Changes detected:\n{stdout}")

    # Add all changes
    success, stdout, stderr = run_git_command("git add -A")
    if not success:
        print(f"❌ Git add failed: {stderr}")
        return 1

    print("✅ Staged all changes")

    # Commit
    commit_msg = """docs: Archive redundant meta-documentation and add autonomous execution directive

- Archived meta-docs (MISSION_COMPLETE, CTO_REPORT)
- Added .cursorrules with autonomous execution directive
- Created docs/_archive/ directory structure
- Kept only actionable docs

All archived files preserved in docs/_archive/ for reference."""

    success, stdout, stderr = run_git_command(f'git commit -m "{commit_msg}"')
    if not success:
        print(f"❌ Git commit failed: {stderr}")
        return 1

    print("✅ Committed changes")

    # Push
    success, stdout, stderr = run_git_command("git push origin main")
    if not success:
        print(f"❌ Git push failed: {stderr}")
        return 1

    print("✅ Pushed to main branch")
    print("\n🎉 All changes committed and pushed successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
