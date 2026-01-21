#!/usr/bin/env python3
"""
GitHub API-based data sync utility.

Syncs data files to GitHub using the Contents API, bypassing git conflicts entirely.
This ensures trading data always gets synced even during concurrent PR merges.

Usage:
    python3 scripts/sync_data_to_github.py --file data/trades_2026-01-06.json
    python3 scripts/sync_data_to_github.py --file data/system_state.json
    python3 scripts/sync_data_to_github.py --all-data  # Syncs all data/*.json files
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

GITHUB_API = "https://api.github.com"
REPO_OWNER = "IgorGanapolsky"
REPO_NAME = "trading"
MAX_RETRIES = 4
BACKOFF_SECONDS = [2, 4, 8, 16]


def get_github_token() -> str:
    """Get GitHub token from environment."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("ERROR: GITHUB_TOKEN or GH_TOKEN environment variable not set")
        sys.exit(1)
    return token


def api_request(
    method: str, endpoint: str, token: str, data: Optional[dict] = None
) -> tuple[int, dict]:
    """Make a GitHub API request with retry logic."""
    url = f"{GITHUB_API}{endpoint}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "trading-bot-sync",
    }

    for attempt, backoff in enumerate(BACKOFF_SECONDS, 1):
        try:
            req = urllib.request.Request(url, headers=headers, method=method)
            if data:
                req.data = json.dumps(data).encode("utf-8")
                req.add_header("Content-Type", "application/json")

            with urllib.request.urlopen(req, timeout=30) as response:
                body = response.read().decode("utf-8")
                return response.status, json.loads(body) if body else {}

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            try:
                error_data = json.loads(body)
            except json.JSONDecodeError:
                error_data = {"message": body}

            # Don't retry on 4xx errors (except 409 conflict)
            if 400 <= e.code < 500 and e.code != 409:
                return e.code, error_data

            print(f"  Attempt {attempt}/{MAX_RETRIES} failed: HTTP {e.code}")
            if attempt < MAX_RETRIES:
                print(f"  Retrying in {backoff}s...")
                time.sleep(backoff)
            else:
                return e.code, error_data

        except (urllib.error.URLError, TimeoutError) as e:
            print(f"  Attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                print(f"  Retrying in {backoff}s...")
                time.sleep(backoff)
            else:
                return 0, {"message": str(e)}

    return 0, {"message": "Max retries exceeded"}


def get_file_sha(path: str, token: str) -> Optional[str]:
    """Get the current SHA of a file on GitHub (needed for updates)."""
    endpoint = f"/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}"
    status, data = api_request("GET", endpoint, token)

    if status == 200:
        return data.get("sha")
    elif status == 404:
        return None  # File doesn't exist yet
    else:
        print(f"  Warning: Could not get SHA for {path}: {data.get('message', 'Unknown error')}")
        return None


def sync_file(local_path: str, token: str, commit_message: Optional[str] = None) -> bool:
    """
    Sync a local file to GitHub using the Contents API.

    This is an atomic operation that bypasses git conflicts.
    """
    path = Path(local_path)
    if not path.exists():
        print(f"ERROR: Local file not found: {local_path}")
        return False

    # Read and encode file content
    content = path.read_bytes()
    content_b64 = base64.b64encode(content).decode("utf-8")

    # Get relative path for GitHub
    repo_root = Path(__file__).parent.parent
    try:
        rel_path = path.relative_to(repo_root)
    except ValueError:
        rel_path = path
    github_path = str(rel_path)

    print(f"Syncing: {github_path}")

    # Get current SHA if file exists
    sha = get_file_sha(github_path, token)

    # Prepare request data
    if not commit_message:
        commit_message = f"chore: Auto-sync {path.name} via API"

    data = {
        "message": commit_message,
        "content": content_b64,
        "branch": "main",
    }
    if sha:
        data["sha"] = sha
        print(f"  Updating existing file (SHA: {sha[:7]})")
    else:
        print("  Creating new file")

    # Make the API call
    endpoint = f"/repos/{REPO_OWNER}/{REPO_NAME}/contents/{github_path}"
    status, response = api_request("PUT", endpoint, token, data)

    if status in (200, 201):
        commit_sha = response.get("commit", {}).get("sha", "unknown")[:7]
        print(f"  ✅ Synced successfully (commit: {commit_sha})")
        return True
    elif status == 409:
        # Conflict - file was modified. Retry with fresh SHA.
        print("  ⚠️  Conflict detected, retrying with fresh SHA...")
        sha = get_file_sha(github_path, token)
        if sha:
            data["sha"] = sha
            status, response = api_request("PUT", endpoint, token, data)
            if status in (200, 201):
                commit_sha = response.get("commit", {}).get("sha", "unknown")[:7]
                print(f"  ✅ Synced successfully after conflict resolution (commit: {commit_sha})")
                return True
        print(f"  ❌ Failed to resolve conflict: {response.get('message', 'Unknown error')}")
        return False
    else:
        print(f"  ❌ Sync failed: HTTP {status} - {response.get('message', 'Unknown error')}")
        return False


def sync_all_data_files(token: str) -> tuple[int, int]:
    """Sync all JSON files in the data directory."""
    data_dir = Path(__file__).parent.parent / "data"
    if not data_dir.exists():
        print(f"ERROR: Data directory not found: {data_dir}")
        return 0, 0

    # Find all JSON files (including subdirectories)
    json_files = list(data_dir.glob("*.json"))

    # Priority files first
    priority_files = ["system_state.json", "performance_log.json"]
    priority_paths = [data_dir / f for f in priority_files if (data_dir / f).exists()]
    other_paths = [f for f in json_files if f not in priority_paths]

    all_files = priority_paths + other_paths

    if not all_files:
        print("No JSON files found in data directory")
        return 0, 0

    print(f"Found {len(all_files)} data files to sync\n")

    success = 0
    failed = 0

    for file_path in all_files:
        if sync_file(str(file_path), token):
            success += 1
        else:
            failed += 1
        print()  # Blank line between files

    return success, failed


def main():
    parser = argparse.ArgumentParser(
        description="Sync data files to GitHub using API (bypasses git conflicts)"
    )
    parser.add_argument("--file", "-f", help="Path to specific file to sync")
    parser.add_argument(
        "--all-data", "-a", action="store_true", help="Sync all JSON files in data directory"
    )
    parser.add_argument("--message", "-m", help="Custom commit message")

    args = parser.parse_args()

    if not args.file and not args.all_data:
        parser.error("Either --file or --all-data must be specified")

    token = get_github_token()

    print("=" * 60)
    print("GitHub API Data Sync")
    print("=" * 60)
    print(f"Repository: {REPO_OWNER}/{REPO_NAME}")
    print("Branch: main")
    print(f"Max retries: {MAX_RETRIES}")
    print("=" * 60)
    print()

    if args.all_data:
        success, failed = sync_all_data_files(token)
        print("=" * 60)
        print(f"Summary: {success} synced, {failed} failed")
        print("=" * 60)
        sys.exit(0 if failed == 0 else 1)
    else:
        success = sync_file(args.file, token, args.message)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
