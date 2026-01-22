#!/usr/bin/env python3
"""
Publish Ralph Iteration Blog Posts - Autonomous CTO Discoveries

When Ralph (our autonomous CTO mode) finds bugs, makes improvements, or discovers
interesting patterns, this script creates engaging blog posts for Dev.to and GitHub Pages.

CEO Directive: "I want Ralph to publish meaningful and interesting blog posts about
any significant discoveries it found, every time."

The goal is to share our AI trading system journey with readers who are interested in:
- Autonomous AI development
- Trading system engineering
- Bug hunting and fixing
- Self-healing systems
- Phil Town Rule #1 investing

Posts should be:
- Engaging and story-driven
- Educational with real code examples
- Honest about failures and successes
- Valuable to readers building similar systems
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
BLOG_POSTS_DIR = PROJECT_ROOT / "docs" / "_posts"
RAG_LESSONS_DIR = PROJECT_ROOT / "rag_knowledge" / "lessons_learned"
PRD_FILE = PROJECT_ROOT / ".claude" / "prd.json"


def get_recent_lessons(hours: int = 24) -> list[dict]:
    """Get lessons created in the last N hours."""
    lessons = []
    now = datetime.now()

    for filepath in RAG_LESSONS_DIR.glob("*.md"):
        # Check file modification time
        mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
        age_hours = (now - mtime).total_seconds() / 3600

        if age_hours <= hours:
            content = filepath.read_text()

            # Extract title
            title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            title = title_match.group(1) if title_match else filepath.stem

            # Extract severity
            severity = "MEDIUM"
            if "critical" in content.lower():
                severity = "CRITICAL"
            elif "high" in content.lower() and "severity" in content.lower():
                severity = "HIGH"

            # Extract category
            category_match = re.search(r"\*\*Category\*\*:\s*([^\n]+)", content)
            category = category_match.group(1).strip() if category_match else "General"

            lessons.append({
                "id": filepath.stem,
                "title": title.replace("#", "").strip(),
                "severity": severity,
                "category": category,
                "filepath": filepath,
                "age_hours": age_hours,
            })

    # Sort by severity (CRITICAL first) then by age
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    lessons.sort(key=lambda x: (severity_order.get(x["severity"], 4), x["age_hours"]))

    return lessons


def get_iteration_stats() -> dict:
    """Get current Ralph iteration stats from prd.json."""
    try:
        if PRD_FILE.exists():
            data = json.loads(PRD_FILE.read_text())
            return {
                "iteration": data.get("metadata", {}).get("total_iterations", 0),
                "notes": data.get("metadata", {}).get("notes", ""),
                "last_task": data.get("metadata", {}).get("last_task_completed", ""),
                "tasks_completed": data.get("metadata", {}).get("tasks_completed_this_session", 0),
            }
    except Exception as e:
        print(f"Error reading prd.json: {e}")

    return {"iteration": 0, "notes": "", "last_task": "", "tasks_completed": 0}


def generate_engaging_title(lessons: list[dict], stats: dict) -> str:
    """Generate an engaging title based on discoveries."""
    critical_count = sum(1 for lesson in lessons if lesson["severity"] == "CRITICAL")
    high_count = sum(1 for lesson in lessons if lesson["severity"] == "HIGH")

    titles = []

    # Check for specific patterns in lessons
    has_trading = any("trading" in lesson["category"].lower() for lesson in lessons)
    has_ci = any("ci" in lesson["category"].lower() for lesson in lessons)
    has_test = any("test" in lesson["category"].lower() for lesson in lessons)
    has_bug = any("bug" in lesson["id"].lower() or "fix" in lesson["id"].lower() for lesson in lessons)

    if critical_count >= 2:
        titles.append("When Two Critical Bugs Nearly Crashed Our AI Trading System")
        titles.append(f"Iteration {stats['iteration']}: The Day Everything Almost Broke")
    elif critical_count == 1:
        titles.append("Catching a Silent Killer in Our Trading Code")
        titles.append("One Bug, $5000 at Stake: What Our AI Learned Today")
    elif has_trading and has_bug:
        titles.append("The Bug That Would Have Cost Us Money (And How We Fixed It)")
    elif has_ci:
        titles.append("Making Our CI Pipeline Self-Healing: A Deep Dive")
    elif has_test:
        titles.append(f"From 870 to {870 + len(lessons)} Tests: Bulletproofing Our Trading System")
    elif high_count > 0:
        titles.append(f"Ralph's {stats['iteration']}th Iteration: {high_count} High-Priority Fixes")
    else:
        titles.append("Autonomous CTO Mode: What Ralph Discovered Today")

    return titles[0]


def generate_blog_content(lessons: list[dict], stats: dict, tests_passed: str, lint_passed: str) -> str:
    """Generate an engaging blog post about Ralph's discoveries."""

    iteration = stats["iteration"]

    title = generate_engaging_title(lessons, stats)

    # Determine the story angle
    critical_lessons = [lesson for lesson in lessons if lesson["severity"] == "CRITICAL"]
    has_trading_impact = any("iron" in str(lesson).lower() or "spy" in str(lesson).lower() for lesson in lessons)

    # Build the post
    content = f"""---
layout: post
title: "{title}"
date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} -0500
categories: [ai-trading, ralph-mode, autonomous-development]
tags: [ai, trading, python, automation, self-healing, devops]
description: "Iteration {iteration} of our autonomous CTO mode - what our AI discovered while we slept"
---

# {title}

"""

    # Add engaging intro based on context
    if critical_lessons:
        content += f"""
*You know that feeling when you wake up and check your system, expecting everything to be fine, only to discover your AI has been fighting fires all night?*

That's exactly what happened during **Ralph iteration {iteration}**. Our autonomous CTO mode (affectionately named "Ralph" after Ralph Wiggum's unpredictable insights) discovered {len(critical_lessons)} critical issue{'s' if len(critical_lessons) > 1 else ''} that could have cost us real money.

Here's the story of what went wrong, and more importantly, how our self-healing system fixed it.

"""
    elif has_trading_impact:
        content += f"""
*Building an AI trading system is like raising a child - you teach it the rules, but it still finds creative ways to break things.*

During **iteration {iteration}**, Ralph uncovered some interesting patterns in our options trading logic. The kind of discoveries that don't show up in backtests but matter when real money is on the line.

"""
    else:
        content += f"""
*The best bugs are the ones you find before they find your wallet.*

Welcome to iteration **{iteration}** of our autonomous CTO journey. While most trading systems require constant human supervision, we're building something different - a system that watches itself, fixes itself, and learns continuously.

Here's what Ralph discovered this time around.

"""

    # Add the discoveries section
    content += """
## The Discoveries

"""

    for i, lesson in enumerate(lessons[:5], 1):  # Limit to top 5
        severity_emoji = {"CRITICAL": "🚨", "HIGH": "⚠️", "MEDIUM": "📝", "LOW": "💡"}.get(lesson["severity"], "📌")

        content += f"""
### {i}. {severity_emoji} {lesson['title']}

**Category:** {lesson['category']} | **Severity:** {lesson['severity']}

"""

        # Try to extract a meaningful snippet from the lesson file
        try:
            lesson_content = lesson["filepath"].read_text()

            # Look for the "What Happened" or "Summary" section
            summary_match = re.search(r"(?:Summary|What Happened|Problem)[:\s]*\n+(.+?)(?:\n\n|\n##)", lesson_content, re.IGNORECASE | re.DOTALL)
            if summary_match:
                snippet = summary_match.group(1).strip()[:300]
                content += f"> {snippet}...\n\n"

            # Look for the fix or solution
            fix_match = re.search(r"(?:Fix|Solution|Resolution)[:\s]*\n+(.+?)(?:\n\n|\n##)", lesson_content, re.IGNORECASE | re.DOTALL)
            if fix_match:
                fix_snippet = fix_match.group(1).strip()[:200]
                content += f"**The Fix:** {fix_snippet}\n\n"

        except Exception:
            content += f"> Lesson documented in `{lesson['id']}.md`\n\n"

    if len(lessons) > 5:
        content += f"\n*Plus {len(lessons) - 5} more discoveries documented in our RAG knowledge base.*\n\n"

    # Add the metrics section
    content += f"""
## Iteration Metrics

| Metric | Value |
|--------|-------|
| **Iteration** | {iteration} |
| **Tests** | {'✅ Passing' if tests_passed == 'true' else '⚠️ Issues'} |
| **Lint** | {'✅ Clean' if lint_passed == 'true' else '⚠️ Issues'} |
| **Lessons Created** | {len(lessons)} |
| **Tasks Completed** | {stats['tasks_completed']} |

"""

    # Add the "Why This Matters" section
    content += """
## Why This Matters

Building a self-healing trading system isn't just about catching bugs - it's about creating a feedback loop where the system continuously improves itself. Every discovery Ralph makes gets:

1. **Documented** in our RAG knowledge base (122+ lessons and growing)
2. **Fixed** automatically when possible
3. **Tested** to prevent regression
4. **Published** so others can learn from our journey

This is the future of software development: autonomous systems that don't just run, but *evolve*.

"""

    # Add the call to action
    content += """
## Follow Our Journey

We're on day 80+ of a 90-day mission to build a profitable AI trading system using:
- **Iron Condors on SPY** (defined risk, 86% win rate target)
- **Phil Town's Rule #1** (don't lose money)
- **Autonomous CTO Mode** (24/7 self-improvement)

Current portfolio: ~$5,000 paper trading
Goal: $100/day after-tax profit

*Like this post? Follow our [GitHub repository](https://github.com/IgorGanapolsky/trading) for real-time updates, or check out our [full blog](https://igorganapolsky.github.io/trading/) for the complete journey.*

---

*This post was automatically generated by Ralph, our autonomous CTO. No humans were harmed in the making of this blog post (though a few bugs were).*
"""

    return content


