#!/usr/bin/env python3
"""
Sync RAG lessons to GitHub Pages blog posts AND Dev.to.

Creates blog posts from RAG lessons for public visibility.
CEO Directive: "We should have blog posts for every day of our journey"
CEO Directive: "You are supposed to be always learning 24/7, and publishing blog posts every day!"
"""

import os
import re
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None  # Optional for local runs without requests

# Paths
RAG_LESSONS_DIR = Path(__file__).parent.parent / "rag_knowledge" / "lessons_learned"
BLOG_POSTS_DIR = Path(__file__).parent.parent / "docs" / "_posts"


def parse_lesson_file(filepath: Path) -> dict | None:
    """Parse a RAG lesson markdown file."""
    try:
        content = filepath.read_text()

        # Extract metadata
        lesson_id = filepath.stem

        # Try to extract date from filename (e.g., ll_131_..._jan12.md)
        # Use negative lookahead to only match 1-2 digit days, not years like jan2026
        date_match = re.search(r"jan(\d{1,2})(?!\d)", lesson_id, re.IGNORECASE)
        if date_match:
            day = int(date_match.group(1))
            year = 2026
            date_str = f"{year}-01-{day:02d}"
        else:
            # Fallback to today
            date_str = datetime.now().strftime("%Y-%m-%d")

        # Extract title from content
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        title = title_match.group(1) if title_match else lesson_id

        # Extract severity
        severity = "LOW"
        if "severity**: critical" in content.lower() or "severity: critical" in content.lower():
            severity = "CRITICAL"
        elif "severity**: high" in content.lower() or "severity: high" in content.lower():
            severity = "HIGH"
        elif "severity**: medium" in content.lower() or "severity: medium" in content.lower():
            severity = "MEDIUM"

        # Extract category
        category_match = re.search(r"category[:\s*]+([^\n]+)", content, re.IGNORECASE)
        category = category_match.group(1).strip() if category_match else "general"

        return {
            "id": lesson_id,
            "date": date_str,
            "title": title.replace("#", "").strip(),
            "severity": severity,
            "category": category,
            "content": content,
            "filepath": filepath,
        }
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        return None


def generate_daily_summary_post(date_str: str, lessons: list[dict]) -> str:
    """Generate a daily summary blog post from lessons."""
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    formatted_date = date_obj.strftime("%B %d, %Y")
    day_of_week = date_obj.strftime("%A")

    # Calculate day number (from Oct 29, 2025)
    start_date = datetime(2025, 10, 29)
    day_num = (date_obj - start_date).days + 1

    # Count by severity
    critical = sum(1 for item in lessons if item["severity"] == "CRITICAL")
    high = sum(1 for item in lessons if item["severity"] == "HIGH")
    medium = sum(1 for item in lessons if item["severity"] == "MEDIUM")
    low = sum(1 for item in lessons if item["severity"] == "LOW")

    # Build lessons summary
    lessons_md = ""
    for lesson in sorted(lessons, key=lambda x: x["severity"], reverse=False):
        severity_badge = {
            "CRITICAL": "**[CRITICAL]**",
            "HIGH": "[HIGH]",
            "MEDIUM": "[MEDIUM]",
            "LOW": "[LOW]",
        }.get(lesson["severity"], "[?]")

        # Get first 200 chars of content as summary
        summary = lesson["content"][:300].replace("\n", " ").strip()
        if len(lesson["content"]) > 300:
            summary += "..."

        lessons_md += f"\n### {severity_badge} {lesson['title']}\n\n"
        lessons_md += f"**ID**: `{lesson['id']}`\n\n"
        lessons_md += f"{summary}\n\n"

    post = f"""---
layout: post
title: "Day {day_num}: {len(lessons)} Lessons Learned - {formatted_date}"
date: {date_str}
day_number: {day_num}
lessons_count: {len(lessons)}
critical_count: {critical}
---

# Day {day_num}/90 - {day_of_week}, {formatted_date}

## Summary

| Metric | Count |
|--------|-------|
| Total Lessons | {len(lessons)} |
| CRITICAL | {critical} |
| HIGH | {high} |
| MEDIUM | {medium} |
| LOW | {low} |

---

## Lessons Learned
{lessons_md}
---

*Auto-generated from RAG knowledge base | [View Source](https://github.com/IgorGanapolsky/trading)*
"""
    return post


