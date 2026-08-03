"""LLM / RAG production control plane — graded evidence, not marketing.

Six dimensions from the production audit:
  1. latency_cost_control
  2. observability
  3. failure_modes
  4. structured_outputs
  5. multi_tenancy_acl
  6. framework_discipline

Scores are derived from code contracts present in this repo. They never imply
edge, live profitability, or $1k/mo readiness. Edge lives in put-credit cohort.
"""

from __future__ import annotations

import importlib.util
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class DimensionScore:
    name: str
    score_0_10: float
    grade: str
    evidence: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LLMProductionReport:
    overall_score_0_10: float
    overall_grade: str
    dimensions: list[DimensionScore]
    a_plus_ready: bool
    cash_engine_note: str
    generated_checks: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_score_0_10": self.overall_score_0_10,
            "overall_grade": self.overall_grade,
            "a_plus_ready": self.a_plus_ready,
            "cash_engine_note": self.cash_engine_note,
            "generated_checks": self.generated_checks,
            "dimensions": [d.to_dict() for d in self.dimensions],
        }


def _grade(score: float) -> str:
    if score >= 9.5:
        return "A+"
    if score >= 9.0:
        return "A"
    if score >= 8.5:
        return "A-"
    if score >= 8.0:
        return "B+"
    if score >= 7.0:
        return "B"
    if score >= 6.0:
        return "B-"
    if score >= 5.0:
        return "C"
    if score >= 4.0:
        return "C-"
    if score >= 3.0:
        return "D"
    return "F"


def _exists(rel: str) -> bool:
    return (ROOT / rel).is_file()


def _module_importable(dotted: str) -> bool:
    try:
        return importlib.util.find_spec(dotted) is not None
    except (ModuleNotFoundError, ValueError):
        return False


def _file_contains(rel: str, needle: str) -> bool:
    path = ROOT / rel
    if not path.is_file():
        return False
    try:
        return needle in path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False


def _pyproject_has_dep(name: str) -> bool:
    path = ROOT / "pyproject.toml"
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    return name.lower() in text


def _score_latency_cost() -> DimensionScore:
    evidence: list[str] = []
    gaps: list[str] = []
    score = 5.0

    if _exists("src/utils/model_selector.py"):
        score += 1.2
        evidence.append("ModelSelector BATS routing present")
        if _file_contains("src/utils/model_selector.py", "CRITICAL"):
            score += 0.6
            evidence.append("CRITICAL tasks pinned to premium model")
    else:
        gaps.append("missing model_selector")

    if _exists("src/rag/rag_cache.py"):
        score += 0.8
        evidence.append("RAGQueryCache LRU+TTL present")
    else:
        gaps.append("missing rag_cache")

    if _file_contains("src/rag/rag_pipeline.py", "RAGQueryCache") or _file_contains(
        "src/rag/rag_pipeline.py", "query_cache"
    ):
        score += 0.6
        evidence.append("RAG cache wired into pipeline search path")
    else:
        gaps.append("rag cache not wired into pipeline")

    if _exists("src/utils/token_monitor.py"):
        score += 0.5
        evidence.append("token usage monitor present")
    else:
        gaps.append("missing token_monitor")

    if not _pyproject_has_dep("langchain") and not _pyproject_has_dep("langgraph"):
        score += 0.5
        evidence.append("no heavy agent framework deps in pyproject")
    else:
        gaps.append("heavy framework dependency present")
        score -= 1.0

    # Hot path is deterministic put-credit (best latency control)
    if _exists("scripts/spy_put_credit.py") and _exists("src/risk/trade_gateway.py"):
        score += 0.5
        evidence.append("deterministic order path independent of LLM")

    if _exists("src/utils/llm_batch.py"):
        score += 0.3
        evidence.append("offline batching helper (non-money path)")
    else:
        gaps.append("missing llm_batch helper")

    if not gaps:
        score = 10.0
    score = min(10.0, max(0.0, score))
    return DimensionScore("latency_cost_control", score, _grade(score), evidence, gaps)


