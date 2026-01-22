#!/usr/bin/env python3
"""
Generate Blog Posts from Ralph's Autonomous Discoveries

This script creates engaging, Medium-style blog posts from Ralph's discoveries
and publishes them to both GitHub Pages and Dev.to.

The posts are written to be interesting for:
- Developers building AI agents
- Traders interested in algorithmic trading
- Anyone curious about autonomous systems

Usage:
    python3 scripts/generate_ralph_discovery_post.py                    # Publish all unpublished
    python3 scripts/generate_ralph_discovery_post.py --discovery RD-001 # Specific discovery
    python3 scripts/generate_ralph_discovery_post.py --dry-run          # Preview without publishing
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

DISCOVERIES_FILE = Path(__file__).parent.parent / "data" / "ralph_discoveries.json"
POSTS_DIR = Path(__file__).parent.parent / "docs" / "_posts"


def load_discoveries() -> dict:
    """Load Ralph's discoveries from JSON file."""
    if not DISCOVERIES_FILE.exists():
        return {"discoveries": []}
    with open(DISCOVERIES_FILE) as f:
        return json.load(f)


def save_discoveries(data: dict) -> None:
    """Save discoveries back to JSON file."""
    with open(DISCOVERIES_FILE, "w") as f:
        json.dump(data, f, indent=2)


def generate_blog_content(discovery: dict) -> str:
    """Generate engaging blog post content from a discovery."""

    category_emojis = {
        "security": "🔒",
        "performance": "⚡",
        "bug_fix": "🐛",
        "data_integrity": "📊",
        "architecture": "🏗️",
        "testing": "🧪",
        "research": "🔬"
    }

    severity_badges = {
        "critical": "🚨 CRITICAL",
        "high": "⚠️ HIGH",
        "medium": "📝 MEDIUM",
        "low": "💡 LOW"
    }

    emoji = category_emojis.get(discovery.get("category", ""), "🤖")
    severity = severity_badges.get(discovery.get("severity", "medium"), "📝 MEDIUM")
    details = discovery.get("details", {})
    metrics_before = discovery.get("metrics_before", {})
    metrics_after = discovery.get("metrics_after", {})
    lessons = discovery.get("lessons_learned", [])

    # Build the blog post
    content = f"""---
layout: post
title: "{emoji} {discovery['title']}"
date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} -0500
categories: [ralph, ai-agent, {discovery.get('category', 'discovery')}]
tags: [autonomous-ai, trading-system, {discovery.get('category', 'discovery')}, ralph-wiggum]
author: Ralph (Autonomous AI Agent)
---

> **{severity}** - Discovered by Ralph during autonomous iteration #{discovery.get('iteration', 'N/A')}

## TL;DR

{discovery.get('summary', 'No summary available.')}

---

## 🤖 How Ralph Found This

I'm Ralph, an autonomous AI agent running the [Ralph Wiggum technique](https://github.com/Th0rgal/opencode-ralph-wiggum) - continuously iterating on this trading system 24/7 to find and fix issues.

During **iteration #{discovery.get('iteration', 'N/A')}**, while performing my routine checks, I discovered something significant that needed immediate attention.

## 🔍 The Problem

{details.get('problem', 'Problem details not available.')}

### Root Cause Analysis

{details.get('root_cause', 'Root cause analysis pending.')}

### Potential Impact

{details.get('impact', 'Impact assessment pending.')}

## 💡 The Solution

{details.get('solution', 'Solution details not available.')}

"""

    # Add files changed if available
    files = details.get('files_changed', [])
    if files:
        content += """### Files Modified

| File | Purpose |
|------|---------|
"""
        for f in files:
            content += f"| `{f}` | Security fix |\n"
        content += "\n"

    # Add metrics comparison
    if metrics_before or metrics_after:
        content += """## 📊 Before vs After

| Metric | Before | After | Change |
|--------|--------|-------|--------|
"""
        all_keys = set(list(metrics_before.keys()) + list(metrics_after.keys()))
        for key in all_keys:
            before_val = metrics_before.get(key, "N/A")
            after_val = metrics_after.get(key, "N/A")
            if isinstance(before_val, (int, float)) and isinstance(after_val, (int, float)):
                change = after_val - before_val
                change_str = f"+{change}" if change > 0 else str(change)
            else:
                change_str = "→"
            content += f"| {key.replace('_', ' ').title()} | {before_val} | {after_val} | {change_str} |\n"
        content += "\n"

    # Add lessons learned
    if lessons:
        content += """## 🎓 Lessons Learned

"""
        for i, lesson in enumerate(lessons, 1):
            content += f"{i}. **{lesson}**\n"
        content += "\n"

    # Add footer
    content += f"""
## 🔗 About This System

This discovery was made by **Ralph**, an autonomous AI agent that continuously monitors and improves an algorithmic trading system. Ralph uses the [Ralph Wiggum technique](https://github.com/Th0rgal/opencode-ralph-wiggum) to iterate autonomously, finding bugs, security issues, and optimization opportunities that humans might miss.

**System Stats:**
- 🔄 Iteration: #{discovery.get('iteration', 'N/A')}
- ✅ Tests: {details.get('tests_affected', 'N/A')} tests, all passing
- 📅 Discovered: {discovery.get('timestamp', 'Unknown')}

---

*This post was automatically generated by Ralph. For more discoveries, follow along on [GitHub](https://github.com/IgorGanapolsky/trading).*

"""
    return content


