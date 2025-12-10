#!/usr/bin/env python3
"""
Agentic PR Reviewer and Merger

This script autonomously reviews and merges open Pull Requests using the PRAgent logic.
It is designed to clear the backlog of low-risk PRs.
"""

import json
import logging
import os
import subprocess
import sys

# Ensure src is in path
sys.path.append(os.getcwd())

from src.agents.pr_agent import PRAgent

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_open_prs() -> list[dict]:
    """Fetch open PRs using gh cli."""
    cmd = [
        "gh",
        "pr",
        "list",
        "--state",
        "open",
        "--json",
        "number,title,body,files",
        "--limit",
        "100",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to fetch PRs: {e}")
        return []


def get_pr_files(pr_number: int) -> list[str]:
    """Fetch files changed in a PR."""
    cmd = ["gh", "pr", "view", str(pr_number), "--json", "files"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        return [f["path"] for f in data.get("files", [])]
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to fetch files for PR #{pr_number}: {e}")
        return []


def merge_pr(pr_number: int, method: str = "squash"):
    """Merge a PR."""
    cmd = ["gh", "pr", "merge", str(pr_number), f"--{method}", "--auto", "--delete-branch"]
    try:
        subprocess.run(cmd, check=True)
        logger.info(f"✅ Successfully merged PR #{pr_number}")
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Failed to merge PR #{pr_number}: {e}")


def main():
    logger.info("🤖 Starting Agentic PR Review...")

    agent = PRAgent()
    prs = get_open_prs()

    if not prs:
        logger.info("No open PRs found.")
        return

    logger.info(f"Found {len(prs)} open PRs.")

    for pr in prs:
        pr_number = pr["number"]
        title = pr["title"]
        body = pr["body"]

        logger.info(f"\nAnalyzing PR #{pr_number}: {title}")

        # Get real files for better risk assessment
        files = get_pr_files(pr_number)

        analysis_data = {"title": title, "body": body, "files": files}

        # Ask the agent
        result = agent.analyze(analysis_data)

        action = result.get("action")
        risk_score = result.get("risk_score")
        comment = result.get("comment")

        logger.info(f"  Risk Score: {risk_score}/100")
        logger.info(f"  Agent Verdict: {action}")

        if action == "APPROVE":
            logger.info("  🚀 Auto-merging low-risk PR...")
            # First approve
            subprocess.run(
                [
                    "gh",
                    "pr",
                    "review",
                    str(pr_number),
                    "--approve",
                    "--body",
                    f"{comment}\n\n*Risk Score: {risk_score}*",
                ]
            )
            # Then merge
            merge_pr(pr_number)
        elif action == "COMMENT":
            logger.info("  ⚠️ Posting comment (Medium Risk)...")
            subprocess.run(
                [
                    "gh",
                    "pr",
                    "comment",
                    str(pr_number),
                    "--body",
                    f"{comment}\n\n*Risk Score: {risk_score}*",
                ]
            )
        else:
            logger.info("  🛑 Skipping (High Risk)")


if __name__ == "__main__":
    main()
