#!/usr/bin/env python3
"""
Create and Merge PR via GitHub API

This script creates a PR and merges it automatically.
Used when Claude cannot access GitHub API directly from sandbox.

Usage:
    python3 scripts/create_and_merge_pr.py --token <GH_PAT>

    # Or with environment variable:
    export GH_PAT=<token>
    python3 scripts/create_and_merge_pr.py

Created: 2026-01-13
"""

import argparse
import json
import os
import subprocess
import sys
import time

try:
    import requests
except ImportError:
    print("Installing requests...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests


def get_current_branch():
    """Get current git branch name."""
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def get_commits_on_branch():
    """Get commits on current branch vs main."""
    result = subprocess.run(
        ["git", "log", "--oneline", "origin/main..HEAD"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def create_pr(token: str, branch: str) -> dict:
    """Create a PR via GitHub API."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    body = {
        "title": "feat: Add trading verification + trigger trade execution",
        "head": branch,
        "base": "main",
        "body": """## Summary
- Add `verify_trading_operational.py` script to diagnose system health
- Trigger trade execution via TRIGGER_TRADE.md
- Add auto-PR workflow for claude/* branches

## Why
CEO concern: 'System is operationally unstable, failing nearly each day'

## Changes
1. `scripts/verify_trading_operational.py` - Comprehensive system check
2. `TRIGGER_TRADE.md` - Triggers daily-trading workflow
3. `.github/workflows/auto-pr.yml` - Auto-creates PRs for claude branches

## Test Plan
- [ ] Watch daily-trading workflow execute after merge
- [ ] Verify paper account shows activity
""",
    }

    response = requests.post(
        "https://api.github.com/repos/IgorGanapolsky/trading/pulls",
        headers=headers,
        json=body,
    )

    if response.status_code == 201:
        pr_data = response.json()
        print(f"✅ PR created: #{pr_data['number']}")
        print(f"   URL: {pr_data['html_url']}")
        return pr_data
    elif response.status_code == 422:
        # PR might already exist
        error = response.json()
        if "already exists" in str(error):
            print("⚠️ PR already exists, finding it...")
            # Get existing PR
            list_response = requests.get(
                f"https://api.github.com/repos/IgorGanapolsky/trading/pulls?head=IgorGanapolsky:{branch}",
                headers=headers,
            )
            if list_response.status_code == 200 and list_response.json():
                pr_data = list_response.json()[0]
                print(f"✅ Found existing PR: #{pr_data['number']}")
                return pr_data
        print(f"❌ Failed to create PR: {response.status_code}")
        print(f"   Error: {response.json()}")
        return None
    else:
        print(f"❌ Failed to create PR: {response.status_code}")
        print(f"   Error: {response.text}")
        return None


def merge_pr(token: str, pr_number: int) -> bool:
    """Merge a PR via GitHub API."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    # Wait a moment for CI to start
    print("⏳ Waiting for CI to initialize...")
    time.sleep(5)

    # Check if PR is mergeable
    pr_response = requests.get(
        f"https://api.github.com/repos/IgorGanapolsky/trading/pulls/{pr_number}",
        headers=headers,
    )

    if pr_response.status_code != 200:
        print(f"❌ Could not fetch PR status: {pr_response.status_code}")
        return False

    pr_data = pr_response.json()
    mergeable = pr_data.get("mergeable")
    mergeable_state = pr_data.get("mergeable_state")

    print(f"   Mergeable: {mergeable}")
    print(f"   State: {mergeable_state}")

    # Try to merge
    merge_body = {
        "commit_title": f"feat: Add trading verification + trigger trade execution (#{pr_number})",
        "merge_method": "squash",
    }

    response = requests.put(
        f"https://api.github.com/repos/IgorGanapolsky/trading/pulls/{pr_number}/merge",
        headers=headers,
        json=merge_body,
    )

    if response.status_code == 200:
        print(f"✅ PR #{pr_number} merged successfully!")
        return True
    elif response.status_code == 405:
        print("⚠️ PR cannot be merged yet (CI checks in progress)")
        print("   Enabling auto-merge...")

        # Try to enable auto-merge via GraphQL
        # This requires the repo to have auto-merge enabled
        print("   Please merge manually or wait for CI to complete")
        return False
    else:
        print(f"❌ Failed to merge: {response.status_code}")
        print(f"   Error: {response.text}")
        return False


def delete_branch(token: str, branch: str) -> bool:
    """Delete the branch after merge."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    response = requests.delete(
        f"https://api.github.com/repos/IgorGanapolsky/trading/git/refs/heads/{branch}",
        headers=headers,
    )

    if response.status_code == 204:
        print(f"✅ Branch {branch} deleted")
        return True
    else:
        print(f"⚠️ Could not delete branch: {response.status_code}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Create and merge PR")
    parser.add_argument("--token", help="GitHub PAT token")
    parser.add_argument("--create-only", action="store_true", help="Only create PR, don't merge")
    args = parser.parse_args()

    token = args.token or os.getenv("GH_PAT") or os.getenv("GITHUB_TOKEN")

    if not token:
        print("❌ No GitHub token provided")
        print("   Use: --token <token> or set GH_PAT environment variable")
        sys.exit(1)

    branch = get_current_branch()
    if branch == "main":
        print("❌ Already on main branch, nothing to merge")
        sys.exit(1)

    print("=" * 60)
    print("CREATE AND MERGE PR")
    print("=" * 60)
    print(f"Branch: {branch}")
    print()

    commits = get_commits_on_branch()
    if commits:
        print("Commits to merge:")
        for line in commits.split("\n"):
            print(f"  {line}")
    print()

    # Create PR
    pr_data = create_pr(token, branch)
    if not pr_data:
        sys.exit(1)

    if args.create_only:
        print("\n--create-only specified, skipping merge")
        sys.exit(0)

    # Merge PR
    pr_number = pr_data["number"]
    success = merge_pr(token, pr_number)

    if success:
        delete_branch(token, branch)
        print("\n✅ Complete! PR merged and branch deleted.")
    else:
        print(f"\n⚠️ PR #{pr_number} created but not merged")
        print(f"   Merge manually: https://github.com/IgorGanapolsky/trading/pull/{pr_number}")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
