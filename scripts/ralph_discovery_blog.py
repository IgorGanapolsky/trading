#!/usr/bin/env python3
"""
Ralph Discovery Blog Publisher

Automatically generates and publishes engaging blog posts when Ralph
makes significant discoveries or fixes. Posts go to:
- GitHub Pages (docs/_posts/)
- Dev.to (via API)

The goal: Share real engineering insights that developers actually want to read.
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import requests


def get_devto_api_key() -> str | None:
    """Get Dev.to API key from environment."""
    return os.environ.get("DEVTO_API_KEY")


def get_recent_ralph_commits(max_count: int = 10) -> list[dict]:
    """Get recent commits from Ralph workflows."""
    import subprocess

    result = subprocess.run(
        [
            "git",
            "log",
            "--since=24 hours ago",
            "--oneline",
            "--grep=ralph\\|self-heal\\|auto-fix\\|fix(\\|feat(",
            "--format=%H|%s|%an|%ad",
            "--date=short",
        ],
        capture_output=True,
        text=True,
    )

    commits = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("|")
        if len(parts) >= 4:
            commits.append(
                {
                    "sha": parts[0][:8],
                    "message": parts[1],
                    "author": parts[2],
                    "date": parts[3],
                }
            )

    return commits[:max_count]


def get_recent_lesson_files(hours: int = 24) -> list[Path]:
    """Get lesson files created in the last N hours."""
    lessons_dir = Path("rag_knowledge/lessons_learned")
    if not lessons_dir.exists():
        return []

    cutoff = datetime.now().timestamp() - (hours * 60 * 60)
    recent = []

    for f in lessons_dir.glob("*.md"):
        if f.stat().st_mtime > cutoff:
            recent.append(f)

    return sorted(recent, key=lambda x: x.stat().st_mtime, reverse=True)


def extract_discovery_content(lesson_file: Path) -> dict:
    """Extract meaningful content from a lesson file."""
    content = lesson_file.read_text()
    lines = content.strip().split("\n")

    # Extract title
    title = lines[0].replace("#", "").strip() if lines else lesson_file.stem

    # Extract key sections
    problem = ""
    solution = ""
    impact = ""

    current_section = None
    section_content = []

    for line in lines[1:]:
        lower_line = line.lower()
        if "problem" in lower_line or "issue" in lower_line or "bug" in lower_line:
            if current_section and section_content:
                if "problem" in current_section:
                    problem = " ".join(section_content)
            current_section = "problem"
            section_content = []
        elif "solution" in lower_line or "fix" in lower_line or "resolution" in lower_line:
            if current_section and section_content:
                if "problem" in current_section:
                    problem = " ".join(section_content)
            current_section = "solution"
            section_content = []
        elif "impact" in lower_line or "result" in lower_line or "outcome" in lower_line:
            if current_section and section_content:
                if "solution" in current_section:
                    solution = " ".join(section_content)
            current_section = "impact"
            section_content = []
        elif line.strip() and not line.startswith("#"):
            section_content.append(line.strip())

    # Capture last section
    if current_section and section_content:
        if "problem" in current_section:
            problem = " ".join(section_content)
        elif "solution" in current_section:
            solution = " ".join(section_content)
        elif "impact" in current_section:
            impact = " ".join(section_content)

    return {
        "title": title,
        "problem": problem[:500] if problem else "Identified during automated scanning",
        "solution": solution[:500] if solution else "Automated fix applied by Ralph",
        "impact": impact[:300] if impact else "System stability improved",
        "raw_content": content[:2000],
    }


def generate_blog_post(discoveries: list[dict], commits: list[dict]) -> dict:
    """Generate an engaging blog post from discoveries."""
    date = datetime.now().strftime("%Y-%m-%d")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Create engaging title
    if len(discoveries) == 1:
        title = f"How Our AI Found and Fixed: {discoveries[0]['title'][:50]}"
    else:
        title = f"Ralph's Discovery Log: {len(discoveries)} Fixes in 24 Hours"

    # Build the post content
    content = f"""---
layout: post
title: "{title}"
date: {timestamp}
categories: [ralph, automation, ai-engineering]
tags: [self-healing, ci-cd, autonomous-systems]
---

## 🤖 Autonomous Engineering in Action

