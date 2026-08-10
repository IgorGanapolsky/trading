#!/usr/bin/env python3
"""Continuous ArXiv Research Paper Ingestion CLI Script.

Queries ArXiv for new papers on quantitative trading, GRPO/RL policy optimization,
and financial RAG, ingests them into the RAG pipeline and Financial Graph, and outputs
a summary report.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Ensure repo root is on python path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research.arxiv_collector import ArxivCollector  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("arxiv_paper_ingestion")


def main() -> int:
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
        default=10,
        help="Maximum number of papers to fetch from arXiv API",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output ingestion results as JSON",
    )

    args = parser.parse_args()

    logger.info("Initializing ArXiv Research Paper Collector...")
    collector = ArxivCollector()

    logger.info("Running continuous paper ingestion job...")
    results = collector.run_continuous_ingestion(
        query=args.query,
        max_results=args.max_results,
    )

    summary = {
        "status": "OK",
        "new_papers_ingested": len(results),
        "total_manifest_papers": collector.manifest.get("total_ingested", 0),
        "papers": results,
    }

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print("\n============================================================")
        print("ARXIV RESEARCH PAPER INGESTION SUMMARY")
        print("============================================================")
        print(f"New Papers Ingested    : {len(results)}")
        print(f"Total Database Papers  : {collector.manifest.get('total_ingested', 0)}")
        print("------------------------------------------------------------")
        for paper in results:
            print(f"• [{paper['arxiv_id']}] {paper['title']}")
            print(f"  Relevance: {paper['relevance_score']} | Chunks: {paper['chunks_created']}")
            print(f"  Saved to: {paper['file_path']}")
        print("============================================================\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
