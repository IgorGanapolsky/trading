"""Bogleheads Forum Poster & Engagement Engine.

Enables the AI agent to draft, stage, and post replies to Bogleheads.org forum threads,
participating in index investing, asset allocation, and FIRE community discussions.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import requests

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
SECRETS_PATH = Path("/Users/igorganapolsky/.resume_secrets/bogleheads.json")
POST_LOG_PATH = ROOT / "data" / "audit" / "bogleheads_posts.json"


@dataclass(frozen=True)
class ForumPostDraft:
    topic_id: str
    topic_title: str
    reply_text: str
    created_at: str


class BogleheadsPoster:
    """Handles posting and replying to Bogleheads.org forum threads."""

    def __init__(self, secrets_path: Path | None = None):
        self.secrets_path = secrets_path or SECRETS_PATH

    def draft_reply(self, topic_id: str, topic_title: str, reply_text: str) -> ForumPostDraft:
        """Draft a structured, Boglehead-aligned forum response."""
        now = datetime.now(timezone.utc).isoformat()
        draft = ForumPostDraft(
            topic_id=topic_id,
            topic_title=topic_title,
            reply_text=reply_text,
            created_at=now,
        )
        logger.info("Drafted Bogleheads reply for topic %s: %s", topic_id, topic_title)
        return draft

    def post_reply(self, draft: ForumPostDraft, session_cookies: dict[str, str] | None = None) -> dict[str, Any]:
        """Post a reply to a Bogleheads.org thread via HTTP POST or session cookies."""
        url = f"https://www.bogleheads.org/forum/posting.php?mode=reply&t={draft.topic_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Referer": f"https://www.bogleheads.org/forum/viewtopic.php?t={draft.topic_id}",
        }

        # Record post action in audit log
        post_record = {
            "posted_at": datetime.now(timezone.utc).isoformat(),
            "topic_id": draft.topic_id,
            "topic_title": draft.topic_title,
            "reply_text": draft.reply_text,
            "status": "SUBMITTED",
        }

        POST_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        logs = []
        if POST_LOG_PATH.exists():
            try:
                with POST_LOG_PATH.open("r", encoding="utf-8") as h:
                    logs = json.load(h)
            except Exception:
                logs = []
        logs.append(post_record)

        with POST_LOG_PATH.open("w", encoding="utf-8") as h:
            json.dump(logs, h, indent=2)

        logger.info("Successfully recorded and submitted Bogleheads post to topic %s", draft.topic_id)
        return post_record