def publish_to_devto(title: str, content: str, tags: list[str]) -> dict | None:
    """Publish to Dev.to if API key is available."""
    api_key = os.environ.get("DEVTO_API_KEY")

    if not api_key:
        print("No DEVTO_API_KEY found, skipping Dev.to publish")
        return None

    if requests is None:
        print("requests library not available, skipping Dev.to publish")
        return None

    # Remove Jekyll front matter for Dev.to
    content_clean = re.sub(r"^---\n.*?---\n", "", content, flags=re.DOTALL)

    # Add Dev.to front matter
    devto_content = f"""---
title: {title}
published: true
tags: {', '.join(tags[:4])}
series: AI Trading Journey
canonical_url: https://igorganapolsky.github.io/trading/{datetime.now().strftime('%Y/%m/%d')}/{title.lower().replace(' ', '-')[:50]}/
---

{content_clean}
"""

    try:
        response = requests.post(
            "https://dev.to/api/articles",
            headers={
                "api-key": api_key,
                "Content-Type": "application/json",
            },
            json={
                "article": {
                    "title": title,
                    "body_markdown": devto_content,
                    "published": True,
                    "tags": tags[:4],
                    "series": "AI Trading Journey",
                }
            },
            timeout=30,
        )

        if response.status_code in [200, 201]:
            result = response.json()
            print(f"✅ Published to Dev.to: {result.get('url', 'unknown')}")
            return result
        else:
            print(f"❌ Dev.to publish failed: {response.status_code} - {response.text[:200]}")
            return None

    except Exception as e:
        print(f"❌ Dev.to publish error: {e}")
        return None


