#!/usr/bin/env python3
"""
Ralph Discovery Blog Publisher

Automatically generates and publishes engaging blog posts when Ralph
makes significant discoveries or fixes. Posts go to:
- GitHub Pages (docs/_posts/)
- Dev.to (via API)

The goal: Share real engineering insights that developers actually want to read.
"""

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

    # Get the lesson ID from filename (e.g., LL-277)
    lesson_id = ""
    if match := re.search(r"LL-\d+", lesson_file.stem):
        lesson_id = match.group(0)

    # Extract key sections with smarter parsing
    problem = ""
    solution = ""
    impact = ""
    tags = []

    current_section = None
    section_content = []

    for line in lines[1:]:
        lower_line = line.lower()

        # Extract tags
        if "tags:" in lower_line or line.startswith("- "):
            tag_match = re.findall(r"[a-z\-]+", lower_line)
            tags.extend([t for t in tag_match if len(t) > 2])

        if (
            "problem" in lower_line
            or "issue" in lower_line
            or "bug" in lower_line
            or "what happened" in lower_line
        ):
            if current_section and section_content:
                if "problem" in current_section:
                    problem = " ".join(section_content)
            current_section = "problem"
            section_content = []
        elif (
            "solution" in lower_line
            or "fix" in lower_line
            or "resolution" in lower_line
            or "how we fixed" in lower_line
        ):
            if current_section and section_content:
                if "problem" in current_section:
                    problem = " ".join(section_content)
            current_section = "solution"
            section_content = []
        elif (
            "impact" in lower_line
            or "result" in lower_line
            or "outcome" in lower_line
            or "lesson" in lower_line
        ):
            if current_section and section_content:
                if "solution" in current_section:
                    solution = " ".join(section_content)
            current_section = "impact"
            section_content = []
        elif line.strip() and not line.startswith("#") and not line.startswith("---"):
            section_content.append(line.strip())

    # Capture last section
    if current_section and section_content:
        if "problem" in current_section:
            problem = " ".join(section_content)
        elif "solution" in current_section:
            solution = " ".join(section_content)
        elif "impact" in current_section:
            impact = " ".join(section_content)

    # If no structured content, use first meaningful paragraph
    if not problem and not solution:
        non_header_lines = [
            line.strip()
            for line in lines
            if line.strip() and not line.startswith("#") and not line.startswith("---")
        ]
        if non_header_lines:
            problem = " ".join(non_header_lines[:3])[:400]
            solution = " ".join(non_header_lines[3:6])[:400] if len(non_header_lines) > 3 else ""
            impact = " ".join(non_header_lines[6:8])[:300] if len(non_header_lines) > 6 else ""

    return {
        "title": title,
        "lesson_id": lesson_id,
        "problem": problem[:500]
        if problem
        else f"See full details in lesson {lesson_id or lesson_file.stem}",
        "solution": solution[:500]
        if solution
        else "Applied targeted fix based on root cause analysis",
        "impact": impact[:300] if impact else "Risk reduced and system resilience improved",
        "tags": tags[:5],
        "raw_content": content[:2000],
    }


def generate_blog_post(discoveries: list[dict], commits: list[dict]) -> dict:
    """Generate an engaging blog post from discoveries."""
    date = datetime.now().strftime("%Y-%m-%d")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    repo_url = "https://github.com/IgorGanapolsky/trading"

    # Create engaging title based on content
    if len(discoveries) == 1:
        d = discoveries[0]
        title = d["title"][:60] if d.get("title") else "Today's Engineering Discovery"
    elif len(discoveries) > 0:
        # Try to pick the most interesting discovery for the title
        titles = [d["title"] for d in discoveries if d.get("title")]
        main_topic = titles[0][:40] if titles else "System Improvements"
        title = f"Engineering Log: {main_topic} (+{len(discoveries) - 1} more)"
    else:
        title = f"What We Shipped Today: {len(commits)} Commits"

    # Collect all tags from discoveries
    all_tags = set()
    for d in discoveries:
        all_tags.update(d.get("tags", []))

    # Build the post content
    content = f"""---
layout: post
title: "{title}"
date: {timestamp}
categories: [engineering, lessons-learned, ai-trading]
tags: [{", ".join(list(all_tags)[:4]) or "self-healing, ci-cd, automation"}]
---

Building an autonomous AI trading system means things break. Here's what we discovered, fixed, and learned today.

"""

    # Add discoveries with more narrative style
    for i, discovery in enumerate(discoveries, 1):
        lesson_link = ""
        if discovery.get("lesson_id"):
            lesson_link = f"\n\n*[View full lesson: {discovery['lesson_id']}]({repo_url}/blob/main/rag_knowledge/lessons_learned/)*"

        content += f"""
## {discovery["title"]}

**The Problem:** {discovery["problem"]}

**What We Did:** {discovery["solution"]}

**The Takeaway:** {discovery["impact"]}{lesson_link}

---
"""

    # Add commit summary with links
    if commits:
        content += f"""
## Code Changes

These commits shipped today ([view on GitHub]({repo_url}/commits/main)):

| Commit | Description |
|--------|-------------|
"""
        for commit in commits[:5]:
            sha_link = f"[{commit['sha']}]({repo_url}/commit/{commit['sha']})"
            content += f"| {sha_link} | {commit['message'][:55]} |\n"

    # Add more engaging footer
    content += f"""

## Why We Share This

Every bug is a lesson. Every fix makes the system stronger. We're building in public because:

1. **Transparency builds trust** - See exactly how an autonomous trading system evolves
2. **Failures teach more than successes** - Our mistakes help others avoid the same pitfalls
3. **Documentation prevents regression** - Writing it down means we won't repeat it

---

*This is part of our journey building an AI-powered iron condor trading system targeting financial independence.*

**Resources:**
- [Source Code]({repo_url})
- [Strategy Guide](https://igorganapolsky.github.io/trading/2026/01/21/iron-condors-ai-trading-complete-guide.html)
- [The Silent 74 Days](https://igorganapolsky.github.io/trading/2026/01/07/the-silent-74-days.html) - How we built a system that did nothing
"""

    return {
        "title": title,
        "content": content,
        "date": date,
        "tags": list(all_tags)[:4] if all_tags else ["ralph", "automation", "self-healing", "ai"],
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
    significant_commits = [
        c for c in commits if "fix" in c["message"].lower() or "feat" in c["message"].lower()
    ]

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
