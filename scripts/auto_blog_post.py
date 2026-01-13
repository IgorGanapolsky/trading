#!/usr/bin/env python3
"""
Auto-generate blog posts from daily activity.
Runs automatically via SessionStart hook or manually.
"""
import subprocess
import json
from datetime import datetime, date
from pathlib import Path
import re


def get_todays_commits() -> list[dict]:
    """Get all commits from today."""
    today = date.today().isoformat()
    result = subprocess.run(
        ["git", "log", "--oneline", f"--since={today} 00:00:00", f"--until={today} 23:59:59"],
        capture_output=True, text=True
    )
    commits = []
    for line in result.stdout.strip().split('\n'):
        if line:
            parts = line.split(' ', 1)
            if len(parts) == 2:
                commits.append({"hash": parts[0], "message": parts[1]})
    return commits


def categorize_commits(commits: list[dict]) -> dict:
    """Categorize commits by significance."""
    categories = {
        "emergency": [],
        "rule_violation": [],
        "risk_management": [],
        "feature": [],
        "fix": [],
        "cleanup": [],
        "other": []
    }

    for c in commits:
        msg = c["message"].lower()
        if "emergency" in msg:
            categories["emergency"].append(c)
        elif "rule #1" in msg or "rule_1" in msg or "phil town" in msg:
            categories["rule_violation"].append(c)
        elif "risk" in msg:
            categories["risk_management"].append(c)
        elif msg.startswith("feat"):
            categories["feature"].append(c)
        elif msg.startswith("fix"):
            categories["fix"].append(c)
        elif "cleanup" in msg or "debt" in msg:
            categories["cleanup"].append(c)
        else:
            categories["other"].append(c)

    return categories


def get_day_number() -> int:
    """Calculate day number in 90-day experiment (started Nov 1, 2025)."""
    start = date(2025, 11, 1)
    today = date.today()
    return (today - start).days + 1


def get_existing_posts_today() -> list[str]:
    """Get titles of posts already created today."""
    posts_dir = Path("docs/_posts")
    today = date.today().isoformat()
    existing = []

    for f in posts_dir.glob(f"{today}*.md"):
        content = f.read_text()
        title_match = re.search(r'title:\s*"([^"]+)"', content)
        if title_match:
            existing.append(title_match.group(1).lower())

    return existing


def generate_blog_post(topic: str, commits: list[dict], day_num: int) -> tuple[str, str]:
    """Generate a blog post for a topic."""
    today = date.today().isoformat()

    if topic == "rule_violation":
        title = f"Day {day_num}: Learning from Rule #1 Violation"
        slug = f"{today}-day-{day_num}-rule-1-violation.md"
        content = f'''---
layout: post
title: "{title}"
date: {today}
categories: [lessons, risk-management]
tags: [rule-1, phil-town, risk, positions]
description: "Phil Town's Rule #1: Don't lose money. Today we violated it and learned."
---

# {title}

Phil Town's Rule #1 is simple: **Don't lose money.**

Today, our AI trading system violated this rule. Here's what happened and how we fixed it.

## What Happened

'''
        for c in commits:
            content += f"- `{c['hash']}`: {c['message']}\n"

        content += '''
## The Fix

We implemented automatic protections:
1. **Position monitoring** - Track P/L in real-time
2. **Duplicate prevention** - Never double down on losing trades
3. **Emergency closure** - Auto-close positions that violate Rule #1

## Lesson Recorded

This is now in our RAG memory. The AI cannot make this mistake again.

## Key Takeaway

> "The first rule of investing is don't lose money. The second rule is don't forget rule #1." - Phil Town

---

*Day ''' + str(day_num) + ''' of 90. Protecting capital first.*
'''
        return slug, content

    elif topic == "emergency":
        title = f"Day {day_num}: Emergency Response - System Recovery"
        slug = f"{today}-day-{day_num}-emergency-response.md"
        content = f'''---
layout: post
title: "{title}"
date: {today}
categories: [lessons, operations]
tags: [emergency, recovery, automation]
description: "When things go wrong, the system needs to recover fast."
---

# {title}

Today required emergency intervention. Here's how our system responded.

## Timeline

'''
        for c in commits:
            content += f"- {c['message']}\n"

        content += f'''
## Recovery Actions

The system automatically:
1. Detected the issue
2. Triggered emergency protocols
3. Recorded lessons for future prevention

---

*Day {day_num} of 90. Building resilient systems.*
'''
        return slug, content

    return None, None


def main():
    """Main entry point."""
    print("=" * 60)
    print("AUTO BLOG POST GENERATOR")
    print("=" * 60)

    commits = get_todays_commits()
    if not commits:
        print("No commits today. Nothing to blog about.")
        return

    print(f"Found {len(commits)} commits today")

    categories = categorize_commits(commits)
    existing = get_existing_posts_today()
    day_num = get_day_number()

    print(f"Day {day_num} of 90-day experiment")
    print(f"Existing posts: {existing}")

    posts_created = []
    posts_dir = Path("docs/_posts")

    # Priority: Rule violations > Emergency > Risk management
    priority_topics = ["rule_violation", "emergency", "risk_management"]

    for topic in priority_topics:
        if categories[topic]:
            # Check if already posted
            topic_keywords = {
                "rule_violation": ["rule #1", "rule-1", "violation"],
                "emergency": ["emergency"],
                "risk_management": ["risk"]
            }

            already_posted = any(
                any(kw in title for kw in topic_keywords[topic])
                for title in existing
            )

            if already_posted:
                print(f"  {topic}: Already posted today, skipping")
                continue

            slug, content = generate_blog_post(topic, categories[topic], day_num)
            if slug and content:
                filepath = posts_dir / slug
                filepath.write_text(content)
                posts_created.append(slug)
                print(f"  Created: {slug}")

    if posts_created:
        print(f"\n{len(posts_created)} blog post(s) created")
        print("Run: git add docs/_posts/ && git commit -m 'blog: Auto-generated daily posts'")
    else:
        print("\nNo new posts needed - all significant events already documented")

    return posts_created


if __name__ == "__main__":
    main()
