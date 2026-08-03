#!/usr/bin/env python3
"""Bogleheads Forum Research & Insight Extractor.

Parses Bogleheads RSS feed (https://www.bogleheads.org/forum/feed.php) to extract
the latest index investing discussions, asset allocation trends, and Phil Town / Jack Bogle philosophy insights.
"""

from __future__ import annotations

import json
import logging
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logger = logging.getLogger(__name__)

FEED_URL = "https://www.bogleheads.org/forum/feed.php"
OUTPUT_PATH = ROOT / "data" / "research" / "bogleheads_latest.json"


def fetch_bogleheads_feed(limit: int = 15) -> list[dict[str, str]]:
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    resp = requests.get(FEED_URL, headers=headers, timeout=15)
    resp.raise_for_status()

    root = ET.fromstring(resp.text)
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    entries = []
    for entry in root.findall("atom:entry", ns)[:limit]:
        title_el = entry.find("atom:title", ns)
        link_el = entry.find("atom:link", ns)
        updated_el = entry.find("atom:updated", ns)
        content_el = entry.find("atom:content", ns)
        author_el = entry.find("atom:author/atom:name", ns)

        title = title_el.text if title_el is not None else ""
        link = link_el.attrib.get("href", "") if link_el is not None else ""
        updated = updated_el.text if updated_el is not None else ""
        author = author_el.text if author_el is not None else ""
        snippet = content_el.text[:300] if content_el is not None and content_el.text else ""

        entries.append(
            {
                "title": title,
                "link": link,
                "author": author,
                "updated": updated,
                "snippet": snippet,
            }
        )

    return entries


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    logger.info("Fetching latest Bogleheads forum discussions...")

    entries = fetch_bogleheads_feed(15)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "total_threads": len(entries),
        "threads": entries,
    }

    with OUTPUT_PATH.open("w", encoding="utf-8") as h:
        json.dump(record, h, indent=2)

    logger.info("Saved %d Bogleheads topics to %s", len(entries), OUTPUT_PATH)
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
