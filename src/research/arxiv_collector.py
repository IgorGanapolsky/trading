"""ArXiv research paper collector for DS / ML / Agentic RAG.

Fetches papers from the public arXiv API (https://arxiv.org / export.arxiv.org),
grades them for relevance to this lab (SPY put-credit validation, risk gates,
GRPO/RL, financial RAG), deduplicates via a durable manifest, and ingests
accepted papers through ``DocumentIngestionPipeline``.

High-relevance papers are also promoted into ``rag_knowledge/research/arxiv/``
so ``build_rag_query_index`` / ``vectorize_rag_knowledge`` can index them.

This module never submits orders.
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
import xml.etree.ElementTree as ET  # nosec B405 — arXiv Atom API XML only
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.rag.document_ingestion_pipeline import DocumentIngestionPipeline

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "it",
    "its",
    "that",
    "this",
    "these",
    "those",
    "we",
    "you",
    "i",
    "as",
    "by",
    "from",
    "into",
    "about",
    "than",
    "our",
    "their",
}


def _tokens(text: str) -> set[str]:
    return {
        t
        for t in _TOKEN_RE.findall(text.lower())
        if len(t) > 2 and t not in _STOP
    }


def _lexical_overlap(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), 1)

ROOT = Path(__file__).resolve().parents[2]
ARXIV_DATA_DIR = ROOT / "data" / "arxiv"
ARXIV_MANIFEST_FILE = ROOT / "data" / "audit" / "arxiv_ingestion_manifest.json"
ARXIV_STATUS_FILE = ROOT / "data" / "runtime" / "arxiv_ingestion_latest.json"
ARXIV_CURATED_DIR = ROOT / "rag_knowledge" / "research" / "arxiv"

# Categories that map to trading / ML / RAG research.
DEFAULT_CATEGORIES = [
    "q-fin.TR",  # Trading and Market Microstructure
    "q-fin.PM",  # Portfolio Management
    "q-fin.RM",  # Risk Management
    "q-fin.CP",  # Computational Finance
    "q-fin.ST",  # Statistical Finance
    "cs.AI",  # Artificial Intelligence / Multi-Agent
    "cs.LG",  # Machine Learning / RL / GRPO
    "cs.CL",  # Language models / RAG
    "cs.MA",  # Multi-agent systems
]

# Keyword phrases used both for API search and domain scoring.
DEFAULT_KEYWORDS = [
    "options trading",
    "credit spread",
    "put credit",
    "iron condor",
    "market microstructure",
    "order book",
    "reinforcement learning trading",
    "GRPO",
    "portfolio optimization",
    "risk management options",
    "financial RAG",
    "retrieval augmented generation finance",
    "agentic trading",
    "quantitative trading",
]

# Tokens that strongly signal applicability to this repository.
DOMAIN_BOOST_TERMS = {
    "option": 0.08,
    "options": 0.08,
    "spy": 0.10,
    "credit": 0.06,
    "spread": 0.05,
    "put": 0.04,
    "iron": 0.04,
    "condor": 0.06,
    "microstructure": 0.07,
    "orderbook": 0.06,
    "grpo": 0.10,
    "ppo": 0.05,
    "reinforcement": 0.06,
    "trading": 0.05,
    "portfolio": 0.04,
    "risk": 0.03,
    "rag": 0.07,
    "retrieval": 0.05,
    "agentic": 0.06,
    "llm": 0.03,
    "market": 0.02,
    "volatility": 0.05,
    "delta": 0.04,
    "greeks": 0.05,
    "hedge": 0.04,
}

# Minimum composite relevance to ingest into RAG (0..1).
DEFAULT_MIN_RELEVANCE = 0.18
# Minimum composite relevance to promote into curated rag_knowledge/.
DEFAULT_PROMOTE_RELEVANCE = 0.28

ARXIV_API = "https://export.arxiv.org/api/query"
USER_AGENT = "IgorTradingLab-ArxivIngest/1.0 (research; paper-only RAG; contact: local)"


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
    faithfulness_score: float = 0.0
    groundedness_score: float = 0.0
    domain_boost: float = 0.0
    answer_relevance: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IngestionRunReport:
    """Structured summary for operators / DS / ML."""

    status: str
    fetched: int = 0
    ingested: int = 0
    skipped_duplicate: int = 0
    skipped_low_relevance: int = 0
    promoted: int = 0
    errors: list[str] = field(default_factory=list)
    papers: list[dict[str, Any]] = field(default_factory=list)
    query: str | None = None
    max_results: int = 0
    min_relevance: float = 0.0
    promote_relevance: float = 0.0
    total_manifest_papers: int = 0
    started_utc: str = ""
    finished_utc: str = ""
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ArxivCollector:
    """Collect papers from arXiv and ingest into RAG + curated research corpus."""

    def __init__(
        self,
        output_dir: Path | None = None,
        manifest_file: Path | None = None,
        status_file: Path | None = None,
        curated_dir: Path | None = None,
        *,
        min_relevance: float = DEFAULT_MIN_RELEVANCE,
        promote_relevance: float = DEFAULT_PROMOTE_RELEVANCE,
        pipeline: DocumentIngestionPipeline | None = None,
    ) -> None:
        self.output_dir = output_dir or ARXIV_DATA_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_file = manifest_file or ARXIV_MANIFEST_FILE
        self.status_file = status_file or ARXIV_STATUS_FILE
        self.curated_dir = curated_dir or ARXIV_CURATED_DIR
        self.min_relevance = float(min_relevance)
        self.promote_relevance = float(promote_relevance)
        self.manifest = self._load_manifest()
        self.ingestion_pipeline = pipeline or DocumentIngestionPipeline()

    def _load_manifest(self) -> dict[str, Any]:
        if self.manifest_file.exists():
            try:
                with self.manifest_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and "papers" in data:
                    return data
            except Exception as e:  # noqa: BLE001 — corrupt local cache is non-fatal
                logger.warning("Failed to load arXiv manifest: %s", e)
        return {
            "papers": {},
            "total_ingested": 0,
            "last_run_utc": "",
            "runs": [],
        }

    def _save_manifest(self) -> None:
        self.manifest_file.parent.mkdir(parents=True, exist_ok=True)
        with self.manifest_file.open("w", encoding="utf-8") as f:
            json.dump(self.manifest, f, indent=2, sort_keys=True)

    def _write_status(self, report: IngestionRunReport) -> None:
        self.status_file.parent.mkdir(parents=True, exist_ok=True)
        payload = report.to_dict()
        payload["schema_version"] = 1
        payload["source"] = "arxiv"
        payload["api"] = ARXIV_API
        with self.status_file.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def build_search_query(
        self,
        query: str | None = None,
        categories: list[str] | None = None,
        keywords: list[str] | None = None,
    ) -> str:
        """Build an arXiv API search_query string."""
        cats = categories or DEFAULT_CATEGORIES
        # Keep category clause compact — arXiv rejects extremely long queries.
        cat_query = " OR ".join(f"cat:{c}" for c in cats[:8])

        if query:
            # Free-text override still constrained to our category set.
            return f"all:({query}) AND ({cat_query})"

        kws = keywords or DEFAULT_KEYWORDS
        # Use a rotating subset of keywords so continuous runs stay diverse.
        day_index = datetime.datetime.now(datetime.UTC).timetuple().tm_yday
        window = 4
        start = (day_index * window) % max(len(kws), 1)
        selected = [kws[(start + i) % len(kws)] for i in range(min(window, len(kws)))]
        kw_query = " OR ".join(f'all:"{kw}"' for kw in selected)
        return f"({kw_query}) AND ({cat_query})"

    def fetch_papers(
        self,
        query: str | None = None,
        categories: list[str] | None = None,
        keywords: list[str] | None = None,
        max_results: int = 15,
        *,
        search_query: str | None = None,
    ) -> list[ArxivPaper]:
        """Fetch papers from the arXiv Atom API."""
        sq = search_query or self.build_search_query(
            query=query, categories=categories, keywords=keywords
        )
        params = {
            "search_query": sq,
            "start": 0,
            "max_results": max(1, min(int(max_results), 50)),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        url = f"{ARXIV_API}?{urllib.parse.urlencode(params)}"
        if not url.startswith("https://export.arxiv.org/"):
            logger.error("Refusing non-arXiv URL: %s", url[:80])
            return []
        logger.info("Querying arXiv API: %s", url)

        xml_data = self._http_get_with_retry(url)
        if xml_data is None:
            return []
        return self._parse_arxiv_atom(xml_data)

    def _http_get_with_retry(self, url: str, *, attempts: int = 5) -> bytes | None:
        """GET with backoff for arXiv 429 / transient network errors."""
        if not url.startswith("https://export.arxiv.org/"):
            logger.error("Refusing non-arXiv URL")
            return None
        delay = 3.0
        last_err: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                # Fixed https host export.arxiv.org only (no user-controlled schemes).
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=45) as resp:  # nosec B310
                    return resp.read()
            except urllib.error.HTTPError as e:
                last_err = e
                if e.code == 429:
                    retry_after = e.headers.get("Retry-After") if e.headers else None
                    wait = float(retry_after) if retry_after and str(retry_after).isdigit() else delay
                    logger.warning(
                        "arXiv rate limited (429) attempt %d/%d; sleeping %.1fs",
                        attempt,
                        attempts,
                        wait,
                    )
                    time.sleep(wait)
                    delay = min(delay * 2, 60.0)
                    continue
                logger.error("arXiv API HTTP %s: %s", e.code, e)
                return None
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last_err = e
                logger.warning(
                    "arXiv API request failed attempt %d/%d: %s",
                    attempt,
                    attempts,
                    e,
                )
                time.sleep(delay)
                delay = min(delay * 2, 60.0)
        logger.error("arXiv API request failed after %d attempts: %s", attempts, last_err)
        return None

    def _parse_arxiv_atom(self, xml_bytes: bytes) -> list[ArxivPaper]:
        papers: list[ArxivPaper] = []
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }
        try:
            root = ET.fromstring(xml_bytes)  # nosec B314 — arXiv Atom feed only
        except ET.ParseError as e:
            logger.error("Failed to parse arXiv XML response: %s", e)
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

            abs_url = id_text or f"https://arxiv.org/abs/{arxiv_id}"
            pdf_url = ""
            for link in entry.findall("atom:link", ns):
                if link.attrib.get("title") == "pdf":
                    pdf_url = link.attrib.get("href", "")
                    break
            if not pdf_url:
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            # Prefer https
            abs_url = abs_url.replace("http://", "https://")
            pdf_url = pdf_url.replace("http://", "https://")

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

    def _domain_boost(self, paper: ArxivPaper) -> float:
        text = f"{paper.title} {paper.summary} {' '.join(paper.categories)}".lower()
        # Normalize compound tokens
        text = text.replace("order book", "orderbook").replace("iron condor", "iron condor")
        boost = 0.0
        for term, weight in DOMAIN_BOOST_TERMS.items():
            if term in text:
                boost += weight
        # Soft cap so keyword stuffing cannot dominate.
        return min(boost, 0.45)

    def evaluate_paper_relevance(self, paper: ArxivPaper) -> ArxivPaper:
        """Grade paper relevance for this trading lab's DS/ML/RAG stack.

        Dependency-free lexical scoring (no optional embedding/LLM judges) so
        CI and LaunchAgent runs stay deterministic and offline-safe.
        """
        context = (
            "Paper-first SPY put credit spreads defined-risk options credit spreads. "
            "Group Relative Policy Optimization GRPO reinforcement learning for trading. "
            "Market microstructure order books statistical finance risk management. "
            "Agentic RAG temporal graph RAG faithfulness groundedness evaluation. "
            "Kill criteria expectancy profit factor inventory hygiene no naked options."
        )
        question = (
            "quantitative options trading risk-controlled credit spreads "
            "GRPO RL policy learning financial RAG agentic retrieval"
        )
        answer = f"{paper.title}. {paper.summary}"

        # Groundedness ≈ answer tokens supported by lab context
        groundedness = _lexical_overlap(answer, context)
        # Faithfulness proxy: fraction of context-overlapping answer tokens
        # (symmetric overlap favors papers that speak the lab's language)
        faithfulness = _lexical_overlap(context, answer)
        # Answer relevance: does the paper address the research question tokens?
        answer_relevance = _lexical_overlap(question, answer)

        paper.faithfulness_score = round(faithfulness, 3)
        paper.groundedness_score = round(groundedness, 3)
        paper.answer_relevance = round(answer_relevance, 3)
        paper.domain_boost = round(self._domain_boost(paper), 3)

        base = (faithfulness * 0.30) + (answer_relevance * 0.35) + (groundedness * 0.15)
        paper.relevance_score = round(min(1.0, base + paper.domain_boost), 3)
        return paper

    def _markdown_for_paper(self, paper: ArxivPaper) -> str:
        authors = ", ".join(paper.authors) if paper.authors else "(unknown)"
        cats = ", ".join(paper.categories) if paper.categories else "(none)"
        return f"""# arXiv Paper: {paper.title}