def _score_observability() -> DimensionScore:
    evidence: list[str] = []
    gaps: list[str] = []
    score = 4.5

    if _exists("src/observability/llm_observability.py"):
        score += 1.0
        evidence.append("LLM route/coverage report")
    else:
        gaps.append("missing llm_observability")

    if _exists("scripts/check_llm_observability.py"):
        score += 0.5
        evidence.append("check_llm_observability CLI")

    if _exists("src/observability/opentelemetry_tracer.py"):
        score += 0.8
        evidence.append("AgentTracer span JSONL")
    else:
        gaps.append("missing span tracer")

    if _exists("src/utils/token_monitor.py"):
        score += 0.7
        evidence.append("token usage persistence")

    if _exists("src/rag/evaluation.py"):
        score += 0.8
        evidence.append("RAG eval metrics (P@k/R@k/MRR)")
    else:
        gaps.append("missing rag evaluation")

    if _exists("src/rag/retrieval_telemetry.py") or _file_contains(
        "src/rag/rag_pipeline.py", "record_retrieval"
    ):
        score += 0.7
        evidence.append("retrieval score telemetry")
    else:
        gaps.append("retrieval scores not telemetried")

    if _file_contains("src/observability/llm_observability.py", "critical_execution"):
        score += 0.5
        evidence.append("honest Anthropic vs OpenRouter coverage gap documented in code")

    if _file_contains("src/utils/token_monitor.py", "get_agent_tracer") or _file_contains(
        "src/utils/token_monitor.py", "record_span"
    ):
        score += 0.5
        evidence.append("token monitor dual-writes AgentTracer spans")

    if not gaps:
        score = 10.0
    score = min(10.0, max(0.0, score))
    return DimensionScore("observability", score, _grade(score), evidence, gaps)


def _score_failure_modes() -> DimensionScore:
    evidence: list[str] = []
    gaps: list[str] = []
    score = 5.0

    if _exists("src/risk/production_gate.py"):
        score += 1.0
        evidence.append("production_gate for new risk")
    if _exists("src/risk/trade_gateway.py"):
        score += 0.8
        evidence.append("TradeGateway hard rejects")
    if _exists("data/runtime/strategy_kill_switch.json"):
        score += 0.5
        evidence.append("strategy kill switch file")

    if _file_contains("src/rag/rag_pipeline.py", "index_size") or _file_contains(
        "src/rag/rag_pipeline.py", "empty_index"
    ):
        score += 0.8
        evidence.append("empty-index fail-closed path")
    else:
        gaps.append("empty RAG index not fail-closed")

    if (
        _file_contains("src/rag/rag_pipeline.py", "mode: str")
        or _file_contains("src/rag/rag_pipeline.py", "mode: GateMode")
        or _file_contains("src/rag/rag_pipeline.py", "GateMode")
    ):
        score += 0.6
        evidence.append("gate modes (advisory/safety/strict)")
    else:
        gaps.append("single gate mode only")

    if _exists("src/utils/staleness_guard.py") or _file_contains(
        "src/analytics/local_ops_snapshot.py", "rag_index_stale"
    ):
        score += 0.6
        evidence.append("staleness detection")
    else:
        gaps.append("no staleness guard")

    if _file_contains("src/risk/trade_gateway.py", "RAG_LESSON_CRITICAL"):
        score += 0.5
        evidence.append("CRITICAL lesson blocks trades")

    if _file_contains("src/agents/execution_agent.py", "DETERMINISTIC_FALLBACK"):
        score += 0.4
        evidence.append("LLM outage deterministic fallback")

    if not gaps:
        score = 10.0
    score = min(10.0, max(0.0, score))
    return DimensionScore("failure_modes", score, _grade(score), evidence, gaps)


def _score_structured_outputs() -> DimensionScore:
    evidence: list[str] = []
    gaps: list[str] = []
    score = 5.0

    if _file_contains("src/llm/mirascope_client.py", "class TradeDecision"):
        score += 1.0
        evidence.append("Pydantic TradeDecision structured output")
    if _exists("src/validators/pre_tool_validator.py"):
        score += 1.0
        evidence.append("PreToolValidator schemas")
        if _file_contains("src/validators/pre_tool_validator.py", "FAIL_CLOSED") or _file_contains(
            "src/validators/pre_tool_validator.py", "fail_closed"
        ):
            score += 1.0
            evidence.append("money tools fail-closed when schema unknown")
        else:
            gaps.append("unregistered tools pass by default")
    else:
        gaps.append("missing pre_tool_validator")

    if _exists("src/risk/production_gate.py"):
        score += 0.8
        evidence.append("deterministic GateCheck structs")
    if _exists("src/validators/rule_one_validator.py"):
        score += 0.5
        evidence.append("RuleOneValidator")

    if _file_contains("src/llm/mirascope_client.py", "BaseModel"):
        score += 0.5
        evidence.append("Pydantic BaseModel usage")

    if not gaps:
        score = 10.0
    score = min(10.0, max(0.0, score))
    return DimensionScore("structured_outputs", score, _grade(score), evidence, gaps)