Our AI system, Ralph (named after the [Ralph Wiggum iterative coding technique](https://github.com/Th0rgal/opencode-ralph-wiggum)),
continuously monitors, discovers, and fixes issues in our trading system. Here's what it found today.

"""

    # Add discoveries
    for i, discovery in enumerate(discoveries, 1):
        content += f"""
### Discovery #{i}: {discovery['title']}

**🔍 What Ralph Found:**
{discovery['problem']}

**🔧 The Fix:**
{discovery['solution']}

**📈 Impact:**
{discovery['impact']}

---
"""

    # Add commit summary
    if commits:
        content += """
## 📝 Commits This Session

| SHA | Message |
|-----|---------|
"""
        for commit in commits[:5]:
            content += f"| `{commit['sha']}` | {commit['message'][:60]} |\n"

    # Add footer
    content += f"""

## 🎯 Why This Matters

Self-healing systems aren't just about fixing bugs—they're about building confidence
in autonomous operations. Every fix Ralph makes is:

1. **Documented** in our lessons learned database
2. **Tested** before being applied
3. **Reviewed** via pull request (when significant)

This is the future of software engineering: systems that improve themselves.

---

*Generated automatically by Ralph Mode on {timestamp}*

**Follow our journey:** [GitHub](https://github.com/IgorGanapolsky/trading) |
Building a $100/day trading system with AI.
"""

    return {
        "title": title,
        "content": content,
        "date": date,
        "tags": ["ralph", "automation", "self-healing", "ai", "python"],
    }


def save_to_github_pages(post: dict) -> str | None:
    """Save post to GitHub Pages _posts directory."""
    posts_dir = Path("docs/_posts")
    posts_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{post['date']}-ralph-discovery.md"
    filepath = posts_dir / filename

    filepath.write_text(post["content"])
    print(f"✅ Saved to GitHub Pages: {filepath}")
    return str(filepath)


def publish_to_devto(post: dict) -> dict | None:
    """Publish post to Dev.to."""
    api_key = get_devto_api_key()
    if not api_key:
        print("⚠️ DEVTO_API_KEY not set - skipping Dev.to publish")
        return None

    # Convert to Dev.to format
    devto_content = post["content"]
    # Remove Jekyll front matter for Dev.to
    devto_content = re.sub(r"---\n.*?---\n", "", devto_content, flags=re.DOTALL)

    payload = {
        "article": {
            "title": post["title"],
            "body_markdown": devto_content,
            "published": True,
            "tags": post["tags"][:4],  # Dev.to allows max 4 tags
            "series": "Ralph Mode: AI Self-Healing Systems",
        }
    }

    try:
        response = requests.post(
            "https://dev.to/api/articles",
            headers={"api-key": api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )

        if response.status_code == 201:
            result = response.json()
            print(f"✅ Published to Dev.to: {result.get('url', 'Success')}")
            return result
        else:
            print(f"⚠️ Dev.to publish failed: {response.status_code} - {response.text[:200]}")
            return None
    except Exception as e:
        print(f"⚠️ Dev.to error: {e}")
        return None


def should_publish() -> bool:
    """Determine if there's enough content to warrant a blog post."""
    lessons = get_recent_lesson_files(hours=24)
    commits = get_recent_ralph_commits()

    # Need at least 1 lesson or 3 significant commits
    significant_commits = [c for c in commits if "fix" in c["message"].lower() or "feat" in c["message"].lower()]

    return len(lessons) >= 1 or len(significant_commits) >= 3


def main():
    print("=" * 60)
    print("RALPH DISCOVERY BLOG PUBLISHER")
    print("=" * 60)

    # Check if there's content to publish
    if not should_publish():
        print("ℹ️ No significant discoveries in last 24 hours - skipping")
        return 0

    # Gather discoveries
    lessons = get_recent_lesson_files(hours=24)
    commits = get_recent_ralph_commits()

    print(f"Found {len(lessons)} recent lessons, {len(commits)} recent commits")

    # Extract discovery content
    discoveries = []
    for lesson in lessons[:3]:  # Max 3 discoveries per post
        try:
            discovery = extract_discovery_content(lesson)
            discoveries.append(discovery)
        except Exception as e:
            print(f"⚠️ Could not parse {lesson}: {e}")

    if not discoveries and not commits:
        print("ℹ️ No parseable discoveries - skipping")
        return 0

    # Generate blog post
    post = generate_blog_post(discoveries, commits)
    print(f"\n📝 Generated post: {post['title']}")

    # Save to GitHub Pages
    gh_path = save_to_github_pages(post)

    # Publish to Dev.to
    devto_result = publish_to_devto(post)

    print("\n" + "=" * 60)
    print("BLOG PUBLISHING COMPLETE")
    print("=" * 60)
    print(f"GitHub Pages: {gh_path or 'Skipped'}")
    print(f"Dev.to: {devto_result.get('url') if devto_result else 'Skipped'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
