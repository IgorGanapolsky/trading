#!/usr/bin/env python3
"""
Setup GitHub branch protection rules.

This script configures branch protection to prevent the Dec 11 incident
where broken code was merged to main.

Usage:
    export GITHUB_TOKEN="your_pat_here"
    python3 scripts/setup_branch_protection.py

Requirements:
    - GitHub PAT with 'repo' scope
    - Admin access to the repository
"""

import json
import os
import sys

try:
    import requests
except ImportError:
    print("Installing requests...")
    os.system("pip install requests -q")
    import requests


def setup_branch_protection():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("❌ GITHUB_TOKEN environment variable not set")
        print("   Run: export GITHUB_TOKEN='your_pat_here'")
        sys.exit(1)

    owner = "IgorGanapolsky"
    repo = "trading"
    branch = "main"

    url = f"https://api.github.com/repos/{owner}/{repo}/branches/{branch}/protection"

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    # Branch protection rules
    protection_rules = {
        "required_status_checks": {
            "strict": True,  # Require branches to be up to date
            "contexts": [
                "Lint & Format",
                "Syntax & Import Verification",  # Our new check
            ],
        },
        "enforce_admins": False,  # Allow admins to bypass (for emergencies)
        "required_pull_request_reviews": None,  # Not requiring reviews (agents work autonomously)
        "restrictions": None,  # No push restrictions
        "required_linear_history": False,
        "allow_force_pushes": False,
        "allow_deletions": False,
    }

    print(f"Setting up branch protection for {owner}/{repo}:{branch}...")
    print(f"Rules: {json.dumps(protection_rules, indent=2)}")
    print()

    response = requests.put(url, headers=headers, json=protection_rules)

    if response.status_code == 200:
        print("✅ Branch protection configured successfully!")
        print()
        print("Protected checks:")
        for ctx in protection_rules["required_status_checks"]["contexts"]:
            print(f"  - {ctx}")
    elif response.status_code == 404:
        print("❌ Repository or branch not found")
        print("   Make sure you have admin access")
    elif response.status_code == 403:
        print("❌ Permission denied")
        print("   Your PAT needs 'repo' scope and admin access")
    else:
        print(f"❌ Failed with status {response.status_code}")
        print(f"   Response: {response.text}")

    return response.status_code == 200


if __name__ == "__main__":
    setup_branch_protection()