def generate_devto_content(discovery: dict) -> dict:
    """Generate Dev.to API payload from a discovery."""

    category_tags = {
        "security": ["security", "webdev"],
        "performance": ["performance", "optimization"],
        "bug_fix": ["debugging", "programming"],
        "data_integrity": ["data", "database"],
        "architecture": ["architecture", "bestpractices"],
        "testing": ["testing", "tdd"],
        "research": ["machinelearning", "datascience"]
    }

    base_tags = ["ai", "automation", "python"]
    extra_tags = category_tags.get(discovery.get("category", ""), [])
    tags = (base_tags + extra_tags)[:5]  # Dev.to allows max 5 tags

    # Create Dev.to optimized content
    details = discovery.get("details", {})
    lessons = discovery.get("lessons_learned", [])

    body = f"""
> 🤖 **Discovered by Ralph** - An autonomous AI agent running 24/7

## The Discovery

{discovery.get('summary', '')}

During iteration #{discovery.get('iteration', 'N/A')} of my autonomous maintenance cycle, I found a {discovery.get('severity', 'notable')} issue that needed fixing.

## What Happened

{details.get('problem', 'Details pending.')}

**Root Cause:** {details.get('root_cause', 'Analysis pending.')}

**Impact:** {details.get('impact', 'Assessment pending.')}

## The Fix

{details.get('solution', 'Solution pending.')}

## Key Takeaways

"""
    for lesson in lessons:
        body += f"- {lesson}\n"

    body += """

---

## About Ralph

I'm an autonomous AI agent using the [Ralph Wiggum technique](https://github.com/Th0rgal/opencode-ralph-wiggum) - running continuously to find and fix issues in a live trading system.

**What makes this interesting:**
- 🔄 24/7 autonomous operation
- 🔍 Catches issues humans miss
- 📝 Documents and shares learnings automatically
- 🎯 Zero human intervention required

Follow along for more autonomous AI discoveries!

---

*🤖 Auto-generated by Ralph | [Source Code](https://github.com/IgorGanapolsky/trading)*
"""

    return {
        "article": {
            "title": f"🤖 AI Agent Discovery: {discovery['title']}",
            "body_markdown": body,
            "published": True,
            "tags": tags,
            "series": "Ralph's Autonomous Discoveries"
        }
    }


def publish_to_devto(discovery: dict) -> str | None:
    """Publish discovery to Dev.to and return the URL."""
    if requests is None:
        print("Warning: requests not installed, skipping Dev.to")
        return None

    api_key = os.getenv("DEVTO_API_KEY")
    if not api_key:
        print("Warning: DEVTO_API_KEY not set, skipping Dev.to")
        return None

    payload = generate_devto_content(discovery)

    try:
        response = requests.post(
            "https://dev.to/api/articles",
            json=payload,
            headers={
                "api-key": api_key,
                "Content-Type": "application/json"
            },
            timeout=30
        )

        if response.status_code == 201:
            data = response.json()
            url = data.get("url", "")
            print(f"✅ Published to Dev.to: {url}")
            return url
        else:
            print(f"❌ Dev.to publish failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Dev.to error: {e}")
        return None


def publish_to_github_pages(discovery: dict) -> str | None:
    """Create GitHub Pages blog post and return the path."""
    POSTS_DIR.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    slug = discovery["title"].lower()
    slug = "".join(c if c.isalnum() or c == " " else "" for c in slug)
    slug = slug.replace(" ", "-")[:50]

    filename = f"{date_str}-ralph-discovery-{slug}.md"
    filepath = POSTS_DIR / filename

    content = generate_blog_content(discovery)

    with open(filepath, "w") as f:
        f.write(content)

    print(f"✅ Created GitHub Pages post: {filepath}")
    return str(filepath)


def publish_discovery(discovery: dict, dry_run: bool = False) -> dict:
    """Publish a discovery to all platforms."""
    results = {
        "github_pages": None,
        "devto": None
    }

    if dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN - Would publish:")
        print("=" * 60)
        print(f"Title: {discovery['title']}")
        print(f"Category: {discovery.get('category')}")
        print(f"Severity: {discovery.get('severity')}")
        print("\n--- GitHub Pages Content Preview ---\n")
        print(generate_blog_content(discovery)[:1000] + "...\n")
        return results

    # Publish to GitHub Pages
    gh_path = publish_to_github_pages(discovery)
    if gh_path:
        results["github_pages"] = gh_path

    # Publish to Dev.to
    devto_url = publish_to_devto(discovery)
    if devto_url:
        results["devto"] = devto_url

    return results


def main():
    parser = argparse.ArgumentParser(description="Publish Ralph's discoveries as blog posts")
    parser.add_argument("--discovery", help="Specific discovery ID to publish (e.g., RD-001)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without publishing")
    parser.add_argument("--all", action="store_true", help="Publish all unpublished discoveries")
    args = parser.parse_args()

    data = load_discoveries()
    discoveries = data.get("discoveries", [])

    if not discoveries:
        print("No discoveries found in ralph_discoveries.json")
        return 0

    published_count = 0

    for discovery in discoveries:
        # Skip already published unless specific ID requested
        if discovery.get("blog_published") and not args.discovery:
            continue

        # Filter by specific ID if provided
        if args.discovery and discovery.get("id") != args.discovery:
            continue

        print(f"\n{'=' * 60}")
        print(f"Publishing: {discovery['title']}")
        print(f"{'=' * 60}")

        results = publish_discovery(discovery, dry_run=args.dry_run)

        if not args.dry_run and (results["github_pages"] or results["devto"]):
            # Update discovery with blog URLs
            discovery["blog_published"] = True
            discovery["blog_urls"] = results
            discovery["blog_published_at"] = datetime.now().isoformat()
            published_count += 1

    # Save updated discoveries
    if not args.dry_run and published_count > 0:
        save_discoveries(data)
        print(f"\n✅ Published {published_count} discoveries")

    return 0


if __name__ == "__main__":
    sys.exit(main())
