#!/usr/bin/env python3
"""Bogleheads Forum Research & Insight Extractor (thin wrapper).

Back-compat entrypoint. Prefer:
  python scripts/bogleheads_ops.py ingest
  python scripts/bogleheads_ops.py pipeline
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    from src.integrations.bogleheads.promote import promote_threads, save_research_snapshot
    from src.integrations.bogleheads.rss import fetch_bogleheads_feed

    entries = fetch_bogleheads_feed(15)
    path = save_research_snapshot(entries)
    promo = promote_threads(entries, min_relevance=0.25, max_promote=10)
    record = {
        "snapshot": str(path),
        "total_threads": len(entries),
        "promoted": promo.get("written"),
        "threads": entries,
    }
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
