#!/usr/bin/env python3
"""
RLHF Blog Publisher - Human-Engaging Content

NOT bot slop. Real stories, technical depth, personality.
Every post tells what ACTUALLY happened with code and context.
"""

from __future__ import annotations

import json
import os
import re
import subprocess  # nosec B404
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

# Allow `python scripts/...` execution where sys.path[0] == scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.content.blog_seo import (
    canonical_url_for_post_file,
    render_frontmatter,
    truncate_meta_description,
)

ET = ZoneInfo("America/New_York")
REPO_URL = "https://github.com/IgorGanapolsky/trading"
DIAGRAM_BASE_URL = "https://igorganapolsky.github.io/trading/assets"


def get_rlhf_stats() -> dict:
    """Get RLHF feedback statistics."""
    stats_file = Path("data/feedback/stats.json")
    if stats_file.exists():
        with open(stats_file) as f:
            return json.load(f)
    return {"positive": 0, "negative": 0, "total": 0}


def get_model_stats() -> dict:
    """Get Thompson Sampling model stats."""
    model_file = Path("../models/ml/feedback_model.json")
    if model_file.exists():
        with open(model_file) as f:
            return json.load(f)
    return {"alpha": 1, "beta": 1}


def get_equity() -> float:
    """Get current account equity."""
    state_file = Path("data/system_state.json")
    if state_file.exists():
        with open(state_file) as f:
            state = json.load(f)
            paper = state.get("paper_account", {})
            return paper.get("equity", paper.get("current_equity", 100000))
    return 100000