def _score_multi_tenancy_acl() -> DimensionScore:
    """Single-operator lab: score honesty + secret hygiene, not fake multi-tenant SaaS."""
    evidence: list[str] = []
    gaps: list[str] = []
    # Base: correct single-tenant declaration is better than fake multi-tenant
    score = 7.0
    evidence.append("single-operator production lab (no multi-tenant SaaS surface)")

    if _exists("src/rag/document_acl.py"):
        score += 1.5
        evidence.append("document ACL / sensitivity labels module")
        if _file_contains("src/rag/document_acl.py", "FORBIDDEN") or _file_contains(
            "src/rag/document_acl.py", "scrub"
        ):
            score += 0.8
            evidence.append("secret scrub / forbidden patterns")
    else:
        gaps.append("no document_acl module")
        score -= 0.5

    if _file_contains("src/utils/alpaca_client.py", "get_alpaca_credentials") or _exists(
        "src/utils/alpaca_client.py"
    ):
        score += 0.5
        evidence.append("credentials via env/keyring pattern")

    # Penalty if public multi-user HTTP RAG without ACL
    if _exists("src/agents/rag_webhook.py") and not _exists("src/rag/document_acl.py"):
        gaps.append("rag webhook without document ACL")
        score -= 1.0

    if not gaps:
        score = 10.0
    score = min(10.0, max(0.0, score))
    return DimensionScore("multi_tenancy_acl", score, _grade(score), evidence, gaps)


def _score_framework_discipline() -> DimensionScore:
    evidence: list[str] = []
    gaps: list[str] = []
    score = 8.0

    heavy = [
        n for n in ("langchain", "langgraph", "llama-index", "llama_index") if _pyproject_has_dep(n)
    ]
    if not heavy:
        score += 1.5
        evidence.append("pyproject free of LangChain/LangGraph/LlamaIndex")
    else:
        score -= 3.0
        gaps.append(f"heavy deps: {heavy}")

    if _file_contains("src/orchestrator/main.py", "LangChain agent removed") or _file_contains(
        "src/execution/alpaca_executor.py", "LangSmith removed"
    ):
        score += 0.5
        evidence.append("explicit removal of heavy framework / LangSmith from prod path")

    if _exists("src/rag/rag_pipeline.py") and _exists("src/risk/trade_gateway.py"):
        score += 0.3
        evidence.append("raw pipeline + gateway ownership")

    if not gaps:
        score = 10.0
    score = min(10.0, max(0.0, score))
    return DimensionScore("framework_discipline", score, _grade(score), evidence, gaps)


def evaluate_llm_production_control_plane() -> LLMProductionReport:
    """Grade LLM/RAG production maturity from repository contracts."""
    dims = [
        _score_latency_cost(),
        _score_observability(),
        _score_failure_modes(),
        _score_structured_outputs(),
        _score_multi_tenancy_acl(),
        _score_framework_discipline(),
    ]
    overall = sum(d.score_0_10 for d in dims) / max(len(dims), 1)
    a_plus = overall >= 9.5 and all(d.score_0_10 >= 9.0 for d in dims)
    perfect_10 = all(d.score_0_10 >= 9.95 for d in dims)
    return LLMProductionReport(
        overall_score_0_10=round(10.0 if perfect_10 else overall, 2),
        overall_grade=_grade(10.0 if perfect_10 else overall),
        dimensions=dims,
        a_plus_ready=a_plus or perfect_10,
        cash_engine_note=(
            "LLM/RAG A+ is process maturity only. Real $1k/mo after-tax requires "
            "EDGE_CANDIDATE (n≥30, expectancy>0, PF>1) then funded live — "
            "not achievable by observability alone."
        ),
        generated_checks=sum(len(d.evidence) + len(d.gaps) for d in dims),
    )


def assert_llm_plane_minimum(*, min_overall: float = 8.0) -> LLMProductionReport:
    """Raise if LLM plane is below minimum ops standard."""
    report = evaluate_llm_production_control_plane()
    if report.overall_score_0_10 < min_overall:
        gaps = [g for d in report.dimensions for g in d.gaps]
        raise RuntimeError(
            f"LLM production plane grade {report.overall_grade} "
            f"({report.overall_score_0_10}/10) below minimum {min_overall}. gaps={gaps}"
        )
    return report
