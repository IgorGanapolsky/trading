"""Public Bogleheads Atom feed ingest (no login required)."""

from __future__ import annotations

import logging
import re
from typing import Any

import requests
from defusedxml import ElementTree as ET

logger = logging.getLogger(__name__)

FEED_URL = "https://www.bogleheads.org/forum/feed.php"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 "
    "IgorTradingBogleIngest/1.0"
)

# Threads that are operationally useful for this repo (tax, FI, passive, SPY/XSP).
RELEVANCE_TERMS = (
    "tax",
    "1256",
    "roth",
    "ira",
    "401",
    "asset allocation",
    "three fund",
    "vtsax",
    "vti",
    "vxus",
    "bnd",
    "spy",
    "spx",
    "xsp",
    "index",
    "drawdown",
    "fire",
    "independence",
    "withdrawal",
    "safe withdrawal",
    "bond",
    "equity",
    "rebalance",
    "expense ratio",
    "bogle",
    "passive",
    "wash sale",
)


def _text(el: Any) -> str:
    if el is None or el.text is None:
        return ""
    return el.text.strip()


def fetch_bogleheads_feed(limit: int = 25, *, timeout: int = 20) -> list[dict[str, Any]]:
    """Fetch latest forum threads from the public Atom feed."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/atom+xml, application/xml, text/xml",
    }
    resp = requests.get(FEED_URL, headers=headers, timeout=timeout)
    resp.raise_for_status()

    root = ET.fromstring(resp.text)
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    entries: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", ns)[: max(1, limit)]:
        title = _text(entry.find("atom:title", ns))
        link_el = entry.find("atom:link", ns)
        link = link_el.attrib.get("href", "") if link_el is not None else ""
        updated = _text(entry.find("atom:updated", ns))
        author = _text(entry.find("atom:author/atom:name", ns))
        content_el = entry.find("atom:content", ns)
        raw_content = content_el.text if content_el is not None and content_el.text else ""
        snippet = re.sub(r"<[^>]+>", " ", raw_content)
        snippet = re.sub(r"\s+", " ", snippet).strip()[:500]
        thread_id = _thread_id_from_link(link)
        score = score_relevance(f"{title} {snippet}")
        entries.append(
            {
                "id": thread_id or title[:40],
                "title": title,
                "link": link,
                "author": author,
                "updated": updated,
                "snippet": snippet,
                "relevance_score": score,
                "source": "bogleheads_rss",
            }
        )

    entries.sort(key=lambda e: float(e.get("relevance_score") or 0.0), reverse=True)
    logger.info("Fetched %d Bogleheads RSS entries", len(entries))
    return entries


def _thread_id_from_link(link: str) -> str:
    m = re.search(r"[?&]t=(\d+)", link or "")
    if m:
        return f"bh_t{m.group(1)}"
    m = re.search(r"[?&#]p=(\d+)", link or "")
    if m:
        return f"bh_p{m.group(1)}"
    m = re.search(r"/(\d+)(?:\.html)?$", (link or "").rstrip("/"))
    return f"bh_{m.group(1)}" if m else ""


def score_relevance(text: str) -> float:
    t = (text or "").lower()
    if not t:
        return 0.0
    hits = sum(1 for term in RELEVANCE_TERMS if term in t)
    return min(hits / 4.0, 1.0)
