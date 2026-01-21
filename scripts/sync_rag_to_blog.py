#!/usr/bin/env python3
"""
Sync RAG lessons to GitHub Pages blog posts AND Dev.to.

Creates blog posts from RAG lessons for public visibility.
CEO Directive: "We should have blog posts for every day of our journey"
CEO Directive: "You are supposed to be always learning 24/7, and publishing blog posts every day!"
CEO Directive: "Why are lessons so mechanical and boring?? No human will read these blogs!!!!"
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


def get_engaging_intro(day_num: int, day_of_week: str, lessons: list[dict]) -> str:
    """Generate an engaging intro based on the day's lessons."""
    critical = sum(1 for lesson in lessons if lesson["severity"] == "CRITICAL")

    if critical >= 2:
        return "Today was a wake-up call. Two critical issues surfaced that could have derailed our entire trading operation. Here's what went wrong and how we're fixing it."
    elif critical == 1:
        return "Every mistake is a lesson in disguise. Today we uncovered a critical flaw in our system - the kind that separates amateur traders from professionals who survive long-term."
    elif day_of_week == "Friday":
        return "End of another trading week. Time to reflect on what worked, what didn't, and what needs to change before Monday's opening bell."
    elif day_of_week in ["Saturday", "Sunday"]:
        return "Markets are closed, but the learning never stops. While other traders take the weekend off, we're refining our edge."
    elif len(lessons) > 10:
        return f"An intense day of discovery. {len(lessons)} lessons emerged from our autonomous trading system - each one a stepping stone toward consistent profitability."
    else:
        return "Another day in the 90-day journey to build a profitable AI trading system. Here's what we learned today."


def extract_key_insight(lesson: dict) -> str:
    """Extract the key insight from a lesson in a readable way."""
    content = lesson["content"]

    # Try to find "What Happened" or similar sections
    what_happened = re.search(
        r"(?:What Happened|Problem|Issue|Bug)[:\s]*\n+([^\n#]+)", content, re.IGNORECASE
    )
    if what_happened:
        return what_happened.group(1).strip()[:200]

    # Try to find the first meaningful paragraph after the title
    paragraphs = re.split(r"\n\n+", content)
    for p in paragraphs[1:4]:  # Skip title, check next 3 paragraphs
        clean = p.strip()
        if len(clean) > 50 and not clean.startswith("#") and not clean.startswith("**"):
            return clean[:200]

    # Fallback to first 200 chars without markdown
    clean = re.sub(r"[#*`\[\]]", "", content)
    return clean[:200].strip()


def get_lesson_takeaway(lesson: dict) -> str:
    """Extract the actionable takeaway from a lesson."""
    content = lesson["content"]

    # Look for fix/solution/action sections
    fix_match = re.search(
        r"(?:Fix|Solution|Action|Resolution|Takeaway)[:\s]*\n+([^\n#]+)", content, re.IGNORECASE
    )
    if fix_match:
        return fix_match.group(1).strip()[:150]

    # Look for bullet points that might be actions
    bullets = re.findall(r"[-*]\s+([A-Z][^.\n]+\.)", content)
    if bullets:
        return bullets[0][:150]

    return ""


def generate_tech_stack_section() -> str:
    """Generate tech stack section with architecture diagram for blog post."""
    return """
## Tech Stack Behind the Lessons

Every lesson we learn is captured, analyzed, and stored by our AI infrastructure:

<div class="mermaid">
flowchart LR
    subgraph Learning["Learning Pipeline"]
        ERROR["Error/Insight<br/>Detected"] --> CLAUDE["Claude Opus<br/>(Analysis)"]
        CLAUDE --> RAG["Vertex AI RAG<br/>(Storage)"]
        RAG --> BLOG["GitHub Pages<br/>(Publishing)"]
        BLOG --> DEVTO["Dev.to<br/>(Distribution)"]
    end
</div>

### How We Learn Autonomously

| Component | Role in Learning |
|-----------|------------------|
| **Claude Opus 4.5** | Analyzes errors, extracts insights, determines severity |
| **Vertex AI RAG** | Stores lessons with 768D embeddings for semantic search |
| **Gemini 2.0 Flash** | Retrieves relevant past lessons before new trades |
| **OpenRouter (DeepSeek)** | Cost-effective sentiment analysis and research |

### Why This Matters

1. **No Lesson Lost**: Every insight persists in our RAG corpus
2. **Contextual Recall**: Before each trade, we query similar past situations
3. **Continuous Improvement**: 200+ lessons shape every decision
4. **Transparent Journey**: All learnings published publicly

*[Full Tech Stack Documentation](/trading/tech-stack/)*
"""


def get_human_readable_title(lesson: dict) -> str:
    """Get a human-readable title from the lesson."""
    raw_title = lesson["title"]

    # If title has a colon, take the part after it (usually more descriptive)
    if ":" in raw_title:
        parts = raw_title.split(":", 1)
        if len(parts[1].strip()) > 10:
            title = parts[1].strip()
        else:
            title = raw_title
    else:
        title = raw_title

    # Remove LL- prefix and number patterns
    title = re.sub(r"^LL-?\d+[:\s]*", "", title)
    title = re.sub(r"^\d+[:\s]*", "", title)

    # Clean up underscores and technical formatting
    title = title.replace("_", " ")

    # Remove date suffixes like "jan16" or "(Jan 16, 2026)"
    title = re.sub(r"\s*[-_]?\s*jan\d+\s*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s*\([^)]*\d{4}\)\s*$", "", title)

    # Capitalize properly if all lowercase
    if title == title.lower():
        title = title.title()

    # Truncate if too long
    if len(title) > 60:
        title = title[:57] + "..."

    return title.strip() or "Untitled Lesson"


