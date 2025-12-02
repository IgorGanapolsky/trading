#!/usr/bin/env python3
"""
Check GitHub Actions Workflow Status

Diagnoses workflow issues and provides actionable fixes.
"""

import json
import subprocess


def run_command(cmd):
    """Run shell command and return output."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip(), result.returncode
    except Exception as e:
        return str(e), 1


def check_workflow_status():
    """Check workflow status and diagnose issues."""
    print("=" * 80)
    print("🔍 GITHUB ACTIONS WORKFLOW STATUS CHECK")
    print("=" * 80)

    # Check if gh CLI is available
    stdout, code = run_command("which gh")
    if code != 0:
        print("\n❌ GitHub CLI (gh) not found")
        print("   Install: brew install gh")
        return

    # Check workflow list
    print("\n📋 Workflow Status:")
    stdout, code = run_command("gh workflow list")
    if code == 0:
        print(stdout)
    else:
        print(f"⚠️  Could not list workflows: {stdout}")

    # Check recent runs
    print("\n📊 Recent Runs:")
    stdout, code = run_command("gh run list --workflow=daily-trading.yml --limit 5")
    if code == 0:
        print(stdout)
    else:
        print(f"⚠️  Could not list runs: {stdout}")

    # Check last run details
    print("\n🔍 Last Run Details:")
    stdout, code = run_command(
        "gh run list --workflow=daily-trading.yml --limit 1 --json conclusion,createdAt,displayTitle"
    )
    if code == 0:
        try:
            runs = json.loads(stdout)
            if runs:
                run = runs[0]
                conclusion = run.get("conclusion", "unknown")
                created = run.get("createdAt", "unknown")
                title = run.get("displayTitle", "unknown")

                print(f"  Conclusion: {conclusion}")
                print(f"  Created: {created}")
                print(f"  Title: {title}")

                if conclusion == "failure":
                    print("\n❌ Last run FAILED")
                    print("   Check logs: gh run view <run-id> --log")
                elif conclusion == "success":
                    print("\n✅ Last run SUCCEEDED")
                elif conclusion == "cancelled":
                    print("\n⚠️  Last run CANCELLED")
            else:
                print("  No runs found")
        except Exception as e:
            print(f"  Could not parse run data: {e}")

    # Recommendations
    print("\n" + "=" * 80)
    print("💡 RECOMMENDATIONS")
    print("=" * 80)

    print("\n1. Check Workflow Status:")
    print("   Visit: https://github.com/IgorGanapolsky/trading/actions/workflows/daily-trading.yml")
    print("   Look for yellow 'disabled' banner")

    print("\n2. If Disabled:")
    print("   Click 'Enable workflow' button")

    print("\n3. Trigger Manual Run:")
    print("   Click 'Run workflow' button")
    print("   Or: gh workflow run daily-trading.yml")

    print("\n4. Check Recent Failures:")
    print("   gh run list --workflow=daily-trading.yml --limit 5")
    print("   gh run view <run-id> --log")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    check_workflow_status()
