"""ArXiv research paper collector for Agentic RAG.

Fetches quantitative finance / RL / options / RAG papers from arXiv's public API
(https://arxiv.org / export.arxiv.org), grades relevance to this trading lab,
deduplicates via manifest + DocumentIngestionPipeline, and writes markdown into:

  * data/arxiv/              — audit corpus + raw ingest artifacts
  * rag_knowledge/arxiv/     — picked up by build_rag_query_index.py + DS/ML RAG

Does NOT claim trading edge. Papers are research context only.
"""

from __future__ import annotations

import datetime
import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET  # nosec B405 — arXiv Atom feed only; no local untrusted XML
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.rag.document_ingestion_pipeline import DocumentIngestionPipeline

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
ARXIV_DATA_DIR = ROOT / "data" / "arxiv"
ARXIV_RAG_DIR = ROOT / "rag_knowledge" / "arxiv"
ARXIV_MANIFEST_FILE = ROOT / "data" / "audit" / "arxiv_ingestion_manifest.json"

# Categories that commonly contain usable research for this lab.
DEFAULT_CATEGORIES = [
    "q-fin.TR",  # Trading / microstructure
    "q-fin.PR",  # Pricing of securities
    "q-fin.RM",  # Risk management
    "q-fin.PM",  # Portfolio management
    "q-fin.CP",  # Computational finance
    "cs.LG",  # ML / RL
    "cs.AI",  # Multi-agent / agents
    "stat.ML",  # Statistical ML
]

# High-signal phrases for *this* system's DS/ML/RAG stack (not generic AI).
DEFAULT_KEYWORDS = [
    "option trading",
    "credit spread",
    "put option",
    "implied volatility",
    "market microstructure",
    "reinforcement learning trading",
    "portfolio risk",
    "order book",
    "volatility forecasting",
    "retrieval augmented generation finance",
    "agentic trading",
]

# Default multi-query fan-out so continuous jobs cover several research lanes.
DEFAULT_QUERIES = [
    "option credit spread OR iron condor OR put credit",
    "implied volatility OR volatility surface trading",
    "reinforcement learning trading OR GRPO OR PPO finance",
    "market microstructure order book",
    "retrieval augmented generation finance OR financial RAG",
]

# Token boosts for lab applicability (case-insensitive substring).
_RELEVANCE_BOOSTS: tuple[tuple[str, float], ...] = (
    ("option", 0.12),
    ("put credit", 0.18),
    ("credit spread", 0.16),
    ("iron condor", 0.12),
    ("implied volatility", 0.14),
    ("volatility", 0.08),
    ("microstructure", 0.10),
    ("order book", 0.10),
    ("reinforcement learning", 0.12),
    ("grpo", 0.14),
    ("ppo", 0.08),
    ("risk management", 0.10),
    ("stop loss", 0.08),
    ("rag", 0.10),
    ("retrieval", 0.08),
    ("spy", 0.10),
    ("equity options", 0.12),
)

MIN_RELEVANCE_DEFAULT = 0.18


