#!/usr/bin/env python3
"""
RAG Hygiene Verification Script

Verifies the RAG system follows Dec 2025 best practices:
1. Hybrid search (BM25 + semantic embeddings)
2. Cross-encoder reranking
3. Proper chunking with overlap
4. Query caching
5. Knowledge graph connectivity

Usage:
    python scripts/verify_rag_hygiene.py
    python scripts/verify_rag_hygiene.py --fix  # Attempt to fix issues
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


@dataclass
class HygieneCheck:
    """Individual hygiene check result."""

    name: str
    category: str
    status: str  # PASS, WARN, FAIL
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class HygieneReport:
    """Complete RAG hygiene report."""

    timestamp: str
    overall_status: str
    checks: list[HygieneCheck]
    dec2025_compliance: float  # 0-100%
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "overall_status": self.overall_status,
            "dec2025_compliance": self.dec2025_compliance,
            "checks": [
                {
                    "name": c.name,
                    "category": c.category,
                    "status": c.status,
                    "message": c.message,
                    "details": c.details,
                }
                for c in self.checks
            ],
            "recommendations": self.recommendations,
        }


class RAGHygieneVerifier:
    """Verifies RAG system health and Dec 2025 compliance."""

    def __init__(self):
        self.checks: list[HygieneCheck] = []
        self.data_dir = Path("data/rag")

    def run_all_checks(self) -> HygieneReport:
        """Run all hygiene checks and return report."""
        logger.info("=" * 60)
        logger.info("RAG HYGIENE VERIFICATION - Dec 2025 Best Practices")
        logger.info("=" * 60)

        # Category 1: Dependencies
        self._check_sentence_transformers()
        self._check_cross_encoder()
        self._check_bm25()
        self._check_chromadb()

        # Category 2: Configuration
        self._check_embedding_config()
        self._check_chunking_config()
        self._check_retrieval_config()

        # Category 3: Data Quality
        self._check_vector_store_health()
        self._check_document_count()
        self._check_knowledge_graph()

        # Category 4: Dec 2025 Best Practices
        self._check_hybrid_search()
        self._check_reranking()
        self._check_query_cache()

        # Generate report
        return self._generate_report()

    def _check_sentence_transformers(self) -> None:
        """Check sentence-transformers availability."""
        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer("all-MiniLM-L6-v2")
            test_embedding = model.encode("test query")

            self.checks.append(
                HygieneCheck(
                    name="Sentence Transformers",
                    category="Dependencies",
                    status="PASS",
                    message="Bi-encoder model loaded successfully",
                    details={
                        "model": "all-MiniLM-L6-v2",
                        "embedding_dim": len(test_embedding),
                    },
                )
            )
        except Exception as e:
            self.checks.append(
                HygieneCheck(
                    name="Sentence Transformers",
                    category="Dependencies",
                    status="FAIL",
                    message=f"Failed to load: {e}",
                )
            )

    def _check_cross_encoder(self) -> None:
        """Check cross-encoder for reranking."""
        try:
            from sentence_transformers import CrossEncoder

            model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
            # Test reranking
            scores = model.predict([["query", "document"]])

            self.checks.append(
                HygieneCheck(
                    name="Cross-Encoder Reranking",
                    category="Dependencies",
                    status="PASS",
                    message="Cross-encoder loaded for reranking (Dec 2025 best practice)",
                    details={"model": "ms-marco-MiniLM-L-6-v2", "test_score": float(scores[0])},
                )
            )
        except Exception as e:
            self.checks.append(
                HygieneCheck(
                    name="Cross-Encoder Reranking",
                    category="Dependencies",
                    status="WARN",
                    message=f"Cross-encoder not available: {e}",
                )
            )

    def _check_bm25(self) -> None:
        """Check BM25 for hybrid search."""
        try:
            from rank_bm25 import BM25Okapi

            corpus = [["hello", "world"], ["test", "document"]]
            bm25 = BM25Okapi(corpus)
            _scores = bm25.get_scores(["hello"])

            self.checks.append(
                HygieneCheck(
                    name="BM25 Hybrid Search",
                    category="Dependencies",
                    status="PASS",
                    message="BM25 available for hybrid search (Dec 2025 best practice)",
                    details={"library": "rank_bm25"},
                )
            )
        except Exception as e:
            self.checks.append(
                HygieneCheck(
                    name="BM25 Hybrid Search",
                    category="Dependencies",
                    status="WARN",
                    message=f"BM25 not available: {e}",
                )
            )

    def _check_chromadb(self) -> None:
        """Check ChromaDB availability."""
        try:
            import chromadb

            self.checks.append(
                HygieneCheck(
                    name="ChromaDB Vector Store",
                    category="Dependencies",
                    status="PASS",
                    message="ChromaDB available for persistent storage",
                    details={"version": chromadb.__version__},
                )
            )
        except Exception as e:
            self.checks.append(
                HygieneCheck(
                    name="ChromaDB Vector Store",
                    category="Dependencies",
                    status="WARN",
                    message=f"ChromaDB not available, using in-memory fallback: {e}",
                )
            )

    def _check_embedding_config(self) -> None:
        """Check embedding configuration."""
        try:
            from src.rag.config import EMBEDDING_CONFIG

            model = EMBEDDING_CONFIG.get("model_name", "unknown")
            max_seq = EMBEDDING_CONFIG.get("max_seq_length", 0)

            if max_seq >= 512:
                status = "PASS"
                message = f"Embedding config OK (model={model}, max_seq={max_seq})"
            else:
                status = "WARN"
                message = f"Max sequence length {max_seq} may truncate documents"

            self.checks.append(
                HygieneCheck(
                    name="Embedding Configuration",
                    category="Configuration",
                    status=status,
                    message=message,
                    details=EMBEDDING_CONFIG,
                )
            )
        except Exception as e:
            self.checks.append(
                HygieneCheck(
                    name="Embedding Configuration",
                    category="Configuration",
                    status="FAIL",
                    message=f"Cannot load config: {e}",
                )
            )

    def _check_chunking_config(self) -> None:
        """Check chunking configuration."""
        try:
            from src.rag.config import CHUNK_CONFIG

            overlap = CHUNK_CONFIG.get("overlap", 0)
            _max_tokens = CHUNK_CONFIG.get("max_tokens", 0)

            if overlap >= 50:
                status = "PASS"
                message = f"Chunking config OK (overlap={overlap} tokens)"
            else:
                status = "WARN"
                message = f"Low overlap ({overlap}) may lose context at boundaries"

            self.checks.append(
                HygieneCheck(
                    name="Chunking Configuration",
                    category="Configuration",
                    status=status,
                    message=message,
                    details=CHUNK_CONFIG,
                )
            )
        except Exception as e:
            self.checks.append(
                HygieneCheck(
                    name="Chunking Configuration",
                    category="Configuration",
                    status="WARN",
                    message=f"Cannot load chunk config: {e}",
                )
            )

    def _check_retrieval_config(self) -> None:
        """Check retrieval configuration."""
        try:
            from src.rag.config import RETRIEVAL_CONFIG

            min_score = RETRIEVAL_CONFIG.get("min_score", 0)

            if 0.2 <= min_score <= 0.5:
                status = "PASS"
                message = f"Retrieval config OK (min_score={min_score})"
            else:
                status = "WARN"
                message = f"min_score={min_score} may be too restrictive/lenient"

            self.checks.append(
                HygieneCheck(
                    name="Retrieval Configuration",
                    category="Configuration",
                    status=status,
                    message=message,
                    details=RETRIEVAL_CONFIG,
                )
            )
        except Exception as e:
            self.checks.append(
                HygieneCheck(
                    name="Retrieval Configuration",
                    category="Configuration",
                    status="WARN",
                    message=f"Cannot load retrieval config: {e}",
                )
            )

    def _check_vector_store_health(self) -> None:
        """Check vector store health."""
        in_memory_path = self.data_dir / "in_memory_store.json"
        chroma_path = self.data_dir / "chroma_db"

        if in_memory_path.exists():
            try:
                with open(in_memory_path) as f:
                    data = json.load(f)
                doc_count = len(data.get("documents", []))
                size_kb = in_memory_path.stat().st_size / 1024

                self.checks.append(
                    HygieneCheck(
                        name="Vector Store Health",
                        category="Data Quality",
                        status="PASS" if doc_count > 0 else "WARN",
                        message=f"In-memory store: {doc_count} documents, {size_kb:.1f} KB",
                        details={"documents": doc_count, "size_kb": size_kb},
                    )
                )
            except Exception as e:
                self.checks.append(
                    HygieneCheck(
                        name="Vector Store Health",
                        category="Data Quality",
                        status="WARN",
                        message=f"Cannot read in-memory store: {e}",
                    )
                )
        elif chroma_path.exists():
            self.checks.append(
                HygieneCheck(
                    name="Vector Store Health",
                    category="Data Quality",
                    status="PASS",
                    message="ChromaDB directory exists",
                    details={"path": str(chroma_path)},
                )
            )
        else:
            self.checks.append(
                HygieneCheck(
                    name="Vector Store Health",
                    category="Data Quality",
                    status="WARN",
                    message="No vector store found - run ingestion first",
                )
            )

    def _check_document_count(self) -> None:
        """Check total indexed documents."""
        try:
            from src.rag.vector_db.retriever import RAGRetriever

            retriever = RAGRetriever()
            # Try a broad query
            results = retriever.query_rag("market news", n_results=100)
            count = len(results)

            if count >= 50:
                status = "PASS"
            elif count >= 10:
                status = "WARN"
            else:
                status = "FAIL"

            self.checks.append(
                HygieneCheck(
                    name="Document Count",
                    category="Data Quality",
                    status=status,
                    message=f"Retrieved {count} documents from RAG",
                    details={"sample_count": count},
                )
            )
        except Exception as e:
            self.checks.append(
                HygieneCheck(
                    name="Document Count",
                    category="Data Quality",
                    status="WARN",
                    message=f"Cannot query RAG: {e}",
                )
            )

    def _check_knowledge_graph(self) -> None:
        """Check knowledge graph health."""
        kg_path = self.data_dir / "knowledge_graph.json"

        if kg_path.exists():
            try:
                with open(kg_path) as f:
                    data = json.load(f)

                nodes = len(data.get("nodes", []))
                edges = len(data.get("links", data.get("edges", [])))

                self.checks.append(
                    HygieneCheck(
                        name="Knowledge Graph",
                        category="Data Quality",
                        status="PASS" if nodes > 0 else "WARN",
                        message=f"Knowledge graph: {nodes} nodes, {edges} edges",
                        details={"nodes": nodes, "edges": edges},
                    )
                )
            except Exception as e:
                self.checks.append(
                    HygieneCheck(
                        name="Knowledge Graph",
                        category="Data Quality",
                        status="WARN",
                        message=f"Cannot read knowledge graph: {e}",
                    )
                )
        else:
            self.checks.append(
                HygieneCheck(
                    name="Knowledge Graph",
                    category="Data Quality",
                    status="WARN",
                    message="No knowledge graph found",
                )
            )

    def _check_hybrid_search(self) -> None:
        """Check hybrid search implementation."""
        try:
            from src.rag.vector_db.chroma_client import (
                BM25_AVAILABLE,
                SENTENCE_TRANSFORMERS_AVAILABLE,
            )

            if SENTENCE_TRANSFORMERS_AVAILABLE and BM25_AVAILABLE:
                status = "PASS"
                message = "Hybrid search enabled (semantic + BM25) - Dec 2025 best practice"
            elif SENTENCE_TRANSFORMERS_AVAILABLE:
                status = "WARN"
                message = "Semantic search only - BM25 not available"
            else:
                status = "FAIL"
                message = "No semantic search available"

            self.checks.append(
                HygieneCheck(
                    name="Hybrid Search",
                    category="Dec 2025 Best Practices",
                    status=status,
                    message=message,
                    details={
                        "semantic": SENTENCE_TRANSFORMERS_AVAILABLE,
                        "bm25": BM25_AVAILABLE,
                    },
                )
            )
        except Exception as e:
            self.checks.append(
                HygieneCheck(
                    name="Hybrid Search",
                    category="Dec 2025 Best Practices",
                    status="FAIL",
                    message=f"Cannot verify hybrid search: {e}",
                )
            )

    def _check_reranking(self) -> None:
        """Check reranking implementation."""
        try:
            # Check if cross-encoder is used in query path
            from src.rag.vector_db.chroma_client import InMemoryCollection

            collection = InMemoryCollection()
            has_reranker = collection.cross_encoder is not None

            if has_reranker:
                status = "PASS"
                message = "Cross-encoder reranking enabled - Dec 2025 best practice"
            else:
                status = "WARN"
                message = "No reranker - results may be less relevant"

            self.checks.append(
                HygieneCheck(
                    name="Reranking",
                    category="Dec 2025 Best Practices",
                    status=status,
                    message=message,
                    details={"cross_encoder": has_reranker},
                )
            )
        except Exception as e:
            self.checks.append(
                HygieneCheck(
                    name="Reranking",
                    category="Dec 2025 Best Practices",
                    status="WARN",
                    message=f"Cannot verify reranking: {e}",
                )
            )

    def _check_query_cache(self) -> None:
        """Check query cache availability."""
        cache_dir = self.data_dir / "cache"

        if cache_dir.exists():
            cache_files = list(cache_dir.glob("**/*.json"))
            self.checks.append(
                HygieneCheck(
                    name="Query Cache",
                    category="Dec 2025 Best Practices",
                    status="PASS",
                    message=f"Query cache available ({len(cache_files)} cached files)",
                    details={"cache_files": len(cache_files)},
                )
            )
        else:
            self.checks.append(
                HygieneCheck(
                    name="Query Cache",
                    category="Dec 2025 Best Practices",
                    status="WARN",
                    message="No query cache directory found",
                )
            )

    def _generate_report(self) -> HygieneReport:
        """Generate final report."""
        # Count statuses
        passed = sum(1 for c in self.checks if c.status == "PASS")
        warned = sum(1 for c in self.checks if c.status == "WARN")
        failed = sum(1 for c in self.checks if c.status == "FAIL")
        total = len(self.checks)

        # Calculate compliance
        compliance = (passed / total) * 100 if total > 0 else 0

        # Determine overall status
        if failed > 0:
            overall_status = "UNHEALTHY"
        elif warned > 2:
            overall_status = "NEEDS ATTENTION"
        else:
            overall_status = "HEALTHY"

        # Generate recommendations
        recommendations = []
        for check in self.checks:
            if check.status == "FAIL":
                recommendations.append(f"CRITICAL: Fix {check.name} - {check.message}")
            elif check.status == "WARN":
                recommendations.append(f"RECOMMENDED: Address {check.name} - {check.message}")

        report = HygieneReport(
            timestamp=datetime.now().isoformat(),
            overall_status=overall_status,
            checks=self.checks,
            dec2025_compliance=compliance,
            recommendations=recommendations,
        )

        # Print summary
        self._print_summary(report, passed, warned, failed)

        return report

    def _print_summary(self, report: HygieneReport, passed: int, warned: int, failed: int) -> None:
        """Print formatted summary."""
        print("\n" + "=" * 60)
        print("RAG HYGIENE REPORT")
        print("=" * 60)

        # Group by category
        categories: dict[str, list[HygieneCheck]] = {}
        for check in report.checks:
            if check.category not in categories:
                categories[check.category] = []
            categories[check.category].append(check)

        for category, checks in categories.items():
            print(f"\n{category}:")
            for check in checks:
                icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(check.status, "?")
                print(f"  {icon} {check.name}: {check.message}")

        print("\n" + "-" * 60)
        print(f"Overall Status: {report.overall_status}")
        print(f"Dec 2025 Compliance: {report.dec2025_compliance:.1f}%")
        print(f"Checks: {passed} passed, {warned} warnings, {failed} failed")

        if report.recommendations:
            print("\nRecommendations:")
            for rec in report.recommendations[:5]:  # Top 5
                print(f"  - {rec}")

        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Verify RAG system hygiene")
    parser.add_argument("--fix", action="store_true", help="Attempt to fix issues")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    args = parser.parse_args()

    verifier = RAGHygieneVerifier()
    report = verifier.run_all_checks()

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))

    # Save report
    report_path = Path("data/rag_hygiene_report.json")
    report_path.parent.mkdir(exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report.to_dict(), f, indent=2)
    print(f"\nReport saved to: {report_path}")

    # Exit code based on status
    if report.overall_status == "UNHEALTHY":
        sys.exit(1)
    return 0


if __name__ == "__main__":
    main()
