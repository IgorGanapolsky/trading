#!/usr/bin/env python3
"""Bogleheads forum ops CLI — ingest, promote, login, draft, optional post.

Examples:
  python scripts/bogleheads_ops.py ingest
  python scripts/bogleheads_ops.py pipeline
  python scripts/bogleheads_ops.py login
  python scripts/bogleheads_ops.py draft
  python scripts/bogleheads_ops.py post --confirm-token BOGLEHEADS_POST_CONFIRMED
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _cmd_ingest(args: argparse.Namespace) -> int:
    from src.integrations.bogleheads.promote import promote_threads, save_research_snapshot
    from src.integrations.bogleheads.rss import fetch_bogleheads_feed

    threads = fetch_bogleheads_feed(limit=args.limit)
    path = save_research_snapshot(threads)
    promo = promote_threads(
        threads,
        min_relevance=args.min_relevance,
        max_promote=args.max_promote,
    )
    print(
        json.dumps(
            {
                "snapshot": str(path),
                "threads": len(threads),
                "promoted": len(promo.get("written") or []),
                "skipped": len(promo.get("skipped_existing") or []),
                "top": [
                    {
                        "title": t.get("title"),
                        "score": t.get("relevance_score"),
                        "link": t.get("link"),
                    }
                    for t in threads[:5]
                ],
            },
            indent=2,
        )
    )
    return 0


def _cmd_login(args: argparse.Namespace) -> int:
    from src.integrations.bogleheads.chrome_session import ensure_logged_in
    from src.integrations.bogleheads.credentials import load_credentials

    creds = load_credentials()
    print(json.dumps({"credentials": creds.masked()}, indent=2))
    status = ensure_logged_in(force_login=args.force)
    print(json.dumps(status, indent=2))
    return 0 if status.get("ok") else 2


def _cmd_pipeline(args: argparse.Namespace) -> int:
    from src.integrations.bogleheads.pipeline import run_pipeline

    report = run_pipeline(
        limit=args.limit,
        min_relevance=args.min_relevance,
        max_promote=args.max_promote,
        draft_top_n=args.draft_top,
        login_chrome=not args.skip_chrome,
        enrich_top_n=args.enrich_top,
        post=args.post,
        post_confirm_token=args.confirm_token,
        post_draft_index=args.draft_index,
    )
    print(json.dumps(report, indent=2))
    return 0 if report.get("ok") else 1


def _cmd_draft(args: argparse.Namespace) -> int:
    from src.integrations.bogleheads.participate import draft_top_threads
    from src.integrations.bogleheads.rss import fetch_bogleheads_feed

    threads = fetch_bogleheads_feed(limit=args.limit)
    drafts = draft_top_threads(
        threads,
        top_n=args.draft_top,
        min_relevance=args.min_relevance,
    )
    print(json.dumps({"drafts": drafts}, indent=2))
    return 0


def _cmd_post(args: argparse.Namespace) -> int:
    """Post the Nth draft (default 0) to its thread via Chrome."""
    from src.integrations.bogleheads.participate import POST_CONFIRM_TOKEN, post_reply_in_chrome

    draft_dir = Path("data/research/bogleheads_drafts")
    drafts = sorted(draft_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not drafts:
        print(json.dumps({"ok": False, "reason": "no_drafts"}))
        return 2
    path = drafts[min(args.draft_index, len(drafts) - 1)]
    meta = json.loads(path.read_text(encoding="utf-8"))
    link = (meta.get("thread") or {}).get("link")
    body = meta.get("draft_body") or ""
    if not link or not body:
        print(json.dumps({"ok": False, "reason": "invalid_draft", "path": str(path)}))
        return 2
    result = post_reply_in_chrome(
        str(link),
        body,
        confirm_token=args.confirm_token or POST_CONFIRM_TOKEN,
    )
    if result.get("posted"):
        meta["posted"] = True
        path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps({"draft": str(path), **result}, indent=2))
    return 0 if result.get("posted") else 2


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Bogleheads forum automation")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ing = sub.add_parser("ingest", help="RSS fetch + promote to rag_knowledge/bogleheads")
    p_ing.add_argument("--limit", type=int, default=25)
    p_ing.add_argument("--min-relevance", type=float, default=0.25)
    p_ing.add_argument("--max-promote", type=int, default=12)
    p_ing.set_defaults(func=_cmd_ingest)

    p_login = sub.add_parser("login", help="Ensure Chrome session logged in via Keychain")
    p_login.add_argument("--force", action="store_true")
    p_login.set_defaults(func=_cmd_login)

    p_pipe = sub.add_parser("pipeline", help="Full automate: ingest+login+enrich+draft")
    p_pipe.add_argument("--limit", type=int, default=25)
    p_pipe.add_argument("--min-relevance", type=float, default=0.25)
    p_pipe.add_argument("--max-promote", type=int, default=12)
    p_pipe.add_argument("--draft-top", type=int, default=3)
    p_pipe.add_argument("--enrich-top", type=int, default=3)
    p_pipe.add_argument("--skip-chrome", action="store_true")
    p_pipe.add_argument("--post", action="store_true", help="Also post one draft (requires token)")
    p_pipe.add_argument(
        "--confirm-token",
        default=None,
        help="Must be BOGLEHEADS_POST_CONFIRMED for live post",
    )
    p_pipe.add_argument("--draft-index", type=int, default=0)
    p_pipe.set_defaults(func=_cmd_pipeline)

    p_draft = sub.add_parser("draft", help="Create draft replies only")
    p_draft.add_argument("--limit", type=int, default=25)
    p_draft.add_argument("--draft-top", type=int, default=3)
    p_draft.add_argument("--min-relevance", type=float, default=0.35)
    p_draft.set_defaults(func=_cmd_draft)

    p_post = sub.add_parser("post", help="Post latest draft via Chrome (gated)")
    p_post.add_argument(
        "--confirm-token",
        default="BOGLEHEADS_POST_CONFIRMED",
        help="Safety token required for live post",
    )
    p_post.add_argument("--draft-index", type=int, default=0)
    p_post.set_defaults(func=_cmd_post)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
