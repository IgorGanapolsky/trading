#!/usr/bin/env python3
"""
Ralph Blog Publisher - Auto-publish discoveries from Ralph Loop iterations.

Generates engaging blog posts about AI-driven bug fixes, improvements, and
discoveries. Publishes to both GitHub Pages and Dev.to.

Usage:
    python scripts/ralph_blog_publisher.py --discovery "Fixed flaky test" --details "..."
    python scripts/ralph_blog_publisher.py --from-results ralph_output.json
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
DOCS_DIR = Path(__file__).parent.parent / "docs"
DISCOVERIES_DIR = DOCS_DIR / "_discoveries"
DATA_DIR = Path(__file__).parent.parent / "data"


def log(message: str, level: str = "INFO"):
    """Log with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


def determine_category(discovery: str, details: str = "") -> tuple[str, str, list[str]]:
    """Determine the category and emoji for the discovery."""
    text = (discovery + " " + details).lower()

    categories = {
        "bug_fix": {
            "keywords": ["fix", "bug", "error", "fail", "broken", "crash", "exception"],
            "emoji": "🐛",
            "title_prefix": "Bug Squashed",
            "tags": ["bugfix", "debugging", "python"],
        },
        "performance": {
            "keywords": ["performance", "speed", "fast", "slow", "optimize", "efficient"],
            "emoji": "⚡",
            "title_prefix": "Performance Boost",
            "tags": ["performance", "optimization", "python"],
        },
        "test": {
            "keywords": ["test", "pytest", "coverage", "assertion", "mock"],
            "emoji": "✅",
            "title_prefix": "Test Suite Improved",
            "tags": ["testing", "pytest", "tdd"],
        },
        "security": {
            "keywords": ["security", "vulnerability", "auth", "credential", "secret"],
            "emoji": "🔒",
            "title_prefix": "Security Enhancement",
            "tags": ["security", "python", "devops"],
        },
        "refactor": {
            "keywords": ["refactor", "clean", "simplify", "restructure", "organize"],
            "emoji": "🔧",
            "title_prefix": "Code Refactored",
            "tags": ["refactoring", "cleancode", "python"],
        },
        "feature": {
            "keywords": ["feature", "add", "new", "implement", "create"],
            "emoji": "✨",
            "title_prefix": "New Feature",
            "tags": ["feature", "python", "ai"],
        },
        "ci_cd": {
            "keywords": ["ci", "cd", "workflow", "github action", "deploy", "pipeline"],
            "emoji": "🚀",
            "title_prefix": "CI/CD Improved",
            "tags": ["cicd", "githubactions", "devops"],
        },
        "ai_ml": {
            "keywords": ["ai", "ml", "model", "training", "inference", "claude", "llm"],
            "emoji": "🤖",
            "title_prefix": "AI Enhancement",
            "tags": ["ai", "machinelearning", "llm"],
        },
    }

    for cat_name, cat_info in categories.items():
        for keyword in cat_info["keywords"]:
            if keyword in text:
                return cat_info["emoji"], cat_info["title_prefix"], cat_info["tags"]

    # Default
    return "💡", "Discovery", ["programming", "python", "automation"]


def generate_engaging_intro(discovery: str, category_emoji: str) -> str:
    """Generate an engaging introduction paragraph."""
    intros = [
        f"Our autonomous AI (Ralph) was hard at work overnight, and look what it found! {category_emoji}",
        f"While humans slept, our AI CTO (Ralph) discovered something interesting... {category_emoji}",
        f"The machines are learning! Here's what our AI-powered CI discovered today: {category_emoji}",
        f"24/7 autonomous iteration pays off - Ralph just made this improvement: {category_emoji}",
        f"Self-healing CI in action! Our AI caught and fixed this issue automatically: {category_emoji}",
    ]

    # Pick based on discovery hash for consistency
    idx = hash(discovery) % len(intros)
    return intros[idx]


