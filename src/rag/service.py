"""Validated FastAPI service for the production trading RAG pipeline."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field

from src.rag.rag_pipeline import GateDecision, get_trading_rag_pipeline

logger = logging.getLogger(__name__)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SearchRequest(StrictModel):
    query: str = Field(min_length=2, max_length=2_000)
    top_k: int = Field(default=5, ge=1, le=50)
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] | None = None
    source: str | None = Field(default=None, max_length=100)
    tag: str | None = Field(default=None, max_length=100)
    section: str | None = Field(default=None, max_length=200)
    min_version: int | None = Field(default=None, ge=1)
    rerank: bool = True


class SearchHit(StrictModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    id: str
    title: str
    severity: str
    score: float = Field(ge=0.0, le=1.0)
    snippet: str
    prevention: str = ""
    file: str = ""
    source: str = ""
    chunk_id: str = ""
    section_title: str = ""
    parent_context: str = ""
    parent_chunk_count: int = 0
    parent_context_truncated: bool = False
    retrieval_channels: list[str] = Field(default_factory=list)
    rrf_score: float = Field(default=0.0, ge=0.0, le=1.0)
    reranker_type: str
    embedding_backend: str


class SearchResponse(StrictModel):
    request_id: str
    results: list[SearchHit]
    query_hash: str
    latency_ms: float
    candidate_count: int
    variant_count: int
    cache_hit: bool
    degraded: bool


class FeedbackCaptureRequest(StrictModel):
    feedback_text: str = Field(min_length=10, max_length=20_000)
    prevention: str = Field(min_length=10, max_length=20_000)
    tool_name: str = Field(min_length=1, max_length=200)
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] = "HIGH"
    event_id: str | None = Field(default=None, min_length=4, max_length=128)
    tool_context: dict[str, Any] = Field(default_factory=dict)


class FeedbackCaptureResponse(StrictModel):
    stored: bool
    detail: str


class GateRequest(StrictModel):
    tool_name: str = Field(min_length=1, max_length=200)
    arguments: dict[str, Any] = Field(default_factory=dict)
    risk_level: Literal["normal", "high"] | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class GateResponse(StrictModel):
    approved: bool
    severity: Literal["APPROVED", "WARN", "BLOCK"]
    reason: str
    reason_code: str
    top_score: float
    citations: list[str]
    degraded: bool
    context: str


def _service_token() -> str:
    return os.getenv("RAG_SERVICE_TOKEN", "").strip()


def _is_production() -> bool:
    return os.getenv("RAG_ENV", "development").strip().lower() == "production"


def _strict_quality() -> bool:
    default = "1" if _is_production() else "0"
    return os.getenv("RAG_STRICT_QUALITY", default).strip().lower() in {"1", "true", "yes"}


def require_auth(authorization: str | None = Header(default=None)) -> None:
    """Require bearer auth when configured, and always in production."""
    expected = _service_token()
    if not expected:
        if _is_production():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="RAG service token is not configured",
            )
        return
    provided = ""
    if authorization and authorization.lower().startswith("bearer "):
        provided = authorization[7:].strip()
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Build and warm the local index before readiness can turn green."""
    pipeline = get_trading_rag_pipeline()
    if os.getenv("RAG_WARMUP_ON_STARTUP", "1").lower() in {"1", "true", "yes"}:
        try:
            if pipeline.lessons_dir is not None:
                await asyncio.to_thread(
                    pipeline.sync_markdown_dir,
                    pipeline.lessons_dir,
                    delete_missing=True,
                    strict_quality=_strict_quality(),
                )
            warmup = await asyncio.to_thread(pipeline.warmup)
            logger.info("RAG startup warmup complete %s", warmup)
        except Exception:
            logger.exception("RAG startup warmup failed; readiness remains closed")
    yield


app = FastAPI(
    title="Trading RAG Service",
    version="1.0.0",
    docs_url=None if _is_production() else "/docs",
    redoc_url=None,
    lifespan=lifespan,
)


