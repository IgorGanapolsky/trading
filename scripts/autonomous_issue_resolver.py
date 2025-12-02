#!/usr/bin/env python3
"""
Autonomous Issue Resolution Script

Monitors GitHub issues and autonomously resolves them using AI agents.
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.issue_resolution_agent import IssueResolutionAgent

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_github_issues(github_token: str, label: str = "trading-failure") -> list[dict[str, Any]]:
    """
    Get GitHub issues with specified label.

    Args:
        github_token: GitHub API token
        label: Label to filter by

    Returns:
        List of issue data
    """
    try:
        import requests

        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        url = "https://api.github.com/repos/IgorGanapolsky/trading/issues"
        params = {"state": "open", "labels": label, "per_page": 100}

        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        return response.json()
    except Exception as e:
        logger.error(f"Failed to fetch GitHub issues: {e}")
        return []


def update_issue(github_token: str, issue_number: int, comment: str, close: bool = False) -> bool:
    """
    Update GitHub issue with comment and optionally close it.

    Args:
        github_token: GitHub API token
        issue_number: Issue number
        comment: Comment to add
        close: Whether to close the issue

    Returns:
        True if successful
    """
    try:
        import requests

        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        # Add comment
        comment_url = (
            f"https://api.github.com/repos/IgorGanapolsky/trading/issues/{issue_number}/comments"
        )
        comment_data = {"body": comment}

        response = requests.post(comment_url, headers=headers, json=comment_data)
        response.raise_for_status()

        # Close issue if requested
        if close:
            close_url = f"https://api.github.com/repos/IgorGanapolsky/trading/issues/{issue_number}"
            close_data = {"state": "closed"}

            response = requests.patch(close_url, headers=headers, json=close_data)
            response.raise_for_status()

        return True
    except Exception as e:
        logger.error(f"Failed to update issue #{issue_number}: {e}")
        return False


def main():
    """Main autonomous issue resolution"""
    parser = argparse.ArgumentParser(description="Autonomous Issue Resolution")
    parser.add_argument(
        "--label",
        type=str,
        default="trading-failure",
        help="GitHub issue label to process (default: trading-failure)",
    )
    parser.add_argument(
        "--max-issues",
        type=int,
        default=10,
        help="Maximum issues to process (default: 10)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode (don't actually fix issues)",
    )

    args = parser.parse_args()

    print("=" * 80)
    print("🤖 AUTONOMOUS ISSUE RESOLUTION AGENT")
    print("=" * 80)
    print(f"Label: {args.label}")
    print(f"Max Issues: {args.max_issues}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print("=" * 80)

    # Get GitHub token
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        logger.error("GITHUB_TOKEN environment variable not set")
        print("\n❌ GITHUB_TOKEN not set - cannot access GitHub API")
        print("   Set it in GitHub Secrets or .env file")
        sys.exit(1)

    # Initialize resolution agent
    agent = IssueResolutionAgent()

    # Get issues
    print(f"\n🔍 Fetching issues with label '{args.label}'...")
    issues = get_github_issues(github_token, label=args.label)

    if not issues:
        print("✅ No open issues found")
        return 0

    print(f"📋 Found {len(issues)} open issues")

    # Process issues
    processed = 0
    resolved = 0
    failed = 0

    for issue in issues[: args.max_issues]:
        issue_number = issue["number"]
        issue_title = issue["title"]

        print(f"\n{'=' * 80}")
        print(f"Issue #{issue_number}: {issue_title}")
        print("=" * 80)

        # Diagnose and resolve
        result = agent.resolve_issue(issue)

        if result["success"]:
            resolved += 1
            print(f"✅ Issue #{issue_number} RESOLVED")

            if not args.dry_run:
                comment = f"""## 🤖 Autonomous Resolution Complete

**Status**: ✅ Auto-resolved

**Root Cause**: {result["diagnosis"]["root_cause"]}

**Fix Strategy**: {result["diagnosis"]["fix_strategy"]}

**Fix Steps Executed**:
{chr(10).join(f"- ✅ {step['step']}: {step.get('message', 'Completed')}" for step in result.get("fix_result", {}).get("fix_results", []))}

**Confidence**: {result["diagnosis"]["confidence"]:.0%}

This issue was automatically resolved by the AI Issue Resolution Agent.

---
*Resolved at: {datetime.now().isoformat()}*
"""
                update_issue(github_token, issue_number, comment, close=True)
        else:
            failed += 1
            print(f"⚠️  Issue #{issue_number} could not be auto-resolved")
            print(f"   Reason: {result.get('message', 'Unknown')}")

            if not args.dry_run and result.get("diagnosis", {}).get("root_cause"):
                comment = f"""## 🤖 Autonomous Diagnosis Complete

**Status**: ⚠️ Requires manual review

**Root Cause**: {result["diagnosis"]["root_cause"]}

**Fix Strategy**: {result["diagnosis"]["fix_strategy"]}

**Why Not Auto-Fixed**: {result.get("message", "Issue cannot be auto-fixed")}

**Recommended Actions**:
{chr(10).join(f"- {step}" for step in result.get("diagnosis", {}).get("fix_steps", []))}

---
*Diagnosed at: {datetime.now().isoformat()}*
"""
                update_issue(github_token, issue_number, comment, close=False)

        processed += 1

    # Summary
    print("\n" + "=" * 80)
    print("📊 RESOLUTION SUMMARY")
    print("=" * 80)
    print(f"Processed: {processed}")
    print(f"Resolved: {resolved}")
    print(f"Failed/Manual: {failed}")
    print("=" * 80)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