def generate_daily_summary_post(date_str: str, lessons: list[dict]) -> str:
    """Generate an engaging, human-readable daily blog post from lessons."""
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    formatted_date = date_obj.strftime("%B %d, %Y")
    day_of_week = date_obj.strftime("%A")

    # Calculate day number (from Oct 29, 2025)
    start_date = datetime(2025, 10, 29)
    day_num = (date_obj - start_date).days + 1
    days_remaining = max(0, 90 - day_num)

    # Count by severity
    critical = sum(1 for item in lessons if item["severity"] == "CRITICAL")
    high = sum(1 for item in lessons if item["severity"] == "HIGH")

    # Get engaging intro
    intro = get_engaging_intro(day_num, day_of_week, lessons)

    # Build the story of today's lessons
    lessons_md = ""

    # Critical lessons first - these are the headlines
    critical_lessons = [lesson for lesson in lessons if lesson["severity"] == "CRITICAL"]
    if critical_lessons:
        lessons_md += "\n## The Hard Lessons\n\n"
        lessons_md += "*These are the moments that test us. Critical issues that demanded immediate attention.*\n\n"
        for lesson in critical_lessons:
            title = get_human_readable_title(lesson)
            insight = extract_key_insight(lesson)
            takeaway = get_lesson_takeaway(lesson)

            lessons_md += f"### {title}\n\n"
            lessons_md += f"{insight}\n\n"
            if takeaway:
                lessons_md += f"**Key takeaway:** {takeaway}\n\n"

    # High priority lessons - important but not fires
    high_lessons = [lesson for lesson in lessons if lesson["severity"] == "HIGH"]
    if high_lessons:
        lessons_md += "\n## Important Discoveries\n\n"
        lessons_md += (
            "*Not emergencies, but insights that will shape how we trade going forward.*\n\n"
        )
        for lesson in high_lessons[:3]:  # Limit to top 3
            title = get_human_readable_title(lesson)
            insight = extract_key_insight(lesson)

            lessons_md += f"### {title}\n\n"
            lessons_md += f"{insight}\n\n"

    # Quick wins and improvements
    other_lessons = [lesson for lesson in lessons if lesson["severity"] in ["MEDIUM", "LOW"]]
    if other_lessons:
        lessons_md += "\n## Quick Wins & Refinements\n\n"
        for lesson in other_lessons[:4]:  # Limit to top 4
            title = get_human_readable_title(lesson)
            lessons_md += f"- **{title}** - {extract_key_insight(lesson)[:100]}...\n"
        lessons_md += "\n"

    # Build the post
    post = f"""---
layout: post
title: "Day {day_num}: What We Learned - {formatted_date}"
date: {date_str}
day_number: {day_num}
lessons_count: {len(lessons)}
critical_count: {critical}
excerpt: "{intro[:150]}..."
---

# Day {day_num} of 90 | {day_of_week}, {formatted_date}

**{days_remaining} days remaining** in our journey to build a profitable AI trading system.

{intro}

---
{lessons_md}
---

## Today's Numbers

| What | Count |
|------|-------|
| Lessons Learned | **{len(lessons)}** |
| Critical Issues | {critical} |
| High Priority | {high} |
| Improvements | {len(other_lessons)} |

---
{generate_tech_stack_section()}
---

## The Journey So Far

We're building an autonomous AI trading system that learns from every mistake. This isn't about getting rich quick - it's about building a system that can consistently generate income through disciplined options trading.

**Our approach:**
- Paper trade for 90 days to validate the strategy
- Document every lesson, every failure, every win
- Use AI (Claude) as CTO to automate and improve
- Follow Phil Town's Rule #1: Don't lose money

Want to follow along? Check out the [full project on GitHub](https://github.com/IgorGanapolsky/trading).

---

*Day {day_num}/90 complete. {days_remaining} to go.*
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
    intro = get_engaging_intro(day_num, day_of_week, lessons)
    body = f"""## Day {day_num}/90 - {day_of_week}, {formatted_date}

{intro}

**{len(lessons)} lessons learned today** ({critical} critical, {high} high priority)

"""
    for lesson in sorted(lessons, key=lambda x: x["severity"], reverse=False)[:5]:
        title = get_human_readable_title(lesson)
        body += f"### {title}\n\n"
        summary = extract_key_insight(lesson)
        body += f"{summary}\n\n"

    body += """---

## Tech Stack Behind the Scenes

Our AI trading system uses:
- **Claude Opus 4.5** - Primary reasoning engine for trade decisions
- **OpenRouter** - Cost-optimized LLM gateway (DeepSeek, Mistral, Kimi)
- **Vertex AI RAG** - Cloud semantic search with 768D embeddings
- **Gemini 2.0 Flash** - Retrieval-augmented generation
- **MCP Protocol** - Standardized tool integration layer

Every lesson is stored in our RAG corpus, enabling the system to learn from past mistakes and improve continuously.

*[Full Tech Stack Documentation](https://igorganapolsky.github.io/trading/tech-stack/)*

---

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
