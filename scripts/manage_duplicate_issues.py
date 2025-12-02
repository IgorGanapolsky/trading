#!/usr/bin/env python3
"""
Manage Duplicate GitHub Issues

Detects and closes duplicate issues to prevent issue spam.
"""

import json
import subprocess
import sys


def run_gh_command(cmd: str) -> tuple[str, int]:
    """Run GitHub CLI command and return output."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=False)
        return result.stdout.strip(), result.returncode
    except Exception as e:
        return str(e), 1


def get_open_issues() -> list[dict]:
    """Get all open issues."""
    stdout, code = run_gh_command(
        "gh issue list --state open --json number,title,body,createdAt,labels"
    )
    if code != 0:
        print(f"❌ Failed to fetch issues: {stdout}")
        return []

    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        print("❌ Failed to parse issues JSON")
        return []


def find_duplicates(issues: list[dict]) -> list[list[dict]]:
    """Find duplicate issues based on title similarity."""
    duplicates = []
    processed = set()

    # Keywords that indicate similar issues
    keywords_sets = [
        {"workflow", "disabled", "enable"},
        {"workflow", "disabled", "re-enable"},
        {"trading", "failed", "execution"},
        {"github", "actions", "workflow"},
    ]

    for i, issue1 in enumerate(issues):
        if i in processed:
            continue

        title1_lower = issue1["title"].lower()
        body1_lower = issue1.get("body", "").lower()

        # Check for keyword matches
        for keyword_set in keywords_sets:
            if all(kw in title1_lower or kw in body1_lower for kw in keyword_set):
                # Found potential duplicate group
                group = [issue1]
                processed.add(i)

                for j, issue2 in enumerate(issues[i + 1 :], start=i + 1):
                    if j in processed:
                        continue

                    title2_lower = issue2["title"].lower()
                    body2_lower = issue2.get("body", "").lower()

                    # Check if similar
                    if all(kw in title2_lower or kw in body2_lower for kw in keyword_set):
                        # Check title similarity (simple word overlap)
                        words1 = set(title1_lower.split())
                        words2 = set(title2_lower.split())
                        overlap = len(words1 & words2) / max(len(words1), len(words2))

                        if overlap > 0.5:  # 50% word overlap
                            group.append(issue2)
                            processed.add(j)

                if len(group) > 1:
                    duplicates.append(group)
                break

    return duplicates


def close_duplicate_issues(duplicates: list[list[dict]], dry_run: bool = True):
    """Close duplicate issues, keeping the oldest one open."""
    for group in duplicates:
        if len(group) < 2:
            continue

        # Sort by creation date (oldest first)
        group.sort(key=lambda x: x["createdAt"])

        # Keep oldest open, close others
        keep_open = group[0]
        to_close = group[1:]

        print("\n📋 Duplicate Group Found:")
        print(f"   Keep open: #{keep_open['number']} - {keep_open['title']}")

        for issue in to_close:
            comment = (
                f"🔗 Duplicate of #{keep_open['number']}\n\n"
                f"This issue is a duplicate and has been closed. "
                f"Please refer to issue #{keep_open['number']} for updates.\n\n"
                f"*Closed automatically by duplicate issue detection.*"
            )

            if dry_run:
                print(f"   Would close: #{issue['number']} - {issue['title']}")
                print(f"   Would add comment: {comment[:100]}...")
            else:
                # Add comment first
                run_gh_command(f"gh issue comment {issue['number']} --body '{comment}'")

                # Close issue
                run_gh_command(f"gh issue close {issue['number']} --comment '{comment}'")
                print(f"   ✅ Closed: #{issue['number']}")


def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(description="Manage duplicate GitHub issues")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually closing issues",
    )
    parser.add_argument(
        "--auto-close",
        action="store_true",
        help="Actually close duplicate issues (use with caution)",
    )
    args = parser.parse_args()

    if not args.dry_run and not args.auto_close:
        print("❌ Error: Must specify --dry-run or --auto-close")
        print("   Use --dry-run to preview changes")
        print("   Use --auto-close to actually close duplicates")
        sys.exit(1)

    print("=" * 80)
    print("🔍 DUPLICATE ISSUE DETECTION")
    print("=" * 80)

    # Check if gh CLI is available
    stdout, code = run_gh_command("which gh")
    if code != 0:
        print("❌ GitHub CLI (gh) not found")
        print("   Install: brew install gh")
        sys.exit(1)

    # Get open issues
    print("\n📋 Fetching open issues...")
    issues = get_open_issues()
    print(f"   Found {len(issues)} open issues")

    if len(issues) < 2:
        print("✅ No duplicates possible (less than 2 issues)")
        return

    # Find duplicates
    print("\n🔍 Detecting duplicates...")
    duplicates = find_duplicates(issues)

    if not duplicates:
        print("✅ No duplicates found")
        return

    print(f"\n🚨 Found {len(duplicates)} duplicate group(s)")

    # Show duplicates
    total_to_close = sum(len(group) - 1 for group in duplicates)
    print(f"   Total issues to close: {total_to_close}")

    # Close duplicates
    close_duplicate_issues(duplicates, dry_run=args.dry_run)

    print("\n" + "=" * 80)
    if args.dry_run:
        print("💡 This was a dry run. Use --auto-close to actually close duplicates.")
    else:
        print("✅ Duplicate issues closed")
    print("=" * 80)


if __name__ == "__main__":
    main()