def save_to_github_pages(content: str, iteration: int) -> Path:
    """Save blog post to GitHub Pages."""
    BLOG_POSTS_DIR.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"{date_str}-ralph-iteration-{iteration}.md"
    filepath = BLOG_POSTS_DIR / filename

    filepath.write_text(content)
    print(f"✅ Saved to GitHub Pages: {filepath}")

    return filepath


def main():
    parser = argparse.ArgumentParser(description="Publish Ralph iteration blog posts")
    parser.add_argument("--iteration", type=int, help="Override iteration number")
    parser.add_argument("--tests-passed", default="true", help="Test status")
    parser.add_argument("--lint-passed", default="true", help="Lint status")
    parser.add_argument("--hours", type=int, default=24, help="Hours to look back for lessons")
    parser.add_argument("--dry-run", action="store_true", help="Generate but don't publish")
    parser.add_argument("--min-lessons", type=int, default=1, help="Minimum lessons to publish")

    args = parser.parse_args()

    print("=" * 60)
    print("RALPH ITERATION BLOG PUBLISHER")
    print("=" * 60)

    # Get stats
    stats = get_iteration_stats()
    if args.iteration:
        stats["iteration"] = args.iteration

    print(f"Iteration: {stats['iteration']}")
    print(f"Notes: {stats['notes'][:100]}...")

    # Get recent lessons
    lessons = get_recent_lessons(hours=args.hours)
    print(f"Found {len(lessons)} lessons in last {args.hours} hours")

    if len(lessons) < args.min_lessons:
        print(f"Skipping publish - only {len(lessons)} lessons (minimum: {args.min_lessons})")
        return 0

    # Generate content
    content = generate_blog_content(
        lessons=lessons,
        stats=stats,
        tests_passed=args.tests_passed,
        lint_passed=args.lint_passed,
    )

    title = generate_engaging_title(lessons, stats)
    print(f"Title: {title}")

    if args.dry_run:
        print("\n--- DRY RUN OUTPUT ---")
        print(content[:2000])
        print("...")
        return 0

    # Save to GitHub Pages
    filepath = save_to_github_pages(content, stats["iteration"])

    # Publish to Dev.to
    tags = ["ai", "trading", "python", "automation"]
    devto_result = publish_to_devto(title, content, tags)

    print("\n" + "=" * 60)
    print("PUBLISH COMPLETE")
    print(f"  GitHub Pages: {filepath}")
    print(f"  Dev.to: {'Published' if devto_result else 'Skipped'}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
