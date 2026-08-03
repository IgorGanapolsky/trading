#!/usr/bin/env python3
"""Ingest and query bounded public Bogleheads research."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logger = logging.getLogger(__name__)

OUTPUT_PATH = ROOT / "data" / "research" / "bogleheads_latest.json"
DB_PATH = ROOT / "data" / "rag" / "bogleheads_research.db"

from src.research.bogleheads_ingestion import (  # noqa: E402
    BogleheadsResearchStore,
    documents_as_json,
    fetch_public_feed,
)


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=15)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--search", help="query the isolated local forum-research index")
    parser.add_argument("--search-limit", type=int, default=10)
    args = parser.parse_args([] if argv is None else argv)
    logging.basicConfig(level=logging.INFO)
    if args.search:
        with BogleheadsResearchStore(args.db) as store:
            results = store.search(args.search, limit=args.search_limit)
        print(json.dumps({"query": args.search, "results": results}, indent=2))
        return 0

    logger.info("Fetching one bounded Bogleheads public-feed page")
    documents, rejected = fetch_public_feed(limit=args.limit)
    with BogleheadsResearchStore(args.db) as store:
        report = store.sync(documents, rejected=rejected)
    record = {
        "fetched_at": datetime.now(UTC).isoformat(),
        "trust_level": "untrusted_research",
        "gate_effect": "none",
        "total_threads": len(documents),
        "ingestion": report.__dict__,
        "threads": documents_as_json(documents),
    }
    _write_json_atomic(args.output, record)
    logger.info("Indexed %d public topics into %s", len(documents), args.db)
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
