#!/usr/bin/env python3
"""
Cross-publish a markdown blog post to Dev.to and LinkedIn.

Usage:
    python scripts/cross_publish.py docs/_posts/2026-02-15-my-post.md
    python scripts/cross_publish.py docs/_posts/2026-02-15-my-post.md --dry-run
    python scripts/cross_publish.py docs/_posts/2026-02-15-my-post.md --platform devto
    python scripts/cross_publish.py docs/_posts/2026-02-15-my-post.md --platform linkedin
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import requests
import yaml
from src.content.blog_seo import canonical_url_for_post_file
from src.content.linkedin_posts import build_answer_first_linkedin_post


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter and body from markdown."""
    match = re.match(r"^---\n(.*?)\n---\n(.*)", content, re.DOTALL)
    if not match:
        return {}, content
    fm = yaml.safe_load(match.group(1)) or {}
    body = match.group(2).strip()
    return fm, body


def publish_to_devto(title: str, body: str, tags: list[str], canonical_url: str) -> str | None:
    """Publish article to Dev.to."""
    api_key = os.environ.get("DEVTO_API_KEY") or os.environ.get("DEV_TO_API_KEY")
    if not api_key:
        print("  DEVTO_API_KEY not set, skipping")
        return None

    # Check for duplicates
    try:
        resp = requests.get(
            "https://dev.to/api/articles/me",
            headers={"api-key": api_key},
            timeout=10,
        )
        if resp.status_code == 200:
            for article in resp.json()[:20]:
                if article["title"] == title:
                    url = article["url"]
                    print(f"  Already exists on Dev.to: {url}")
                    return url
    except Exception:
        pass

    payload = {
        "article": {
            "title": title,
            "body_markdown": body,
            "published": True,
            "tags": [re.sub(r"[^a-z0-9]", "", t.lower())[:20] for t in tags[:4]],
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
            url = resp.json().get("url", "")
            print(f"  Dev.to: {url}")
            return url
        else:
            print(f"  Dev.to failed: {resp.status_code} - {resp.text[:200]}")
            return None
    except Exception as e:
        print(f"  Dev.to error: {e}")
        return None


def publish_to_linkedin(
    title: str,
    body: str,
    canonical_url: str,
    *,
    tags: list[str] | None = None,
    question_cluster: str | None = None,
    result_summary: str | None = None,
) -> bool:
    """Publish post to LinkedIn."""
    raw_token = os.environ.get("LINKEDIN_ACCESS_TOKEN") or ""
    token = re.sub(r"\s+", "", raw_token)  # Remove ALL whitespace including internal newlines
    if not token:
        print("  LINKEDIN_ACCESS_TOKEN not set, skipping")
        return False

    # Get user URN
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(
            "https://api.linkedin.com/v2/userinfo",
            headers=headers,
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"  LinkedIn auth failed: {resp.status_code} - {resp.text[:200]}")
            return False
        user_id = resp.json().get("sub")
        if not user_id:
            print("  LinkedIn: no user ID in response")
            return False
        user_urn = f"urn:li:person:{user_id}"
    except Exception as e:
        print(f"  LinkedIn user lookup error: {e}")
        return False

    text = build_answer_first_linkedin_post(
        title=title,
        body_markdown=body,
        canonical_url=canonical_url,
        tags=tags,
        question_cluster=question_cluster,
        result_summary=result_summary,
    )

    payload = {
        "author": user_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "ARTICLE",
                "media": [
                    {
                        "status": "READY",
                        "originalUrl": canonical_url,
                        "title": {"text": title},
                    }
                ],
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }

    try:
        resp = requests.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0",
            },
            json=payload,
            timeout=30,
        )
        if resp.status_code == 201:
            print("  LinkedIn: posted successfully")
            return True
        else:
            print(f"  LinkedIn failed: {resp.status_code} - {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"  LinkedIn error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Cross-publish markdown post to Dev.to and LinkedIn"
    )
    parser.add_argument("file", help="Path to markdown post file")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, don't publish")
    parser.add_argument("--platform", choices=["devto", "linkedin", "all"], default="all")
    parser.add_argument(
        "--question-cluster",
        default="",
        help="Primary query cluster this post answers (used for LinkedIn formatting).",
    )
    parser.add_argument(
        "--result-summary",
        default="",
        help="Optional explicit result line for LinkedIn post formatting.",
    )
    args = parser.parse_args()

    filepath = Path(args.file)
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return 1

    content = filepath.read_text()
    fm, body = parse_frontmatter(content)

    title = fm.get("title", filepath.stem)
    tags = fm.get("tags", fm.get("categories", ["ai", "trading"]))
    canonical_url = fm.get("canonical_url", "")
    if not canonical_url:
        try:
            canonical_url = canonical_url_for_post_file(filepath)
        except ValueError:
            slug = filepath.stem.split("-", 3)[-1] if "-" in filepath.stem else filepath.stem
            canonical_url = f"https://igorganapolsky.github.io/trading/{slug}/"

    print(f"Title: {title}")
    print(f"Tags: {tags}")
    print(f"Canonical: {canonical_url}")
    print(f"Body: {len(body)} chars")
    print()

    if args.dry_run:
        print("--- DRY RUN (not publishing) ---")
        if args.platform in ("linkedin", "all"):
            linkedin_preview = build_answer_first_linkedin_post(
                title=title,
                body_markdown=body,
                canonical_url=canonical_url,
                tags=tags if isinstance(tags, list) else None,
                question_cluster=args.question_cluster or fm.get("question_cluster"),
                result_summary=args.result_summary or fm.get("result_summary"),
            )
            print("\nLinkedIn preview:\n")
            print(linkedin_preview)
        else:
            print(body[:500])
        return 0

    results = {}

    if args.platform in ("devto", "all"):
        print("Publishing to Dev.to...")
        results["devto"] = publish_to_devto(title, body, tags, canonical_url)

    if args.platform in ("linkedin", "all"):
        print("Publishing to LinkedIn...")
        results["linkedin"] = publish_to_linkedin(
            title,
            body,
            canonical_url,
            tags=tags if isinstance(tags, list) else None,
            question_cluster=args.question_cluster or fm.get("question_cluster"),
            result_summary=args.result_summary or fm.get("result_summary"),
        )

    print()
    success = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"Published to {success}/{total} platforms")

    return 0 if success > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