def get_recent_commits() -> list[str]:
    """Get recent commits for context."""
    try:
        result = subprocess.run(  # nosec B603 B607 - safe git command, no untrusted input
            ["git", "log", "--oneline", "-5", "--format=%s"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip().split("\n")
    except Exception:
        return []


def generate_engaging_content(
    title: str,
    signal: str,
    intensity: float,
    context: str,
    stats: dict,
    model: dict,
    equity: float,
) -> str:
    """Generate engaging blog content from actual context, not hardcoded stories."""

    positive = stats.get("positive", 0)
    negative = stats.get("negative", 0)
    total = stats.get("total", 0)
    alpha = model.get("alpha", 1)
    beta = model.get("beta", 1)
    thompson_success_rate = (alpha / (alpha + beta)) * 100 if (alpha + beta) > 0 else 50
    observed_success_rate = ((positive / total) * 100) if total > 0 else 0

    commits = get_recent_commits()
    recent_work = commits[0] if commits else "system improvements"

    # Build story from ACTUAL context, not keyword-matched templates
    if signal == "positive":
        story = _build_positive_story(context, recent_work, total, thompson_success_rate)
        technical = _build_technical_section(commits, model)
    else:
        story = _build_negative_story(context, recent_work, negative)
        technical = _build_correction_section(context, model, alpha, beta)

    # Build the post
    diagram_section = generate_diagram_section(context)

    now = datetime.now(ET)
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    date_str = now.strftime("%Y-%m-%d")

    description = truncate_meta_description(
        f"{title} — RLHF update from our AI trading system. {context[:80]}",
        max_chars=160,
    )

    questions = _generate_contextual_faq(signal, context, thompson_success_rate, observed_success_rate, total)

    frontmatter = render_frontmatter(
        {
            "layout": "post",
            "title": title,
            "description": description,
            "date": timestamp,
            "last_modified_at": date_str,
            "image": "/assets/og-image.png",
            "categories": ["rlhf", "trading", "building-in-public"],
            "tags": [signal, "rlhf", "ai-trading", "fintech"],
        },
        questions=questions,
    )

    return (
        frontmatter
        + f"""{story}

## Architecture

{diagram_section}

**Current state**: {positive} positive / {negative} negative = {observed_success_rate:.0f}% observed success rate after {total} signals. Thompson expected success rate: {thompson_success_rate:.0f}%.

## Technical Details

{technical}

---

**Building in public.** {total} feedback signals and counting.

[Source Code]({REPO_URL}) | [Live Dashboard](https://igorganapolsky.github.io/trading/)
"""
    )


def _build_positive_story(context: str, recent_work: str, total: int, win_rate: float) -> str:
    """Build a positive feedback story from actual context."""
    return f"""Something worked: {recent_work.lower()}.

**What happened:** {context}

After {total} feedback signals, the system's success rate sits at {win_rate:.0f}%. Each positive signal reinforces what's working."""


def _build_negative_story(context: str, recent_work: str, negative: int) -> str:
    """Build a negative feedback story from actual context."""
    return f"""Mistake made while working on {recent_work.lower()}.

**What went wrong:** {context}

This is negative signal #{negative}. It gets indexed in RAG so the system sees it before making similar decisions in the future."""


def _build_technical_section(commits: list[str], model: dict) -> str:
    """Build technical section from real commits and model state."""
    alpha = model.get("alpha", 1)
    beta = model.get("beta", 1)

    commit_list = "\n".join(f"- `{c}`" for c in commits[:5]) if commits else "- No recent commits"

    return f"""Recent commits:

{commit_list}

Thompson Sampling state: alpha={alpha}, beta={beta} (Beta-Bernoulli, 30-day decay)."""


def _build_correction_section(context: str, model: dict, alpha: int, beta: int) -> str:
    """Build correction section for negative feedback."""
    return f"""This negative feedback updates the Thompson Sampling model: alpha={alpha}, beta={beta + 1}.

The correction is stored in RAG. Next time a similar situation arises, the system will see this lesson before acting.

Context: {truncate_meta_description(context, max_chars=200)}"""


def _generate_contextual_faq(
    signal: str, context: str, thompson_rate: float, observed_rate: float, total: int
) -> list[dict]:
    """Generate FAQ questions specific to this post's content."""
    ctx_lower = context.lower()

    faqs = [
        {
            "question": "What triggered this update?",
            "answer": truncate_meta_description(context, max_chars=200),
        },
    ]

    if "test" in ctx_lower or "ci" in ctx_lower:
        faqs.append(
            {
                "question": "How many tests does the system have?",
                "answer": "The CI pipeline runs 1300+ tests on every push, covering trading logic, risk management, and data integrity.",
            }
        )
    elif "trade" in ctx_lower or "iron condor" in ctx_lower:
        faqs.append(
            {
                "question": "What trading strategy is being used?",
                "answer": "SPY iron condors with 15-delta wings, 30-45 DTE, $10-wide spreads. Exit at 50% profit or 7 DTE.",
            }
        )
    else:
        faqs.append(
            {
                "question": "How does the feedback system work?",
                "answer": (
                    "Thompson Sampling with a Beta-Bernoulli model. "
                    f"{total} signals captured, {observed_rate:.0f}% observed success, "
                    f"{thompson_rate:.0f}% Thompson expected success."
                ),
            }
        )

    faqs.append(
        {
            "question": "Is this using real money?",
            "answer": "No. All trades are on Alpaca paper trading accounts. No real capital at risk.",
        }
    )

    return faqs


def generate_engaging_title(signal: str, context: str) -> str:
    """Generate a title from actual context, not keyword templates."""
    ctx_clean = context.strip()

    # Truncate at word boundary for title
    if len(ctx_clean) > 60:
        ctx_clean = ctx_clean[:60].rsplit(" ", 1)[0]

    if signal == "positive":
        return f"Win: {ctx_clean}"
    else:
        return f"Lesson: {ctx_clean}"


def select_paperbanana_diagram(context: str) -> tuple[str, str]:
    """Select the most relevant PaperBanana diagram for the blog post."""
    ctx = context.lower()

    if any(k in ctx for k in ("iron condor", "trade", "position", "strike", "delta")):
        return (
            f"{DIAGRAM_BASE_URL}/iron_condor_payoff.png",
            "Iron Condor Payoff: profit zone, breakevens, and probability (PaperBanana)",
        )
    if any(k in ctx for k in ("thompson", "feedback", "rlhf", "sampling")):
        return (
            f"{DIAGRAM_BASE_URL}/thompson_sampling.png",
            "Thompson Sampling: how the system learns from feedback (PaperBanana)",
        )
    if any(k in ctx for k in ("theta", "decay", "dte", "expiration", "exit")):
        return (
            f"{DIAGRAM_BASE_URL}/theta_decay_curve.png",
            "Theta Decay: why we exit at 7 DTE (PaperBanana)",
        )
    if any(k in ctx for k in ("rag", "lesson", "knowledge", "retrieval", "memory")):
        return (
            f"{DIAGRAM_BASE_URL}/rag_retrieval_flow.png",
            "RAG Retrieval: how past lessons inform decisions (PaperBanana)",
        )
    if any(k in ctx for k in ("model", "llm", "tars", "gateway", "route", "openrouter")):
        return (
            f"{DIAGRAM_BASE_URL}/llm_gateway_architecture.png",
            "LLM Gateway Architecture (PaperBanana)",
        )
    # Default: feedback pipeline
    return (
        f"{DIAGRAM_BASE_URL}/feedback_pipeline.png",
        "Feedback-Driven Context Pipeline (PaperBanana)",
    )


def generate_diagram_section(context: str) -> str:
    """Generate the architecture diagram section using PaperBanana images."""
    img_url, caption = select_paperbanana_diagram(context)
    return f"![{caption}]({img_url})\n*{caption}*"


def generate_post(signal: str, intensity: float, context: str) -> dict:
    """Generate engaging blog post with real stories."""
    stats = get_rlhf_stats()
    model = get_model_stats()
    equity = get_equity()

    title = generate_engaging_title(signal, context)
    content = generate_engaging_content(title, signal, intensity, context, stats, model, equity)

    return {
        "title": title,
        "content": content,
        "date": datetime.now(ET).strftime("%Y-%m-%d"),
        "tags": [signal, "rlhf", "aitrading", "buildinginpublic"],
        "signal": signal,
        "summary": f"{title} — Building an AI trading system that learns from every decision.",
    }


def save_to_github_pages(post: dict) -> str | None:
    """Save post to GitHub Pages."""
    posts_dir = Path("docs/_posts")
    posts_dir.mkdir(parents=True, exist_ok=True)

    slug = "win" if post["signal"] == "positive" else "lesson"
    filename = f"{post['date']}-rlhf-{slug}.md"
    filepath = posts_dir / filename

    if filepath.exists():
        ts = datetime.now(ET).strftime("%H%M")
        filename = f"{post['date']}-rlhf-{slug}-{ts}.md"
        filepath = posts_dir / filename

    filepath.write_text(post["content"])
    print(f"✅ GitHub Pages: {filepath}")
    return str(filepath)


def publish_to_devto(post: dict, *, canonical_url: str) -> dict | None:
    """Publish to Dev.to with duplicate detection."""
    api_key = os.environ.get("DEVTO_API_KEY") or os.environ.get("DEV_TO_API_KEY")
    if not api_key:
        print("⚠️ DEV_TO_API_KEY not set")
        return None

    # Check for recent duplicates (published in last 2 hours)
    try:
        resp = requests.get(
            "https://dev.to/api/articles/me",
            headers={"api-key": api_key},
            timeout=10,
        )
        if resp.status_code == 200:
            articles = resp.json()
            from datetime import datetime, timedelta

            two_hours_ago = datetime.now() - timedelta(hours=2)
            for article in articles[:10]:  # Check last 10 articles
                pub_date = datetime.fromisoformat(article["published_at"].replace("Z", "+00:00"))
                # Check if same title published in last 2 hours
                if article["title"] == post["title"] and pub_date > two_hours_ago.replace(
                    tzinfo=pub_date.tzinfo
                ):
                    print(
                        f"⚠️ Duplicate detected: '{post['title']}' already published at {article['url']}"
                    )
                    print("   Skipping to prevent spam.")
                    return article
    except Exception as e:
        print(f"⚠️ Duplicate check failed: {e}, proceeding with publish")

    content = re.sub(r"---\n.*?---\n", "", post["content"], flags=re.DOTALL)

    payload = {
        "article": {
            "title": post["title"],
            "body_markdown": content,
            "published": True,
            "tags": post["tags"][:4],
            "series": "AI Trading RLHF",
            "canonical_url": canonical_url,
        }
    }

    try:
        resp = requests.post(
            "https://dev.to/api/articles",
            headers={"api-key": api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        if resp.status_code == 201:
            result = resp.json()
            print(f"✅ Dev.to: {result.get('url')}")
            return result
        else:
            print(f"⚠️ Dev.to failed: {resp.status_code} - {resp.text[:100]}")
            return None
    except Exception as e:
        print(f"⚠️ Dev.to error: {e}")
        return None


def post_to_linkedin_direct(post: dict, link_url: str) -> bool:
    """Post to LinkedIn using the LinkedIn API via publish_linkedin.py."""
    import subprocess

    try:
        result = subprocess.run(  # nosec B603 B607 - safe call with no untrusted input
            [
                "python3",
                str(Path(__file__).parent / "publish_linkedin.py"),
                "--signal",
                post["signal"],
                "--context",
                post["summary"][:200],
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            return True
        else:
            print(f"⚠️ LinkedIn posting failed: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"⚠️ LinkedIn error: {e}")
        return False


def post_to_twitter_api(post: dict, link_url: str) -> bool:
    """Post to X.com using Twitter API v2."""
    import subprocess

    # Call publish_twitter.py
    try:
        result = subprocess.run(  # nosec B603 B607 - safe call with no untrusted input
            [
                "python3",
                str(Path(__file__).parent / "publish_twitter.py"),
                "--signal",
                post["signal"],
                "--title",
                post["title"],
                "--url",
                link_url,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            return True
        else:
            detail = (result.stderr or result.stdout or "").strip()
            print(f"⚠️ X.com posting failed: {detail[:300]}")
            return False
    except Exception as e:
        print(f"⚠️ X.com error: {e}")
        return False


def queue_for_linkedin_backup(post: dict, link_url: str) -> bool:
    """BACKUP: Queue for LinkedIn if direct posting fails."""
    queue_file = Path(__file__).parent.parent.parent / "docs" / "linkedin_post_queue.json"

    if not queue_file.exists():
        return False

    link = link_url
    emoji = "✅" if post["signal"] == "positive" else "📚"

    content = f"""{emoji} {post["title"]}

{post["summary"]}

#AITrading #RLHF #BuildingInPublic #FinTech

{link}"""

    try:
        with open(queue_file) as f:
            data = json.load(f)

        next_id = max([item.get("id", 0) for item in data.get("queue", [])], default=0) + 1

        data["queue"].append(
            {
                "id": next_id,
                "title": post["title"],
                "status": "pending",
                "content": content,
                "source": "rlhf_auto",
                "signal": post["signal"],
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "tags": ["AITrading", "RLHF", "BuildingInPublic", "FinTech"],
            }
        )

        with open(queue_file, "w") as f:
            json.dump(data, f, indent=2)

        print(f"✅ LinkedIn: Queued (ID: {next_id})")
        return True
    except Exception as e:
        print(f"⚠️ LinkedIn queue error: {e}")
        return False


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--signal", required=True, choices=["positive", "negative"])
    parser.add_argument("--intensity", type=float, default=0.5)
    parser.add_argument("--context", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"📝 RLHF Blog: {args.signal} ({args.intensity})")

    post = generate_post(args.signal, args.intensity, args.context)
    print(f"   Title: {post['title']}")

    if args.dry_run:
        print("\n--- DRY RUN ---")
        print(post["content"][:500])
        return 0

    gh_path = save_to_github_pages(post)
    if not gh_path:
        print("❌ Could not save GitHub Pages post")
        return 1

    canonical_url = canonical_url_for_post_file(gh_path)
    devto_result = publish_to_devto(post, canonical_url=canonical_url)
    devto_url = devto_result.get("url") if devto_result else None

    # Post directly to LinkedIn (browser automation)
    print("\n📤 Posting to LinkedIn...")
    linkedin_ok = post_to_linkedin_direct(post, canonical_url)
    if not linkedin_ok:
        queue_for_linkedin_backup(post, canonical_url)

    # Post to X.com (API)
    print("\n📤 Posting to X.com...")
    twitter_ok = post_to_twitter_api(post, canonical_url)

    # Count successful platforms
    platforms = []
    if gh_path:
        platforms.append("GitHub Pages")
    if devto_result:
        platforms.append(f"Dev.to ({devto_url})")
    if linkedin_ok:
        platforms.append("LinkedIn")
    if twitter_ok:
        platforms.append("X.com")

    print(f"\n✅ Published to {len(platforms)}/4 platforms:")
    for p in platforms:
        print(f"   - {p}")

    if not linkedin_ok:
        print("   ⚠️  LinkedIn posting failed")
    if not twitter_ok:
        print("   ⚠️  X.com posting failed")

    return 0


if __name__ == "__main__":
    sys.exit(main())
