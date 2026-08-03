"""Draft (and optionally post) value-first Bogleheads replies.

Default is draft-only. Live post requires --post and confirmation token.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.integrations.bogleheads.chrome_session import (
    chrome_exec_js,
    ensure_logged_in,
    open_url_in_chrome,
)
from src.integrations.bogleheads.rss import score_relevance

logger = logging.getLogger(__name__)

DRAFT_DIR = Path("data/research/bogleheads_drafts")
# Gate token (not a secret password) — operator must pass explicitly to post.
POST_CONFIRM_TOKEN = "BOGLEHEADS_POST_CONFIRMED"  # nosec B105  # gate token not a secret

# Keep participation educational, not promotional of active trading systems.
DRAFT_FOOTER = (
    "\n\n(Speaking for myself as an individual investor; not advice. "
    "I track taxes/structure carefully — Section 1256 and asset location matter.)"
)


def draft_reply(thread: dict[str, Any]) -> str:
    """Produce a short, value-first reply grounded in Bogleheads norms."""
    title = (thread.get("title") or "").strip()
    snippet = (thread.get("snippet") or "").strip()
    blob = f"{title}\n{snippet}".lower()
    score = float(thread.get("relevance_score") or score_relevance(blob))

    lines = [
        "Interesting thread — thanks for posting.",
    ]

    if any(k in blob for k in ("tax", "1256", "roth", "ira", "wash")):
        lines.append(
            "On the tax angle: for broad equity exposure I've found it useful to "
            "separate *asset allocation* (stocks/bonds/international) from *asset location* "
            "(which account holds which sleeve). Section 1256 treatment on some index options "
            "is a real edge for traders, but most long-term holders still win with simple "
            "low-cost index funds in the right account type."
        )
    elif any(k in blob for k in ("three fund", "vtsax", "vti", "allocation", "rebalance")):
        lines.append(
            "The three-fund (or total-market) approach is hard to beat once costs and behavior "
            "are included. Rebalancing on a calendar or band keeps the plan mechanical so "
            "you don't have to time markets."
        )
    elif any(k in blob for k in ("fire", "independence", "withdrawal", "swr")):
        lines.append(
            "For FI math, sequence-of-returns risk usually dominates product selection. "
            "A written withdrawal policy (and cash buffer) has mattered more in my planning "
            "than optimizing every basis point of expected return."
        )
    else:
        lines.append(
            "Agree that simplicity and low costs compound. When I get stuck I go back to: "
            "own the market, keep fees tiny, don't panic-sell, and only complicate the plan "
            "when there's a clear, written reason."
        )

    if score < 0.25:
        lines.append(
            "(I'll keep this light — the thread may already cover the main points.)"
        )

    body = " ".join(lines) + DRAFT_FOOTER
    # Soft length cap for forum etiquette
    if len(body) > 1200:
        body = body[:1150].rsplit(" ", 1)[0] + "…"
    return body


def save_draft(thread: dict[str, Any], body: str, *, draft_dir: Path | None = None) -> Path:
    out_dir = Path(draft_dir or DRAFT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    tid = re.sub(r"[^a-z0-9_\-]+", "_", str(thread.get("id") or "unknown").lower())
    path = out_dir / f"{tid}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    payload = {
        "created_at": datetime.now(UTC).isoformat(),
        "thread": {
            "id": thread.get("id"),
            "title": thread.get("title"),
            "link": thread.get("link"),
            "relevance_score": thread.get("relevance_score"),
        },
        "draft_body": body,
        "posted": False,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _resolve_reply_url(topic_url: str) -> str | None:
    """Open topic page and extract posting.php?mode=reply&t=… link."""
    open_url_in_chrome(topic_url)
    time.sleep(2.5)
    js = """
(() => {
  const a = Array.from(document.querySelectorAll('a[href*="posting.php"]'))
    .find(x => /mode=reply/i.test(x.href) && /[?&]t=\\d+/.test(x.href));
  return JSON.stringify({
    reply: a ? a.href : null,
    title: document.title,
    url: location.href
  });
})()
"""
    try:
        raw = chrome_exec_js(js)
        data = json.loads(raw) if raw.startswith("{") else {}
        return data.get("reply")
    except Exception:
        return None


def post_reply_in_chrome(
    topic_url: str,
    body: str,
    *,
    confirm_token: str | None = None,
) -> dict[str, Any]:
    """Submit a reply in Chrome. Requires confirm_token == BOGLEHEADS_POST_CONFIRMED."""
    if confirm_token != POST_CONFIRM_TOKEN:
        return {
            "ok": False,
            "posted": False,
            "reason": "missing_confirm_token",
            "hint": f"Pass confirm_token={POST_CONFIRM_TOKEN} to allow live post",
        }

    login = ensure_logged_in()
    if not login.get("ok"):
        return {"ok": False, "posted": False, "reason": "not_logged_in", "login": login}

    reply_url = _resolve_reply_url(topic_url)
    if not reply_url:
        return {
            "ok": False,
            "posted": False,
            "reason": "no_reply_link",
            "topic_url": topic_url,
            "hint": "Could not find Post Reply link (permissions or not logged in)",
        }

    open_url_in_chrome(reply_url)
    time.sleep(3.0)

    # Escape body for JS single-quoted string
    body_esc = (
        body.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\n", "\\n")
        .replace("\r", "")
    )

    js = f"""
(() => {{
  const ta = document.querySelector('textarea[name="message"], #message, textarea');
  if (!ta) return JSON.stringify({{
    ok: false,
    reason: 'no_textarea',
    title: document.title,
    url: location.href
  }});
  ta.focus();
  ta.value = '{body_esc}';
  ta.dispatchEvent(new Event('input', {{bubbles: true}}));
  ta.dispatchEvent(new Event('change', {{bubbles: true}}));
  const submit = document.querySelector(
    'input[name="post"], input[type="submit"][name="post"], ' +
    'input[type="submit"][value*="Submit"], button[name="post"]'
  );
  if (!submit) return JSON.stringify({{ok: false, reason: 'no_submit', title: document.title}});
  submit.click();
  return JSON.stringify({{ok: true, submitted: true, title: document.title, replyUrl: location.href}});
}})()
"""
    try:
        raw = chrome_exec_js(js)
        result = json.loads(raw) if raw.startswith("{") else {"raw": raw[:300]}
    except Exception as exc:
        return {"ok": False, "posted": False, "reason": str(exc)[:300]}

    time.sleep(3.0)
    result["posted"] = bool(result.get("ok") or result.get("submitted"))
    result["topic_url"] = topic_url
    result["reply_url"] = reply_url
    try:
        result["final_url"] = chrome_exec_js("location.href")
    except Exception:
        pass  # nosec B110
    return result


def draft_top_threads(
    threads: list[dict[str, Any]],
    *,
    top_n: int = 3,
    min_relevance: float = 0.35,
) -> list[dict[str, Any]]:
    """Create draft replies for the most relevant threads."""
    ranked = sorted(
        threads,
        key=lambda t: float(t.get("relevance_score") or 0.0),
        reverse=True,
    )
    out: list[dict[str, Any]] = []
    for thread in ranked:
        if float(thread.get("relevance_score") or 0.0) < min_relevance:
            continue
        if not thread.get("link"):
            continue
        body = draft_reply(thread)
        path = save_draft(thread, body)
        out.append(
            {
                "thread_id": thread.get("id"),
                "title": thread.get("title"),
                "link": thread.get("link"),
                "draft_path": str(path),
                "body_preview": body[:180],
            }
        )
        if len(out) >= top_n:
            break
    return out
