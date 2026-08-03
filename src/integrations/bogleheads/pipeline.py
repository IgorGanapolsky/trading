"""End-to-end Bogleheads automation pipeline."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.integrations.bogleheads.chrome_session import ensure_logged_in, fetch_topic_text
from src.integrations.bogleheads.participate import draft_top_threads, post_reply_in_chrome
from src.integrations.bogleheads.promote import promote_threads, save_research_snapshot
from src.integrations.bogleheads.rss import fetch_bogleheads_feed

logger = logging.getLogger(__name__)

DEFAULT_RUN_LOG = Path("data/research/bogleheads_pipeline_latest.json")


def run_pipeline(
    *,
    limit: int = 25,
    min_relevance: float = 0.25,
    max_promote: int = 12,
    draft_top_n: int = 3,
    login_chrome: bool = True,
    enrich_top_n: int = 3,
    post: bool = False,
    post_confirm_token: str | None = None,
    post_draft_index: int = 0,
) -> dict[str, Any]:
    """Ingest RSS → promote to RAG → optional Chrome login/enrich → draft (optional post)."""
    report: dict[str, Any] = {
        "started_at": datetime.now(UTC).isoformat(),
        "ok": False,
        "stages": {},
    }

    # 1) RSS
    threads = fetch_bogleheads_feed(limit=limit)
    snap = save_research_snapshot(threads)
    report["stages"]["rss"] = {
        "count": len(threads),
        "snapshot": str(snap),
        "top_titles": [t.get("title") for t in threads[:5]],
    }

    # 2) Promote to rag_knowledge/bogleheads
    promo = promote_threads(
        threads,
        min_relevance=min_relevance,
        max_promote=max_promote,
    )
    report["stages"]["promote"] = promo

    # 3) Chrome login + enrich top relevant topics with full post text
    if login_chrome:
        try:
            login = ensure_logged_in()
            report["stages"]["login"] = {
                k: v for k, v in login.items() if k != "password"
            }
        except Exception as exc:
            report["stages"]["login"] = {"ok": False, "error": str(exc)[:300]}
            login = {"ok": False}

        enriched: list[dict[str, Any]] = []
        if login.get("ok"):
            for thread in threads[:enrich_top_n]:
                link = thread.get("link")
                if not link:
                    continue
                try:
                    page = fetch_topic_text(str(link))
                    enriched.append(
                        {
                            "id": thread.get("id"),
                            "title": thread.get("title"),
                            "text_len": page.get("text_len"),
                            "post_count": len(page.get("posts") or []),
                        }
                    )
                    # Attach first posts into a sidecar for RAG quality
                    if page.get("posts"):
                        thread["chrome_posts"] = (page.get("posts") or [])[:3]
                except Exception as exc:
                    enriched.append(
                        {
                            "id": thread.get("id"),
                            "error": str(exc)[:200],
                        }
                    )
            # Re-save snapshot with chrome enrichment
            save_research_snapshot(threads)
        report["stages"]["enrich"] = {"items": enriched}
    else:
        report["stages"]["login"] = {"skipped": True}

    # 4) Draft replies for top relevant threads
    drafts = draft_top_threads(
        threads,
        top_n=draft_top_n,
        min_relevance=max(min_relevance, 0.35),
    )
    report["stages"]["drafts"] = drafts

    # 5) Optional live post (gated)
    if post:
        if not drafts:
            report["stages"]["post"] = {"ok": False, "reason": "no_drafts"}
        else:
            idx = max(0, min(post_draft_index, len(drafts) - 1))
            d = drafts[idx]
            draft_path = Path(d["draft_path"])
            body = json.loads(draft_path.read_text(encoding="utf-8")).get("draft_body", "")
            post_result = post_reply_in_chrome(
                str(d.get("link")),
                body,
                confirm_token=post_confirm_token,
            )
            report["stages"]["post"] = post_result
            if post_result.get("posted") and draft_path.exists():
                meta = json.loads(draft_path.read_text(encoding="utf-8"))
                meta["posted"] = True
                meta["posted_at"] = datetime.now(UTC).isoformat()
                draft_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    else:
        report["stages"]["post"] = {
            "skipped": True,
            "reason": "draft_only_default",
            "hint": "Re-run with --post --confirm-token BOGLEHEADS_POST_CONFIRMED to publish one draft",
        }

    report["finished_at"] = datetime.now(UTC).isoformat()
    report["ok"] = True
    DEFAULT_RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_RUN_LOG.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Bogleheads pipeline complete → %s", DEFAULT_RUN_LOG)
    return report
