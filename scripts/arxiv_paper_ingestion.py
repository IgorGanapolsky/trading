#!/usr/bin/env python3
"""Continuous arXiv paper ingestion → Agentic RAG CLI.

Usage:
  python scripts/arxiv_paper_ingestion.py --max-results 15
  python scripts/arxiv_paper_ingestion.py --query "option credit spread" --json
  python scripts/arxiv_paper_ingestion.py --rebuild-index

Sources: https://arxiv.org / https://export.arxiv.org/api/query
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess  # nosec B404 — fixed argv to local rebuild script only
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research.arxiv_collector import (  # noqa: E402
    MIN_RELEVANCE_DEFAULT,
    ArxivCollector,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("arxiv_paper_ingestion")


def _rebuild_rag_index() -> dict[str, object]:
    """Refresh lessons_query.json so arXiv markdown is queryable."""
    script = ROOT / "scripts" / "build_rag_query_index.py"
    cmd = [sys.executable, str(script)]
    env = os.environ.copy()
    env["RAG_WRITE_PROFILE"] = "repo"
    try:
        proc = subprocess.run(  # nosec B603 — absolute interpreter + fixed local script
            cmd,
            cwd=str(ROOT),
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
            env=env,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-500:],
            "stderr_tail": (proc.stderr or "")[-500:],
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("RAG index rebuild failed: %s", exc)
        return {"ok": False, "error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch and ingest arXiv research papers into lab Agentic RAG."
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Optional single search query override",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=15,
        help="Max papers across fan-out queries (default 15)",
    )
    parser.add_argument(
        "--min-relevance",
        type=float,
        default=MIN_RELEVANCE_DEFAULT,
        help=f"Skip papers below this score (default {MIN_RELEVANCE_DEFAULT})",
    )
    parser.add_argument(
        "--single-query",
        action="store_true",
        help="Disable multi-query fan-out (use default keyword pack or --query only)",
    )
    parser.add_argument(
        "--rebuild-index",
        action="store_true",
        help="Rebuild data/rag/lessons_query.json after ingest",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON summary",
    )
    args = parser.parse_args()

    collector = ArxivCollector(min_relevance=args.min_relevance)
    results = collector.run_continuous_ingestion(
        query=args.query,
        max_results=args.max_results,
        multi_query=not args.single_query and args.query is None,
    )

    ingested = [r for r in results if not r.get("skipped")]
    skipped = [r for r in results if r.get("skipped")]

    index_result = None
    if args.rebuild_index:
        index_result = _rebuild_rag_index()

    summary = {
        "status": "OK",
        "new_papers_ingested": len(ingested),
        "skipped_low_relevance": len(skipped),
        "total_manifest_papers": collector.manifest.get("total_ingested", 0),
        "min_relevance": args.min_relevance,
        "last_run_utc": collector.manifest.get("last_run_utc"),
        "papers": results,
        "index_rebuild": index_result,
        "source": "https://arxiv.org",
        "api": "https://export.arxiv.org/api/query",
    }

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print("\n============================================================")
        print("ARXIV → AGENTIC RAG INGESTION")
        print("============================================================")
        print(f"New papers ingested   : {len(ingested)}")
        print(f"Skipped (low rel.)    : {len(skipped)}")
        print(f"Manifest total        : {collector.manifest.get('total_ingested', 0)}")
        print(f"Min relevance         : {args.min_relevance}")
        print("------------------------------------------------------------")
        for paper in ingested:
            print(f"• [{paper['arxiv_id']}] {paper['title'][:90]}")
            print(
                f"  relevance={paper.get('relevance_score')} chunks={paper.get('chunks_created')} "
                f"dup={paper.get('is_duplicate')}"
            )
        if skipped:
            print("------------------------------------------------------------")
            print("Skipped (low relevance):")
            for paper in skipped[:10]:
                print(
                    f"  - [{paper['arxiv_id']}] score={paper.get('relevance_score')} "
                    f"{str(paper.get('title', ''))[:70]}"
                )
        if index_result is not None:
            print(f"Index rebuild ok={index_result.get('ok')}")
        print("============================================================\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
