#!/usr/bin/env python3
"""Continuous arXiv research paper ingestion CLI.

Fetches papers from https://arxiv.org via the public API, grades relevance for
this lab's DS/ML/Agentic RAG stack, dedupes, ingests through
DocumentIngestionPipeline, and promotes high-signal papers into
``rag_knowledge/research/arxiv/``.

Examples::

    python scripts/arxiv_paper_ingestion.py
    python scripts/arxiv_paper_ingestion.py --max-results 20 --json
    python scripts/arxiv_paper_ingestion.py --query "put credit spread options"
    python scripts/arxiv_paper_ingestion.py --status
    python scripts/arxiv_paper_ingestion.py --rebuild-index
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess  # nosec B404 — rebuild index only via fixed local script path
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research.arxiv_collector import (  # noqa: E402
    DEFAULT_MIN_RELEVANCE,
    DEFAULT_PROMOTE_RELEVANCE,
    ArxivCollector,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("arxiv_paper_ingestion")


def _print_human(report) -> None:
    d = report.to_dict() if hasattr(report, "to_dict") else report
    print("\n============================================================")
    print("ARXIV RESEARCH PAPER INGESTION SUMMARY")
    print("============================================================")
    print(f"Status                 : {d.get('status')}")
    print(f"Fetched                : {d.get('fetched')}")
    print(f"New Ingested           : {d.get('ingested')}")
    print(f"Skipped (duplicate)    : {d.get('skipped_duplicate')}")
    print(f"Skipped (low relevance): {d.get('skipped_low_relevance')}")
    print(f"Promoted to curated    : {d.get('promoted')}")
    print(f"Manifest total         : {d.get('total_manifest_papers')}")
    print(f"Min relevance          : {d.get('min_relevance')}")
    print(f"Duration (ms)          : {d.get('duration_ms')}")
    if d.get("errors"):
        print("Errors:")
        for err in d["errors"][:10]:
            print(f"  - {err}")
    print("------------------------------------------------------------")
    for paper in d.get("papers") or []:
        print(f"• [{paper.get('arxiv_id')}] {paper.get('title')}")
        print(
            f"  Relevance: {paper.get('relevance_score')} | "
            f"Chunks: {paper.get('chunks_created')} | "
            f"Promoted: {paper.get('promoted')}"
        )
        if paper.get("file_path"):
            print(f"  Saved to: {paper['file_path']}")
    print("============================================================\n")


def _rebuild_indexes() -> int:
    """Best-effort rebuild of dependency-free RAG query index."""
    build = ROOT / "scripts" / "build_rag_query_index.py"
    if not build.is_file():
        logger.warning("build_rag_query_index.py not found; skip rebuild")
        return 0
    cmd = [sys.executable, str(build)]
    logger.info("Rebuilding RAG query index: %s", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=str(ROOT), check=False)  # nosec B603
    return int(proc.returncode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Continuously fetch and ingest research papers from arXiv into RAG."
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Optional search query override (e.g. 'reinforcement learning trading')",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=15,
        help="Maximum papers to fetch from arXiv API (1-50)",
    )
    parser.add_argument(
        "--min-relevance",
        type=float,
        default=DEFAULT_MIN_RELEVANCE,
        help=f"Minimum composite relevance to ingest (default {DEFAULT_MIN_RELEVANCE})",
    )
    parser.add_argument(
        "--promote-relevance",
        type=float,
        default=DEFAULT_PROMOTE_RELEVANCE,
        help=(
            "Minimum relevance to promote into rag_knowledge/research/arxiv "
            f"(default {DEFAULT_PROMOTE_RELEVANCE})"
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-ingest even if arxiv_id already in manifest",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output ingestion results as JSON",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print last run status artifact and exit",
    )
    parser.add_argument(
        "--rebuild-index",
        action="store_true",
        help="After successful ingest, rebuild data/rag/lessons_query.json",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Debug logging",
    )
    args = parser.parse_args(argv)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    collector = ArxivCollector(
        min_relevance=args.min_relevance,
        promote_relevance=args.promote_relevance,
    )

    if args.status:
        status_path = collector.status_file
        if not status_path.exists():
            payload = {
                "status": "NO_STATUS",
                "message": f"No status file at {status_path}",
                "total_manifest_papers": collector.manifest.get("total_ingested", 0),
                "last_run_utc": collector.manifest.get("last_run_utc", ""),
            }
        else:
            payload = json.loads(status_path.read_text(encoding="utf-8"))
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(json.dumps(payload, indent=2))
        return 0

    logger.info("Running continuous arXiv paper ingestion job...")
    report = collector.run_continuous_ingestion(
        query=args.query,
        max_results=args.max_results,
        force=args.force,
    )

    if args.rebuild_index and report.ingested > 0:
        rc = _rebuild_indexes()
        if rc != 0:
            report.status = "PARTIAL" if report.status == "OK" else report.status
            report.errors.append(f"rebuild_index_exit={rc}")
            collector._write_status(report)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        _print_human(report)

    if report.status == "ERROR":
        return 2
    if report.status == "EMPTY_OR_API_ERROR":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