def generate_blog_post(
    discovery: str,
    details: str = "",
    files_changed: list[str] | None = None,
    iterations: int = 1,
    cost_usd: float = 0.0,
    termination_reason: str = "",
) -> str:
    """Generate an engaging Medium-style blog post about a Ralph discovery."""
    today = datetime.now()
    formatted_date = today.strftime("%B %d, %Y")
    post_date = today.strftime("%Y-%m-%d")

    emoji, title_prefix, tags = determine_category(discovery, details)
    intro = generate_engaging_intro(discovery, emoji)

    # Build files changed section
    files_section = ""
    if files_changed:
        files_section = "\n## Files Modified\n\n"
        for f in files_changed[:10]:  # Limit to 10
            files_section += f"- `{f}`\n"

    # Build the technical details section
    tech_details = ""
    if details:
        # Clean up the details (remove excessive whitespace, format code blocks)
        cleaned = details.strip()
        if "```" not in cleaned and len(cleaned) > 100:
            # Wrap long details in code block
            tech_details = f"\n## Technical Details\n\n```\n{cleaned[:2000]}\n```\n"
        else:
            tech_details = f"\n## Technical Details\n\n{cleaned[:2000]}\n"

    # Build iteration stats
    stats_section = f"""
## Ralph Loop Stats

| Metric | Value |
|--------|-------|
| **Iterations** | {iterations} |
| **API Cost** | ${cost_usd:.3f} |
| **Outcome** | {termination_reason or 'Success'} |
| **Timestamp** | {today.strftime("%Y-%m-%d %H:%M UTC")} |
"""

    # Main blog post
    post = f"""---
layout: post
title: "{emoji} {title_prefix}: {discovery[:60]}"
date: {post_date}
category: ralph-discoveries
tags: {tags}
---

# {emoji} {title_prefix}: {discovery}

*{formatted_date}*

---

{intro}

## What Ralph Found

**Discovery:** {discovery}

{tech_details}
{files_section}
{stats_section}

## Why This Matters

This improvement was made **completely autonomously** by our AI-powered CI system:

1. **Ralph Loop** detected an issue (failing tests, lint errors, or improvement opportunity)
2. **Claude API** analyzed the problem and generated a fix
3. **Automated testing** verified the fix worked
4. **Auto-commit** pushed the change to main
5. **This blog post** was auto-generated to share the discovery

### The Power of Autonomous AI Coding

This is what 24/7 AI-powered development looks like. While the team sleeps, Ralph:

- 🔍 Monitors for issues every 6 hours
- 🧠 Uses Claude to understand and fix problems
- ✅ Runs comprehensive test suites
- 📝 Documents discoveries automatically
- 💰 Tracks costs (this fix cost just ${cost_usd:.3f}!)

## How We Built Ralph

Ralph implements the [Ralph Wiggum methodology](https://github.com/Th0rgal/opencode-ralph-wiggum):

```python
# Simplified Ralph Loop
while not tests_pass and iterations < max_iterations:
    response = claude_api.fix(failure_context)
    apply_changes(response)
    tests_pass = run_pytest()
    iterations += 1
```

Key features:
- **Struggle Detection**: Stops if AI gets stuck (saves API costs)
- **Cost Budgeting**: Max $5 per run to prevent runaway spending
- **Auto-commits**: Changes are committed and pushed automatically
- **Self-documentation**: Every fix generates a blog post (like this one!)

---

## Try It Yourself

Want to add autonomous AI coding to your project?

```bash
# Install Ralph Loop
pip install anthropic

# Run with your failing tests
python scripts/ralph_loop.py --task fix_tests --max-iterations 5 --max-cost 2.00
```

[View the full source code →](https://github.com/IgorGanapolsky/trading/blob/main/scripts/ralph_loop.py)

---

*This post was auto-generated by Ralph, our AI CTO. Follow our journey at [github.com/IgorGanapolsky/trading](https://github.com/IgorGanapolsky/trading)*

*No humans were involved in creating this blog post.* 🤖
"""
    return post


def save_to_github_pages(content: str, discovery: str) -> Path:
    """Save blog post to GitHub Pages _discoveries collection."""
    DISCOVERIES_DIR.mkdir(parents=True, exist_ok=True)

    # Generate filename from discovery
    today = datetime.now().strftime("%Y-%m-%d")
    slug = re.sub(r"[^a-z0-9]+", "-", discovery.lower())[:50].strip("-")
    filename = f"{today}-{slug}.md"
    filepath = DISCOVERIES_DIR / filename

    with open(filepath, "w") as f:
        f.write(content)

    log(f"Saved to GitHub Pages: {filepath}")
    return filepath


def post_to_devto(content: str, discovery: str, tags: list[str]) -> str | None:
    """Post to Dev.to via API."""
    api_key = os.getenv("DEVTO_API_KEY")
    if not api_key:
        log("DEVTO_API_KEY not set - skipping Dev.to publish", "WARN")
        return None

    if not requests:
        log("requests module not available - skipping Dev.to publish", "WARN")
        return None

    emoji, title_prefix, auto_tags = determine_category(discovery, "")

    # Remove Jekyll front matter for Dev.to
    lines = content.split("\n")
    in_frontmatter = False
    clean_lines = []
    for line in lines:
        if line.strip() == "---":
            in_frontmatter = not in_frontmatter
            continue
        if not in_frontmatter:
            clean_lines.append(line)

    body = "\n".join(clean_lines)

    headers = {"api-key": api_key, "Content-Type": "application/json"}

    # Use first 4 tags (Dev.to limit)
    final_tags = (tags or auto_tags)[:4]

    payload = {
        "article": {
            "title": f"{emoji} {title_prefix}: {discovery[:60]}",
            "body_markdown": body,
            "published": True,
            "tags": final_tags,
            "series": "Ralph Discoveries - AI-Powered Bug Fixes",
            "canonical_url": None,  # Let Dev.to generate
        }
    }

    try:
        resp = requests.post(
            "https://dev.to/api/articles", headers=headers, json=payload, timeout=30
        )

        if resp.status_code in [200, 201]:
            url = resp.json().get("url")
            log(f"Published to Dev.to: {url}")
            return url
        else:
            log(f"Dev.to publish failed: {resp.status_code} - {resp.text[:200]}", "ERROR")
            return None

    except Exception as e:
        log(f"Dev.to error: {e}", "ERROR")
        return None