- **arXiv ID**: `{paper.arxiv_id}`
- **Published**: {paper.published}
- **Updated**: {paper.updated}
- **Authors**: {authors}
- **Categories**: {cats}
- **URL**: [{paper.abs_url}]({paper.abs_url})
- **PDF**: [{paper.pdf_url}]({paper.pdf_url})
- **Source**: continuous arXiv ingestion job (Agentic RAG)

## RAG Quality Scores

- **Relevance Score**: {paper.relevance_score}
- **Domain Boost**: {paper.domain_boost}
- **Faithfulness Score**: {paper.faithfulness_score}
- **Groundedness Score**: {paper.groundedness_score}
- **Answer Relevance**: {paper.answer_relevance}

## Abstract / Summary

{paper.summary}

## Trading System Applicability

Automatically ingested for Data Science, ML (GRPO/RL), and Agentic RAG research.
Does **not** authorize live capital, iron-condor re-entry, or profit claims.
Use only as research context against broker-reconciled evidence and kill criteria.
"""

    def ingest_paper(
        self,
        paper: ArxivPaper,
        *,
        force: bool = False,
    ) -> dict[str, Any]:
        """Ingest one paper into local markdown + DocumentIngestionPipeline."""
        paper = self.evaluate_paper_relevance(paper)

        if not force and paper.relevance_score < self.min_relevance:
            return {
                "arxiv_id": paper.arxiv_id,
                "title": paper.title,
                "relevance_score": paper.relevance_score,
                "status": "skipped_low_relevance",
                "chunks_created": 0,
                "is_duplicate": False,
                "promoted": False,
            }

        clean_id = re.sub(r"[^a-zA-Z0-9_.-]", "_", paper.arxiv_id)
        filename = f"arxiv_{clean_id.replace('.', '_')}.md"
        file_path = self.output_dir / filename
        md_content = self._markdown_for_paper(paper)
        file_path.write_text(md_content, encoding="utf-8")

        doc = self.ingestion_pipeline.ingest_document(file_path, md_content)

        promoted = False
        curated_path: str | None = None
        if paper.relevance_score >= self.promote_relevance:
            promoted = self._promote_to_curated(paper, md_content)
            if promoted:
                curated_path = str(self.curated_dir / filename)

        now = datetime.datetime.now(datetime.UTC).isoformat()
        self.manifest["papers"][paper.arxiv_id] = {
            "title": paper.title,
            "published": paper.published,
            "categories": paper.categories,
            "relevance_score": paper.relevance_score,
            "domain_boost": paper.domain_boost,
            "faithfulness_score": paper.faithfulness_score,
            "groundedness_score": paper.groundedness_score,
            "answer_relevance": paper.answer_relevance,
            "file_path": str(file_path),
            "curated_path": curated_path,
            "promoted": promoted,
            "ingested_at": now,
            "abs_url": paper.abs_url,
            "pdf_url": paper.pdf_url,
        }
        self.manifest["total_ingested"] = len(self.manifest["papers"])
        self.manifest["last_run_utc"] = now
        self._save_manifest()

        logger.info(
            "Ingested arXiv %s (rel=%.3f promote=%s): %s",
            paper.arxiv_id,
            paper.relevance_score,
            promoted,
            paper.title[:80],
        )
        return {
            "arxiv_id": paper.arxiv_id,
            "title": paper.title,
            "relevance_score": paper.relevance_score,
            "domain_boost": paper.domain_boost,
            "file_path": str(file_path),
            "chunks_created": len(doc.chunks),
            "is_duplicate": doc.is_duplicate,
            "promoted": promoted,
            "curated_path": curated_path,
            "status": "ingested",
            "abs_url": paper.abs_url,
        }

    def _promote_to_curated(self, paper: ArxivPaper, md_content: str) -> bool:
        """Copy high-relevance papers into rag_knowledge for index rebuilds."""
        try:
            self.curated_dir.mkdir(parents=True, exist_ok=True)
            clean_id = re.sub(r"[^a-zA-Z0-9_.-]", "_", paper.arxiv_id)
            filename = f"arxiv_{clean_id.replace('.', '_')}.md"
            target = self.curated_dir / filename
            # Header note so curated corpus is clearly research-only.
            header = (
                "---\n"
                f"source: arxiv\n"
                f"arxiv_id: {paper.arxiv_id}\n"
                f"relevance: {paper.relevance_score}\n"
                f"kind: research_paper\n"
                f"strategy_scope: research_only\n"
                "---\n\n"
            )
            target.write_text(header + md_content, encoding="utf-8")
            return True
        except OSError as e:
            logger.warning("Failed to promote arXiv %s: %s", paper.arxiv_id, e)
            return False

    def run_continuous_ingestion(
        self,
        query: str | None = None,
        max_results: int = 15,
        *,
        categories: list[str] | None = None,
        keywords: list[str] | None = None,
        force: bool = False,
    ) -> IngestionRunReport:
        """Fetch, dedupe, grade, filter, and ingest papers."""
        started = datetime.datetime.now(datetime.UTC)
        search_query = self.build_search_query(
            query=query, categories=categories, keywords=keywords
        )
        report = IngestionRunReport(
            status="OK",
            query=search_query,
            max_results=max_results,
            min_relevance=self.min_relevance,
            promote_relevance=self.promote_relevance,
            started_utc=started.isoformat(),
        )

        papers = self.fetch_papers(
            query=query,
            categories=categories,
            keywords=keywords,
            max_results=max_results,
            search_query=search_query,
        )
        report.fetched = len(papers)

        if not papers:
            report.status = "EMPTY_OR_API_ERROR"
            report.errors.append("No papers returned from arXiv API")
            finished = datetime.datetime.now(datetime.UTC)
            report.finished_utc = finished.isoformat()
            report.duration_ms = (finished - started).total_seconds() * 1000
            report.total_manifest_papers = len(self.manifest.get("papers", {}))
            self._write_status(report)
            self._append_run_summary(report)
            return report

        for paper in papers:
            if paper.arxiv_id in self.manifest.get("papers", {}) and not force:
                logger.info("Paper %s already ingested; skipping.", paper.arxiv_id)
                report.skipped_duplicate += 1
                continue
            try:
                result = self.ingest_paper(paper, force=force)
            except Exception as e:  # noqa: BLE001 — keep job alive across bad papers
                logger.exception("Failed to ingest %s", paper.arxiv_id)
                report.errors.append(f"{paper.arxiv_id}: {e}")
                continue

            if result.get("status") == "skipped_low_relevance":
                report.skipped_low_relevance += 1
                continue

            report.ingested += 1
            if result.get("promoted"):
                report.promoted += 1
            report.papers.append(result)

        finished = datetime.datetime.now(datetime.UTC)
        report.finished_utc = finished.isoformat()
        report.duration_ms = round((finished - started).total_seconds() * 1000, 1)
        report.total_manifest_papers = len(self.manifest.get("papers", {}))
        if report.errors and report.ingested == 0:
            report.status = "ERROR"
        elif report.errors:
            report.status = "PARTIAL"

        self._write_status(report)
        self._append_run_summary(report)
        logger.info(
            "arXiv ingestion done: fetched=%d ingested=%d dup=%d low_rel=%d promoted=%d",
            report.fetched,
            report.ingested,
            report.skipped_duplicate,
            report.skipped_low_relevance,
            report.promoted,
        )
        return report

    def _append_run_summary(self, report: IngestionRunReport) -> None:
        runs = self.manifest.setdefault("runs", [])
        if not isinstance(runs, list):
            runs = []
            self.manifest["runs"] = runs
        runs.append(
            {
                "finished_utc": report.finished_utc,
                "status": report.status,
                "fetched": report.fetched,
                "ingested": report.ingested,
                "skipped_duplicate": report.skipped_duplicate,
                "skipped_low_relevance": report.skipped_low_relevance,
                "promoted": report.promoted,
                "errors": report.errors[:5],
            }
        )
        # Bound history so the manifest stays small.
        if len(runs) > 50:
            self.manifest["runs"] = runs[-50:]
        self.manifest["last_run_utc"] = report.finished_utc
        self._save_manifest()
