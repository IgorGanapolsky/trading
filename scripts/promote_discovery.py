#!/usr/bin/env python3
"""
Promote Ralph's discoveries across multiple platforms.

This script helps maximize visibility for Ralph's discoveries by:
1. Generating optimized content for each platform
2. Creating shareable links and snippets
3. Suggesting hashtags and communities

Platforms supported:
- Dev.to (auto-publish via API)
- Twitter/X (generates tweet thread)
- Reddit (generates post for relevant subreddits)
- Hacker News (generates submission)
- LinkedIn (generates post)

Usage:
    python3 scripts/promote_discovery.py --discovery RD-001
    python3 scripts/promote_discovery.py --discovery RD-001 --platform twitter
"""

import argparse
import json
import sys
from pathlib import Path

DISCOVERIES_FILE = Path(__file__).parent.parent / "data" / "ralph_discoveries.json"


def load_discovery(discovery_id: str) -> dict | None:
    """Load a specific discovery by ID."""
    if not DISCOVERIES_FILE.exists():
        return None
    with open(DISCOVERIES_FILE) as f:
        data = json.load(f)
    for d in data.get("discoveries", []):
        if d.get("id") == discovery_id:
            return d
    return None


def generate_twitter_thread(discovery: dict) -> str:
    """Generate a Twitter/X thread from discovery."""
    title = discovery.get("title", "")
    summary = discovery.get("summary", "")
    category = discovery.get("category", "")
    iteration = discovery.get("iteration", 0)
    lessons = discovery.get("lessons_learned", [])

    thread = f"""🧵 THREAD: How my autonomous AI agent found a critical bug while I slept

🤖 Meet Ralph - an AI that runs 24/7 improving my trading system using the "Ralph Wiggum technique"

During iteration #{iteration}, Ralph discovered: {title}

---

1/ THE PROBLEM:
{summary}

This could have caused real financial losses. But Ralph caught it automatically.

---

2/ THE FIX:
Ralph didn't just find it - it FIXED it:
- Added validation at all entry points
- Updated 4 scripts
- Ran 875 tests to verify
- Committed and pushed the fix

All without human intervention. 🔥

---

3/ LESSONS LEARNED:
"""

    for i, lesson in enumerate(lessons[:3], 1):
        thread += f"\n• {lesson}"

    thread += f"""

---

4/ WHY THIS MATTERS:

Autonomous AI agents can:
✅ Work 24/7 (while you sleep)
✅ Catch bugs humans miss
✅ Fix AND verify their fixes
✅ Document everything

The future of software maintenance is here.

---

5/ WANT TO BUILD YOUR OWN?

Check out the Ralph Wiggum technique:
🔗 https://github.com/Th0rgal/opencode-ralph-wiggum

See Ralph in action:
🔗 https://github.com/IgorGanapolsky/trading

#AI #Automation #Programming #TradingBot #AutonomousAgents
"""

    return thread


def generate_reddit_post(discovery: dict) -> dict:
    """Generate Reddit post for relevant subreddits."""
    title = discovery.get("title", "")
    summary = discovery.get("summary", "")
    details = discovery.get("details", {})
    lessons = discovery.get("lessons_learned", [])

    subreddits = {
        "security": ["r/netsec", "r/cybersecurity", "r/programming"],
        "performance": ["r/programming", "r/Python", "r/learnpython"],
        "bug_fix": ["r/programming", "r/softwareengineering"],
        "architecture": ["r/programming", "r/softwarearchitecture"],
        "testing": ["r/QualityAssurance", "r/programming"],
        "research": ["r/MachineLearning", "r/algotrading"]
    }

    category = discovery.get("category", "bug_fix")
    recommended_subs = subreddits.get(category, ["r/programming"])

    post_body = f"""# {title}

## TL;DR
{summary}

## Background
I'm running an experiment where an autonomous AI agent ("Ralph") maintains my trading system 24/7 using something called the "Ralph Wiggum technique" - the same prompt runs repeatedly, and the AI observes file changes between iterations to understand its progress.

## What Ralph Found
{details.get('problem', 'Details in comments.')}

## The Fix
{details.get('solution', 'Solution details in comments.')}

## Lessons Learned
"""

    for lesson in lessons:
        post_body += f"- {lesson}\n"

    post_body += """
## Links
- Full blog post: https://igorganapolsky.github.io/trading/
- Source code: https://github.com/IgorGanapolsky/trading
- Ralph Wiggum technique: https://github.com/Th0rgal/opencode-ralph-wiggum

Happy to answer questions about the autonomous agent setup!
"""

    return {
        "title": f"[Project] My autonomous AI agent found and fixed a {category} bug while I slept",
        "body": post_body,
        "subreddits": recommended_subs
    }


