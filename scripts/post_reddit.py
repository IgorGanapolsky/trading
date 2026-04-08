#!/usr/bin/env python3
"""Post drafts from docs/_drafts/ to Reddit.

Reads markdown drafts with frontmatter (target subreddit, title),
posts them via PRAW, and moves to docs/_published/ after success.

Required env vars:
    REDDIT_CLIENT_ID
    REDDIT_CLIENT_SECRET
    REDDIT_USERNAME
    REDDIT_PASSWORD

Usage:
    python3 scripts/post_reddit.py                    # post all drafts
    python3 scripts/post_reddit.py --dry-run          # preview without posting
    python3 scripts/post_reddit.py --file reddit-options.md  # post one draft
"""

import argparse
import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass
import re
import shutil
import sys
from pathlib import Path

DRAFTS_DIR = Path(__file__).parent.parent / "docs" / "_drafts"
PUBLISHED_DIR = Path(__file__).parent.parent / "docs" / "_published"


def parse_draft(path: Path) -> dict:
    """Parse a draft markdown file with YAML-ish frontmatter."""
    text = path.read_text()
    meta = {}
    body = text

    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    meta[key.strip()] = val.strip()
            body = parts[2].strip()

    # Extract title from first **Title:** line
    title_match = re.search(r"\*\*Title:\*\*\s*(.+)", body)
    if title_match:
        meta["title"] = title_match.group(1).strip()
        body = body[title_match.end() :].strip()

    meta["body"] = body
    meta["file"] = path.name
    return meta


def get_reddit_client():
    """Create authenticated Reddit client."""
    import praw

    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
    username = os.environ.get("REDDIT_USERNAME")
    password = os.environ.get("REDDIT_PASSWORD")

    missing = []
    if not client_id:
        missing.append("REDDIT_CLIENT_ID")
    if not client_secret:
        missing.append("REDDIT_CLIENT_SECRET")
    if not username:
        missing.append("REDDIT_USERNAME")
    if not password:
        missing.append("REDDIT_PASSWORD")

    if missing:
        print(f"Missing env vars: {', '.join(missing)}")
        print("Set up at: https://www.reddit.com/prefs/apps")
        sys.exit(1)

    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        username=username,
        password=password,
        user_agent="trading-system-poster/1.0",
    )


def post_draft(reddit, draft: dict, dry_run: bool = False) -> str | None:
    """Post a draft to its target subreddit. Returns post URL or None."""
    target = draft.get("target", "").replace("r/", "")
    title = draft.get("title", "Untitled")
    body = draft.get("body", "")

    if not target:
        print(f"  Skipping {draft['file']}: no target subreddit")
        return None

    print(f"  Posting to r/{target}: {title[:60]}...")

    if dry_run:
        print(f"  [DRY RUN] Would post {len(body)} chars to r/{target}")
        return "https://reddit.com/dry-run"

    subreddit = reddit.subreddit(target)
    flair_id = draft.get("flair_id")
    kwargs = {"title": title, "selftext": body}
    if flair_id:
        kwargs["flair_id"] = flair_id
    submission = subreddit.submit(**kwargs)
    url = f"https://reddit.com{submission.permalink}"
    print(f"  Posted: {url}")
    return url


def main():
    parser = argparse.ArgumentParser(description="Post drafts to Reddit")
    parser.add_argument("--dry-run", action="store_true", help="Preview without posting")
    parser.add_argument("--file", help="Post a specific draft file")
    args = parser.parse_args()

    if not DRAFTS_DIR.exists():
        print(f"No drafts directory: {DRAFTS_DIR}")
        sys.exit(0)

    drafts = []
    if args.file:
        path = DRAFTS_DIR / args.file
        if not path.exists():
            print(f"Draft not found: {path}")
            sys.exit(1)
        drafts = [path]
    else:
        drafts = sorted(DRAFTS_DIR.glob("reddit-*.md"))

    if not drafts:
        print("No Reddit drafts found in docs/_drafts/")
        sys.exit(0)

    print(f"Found {len(drafts)} draft(s)")

    reddit = None if args.dry_run else get_reddit_client()

    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)
    posted = 0

    for path in drafts:
        draft = parse_draft(path)
        url = post_draft(reddit, draft, dry_run=args.dry_run)
        if url:
            posted += 1
            if not args.dry_run:
                shutil.move(str(path), str(PUBLISHED_DIR / path.name))
                print("  Moved to _published/")

    print(f"\nDone: {posted}/{len(drafts)} posted")


if __name__ == "__main__":
    main()