def post_lessons_to_devto(date_str: str, lessons: list[dict]) -> str | None:
    """Post lessons summary to Dev.to."""
    if not requests:
        print("  requests library not available, skipping Dev.to")
        return None

    api_key = os.getenv("DEVTO_API_KEY")
    if not api_key:
        print("  DEVTO_API_KEY not set, skipping Dev.to")
        return None

    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    formatted_date = date_obj.strftime("%B %d, %Y")
    day_of_week = date_obj.strftime("%A")

    # Calculate day number
    start_date = datetime(2025, 10, 29)
    day_num = (date_obj - start_date).days + 1

    # Count severities
    critical = sum(1 for item in lessons if item["severity"] == "CRITICAL")
    high = sum(1 for item in lessons if item["severity"] == "HIGH")

    # Build body
    body = f"""## Day {day_num}/90 - {day_of_week}, {formatted_date}

**{len(lessons)} lessons learned today** ({critical} critical, {high} high priority)

"""
    for lesson in sorted(lessons, key=lambda x: x["severity"], reverse=False)[:5]:
        severity_badge = {
            "CRITICAL": "**[CRITICAL]**",
            "HIGH": "[HIGH]",
            "MEDIUM": "[MEDIUM]",
            "LOW": "[LOW]",
        }.get(lesson["severity"], "[?]")
        body += f"### {severity_badge} {lesson['title'][:80]}\n\n"
        summary = lesson["content"][:200].replace("\n", " ").strip()
        body += f"{summary}...\n\n"

    body += """---

*Auto-generated from our AI Trading System's RAG knowledge base.*

Follow our journey: [AI Trading Journey on GitHub](https://github.com/IgorGanapolsky/trading)
"""

    headers = {"api-key": api_key, "Content-Type": "application/json"}
    payload = {
        "article": {
            "title": f"AI Trading: Day {day_num} - {len(lessons)} Lessons Learned ({formatted_date})",
            "body_markdown": body,
            "published": True,
            "series": "AI Trading Journey",
            "tags": ["ai", "trading", "machinelearning", "automation"],
        }
    }

    try:
        resp = requests.post(
            "https://dev.to/api/articles",
            headers=headers,
            json=payload,
            timeout=30,
        )
        if resp.status_code == 201:
            url = resp.json().get("url", "")
            print(f"  Published to Dev.to: {url}")
            return url
        else:
            print(f"  Dev.to publish failed: {resp.status_code} - {resp.text[:100]}")
            return None
    except Exception as e:
        print(f"  Dev.to publish error: {e}")
        return None


def sync_lessons_to_blog(publish_devto: bool = True):
    """Main sync function."""
    print("=" * 70)
    print("SYNCING RAG LESSONS TO BLOG" + (" + DEV.TO" if publish_devto else ""))
    print("=" * 70)

    # Ensure directories exist
    BLOG_POSTS_DIR.mkdir(parents=True, exist_ok=True)

    if not RAG_LESSONS_DIR.exists():
        print(f"ERROR: RAG lessons directory not found: {RAG_LESSONS_DIR}")
        return

    # Parse all lessons
    lessons_by_date: dict[str, list[dict]] = {}

    for lesson_file in RAG_LESSONS_DIR.glob("*.md"):
        lesson = parse_lesson_file(lesson_file)
        if lesson:
            date_str = lesson["date"]
            if date_str not in lessons_by_date:
                lessons_by_date[date_str] = []
            lessons_by_date[date_str].append(lesson)

    print(
        f"Found {sum(len(v) for v in lessons_by_date.values())} lessons across {len(lessons_by_date)} days"
    )

    # Generate blog posts for each day
    created = 0
    skipped = 0
    devto_published = 0

    for date_str, lessons in sorted(lessons_by_date.items()):
        # Generate filename
        filename = f"{date_str}-lessons-learned.md"
        filepath = BLOG_POSTS_DIR / filename

        # Generate post content
        post_content = generate_daily_summary_post(date_str, lessons)

        # Check if already exists with same content
        if filepath.exists():
            existing = filepath.read_text()
            if f"lessons_count: {len(lessons)}" in existing:
                print(f"  SKIP {filename} (already up to date)")
                skipped += 1
                continue

        # Write post
        filepath.write_text(post_content)
        print(f"  CREATE {filename} ({len(lessons)} lessons)")
        created += 1

        # Publish to Dev.to for new posts
        if publish_devto:
            url = post_lessons_to_devto(date_str, lessons)
            if url:
                devto_published += 1

    print("\n" + "=" * 70)
    print(f"SYNC COMPLETE: {created} created, {skipped} skipped, {devto_published} to Dev.to")
    print("=" * 70)

    return created, skipped


if __name__ == "__main__":
    import sys
    publish_devto = "--no-devto" not in sys.argv
    sync_lessons_to_blog(publish_devto=publish_devto)