@dataclass
class ArxivPaper:
    arxiv_id: str
    title: str
    authors: list[str]
    published: str
    updated: str
    summary: str
    categories: list[str]
    abs_url: str
    pdf_url: str
    relevance_score: float = 0.0
    relevance_method: str = "keyword_boost"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ArxivCollector:
    """Collect arXiv papers and ingest them into the lab RAG corpus."""

    def __init__(
        self,
        output_dir: Path | None = None,
        rag_dir: Path | None = None,
        manifest_file: Path | None = None,
        *,
        min_relevance: float = MIN_RELEVANCE_DEFAULT,
    ) -> None:
        self.output_dir = output_dir or ARXIV_DATA_DIR
        self.rag_dir = rag_dir or ARXIV_RAG_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.rag_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_file = manifest_file or ARXIV_MANIFEST_FILE
        self.manifest = self._load_manifest()
        self.min_relevance = float(min_relevance)
        self.ingestion_pipeline = DocumentIngestionPipeline()

    def _load_manifest(self) -> dict[str, Any]:
        if self.manifest_file.exists():
            try:
                with self.manifest_file.open("r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to load arXiv manifest: %s", exc)
        return {
            "papers": {},
            "skipped_low_relevance": {},
            "total_ingested": 0,
            "last_run_utc": "",
            "runs": [],
        }

    def _save_manifest(self) -> None:
        self.manifest_file.parent.mkdir(parents=True, exist_ok=True)
        with self.manifest_file.open("w", encoding="utf-8") as f:
            json.dump(self.manifest, f, indent=2)

    def fetch_papers(
        self,
        query: str | None = None,
        categories: list[str] | None = None,
        max_results: int = 15,
    ) -> list[ArxivPaper]:
        """Fetch papers from the arXiv Atom API."""
        cats = categories or DEFAULT_CATEGORIES
        cat_query = " OR ".join(f"cat:{c}" for c in cats)

        if query:
            search_query = f"({query}) AND ({cat_query})"
        else:
            kw_query = " OR ".join(f'all:"{kw}"' for kw in DEFAULT_KEYWORDS[:5])
            search_query = f"({kw_query}) AND ({cat_query})"

        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": max(1, min(int(max_results), 50)),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        url = f"https://export.arxiv.org/api/query?{urllib.parse.urlencode(params)}"
        logger.info("Querying arXiv API (max_results=%s)", params["max_results"])

        # arXiv asks polite clients to space requests; retry on 429/timeouts.
        last_err: Exception | None = None
        for attempt in range(4):
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "IgorTradingLab-ArxivIngest/1.0 (research; paper-first)"
                    },
                )
                # Public HTTPS arXiv API only (scheme fixed above).
                with urllib.request.urlopen(req, timeout=45) as resp:  # nosec B310
                    xml_data = resp.read()
                return self._parse_arxiv_atom(xml_data)
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                sleep_s = 3 * (attempt + 1)
                logger.warning(
                    "arXiv API attempt %s failed (%s); retry in %ss",
                    attempt + 1,
                    exc,
                    sleep_s,
                )
                time.sleep(sleep_s)
        logger.error("arXiv API request failed after retries: %s", last_err)
        return []

    def _parse_arxiv_atom(self, xml_bytes: bytes) -> list[ArxivPaper]:
        papers: list[ArxivPaper] = []
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }
        try:
            root = ET.fromstring(xml_bytes)  # nosec B314 — Atom from arXiv API only
        except ET.ParseError as exc:
            logger.error("Failed to parse arXiv XML: %s", exc)
            return []

        for entry in root.findall("atom:entry", ns):
            id_text = entry.findtext("atom:id", default="", namespaces=ns) or ""
            arxiv_id = id_text.split("/abs/")[-1] if "/abs/" in id_text else id_text
            arxiv_id = arxiv_id.strip()
            if not arxiv_id:
                continue

            title = entry.findtext("atom:title", default="", namespaces=ns) or ""
            title = re.sub(r"\s+", " ", title).strip()
            summary = entry.findtext("atom:summary", default="", namespaces=ns) or ""
            summary = re.sub(r"\s+", " ", summary).strip()
            published = entry.findtext("atom:published", default="", namespaces=ns) or ""
            updated = entry.findtext("atom:updated", default="", namespaces=ns) or ""

            authors = [
                (author.findtext("atom:name", default="", namespaces=ns) or "").strip()
                for author in entry.findall("atom:author", ns)
            ]
            authors = [a for a in authors if a]

            categories = [
                cat.attrib.get("term", "")
                for cat in entry.findall("atom:category", ns)
                if cat.attrib.get("term")
            ]

            abs_url = id_text.replace("http://", "https://")
            pdf_url = ""
            for link in entry.findall("atom:link", ns):
                if link.attrib.get("title") == "pdf":
                    pdf_url = (link.attrib.get("href") or "").replace("http://", "https://")
                    break
            if not pdf_url:
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

            papers.append(
                ArxivPaper(
                    arxiv_id=arxiv_id,
                    title=title,
                    authors=authors,
                    published=published,
                    updated=updated,
                    summary=summary,
                    categories=categories,
                    abs_url=abs_url,
                    pdf_url=pdf_url,
                )
            )
        return papers

    def evaluate_paper_relevance(self, paper: ArxivPaper) -> ArxivPaper:
        """Deterministic relevance grade for this trading lab (no network)."""
        hay = f"{paper.title}\n{paper.summary}\n{' '.join(paper.categories)}".lower()
        score = 0.05
        # Category prior
        for cat in paper.categories:
            if cat.startswith("q-fin"):
                score += 0.12
            elif cat in {"cs.LG", "cs.AI", "stat.ML"}:
                score += 0.05
        for token, boost in _RELEVANCE_BOOSTS:
            if token in hay:
                score += boost
        # Cap + slight length prior (longer abstracts often more usable)
        if len(paper.summary) > 400:
            score += 0.03
        paper.relevance_score = round(min(1.0, score), 3)
        paper.relevance_method = "keyword_boost_v1"
        return paper

    def _paper_markdown(self, paper: ArxivPaper) -> str:
        today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        tags = ["arxiv", "research", *paper.categories[:4]]
        tags_fmt = ", ".join(f'"{t}"' for t in tags)
        authors = ", ".join(paper.authors[:12])
        return f"""---
title: "{paper.title.replace('"', "'")}"
date: {today}
source: arxiv
arxiv_id: "{paper.arxiv_id}"
relevance_score: {paper.relevance_score}
tags: [{tags_fmt}]
---

# arXiv Paper: {paper.title}

- **Date**: {today}
- **arXiv ID**: `{paper.arxiv_id}`
- **Published**: {paper.published}
- **Authors**: {authors}
- **Categories**: {", ".join(paper.categories)}
- **URL**: [{paper.abs_url}]({paper.abs_url})
- **PDF**: [{paper.pdf_url}]({paper.pdf_url})
- **Relevance Score**: {paper.relevance_score} ({paper.relevance_method})

## Abstract

{paper.summary}

## Lab applicability (automatic)

Ingested for **Data Science / ML / Agentic RAG** context only. Use for:

- Feature ideas, risk models, volatility structure, RL/GRPO research
- RAG retrieval quality and agent memory design
- **Not** as a live order signal and **not** proof of edge

Cross-check any operational claim against `data/trades.json` paired outcomes and
the active put-credit cohort scorecard before changing trading policy.
"""

    def ingest_paper(self, paper: ArxivPaper) -> dict[str, Any]:
        """Write markdown, pipeline-ingest, and update manifest."""
        paper = self.evaluate_paper_relevance(paper)
        if paper.relevance_score < self.min_relevance:
            self.manifest.setdefault("skipped_low_relevance", {})[paper.arxiv_id] = {
                "title": paper.title,
                "relevance_score": paper.relevance_score,
                "min_relevance": self.min_relevance,
                "evaluated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
            self._save_manifest()
            return {
                "arxiv_id": paper.arxiv_id,
                "title": paper.title,
                "relevance_score": paper.relevance_score,
                "skipped": True,
                "reason": "low_relevance",
                "chunks_created": 0,
                "is_duplicate": False,
            }

        clean_id = re.sub(r"[^a-zA-Z0-9_.-]", "_", paper.arxiv_id)
        filename = f"arxiv_{clean_id.replace('.', '_')}.md"
        audit_path = self.output_dir / filename
        rag_path = self.rag_dir / filename
        md_content = self._paper_markdown(paper)

        audit_path.write_text(md_content, encoding="utf-8")
        rag_path.write_text(md_content, encoding="utf-8")

        doc = self.ingestion_pipeline.ingest_document(rag_path, md_content)

        self.manifest.setdefault("papers", {})[paper.arxiv_id] = {
            "title": paper.title,
            "published": paper.published,
            "relevance_score": paper.relevance_score,
            "relevance_method": paper.relevance_method,
            "categories": paper.categories,
            "abs_url": paper.abs_url,
            "file_path": str(rag_path.relative_to(ROOT)) if rag_path.is_relative_to(ROOT) else str(rag_path),
            "audit_path": str(audit_path.relative_to(ROOT))
            if audit_path.is_relative_to(ROOT)
            else str(audit_path),
            "ingested_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "sha256": doc.sha256_hash,
            "chunks": len(doc.chunks),
        }
        self.manifest["total_ingested"] = len(self.manifest["papers"])
        self.manifest["last_run_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self._save_manifest()

        logger.info(
            "Ingested arXiv %s (relevance=%.3f, chunks=%s): %s",
            paper.arxiv_id,
            paper.relevance_score,
            len(doc.chunks),
            paper.title[:80],
        )
        return {
            "arxiv_id": paper.arxiv_id,
            "title": paper.title,
            "relevance_score": paper.relevance_score,
            "file_path": str(rag_path),
            "chunks_created": len(doc.chunks),
            "is_duplicate": doc.is_duplicate,
            "skipped": False,
        }

    def run_continuous_ingestion(
        self,
        query: str | None = None,
        max_results: int = 12,
        *,
        multi_query: bool = True,
    ) -> list[dict[str, Any]]:
        """Fetch, dedupe, grade, and ingest papers.

        When ``query`` is None and ``multi_query`` is True, runs DEFAULT_QUERIES
        (fan-out) and merges unique arXiv IDs.
        """
        seen_ids: set[str] = set()
        papers: list[ArxivPaper] = []

        if query:
            queries = [query]
        elif multi_query:
            queries = list(DEFAULT_QUERIES)
        else:
            queries = [None]  # type: ignore[list-item]

        per_query = max(3, max_results // max(1, len(queries)))
        for i, q in enumerate(queries):
            if i > 0:
                time.sleep(3.1)  # polite spacing (arXiv courtesy)
            batch = self.fetch_papers(query=q, max_results=per_query)
            for paper in batch:
                if paper.arxiv_id in seen_ids:
                    continue
                seen_ids.add(paper.arxiv_id)
                papers.append(paper)

        results: list[dict[str, Any]] = []
        ingested = 0
        skipped = 0
        known = set(self.manifest.get("papers", {})) | set(
            self.manifest.get("skipped_low_relevance", {})
        )
        for paper in papers:
            if paper.arxiv_id in known:
                logger.info("Paper %s already seen; skipping.", paper.arxiv_id)
                continue
            res = self.ingest_paper(paper)
            results.append(res)
            known.add(paper.arxiv_id)
            if res.get("skipped"):
                skipped += 1
            else:
                ingested += 1

        run_row = {
            "finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "candidates": len(papers),
            "new_ingested": ingested,
            "skipped_low_relevance": skipped,
            "min_relevance": self.min_relevance,
            "queries": queries if query or multi_query else ["default_keywords"],
        }
        runs = list(self.manifest.get("runs") or [])
        runs.append(run_row)
        self.manifest["runs"] = runs[-50:]  # keep last 50 runs
        self.manifest["last_run_utc"] = run_row["finished_at"]
        self._save_manifest()

        logger.info(
            "arXiv ingest done: candidates=%s new=%s skipped_low_rel=%s total=%s",
            len(papers),
            ingested,
            skipped,
            self.manifest.get("total_ingested", 0),
        )
        return results