def parse_ralph_results(results_file: str) -> dict:
    """Parse Ralph loop results JSON file."""
    try:
        with open(results_file) as f:
            return json.load(f)
    except Exception as e:
        log(f"Could not parse results file: {e}", "ERROR")
        return {}


def is_significant_discovery(results: dict) -> bool:
    """Determine if a Ralph result is significant enough to blog about."""
    # Blog about: successful fixes, interesting struggles, any code changes
    if results.get("success"):
        return True
    if results.get("changes_made", 0) > 0:
        return True
    if "struggle" in str(results.get("termination_reason", "")):
        # Only blog about struggles if interesting (not just max iterations)
        reason = results.get("termination_reason", "")
        if "repetitive" in reason or "same_error" in reason:
            return True
    return False


def main():
    """Main entry point for Ralph blog publisher."""
    parser = argparse.ArgumentParser(description="Publish Ralph discoveries to blog")
    parser.add_argument("--discovery", help="Short description of the discovery")
    parser.add_argument("--details", default="", help="Detailed technical information")
    parser.add_argument(
        "--files", nargs="*", default=[], help="List of files changed"
    )
    parser.add_argument(
        "--from-results", help="Path to Ralph results JSON file"
    )
    parser.add_argument(
        "--iterations", type=int, default=1, help="Number of iterations"
    )
    parser.add_argument(
        "--cost", type=float, default=0.0, help="API cost in USD"
    )
    parser.add_argument(
        "--reason", default="", help="Termination reason"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Generate but don't publish"
    )
    parser.add_argument(
        "--force", action="store_true", help="Publish even if not significant"
    )

    args = parser.parse_args()

    # Parse from results file if provided
    if args.from_results:
        results = parse_ralph_results(args.from_results)
        if not results:
            log("No valid results found", "ERROR")
            sys.exit(1)

        # Check significance
        if not args.force and not is_significant_discovery(results):
            log("Discovery not significant enough to blog about")
            sys.exit(0)

        # Extract info from results
        discovery = f"Ralph Loop completed: {results.get('task', 'auto')} task"
        if results.get("success"):
            discovery = f"Successfully fixed {results.get('changes_made', 0)} files"
        elif results.get("termination_reason"):
            discovery = f"Interesting finding: {results.get('termination_reason')}"

        args.discovery = discovery
        args.iterations = results.get("iterations", 1)
        args.cost = results.get("struggle_status", {}).get("estimated_cost_usd", 0.0)
        args.reason = results.get("termination_reason", "")

        # Build details from history
        history = results.get("history", [])
        if history:
            args.details = json.dumps(history[-3:], indent=2)  # Last 3 iterations

    if not args.discovery:
        log("No discovery provided. Use --discovery or --from-results", "ERROR")
        sys.exit(1)

    log(f"Generating blog post: {args.discovery}")

    # Generate the blog post
    content = generate_blog_post(
        discovery=args.discovery,
        details=args.details,
        files_changed=args.files,
        iterations=args.iterations,
        cost_usd=args.cost,
        termination_reason=args.reason,
    )

    if args.dry_run:
        print("\n" + "=" * 70)
        print("DRY RUN - Blog post content:")
        print("=" * 70)
        print(content)
        return

    # Publish
    filepath = save_to_github_pages(content, args.discovery)
    devto_url = post_to_devto(content, args.discovery, [])

    # Output summary
    print("\n" + "=" * 70)
    print("RALPH BLOG PUBLISHED")
    print("=" * 70)
    print(f"GitHub Pages: {filepath}")
    if devto_url:
        print(f"Dev.to: {devto_url}")
    else:
        print("Dev.to: Skipped (no API key or error)")

    # Save record of publication
    record_file = DATA_DIR / "ralph_blog_posts.json"
    try:
        if record_file.exists():
            with open(record_file) as f:
                records = json.load(f)
        else:
            records = []

        records.append({
            "date": datetime.now().isoformat(),
            "discovery": args.discovery,
            "github_pages": str(filepath),
            "devto_url": devto_url,
        })

        with open(record_file, "w") as f:
            json.dump(records[-100:], f, indent=2)  # Keep last 100

    except Exception as e:
        log(f"Could not save record: {e}", "WARN")


if __name__ == "__main__":
    main()
