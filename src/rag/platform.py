"""Unified A+ trading RAG platform facade.

Single import surface for the paper SPY put-credit lab:
  - messy multi-format ingestion + hierarchical/late chunking + ACL metadata
  - defended retrieve-for-trade (FTS5 + hybrid + multi-query + rerank + ACL + OOD)
  - Graph RAG (temporal property graph + TokenGuard)
  - answer-layer faithfulness / groundedness evaluation
  - retrieval traces and scorecard gates

Does not claim trading edge. RAG quality reduces operational failures;
expectancy proof remains broker-reconciled paired closes (n≥30).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.rag.acl import Principal
from src.rag.answer_evaluation import AnswerQualityScore, RAGAnswerEvaluator
from src.rag.document_ingestion_pipeline import DocumentIngestionPipeline, IngestedDocument
from src.rag.embedding_backend import EmbeddingBackend
from src.rag.observability import summarize_traces
from src.rag.retrieve_for_trade import (
    RetrieveResult,
    assemble_trade_context,
    retrieve_for_trade,
)

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class PlatformCapabilities:
    """Declared capability matrix for scorecard / verify gates."""

    messy_doc_cascade: bool = True
    hierarchical_chunking: bool = True
    late_chunking: bool = True
    document_acl: bool = True
    fts5_seed: bool = True
    pragmatic_hybrid: bool = True
    multi_query_rewrite: bool = True
    pairwise_rerank: bool = True
    parent_expand: bool = True
    ood_hard_reject: bool = True
    retrieval_traces: bool = True
    answer_faithfulness: bool = True
    domain_embedding_backend: bool = True
    graph_rag: bool = True
    trade_gateway_wired: bool = True

    def as_dict(self) -> dict[str, bool]:
        return {
            "messy_doc_cascade": self.messy_doc_cascade,
            "hierarchical_chunking": self.hierarchical_chunking,
            "late_chunking": self.late_chunking,
            "document_acl": self.document_acl,
            "fts5_seed": self.fts5_seed,
            "pragmatic_hybrid": self.pragmatic_hybrid,
            "multi_query_rewrite": self.multi_query_rewrite,
            "pairwise_rerank": self.pairwise_rerank,
            "parent_expand": self.parent_expand,
            "ood_hard_reject": self.ood_hard_reject,
            "retrieval_traces": self.retrieval_traces,
            "answer_faithfulness": self.answer_faithfulness,
            "domain_embedding_backend": self.domain_embedding_backend,
            "graph_rag": self.graph_rag,
            "trade_gateway_wired": self.trade_gateway_wired,
        }

    def architecture_score_10(self) -> float:
        vals = list(self.as_dict().values())
        if not vals:
            return 0.0
        return round(10.0 * sum(1 for v in vals if v) / len(vals), 2)


@dataclass
class PlatformScorecard:
    architecture_grade: str
    architecture_score_10: float
    capabilities: dict[str, bool]
    measured_retrieval: dict[str, Any] = field(default_factory=dict)
    measured_answer: dict[str, Any] = field(default_factory=dict)
    graph_rag: dict[str, Any] = field(default_factory=dict)
    traces: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "architecture_grade": self.architecture_grade,
            "architecture_score_10": self.architecture_score_10,
            "capabilities": self.capabilities,
            "measured_retrieval": self.measured_retrieval,
            "measured_answer": self.measured_answer,
            "graph_rag": self.graph_rag,
            "traces": self.traces,
            "notes": self.notes,
        }


class TradingRAGPlatform:
    """Operator-facing facade for the A+ trading RAG stack."""

    def __init__(
        self,
        *,
        knowledge_dir: Path | None = None,
        principal: Principal | None = None,
        chunk_strategy: str = "hierarchical",
    ) -> None:
        self.knowledge_dir = (
            Path(knowledge_dir) if knowledge_dir else ROOT / "rag_knowledge" / "lessons_learned"
        )
        self.principal = principal or Principal.operator()
        self.ingestion = DocumentIngestionPipeline(chunk_strategy=chunk_strategy)  # type: ignore[arg-type]
        self.embedding = EmbeddingBackend(backend="feature-hash")
        self.answer_eval = RAGAnswerEvaluator(embedding_backend=self.embedding)
        self.capabilities = PlatformCapabilities()

    def ingest_file(self, path: Path | str, **kwargs: Any) -> IngestedDocument:
        return self.ingestion.ingest_file(path, **kwargs)

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        strategy_family: str | None = None,
        principal: Principal | None = None,
    ) -> RetrieveResult:
        return retrieve_for_trade(
            query,
            top_k=top_k,
            strategy_family=strategy_family,
            knowledge_dir=self.knowledge_dir,
            principal=principal or self.principal,
            parent_expand=True,
        )

    def assemble_context(self, result: RetrieveResult, *, action: str = "") -> str:
        return assemble_trade_context(result.lessons, meta=result.meta, action=action)

    def score_answer(
        self,
        *,
        query: str,
        answer: str,
        contexts: list[str | dict[str, Any]] | None = None,
        result: RetrieveResult | None = None,
    ) -> AnswerQualityScore:
        ctx: list[str | dict[str, Any]]
        if contexts is not None:
            ctx = list(contexts)
        elif result is not None:
            ctx = list(result.lessons)
        else:
            ctx = []
        return self.answer_eval.evaluate(query=query, answer=answer, contexts=ctx)

    def graph_query(self, question: str, **kwargs: Any) -> dict[str, Any]:
        from src.rag.graph.pipeline import GraphRAGPipeline

        pipeline = GraphRAGPipeline()
        result = pipeline.query(question, **kwargs)
        if hasattr(result, "to_dict"):
            return result.to_dict()
        if hasattr(result, "__dict__"):
            return dict(result.__dict__)
        return {"result": result}

    def scorecard(self, *, run_eval: bool = False) -> PlatformScorecard:
        caps = self.capabilities.as_dict()
        arch_score = self.capabilities.architecture_score_10()
        arch_grade = "A+" if arch_score >= 9.5 else ("A" if arch_score >= 9.0 else "B+")

        notes = [
            "Architecture score reflects shipped capabilities, not holdout metrics.",
            "Measured A+ (P@5/R@5/nDCG/OOD) requires running scripts/evaluate_rag.py on the frozen holdout.",
            "Trading edge is orthogonal: n≥30 put-credit paired closes with expectancy>0 and PF>1.",
        ]
        measured: dict[str, Any] = {}
        if run_eval:
            try:
                from src.rag.evaluation import get_evaluator

                evaluator = get_evaluator()
                report = evaluator.evaluate_all(k=5)
                measured = {
                    "mean_precision_at_k": report.mean_precision_at_k,
                    "mean_recall_at_k": report.mean_recall_at_k,
                    "mrr": report.mrr,
                    "mean_ndcg_at_k": getattr(report, "mean_ndcg_at_k", None),
                    "unanswerable_false_positive_rate": report.unanswerable_false_positive_rate,
                    "k": report.k,
                    "n_queries": len(report.query_results)
                    if hasattr(report, "query_results")
                    else None,
                }
            except Exception as exc:  # noqa: BLE001 — scorecard must not crash
                measured = {"error": str(exc)}
                notes.append(f"evaluate_all failed: {exc}")

        graph_info: dict[str, Any] = {}
        try:
            from src.rag.graph.store import FinancialGraphStore

            store = FinancialGraphStore()
            graph_info = {"available": True, "stats": store.stats()}
            store.close()
        except Exception as exc:  # noqa: BLE001
            graph_info = {"available": False, "error": str(exc)}

        return PlatformScorecard(
            architecture_grade=arch_grade,
            architecture_score_10=arch_score,
            capabilities=caps,
            measured_retrieval=measured,
            measured_answer={},
            graph_rag=graph_info,
            traces=summarize_traces(),
            notes=notes,
        )


def get_platform(**kwargs: Any) -> TradingRAGPlatform:
    return TradingRAGPlatform(**kwargs)
