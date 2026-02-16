#!/usr/bin/env python3
"""
Blog Post Generator - Two-Stage Approach (Instacart-Inspired)

Stage 1: Fast intent classification (<100ms)
Stage 2: Specialized narrative generation (<1s)

Total: <1 second vs 3-5 seconds monolithic approach

Inspired by Instacart's "brownie recipe problem" solution:
- Large model understands intent
- Small specialized models execute
- Fine-grained context per intent type
"""

import subprocess  # nosec B404

from blog_intent_classifier import IntentContext, classify_intent, extract_context
from blog_narrative_generators import generate_narrative


def get_recent_commits() -> list[str]:
    """Get last 5 commits for context."""
    try:
        result = subprocess.run(  # nosec B603 B607 - safe git command
            ["git", "log", "--oneline", "-5", "--format=%s"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip().split("\n") if result.returncode == 0 else []
    except Exception:
        return []


def generate_headline(ctx: IntentContext) -> str:
    """
    Generate engaging headline following 2026 best practices.

    Optimized per intent type for better SEO and engagement.
    """
    headlines = {
        "pivot": "When {} Fails, Pivot Fast",
        "prevention": "How I Fixed {} (The Prevention Way)",
        "meta": "Why Your Blog Posts Read Like Bot Slop (And How to Fix It)",
        "guardrail": "The Test That Saved Me $5K",
        "learning": "What I Learned: {}",
        "failure": "I Screwed Up: {}",
        "default": "Small Win: {}",
    }

    template = headlines.get(ctx.intent.value, headlines["default"])

    # Extract key phrase from problem
    if ctx.intent.value == "pivot":
        key = ctx.problem.split()[0:3]  # First 3 words
        return template.format(" ".join(key))
    elif ctx.intent.value in ("prevention", "failure", "default"):
        return template.format(ctx.problem[:50])
    else:
        return template


def generate_blog_post(signal: str, context: str) -> dict:
    """
    Two-stage blog generation (Instacart-inspired).

    Stage 1: Classify intent + extract fine-grained context (<100ms)
    Stage 2: Route to specialized generator (<1s)
    """

    # Get recent commits for context
    commits = get_recent_commits()

    # STAGE 1: Fast intent classification
    intent = classify_intent(signal, context, commits)

    # STAGE 2: Extract fine-grained context (the "brownie recipe problem" solution)
    ctx = extract_context(signal, context, commits, intent)

    # STAGE 3: Route to specialized generator
    content = generate_narrative(ctx)
    headline = generate_headline(ctx)

    return {
        "title": headline,
        "content": content,
        "signal": signal,
        "context": context,
        "tags": [signal, "rlhf", "aitrading", "buildinginpublic"],
        "intent": ctx.intent.value,  # For analytics/debugging
    }


if __name__ == "__main__":
    # Test all story types
    test_cases = [
        ("positive", "browser automation failed, switched to API"),
        ("positive", "duplicate blog posts - added detection"),
        ("negative", "bot slop - templates creating generic content"),
        ("positive", "tests passing - caught position sizing bug"),
    ]

    for signal, context in test_cases:
        print("\n" + "=" * 60)
        post = generate_blog_post(signal, context)
        print(f"Intent: {post['intent']}")
        print(f"Title: {post['title']}")
        print(f"\n{post['content'][:300]}...")
        print("=" * 60)
