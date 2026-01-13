#!/usr/bin/env python3
"""
Backfill blog posts from git commit history.

Creates summary posts for days before RAG was implemented (Days 1-72).
"""

import subprocess
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

BLOG_POSTS_DIR = Path(__file__).parent.parent / "docs" / "_posts"
START_DATE = datetime(2025, 10, 29)  # Day 1


def get_commits_by_date() -> dict[str, list[str]]:
    """Get all commits grouped by date."""
    commits_by_date = defaultdict(list)

    # Get all commits with date and message
    result = subprocess.run(
        ["git", "log", "--pretty=format:%ad|%s", "--date=short", "--all"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
    )

    if result.returncode != 0:
        print(f"Git error: {result.stderr}")
        return {}

    for line in result.stdout.strip().split("\n"):
        if "|" in line:
            date_str, message = line.split("|", 1)
            commits_by_date[date_str].append(message)

    return commits_by_date


def categorize_commit(message: str) -> str:
    """Categorize a commit message."""
    msg_lower = message.lower()

    if any(x in msg_lower for x in ["fix", "bug", "error", "broken"]):
        return "Bug Fixes"
    elif any(x in msg_lower for x in ["feat", "add", "implement", "new"]):
        return "Features"
    elif any(x in msg_lower for x in ["test", "spec"]):
        return "Testing"
    elif any(x in msg_lower for x in ["doc", "readme", "comment"]):
        return "Documentation"
    elif any(x in msg_lower for x in ["refactor", "clean", "improve"]):
        return "Improvements"
    elif any(x in msg_lower for x in ["ci", "workflow", "deploy", "build"]):
        return "CI/CD"
    elif any(x in msg_lower for x in ["trade", "strategy", "options", "alpaca"]):
        return "Trading"
    else:
        return "Other"


def generate_historical_post(date_str: str, commits: list[str], day_num: int) -> str:
    """Generate a blog post from commits."""
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    formatted_date = date_obj.strftime("%B %d, %Y")
    day_of_week = date_obj.strftime("%A")

    # Categorize commits
    by_category = defaultdict(list)
    for commit in commits:
        cat = categorize_commit(commit)
        by_category[cat].append(commit)

    # Build content
    commits_md = ""
    for category in ["Features", "Trading", "Bug Fixes", "Testing", "CI/CD", "Improvements", "Documentation", "Other"]:
        if category in by_category:
            commits_md += f"\n### {category}\n\n"
            for commit in by_category[category][:10]:  # Limit per category
                # Clean up commit message
                clean = commit.strip()
                if len(clean) > 100:
                    clean = clean[:100] + "..."
                commits_md += f"- {clean}\n"

    # Determine phase
    if day_num <= 30:
        phase = "Foundation Building"
    elif day_num <= 60:
        phase = "Strategy Development"
    else:
        phase = "Optimization & Testing"

    post = f"""---
layout: post
title: "Day {day_num}: {len(commits)} Commits - {formatted_date}"
date: {date_str}
day_number: {day_num}
commits_count: {len(commits)}
phase: "{phase}"
---

# Day {day_num}/90 - {day_of_week}, {formatted_date}

**Phase**: {phase}

## Summary

| Metric | Value |
|--------|-------|
| Commits | {len(commits)} |
| Categories | {len(by_category)} |

---

## Development Activity
{commits_md}
---

*Reconstructed from git history | [View Source](https://github.com/IgorGanapolsky/trading)*

*Note: This post was backfilled from git commits. Detailed lessons were not recorded for this day.*
"""
    return post


def backfill():
    """Main backfill function."""
    print("=" * 70)
    print("BACKFILLING BLOG FROM GIT HISTORY")
    print("=" * 70)

    BLOG_POSTS_DIR.mkdir(parents=True, exist_ok=True)

    commits_by_date = get_commits_by_date()
    print(f"Found commits for {len(commits_by_date)} dates")

    # Filter to dates in our project range (Oct 29, 2025 to Jan 11, 2026)
    end_date = datetime(2026, 1, 11)  # Day before RAG started

    created = 0
    skipped = 0

    current = START_DATE
    while current <= end_date:
        date_str = current.strftime("%Y-%m-%d")
        day_num = (current - START_DATE).days + 1

        filename = f"{date_str}-daily-activity.md"
        filepath = BLOG_POSTS_DIR / filename

        # Skip if already exists
        if filepath.exists():
            print(f"  SKIP {date_str} (Day {day_num}) - already exists")
            skipped += 1
            current += timedelta(days=1)
            continue

        commits = commits_by_date.get(date_str, [])

        if commits:
            post_content = generate_historical_post(date_str, commits, day_num)
            filepath.write_text(post_content)
            print(f"  CREATE {date_str} (Day {day_num}) - {len(commits)} commits")
            created += 1
        else:
            # Create placeholder for days with no commits
            post_content = f"""---
layout: post
title: "Day {day_num}: No Activity - {current.strftime('%B %d, %Y')}"
date: {date_str}
day_number: {day_num}
commits_count: 0
---

# Day {day_num}/90 - {current.strftime('%A, %B %d, %Y')}

No git commits recorded for this day.

*Possible reasons: Weekend, holiday, planning day, or work on a different branch.*

---

*Reconstructed from git history*
"""
            filepath.write_text(post_content)
            print(f"  CREATE {date_str} (Day {day_num}) - no commits (placeholder)")
            created += 1

        current += timedelta(days=1)

    print("\n" + "=" * 70)
    print(f"BACKFILL COMPLETE: {created} created, {skipped} skipped")
    print("=" * 70)

    return created, skipped


if __name__ == "__main__":
    backfill()
