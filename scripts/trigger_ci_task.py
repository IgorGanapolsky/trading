#!/usr/bin/env python3
"""
Trigger CI Tasks from Sandbox

CEO Directive (Jan 7, 2026): "Don't tell me sandbox can't do it, create CI workflows"

This script allows Claude to trigger GitHub Actions workflows from the sandbox
to accomplish tasks that cannot be done locally (tests, RAG sync, etc.)

Usage:
    python3 scripts/trigger_ci_task.py --task run-tests
    python3 scripts/trigger_ci_task.py --task verify-rag
    python3 scripts/trigger_ci_task.py --task sync-trades-to-rag
    python3 scripts/trigger_ci_task.py --task system-health-check

Or via curl:
    curl -X POST \
      -H "Authorization: token $GITHUB_TOKEN" \
      -H "Accept: application/vnd.github.v3+json" \
      https://api.github.com/repos/IgorGanapolsky/trading/actions/workflows/claude-agent-utility.yml/dispatches \
      -d '{"ref":"main","inputs":{"task":"run-tests"}}'
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

# Configuration
REPO_OWNER = "IgorGanapolsky"
REPO_NAME = "trading"
WORKFLOW_FILE = "claude-agent-utility.yml"

VALID_TASKS = [
    "run-tests",
    "run-lint",
    "verify-rag",
    "sync-trades-to-rag",
    "system-health-check",
    "verify-chromadb",
    "dry-run-trading",
    "deploy-webhook",
    "set-trailing-stops",
    "manage-positions",
    "custom-command",
]


def get_github_token() -> str | None:
    """Get GitHub token from environment."""
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def trigger_workflow(
    task: str,
    token: str,
    ref: str = "main",
    custom_command: str = "",
    test_pattern: str = "tests/",
    verbose: bool = True,
) -> dict:
    """Trigger the claude-agent-utility workflow via GitHub API."""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/workflows/{WORKFLOW_FILE}/dispatches"

    payload = {
        "ref": ref,
        "inputs": {
            "task": task,
            "custom_command": custom_command,
            "test_pattern": test_pattern,
            "verbose": str(verbose).lower(),
        },
    }

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=30) as response:  # noqa: S310
            # 204 No Content is success for this endpoint
            return {"success": True, "status": response.status}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        return {"success": False, "status": e.code, "error": error_body}
    except urllib.error.URLError as e:
        return {"success": False, "error": str(e)}


def get_latest_run(token: str, wait_for_new: bool = True) -> dict | None:
    """Get the latest workflow run status."""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/workflows/{WORKFLOW_FILE}/runs?per_page=1"

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=30) as response:  # noqa: S310
            data = json.loads(response.read().decode("utf-8"))
            runs = data.get("workflow_runs", [])
            if runs:
                return runs[0]
    except Exception as e:
        print(f"Error fetching run status: {e}")

    return None


def wait_for_completion(token: str, timeout: int = 600) -> dict:
    """Wait for the triggered workflow to complete."""
    print("Waiting for workflow to start...")
    time.sleep(5)  # Give it time to start

    start_time = time.time()
    last_status = None

    while time.time() - start_time < timeout:
        run = get_latest_run(token)
        if run:
            status = run.get("status")
            conclusion = run.get("conclusion")

            if status != last_status:
                print(f"  Status: {status} | Conclusion: {conclusion or 'pending'}")
                last_status = status

            if status == "completed":
                return {
                    "completed": True,
                    "conclusion": conclusion,
                    "run_id": run.get("id"),
                    "html_url": run.get("html_url"),
                }

        time.sleep(10)

    return {"completed": False, "error": "Timeout waiting for completion"}


def main():
    parser = argparse.ArgumentParser(
        description="Trigger CI tasks from sandbox",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--task",
        required=True,
        choices=VALID_TASKS,
        help="Task to execute",
    )
    parser.add_argument(
        "--token",
        help="GitHub token (or set GITHUB_TOKEN env var)",
    )
    parser.add_argument(
        "--ref",
        default="main",
        help="Git ref to run on (default: main)",
    )
    parser.add_argument(
        "--custom-command",
        default="",
        help="Custom Python command (for custom-command task)",
    )
    parser.add_argument(
        "--test-pattern",
        default="tests/",
        help="Test pattern for pytest (default: tests/)",
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for workflow completion",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Timeout in seconds when waiting (default: 600)",
    )

    args = parser.parse_args()

    # Get token
    token = args.token or get_github_token()
    if not token:
        print("Error: GitHub token required. Set GITHUB_TOKEN or use --token")
        sys.exit(1)

    print(f"Triggering task: {args.task}")
    print(f"Repository: {REPO_OWNER}/{REPO_NAME}")
    print(f"Ref: {args.ref}")

    # Trigger workflow
    result = trigger_workflow(
        task=args.task,
        token=token,
        ref=args.ref,
        custom_command=args.custom_command,
        test_pattern=args.test_pattern,
    )

    if result.get("success"):
        print(f"Workflow triggered successfully (HTTP {result.get('status', 204)})")

        if args.wait:
            print("\nWaiting for completion...")
            completion = wait_for_completion(token, args.timeout)

            if completion.get("completed"):
                conclusion = completion.get("conclusion")
                print(f"\nWorkflow completed: {conclusion}")
                print(f"Run URL: {completion.get('html_url')}")
                sys.exit(0 if conclusion == "success" else 1)
            else:
                print(f"\nWorkflow did not complete: {completion.get('error')}")
                sys.exit(1)
        else:
            print("\nTo monitor progress:")
            print(f"  https://github.com/{REPO_OWNER}/{REPO_NAME}/actions")
    else:
        print(f"Failed to trigger workflow: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
