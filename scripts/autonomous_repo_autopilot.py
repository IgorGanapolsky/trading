#!/usr/bin/env python3
"""
Autonomous Repo Autopilot & System Hygiene Daemon.

Autonomously manages open PRs, auto-approves passing state sync PRs
(Alpaca state, premarket data, put-credit trade ledgers, arXiv ingest),
prunes superseded duplicate sync branches, and enforces branch hygiene
without requiring manual operator intervention.

Usage:
    python3 scripts/autonomous_repo_autopilot.py --once
    python3 scripts/autonomous_repo_autopilot.py --daemon --interval 300
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import time
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("autonomous_autopilot")

AUTO_LAND_PREFIX = "chore/auto-"
SLUG_REGEX = re.compile(r"^chore/auto-([a-zA-Z0-9_-]+?)-\d+-\d+$")


def run_cmd(
    cmd: list[str], check: bool = False, capture_output: bool = True
) -> subprocess.CompletedProcess[str]:
    """Execute a CLI command with environment preservation."""
    env = os.environ.copy()
    env["PAGER"] = "cat"
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture_output,
        text=True,
        env=env,
    )


def extract_slug(branch: str) -> str:
    """Extract sync slug from branch name (e.g. chore/auto-alpaca-sync-123-1 -> alpaca-sync)."""
    match = SLUG_REGEX.match(branch)
    if match:
        return match.group(1)
    if branch.startswith(AUTO_LAND_PREFIX):
        parts = branch[len(AUTO_LAND_PREFIX) :].split("-")
        return parts[0] if parts else "unknown"
    return "unknown"


def list_open_prs() -> list[dict[str, Any]]:
    """List open pull requests with metadata and status checks."""
    cmd = [
        "gh",
        "pr",
        "list",
        "--state",
        "open",
        "--limit",
        "200",
        "--json",
        "number,title,headRefName,author,statusCheckRollup,mergeable,reviewDecision,createdAt",
    ]
    proc = run_cmd(cmd)
    if proc.returncode != 0:
        logger.error(f"Failed to list PRs: {proc.stderr}")
        return []
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        logger.error("Failed to parse gh pr list JSON output")
        return []


def are_checks_passing(checks: list[dict[str, Any]]) -> bool:
    """Return True if all checks in statusCheckRollup are completed successfully or skipped."""
    if not checks:
        return False
    for check in checks:
        # CheckRun vs StatusContext
        conclusion = check.get("conclusion")
        status = check.get("status")
        state = check.get("state")  # StatusContext

        if status and status != "COMPLETED":
            return False
        if state and state != "SUCCESS":
            return False
        if conclusion and conclusion not in {"SUCCESS", "SKIPPED", "NEUTRAL"}:
            return False
    return True


def close_superseded_pr(pr_number: int, slug: str, newest_pr_number: int) -> bool:
    """Close an obsolete superseded automated sync PR."""
    logger.info(
        f"Closing superseded PR #{pr_number} (slug: {slug}) in favor of #{newest_pr_number}"
    )
    cmd = [
        "gh",
        "pr",
        "close",
        str(pr_number),
        "--comment",
        f"Superseded by newer automated {slug} sync PR #{newest_pr_number}",
        "--delete-branch",
    ]
    proc = run_cmd(cmd)
    return proc.returncode == 0


def approve_pr(pr_number: int) -> bool:
    """Submit code-owner approval review as IgorGanapolsky."""
    logger.info(f"Submitting codeowner approval for PR #{pr_number}")
    cmd = [
        "gh",
        "pr",
        "review",
        str(pr_number),
        "--approve",
        "--body",
        "Auto-approved automated state sync via autonomous repo autopilot.",
    ]
    proc = run_cmd(cmd)
    return proc.returncode == 0


def merge_pr(pr_number: int) -> bool:
    """Squash merge the pull request and delete remote branch."""
    logger.info(f"Squash-merging PR #{pr_number}")
    cmd = ["gh", "pr", "merge", str(pr_number), "--squash", "--delete-branch"]
    proc = run_cmd(cmd)
    if proc.returncode == 0:
        logger.info(f"Successfully merged PR #{pr_number}")
        return True
    logger.warning(f"Failed to merge PR #{pr_number}: {proc.stderr.strip()}")
    stderr_lower = proc.stderr.lower()
    if (
        "not up to date" in stderr_lower
        or "out of date" in stderr_lower
        or "base branch policy" in stderr_lower
    ):
        logger.info(f"Attempting gh pr update-branch for #{pr_number}")
        run_cmd(["gh", "pr", "update-branch", str(pr_number)])
    return False


def run_cycle() -> dict[str, Any]:
    """Execute a single PR triage and hygiene cycle."""
    prs = list_open_prs()
    logger.info(f"Scanned {len(prs)} open pull requests")

    auto_prs_by_slug: dict[str, list[dict[str, Any]]] = {}
    for pr in prs:
        branch = pr.get("headRefName", "")
        title = pr.get("title", "")
        if branch.startswith(AUTO_LAND_PREFIX) and "[auto]" in title.lower():
            slug = extract_slug(branch)
            auto_prs_by_slug.setdefault(slug, []).append(pr)

    closed_count = 0
    merged_count = 0

    for slug, pr_list in auto_prs_by_slug.items():
        # Sort by creation date descending (newest first)
        pr_list.sort(key=lambda p: p.get("createdAt", ""), reverse=True)
        newest = pr_list[0]
        superseded = pr_list[1:]

        for old_pr in superseded:
            if close_superseded_pr(old_pr["number"], slug, newest["number"]):
                closed_count += 1

        # Evaluate the newest PR
        checks = newest.get("statusCheckRollup", [])
        if are_checks_passing(checks):
            num = newest["number"]
            if newest.get("reviewDecision") != "APPROVED":
                approve_pr(num)
            if merge_pr(num):
                merged_count += 1

    summary = {
        "open_prs_scanned": len(prs),
        "auto_slugs": list(auto_prs_by_slug.keys()),
        "superseded_closed": closed_count,
        "auto_merged": merged_count,
    }
    logger.info(f"Cycle complete: {summary}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Autonomous Repo Autopilot")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--daemon", action="store_true", help="Run continuously in background")
    parser.add_argument(
        "--interval", type=int, default=300, help="Poll interval in seconds (default: 300)"
    )
    args = parser.parse_args()

    if args.daemon:
        logger.info(f"Starting autonomous repo autopilot daemon (interval: {args.interval}s)")
        try:
            while True:
                run_cycle()
                time.sleep(args.interval)
        except KeyboardInterrupt:
            logger.info("Daemon stopped by user")
    else:
        run_cycle()


if __name__ == "__main__":
    main()