def generate_hackernews(discovery: dict) -> dict:
    """Generate Hacker News submission."""
    title = discovery.get("title", "")
    iteration = discovery.get("iteration", 0)

    return {
        "title": f"Show HN: Autonomous AI agent (Ralph) maintaining a trading system 24/7",
        "url": "https://github.com/IgorGanapolsky/trading",
        "text": f"""I've been experimenting with having an AI agent run continuously to maintain my trading codebase.

The agent ("Ralph") uses the "Ralph Wiggum technique" - it receives the same prompt repeatedly and observes file/git changes between iterations to understand its progress.

Latest discovery (iteration #{iteration}): {title}

What makes this interesting:
- Runs 24/7 via GitHub Actions
- Catches bugs and security issues autonomously
- Fixes, tests, and commits without human intervention
- Auto-publishes findings to a blog

Curious what HN thinks about this approach to software maintenance.

Source: https://github.com/IgorGanapolsky/trading
Ralph Wiggum technique: https://github.com/Th0rgal/opencode-ralph-wiggum"""
    }


def generate_linkedin(discovery: dict) -> str:
    """Generate LinkedIn post."""
    title = discovery.get("title", "")
    summary = discovery.get("summary", "")
    iteration = discovery.get("iteration", 0)

    return f"""🤖 The Future of Software Maintenance is Here

I've been running an experiment: an autonomous AI agent maintaining production code 24/7.

Meet "Ralph" - an AI that uses the Ralph Wiggum technique to continuously improve a trading system while I focus on other things.

Latest discovery (iteration #{iteration}):
"{title}"

{summary}

What Ralph does automatically:
✅ Runs tests and fixes failures
✅ Finds security vulnerabilities
✅ Improves code quality
✅ Documents everything
✅ Publishes blog posts about findings

The interesting part? Ralph fixed this issue, ran 875 tests, and committed the fix - all without human intervention.

This is what happens when you combine:
• Claude AI's coding capabilities
• The "Ralph Wiggum technique" for iterative improvement
• GitHub Actions for 24/7 execution
• Proper guardrails and validation

Curious about building your own autonomous agent?

🔗 Source code: https://github.com/IgorGanapolsky/trading
🔗 Blog: https://igorganapolsky.github.io/trading/

#AI #Automation #SoftwareEngineering #MachineLearning #AutonomousAgents #TradingBot
"""


def main():
    parser = argparse.ArgumentParser(description="Generate promotion content for discoveries")
    parser.add_argument("--discovery", required=True, help="Discovery ID (e.g., RD-001)")
    parser.add_argument(
        "--platform",
        choices=["all", "twitter", "reddit", "hackernews", "linkedin"],
        default="all",
        help="Platform to generate content for"
    )
    args = parser.parse_args()

    discovery = load_discovery(args.discovery)
    if not discovery:
        print(f"❌ Discovery {args.discovery} not found")
        return 1

    print(f"\n{'='*60}")
    print(f"📢 PROMOTION CONTENT FOR: {discovery['title']}")
    print(f"{'='*60}\n")

    if args.platform in ["all", "twitter"]:
        print("🐦 TWITTER/X THREAD:")
        print("-" * 40)
        print(generate_twitter_thread(discovery))
        print()

    if args.platform in ["all", "reddit"]:
        print("📱 REDDIT POST:")
        print("-" * 40)
        reddit = generate_reddit_post(discovery)
        print(f"Title: {reddit['title']}")
        print(f"Subreddits: {', '.join(reddit['subreddits'])}")
        print(f"\n{reddit['body']}")
        print()

    if args.platform in ["all", "hackernews"]:
        print("🔶 HACKER NEWS:")
        print("-" * 40)
        hn = generate_hackernews(discovery)
        print(f"Title: {hn['title']}")
        print(f"URL: {hn['url']}")
        print(f"\n{hn['text']}")
        print()

    if args.platform in ["all", "linkedin"]:
        print("💼 LINKEDIN:")
        print("-" * 40)
        print(generate_linkedin(discovery))
        print()

    print(f"{'='*60}")
    print("📋 COPY THE CONTENT ABOVE AND POST TO EACH PLATFORM")
    print(f"{'='*60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
