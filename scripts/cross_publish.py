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
from urllib.parse import urlparse

import requests
import yaml
from scripts.publish_twitter import (
    generate_twitter_post,
    missing_credential_names,
    post_to_twitter,
    resolve_credentials,
)

PAGES_SITE_BASE_URL = "https://igorganapolsky.github.io"


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter and body from markdown."""
    match = re.match(r"^---\n(.*?)\n---\n(.*)", content, re.DOTALL)
    if not match:
        return {}, content
    fm = yaml.safe_load(match.group(1)) or {}
    body = match.group(2).strip()
    return fm, body


def _site_base_from_canonical(canonical_url: str) -> str:
    parsed = urlparse(canonical_url.strip())
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return PAGES_SITE_BASE_URL


def absolutize_site_relative_urls(body: str, canonical_url: str) -> str:
    """Convert site-relative asset URLs to absolute URLs for external platforms."""
    site_base = _site_base_from_canonical(canonical_url)
    converted = re.sub(
        r"\]\((/(?!/)[^)]+)\)",
        lambda m: f"]({site_base}{m.group(1)})",
        body,
    )
    converted = re.sub(
        r'src="(/(?!/)[^"]+)"',
        lambda m: f'src="{site_base}{m.group(1)}"',
        converted,
    )
    return converted


def _update_devto_article(
    *,
    api_key: str,
    article_id: int,
    title: str,
    body: str,
    tags: list[str],
    canonical_url: str,
) -> str | None:
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
        resp = requests.put(
            f"https://dev.to/api/articles/{article_id}",
            headers={"api-key": api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        if resp.status_code == 200:
            url = resp.json().get("url", "")
            print(f"  Dev.to updated: {url}")
            return url
        print(f"  Dev.to update failed: {resp.status_code} - {resp.text[:200]}")
    except Exception as e:
        print(f"  Dev.to update error: {e}")
    return None


def publish_to_devto(title: str, body: str, tags: list[str], canonical_url: str) -> str | None:
    """Publish article to Dev.to."""
    api_key = os.environ.get("DEVTO_API_KEY") or os.environ.get("DEV_TO_API_KEY")
    if not api_key:
        print("  DEVTO_API_KEY not set, skipping")
        return None

    # Dev.to cannot resolve /trading/... site-relative links from markdown.
    body = absolutize_site_relative_urls(body, canonical_url)

    # Check for duplicates
    try:
        resp = requests.get(
            "https://dev.to/api/articles/me",
            headers={"api-key": api_key},
            timeout=10,
        )
        if resp.status_code == 200:
            for article in resp.json()[:20]:
                if article.get("title") == title or str(article.get("canonical_url") or "").strip() == canonical_url:
                    article_id = article.get("id")
                    if isinstance(article_id, int):
                        updated_url = _update_devto_article(
                            api_key=api_key,
                            article_id=article_id,
                            title=title,
                            body=body,
                            tags=tags,
                            canonical_url=canonical_url,
                        )
                        if updated_url:
                            return updated_url
                    url = article.get("url", "")
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
        elif resp.status_code == 422 and "Canonical url has already been taken" in resp.text:
            # Canonical URL uniqueness means this post is already published.
            # Resolve existing URL so callers can treat this as success.
            try:
                existing = requests.get(
                    "https://dev.to/api/articles/me",
                    headers={"api-key": api_key},
                    timeout=15,
                )
                if existing.status_code == 200:
                    for article in existing.json()[:100]:
                        if str(article.get("canonical_url") or "").strip() == canonical_url:
                            article_id = article.get("id")
                            if isinstance(article_id, int):
                                updated_url = _update_devto_article(
                                    api_key=api_key,
                                    article_id=article_id,
                                    title=title,
                                    body=body,
                                    tags=tags,
                                    canonical_url=canonical_url,
                                )
                                if updated_url:
                                    return updated_url
                            url = str(article.get("url") or canonical_url)
                            print(f"  Dev.to (already published): {url}")
                            return url
            except Exception:
                pass
            print(f"  Dev.to (already published): {canonical_url}")
            return canonical_url
        else:
            print(f"  Dev.to failed: {resp.status_code} - {resp.text[:200]}")
            return None
    except Exception as e:
        print(f"  Dev.to error: {e}")
        return None


def publish_to_linkedin(title: str, body: str, canonical_url: str) -> bool:
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

    # Build concise post text (LinkedIn max ~3000 chars)
    # Use first 2 paragraphs of body + link
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip() and not p.startswith("```")]
    excerpt = "\n\n".join(paragraphs[:3])[:1500]

    text = f"{title}\n\n{excerpt}\n\nRead more: {canonical_url}\n\n#AITrading #BuildingInPublic #FinTech #MachineLearning"

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


def publish_to_x(title: str, canonical_url: str, *, dry_run: bool = False) -> bool:
    """Publish concise post to X.com."""
    creds = resolve_credentials()
    missing = missing_credential_names(creds)
    if missing:
        print(f"  X skipped: missing credentials ({', '.join(missing)})")
        return False

    text = generate_twitter_post("positive", title, canonical_url)
    return post_to_twitter(text, dry_run=dry_run)


def submit_to_search_console(canonical_url: str) -> bool:
    """Submit URL to Google Search Console for indexing."""
    if not os.environ.get("GOOGLE_SEARCH_CONSOLE_KEY"):
        print("  Search Console: skipped (GOOGLE_SEARCH_CONSOLE_KEY not set)")
        return False

    try:
        # Import inline to avoid hard dependency
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).parent / "submit_to_search_console.py"),
                canonical_url,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            print("  Search Console: submitted for indexing")
            return True
        else:
            print(f"  Search Console: failed ({result.stderr[:100]})")
            return False

    except Exception as e:
        print(f"  Search Console: error ({e})")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Cross-publish markdown post to Dev.to and LinkedIn"
    )
    parser.add_argument("file", help="Path to markdown post file")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, don't publish")
    parser.add_argument("--platform", choices=["devto", "linkedin", "x", "all"], default="all")
    parser.add_argument(
        "--skip-search-console", action="store_true", help="Skip Search Console submission"
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
        slug = filepath.stem.split("-", 3)[-1] if "-" in filepath.stem else filepath.stem
        canonical_url = f"https://igorganapolsky.github.io/trading/{slug}/"

    print(f"Title: {title}")
    print(f"Tags: {tags}")
    print(f"Canonical: {canonical_url}")
    print(f"Body: {len(body)} chars")
    print()

    if args.dry_run:
        print("--- DRY RUN (not publishing) ---")
        print(body[:500])
        return 0

    results = {}

    if args.platform in ("devto", "all"):
        print("Publishing to Dev.to...")
        results["devto"] = publish_to_devto(title, body, tags, canonical_url)

    if args.platform in ("linkedin", "all"):
        print("Publishing to LinkedIn...")
        results["linkedin"] = publish_to_linkedin(title, body, canonical_url)

    if args.platform in ("x", "all"):
        print("Publishing to X...")
        results["x"] = publish_to_x(title, canonical_url, dry_run=args.dry_run)

    # Auto-submit to Search Console for indexing
    if not args.skip_search_console:
        print("Submitting to Search Console...")
        results["search_console"] = submit_to_search_console(canonical_url)

    print()
    success = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"Published to {success}/{total} platforms")

    return 0 if success > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