@app.middleware("http")
async def request_observability(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "RAG service request failed request_id=%s path=%s", request_id, request.url.path
        )
        raise
    duration_ms = round((time.perf_counter() - started) * 1000.0, 3)
    response.headers["x-request-id"] = request_id
    response.headers["server-timing"] = f"app;dur={duration_ms:.3f}"
    logger.info(
        "RAG service request_id=%s method=%s path=%s status=%d latency_ms=%.3f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.exception_handler(ValueError)
async def value_error_handler(_request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready")
async def ready(response: Response) -> dict[str, Any]:
    pipeline = get_trading_rag_pipeline()
    health = await asyncio.to_thread(pipeline.health)
    auth_ready = bool(_service_token()) or not _is_production()
    health["auth_ready"] = auth_ready
    health["ready"] = bool(health["ready"] and auth_ready)
    if not health["ready"]:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return health


@app.post("/v1/search", response_model=SearchResponse, dependencies=[Depends(require_auth)])
async def search(payload: SearchRequest, request: Request) -> SearchResponse:
    pipeline = get_trading_rag_pipeline()
    results = await asyncio.to_thread(
        pipeline.query,
        payload.query,
        payload.top_k,
        severity_filter=payload.severity,
        source_filter=payload.source,
        tag_filter=payload.tag,
        section_filter=payload.section,
        min_version=payload.min_version,
        rerank=payload.rerank,
    )
    trace = pipeline.last_query_trace
    if trace is None:
        raise HTTPException(status_code=500, detail="query trace missing")
    hits = [SearchHit.model_validate(item) for item in results]
    return SearchResponse(
        request_id=request.state.request_id,
        results=hits,
        query_hash=trace.query_hash,
        latency_ms=trace.latency_ms,
        candidate_count=trace.candidate_count,
        variant_count=trace.variant_count,
        cache_hit=trace.cache_hit,
        degraded=trace.degraded,
    )


@app.post(
    "/v1/feedback/thumbs-down",
    response_model=FeedbackCaptureResponse,
    dependencies=[Depends(require_auth)],
)
async def capture_feedback(payload: FeedbackCaptureRequest) -> FeedbackCaptureResponse:
    pipeline = get_trading_rag_pipeline()
    stored, detail = await asyncio.to_thread(
        pipeline.capture_thumbs_down,
        feedback_text=payload.feedback_text,
        prevention=payload.prevention,
        tool_name=payload.tool_name,
        severity=payload.severity,
        event_id=payload.event_id,
        tool_context=payload.tool_context,
    )
    if not stored:
        raise HTTPException(status_code=422, detail=detail)
    return FeedbackCaptureResponse(stored=True, detail=detail)


def _gate_response(decision: GateDecision, context: str) -> GateResponse:
    return GateResponse(
        approved=decision.approved,
        severity=decision.severity,
        reason=decision.reason,
        reason_code=decision.reason_code,
        top_score=decision.top_score,
        citations=list(decision.citations),
        degraded=decision.degraded,
        context=context,
    )


@app.post("/v1/gate", response_model=GateResponse, dependencies=[Depends(require_auth)])
async def gate(payload: GateRequest) -> GateResponse:
    pipeline = get_trading_rag_pipeline()
    decision, context = await asyncio.to_thread(
        pipeline.gate_tool_call,
        payload.tool_name,
        payload.arguments,
        risk_level=payload.risk_level,
        top_k=payload.top_k,
    )
    return _gate_response(decision, context)


@app.post("/v1/admin/reindex", dependencies=[Depends(require_auth)])
async def reindex() -> dict[str, Any]:
    pipeline = get_trading_rag_pipeline()
    if pipeline.lessons_dir is None:
        raise HTTPException(status_code=503, detail="lessons directory is not configured")
    report = await asyncio.to_thread(
        pipeline.sync_markdown_dir,
        pipeline.lessons_dir,
        delete_missing=True,
        strict_quality=_strict_quality(),
    )
    return {**report.__dict__, "ok": report.ok}


@app.get("/metrics", response_class=PlainTextResponse, dependencies=[Depends(require_auth)])
async def metrics() -> PlainTextResponse:
    snapshot = await asyncio.to_thread(get_trading_rag_pipeline().metrics_snapshot)
    health = snapshot.pop("health")
    lines = [
        "# HELP trading_rag_info Static RAG capability information.",
        "# TYPE trading_rag_info gauge",
        f'trading_rag_info{{embedding="{health["embedding_backend"]}",'
        f'reranker="{health["reranker"]}"}} 1',
    ]
    for key, value in sorted(snapshot.items()):
        if isinstance(value, (int, float)):
            metric_name = "trading_rag_" + "".join(
                character if character.isalnum() or character == "_" else "_" for character in key
            )
            lines.extend([f"# TYPE {metric_name} gauge", f"{metric_name} {value}"])
    lines.extend(
        [
            "# TYPE trading_rag_ready gauge",
            f"trading_rag_ready {int(bool(health['ready']))}",
            "# TYPE trading_rag_documents gauge",
            f"trading_rag_documents {health['documents']}",
            "# TYPE trading_rag_chunks gauge",
            f"trading_rag_chunks {health['chunks']}",
        ]
    )
    return PlainTextResponse("\n".join(lines) + "\n")


def query_fingerprint(query: str) -> str:
    """Public helper for clients that need a privacy-preserving query ID."""
    return hashlib.sha256(" ".join(query.lower().split()).encode("utf-8")).hexdigest()[:16]
