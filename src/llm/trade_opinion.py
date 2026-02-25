"""
Pre-Trade Research Agent — DeepSeek-R1 powered IC entry opinion.

Autonomous advisory layer that runs before every iron condor entry.
Consumes: market regime, Thompson sampling stats, VIX data, RAG lessons.
Outputs: structured JSON opinion (trade/skip, confidence, suggested params).

The opinion is ADVISORY ONLY — hard risk limits in Python are never overridden.
Phil Town Rule #1: Don't lose money. The risk engine has final say.

Integration points:
- Called by iron_condor_trader.py between VIX check and find_trade()
- Uses model_selector for budget-aware routing (DeepSeek-R1 via OpenRouter)
- Falls back gracefully: if LLM call fails, trade proceeds with existing logic

Feb 2026 — Built per CEO directive for autonomous, smart, automated execution.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from src.utils.llm_gateway import (
    OPENROUTER_BASE_URL,
    resolve_openrouter_primary_and_fallback_configs,
)
from src.utils.model_selector import get_model_selector

logger = logging.getLogger(__name__)
JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.IGNORECASE | re.DOTALL)


# =============================================================================
# STRUCTURED OUTPUT SCHEMA
# =============================================================================


class TradeOpinion(BaseModel):
    """Structured pre-trade opinion from LLM research agent."""

    should_trade: bool = Field(description="Whether to enter the iron condor")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in recommendation")
    regime: str = Field(description="Detected market regime (calm/trending/volatile/spike)")
    suggested_short_delta: float = Field(
        ge=0.05,
        le=0.30,
        default=0.15,
        description="Suggested short strike delta (0.10-0.20 typical)",
    )
    suggested_dte: int = Field(
        ge=14,
        le=60,
        default=35,
        description="Suggested days to expiration",
    )
    reasoning: str = Field(description="Brief reasoning for the decision")
    risk_flags: list[str] = Field(
        default_factory=list,
        description="Any risk warnings (earnings, FOMC, etc.)",
    )
    consensus_samples: int = Field(
        ge=1,
        le=10,
        default=1,
        description="How many independent samples were used (1=single pass).",
    )
    consensus_agreement: float = Field(
        ge=0.0,
        le=1.0,
        default=1.0,
        description="Agreement ratio among sampled opinions.",
    )


class TradeOpinionJudgeVerdict(BaseModel):
    """Structured evaluation of a generated trade opinion."""

    approved: bool = Field(description="Whether the opinion passes risk/compliance checks.")
    score: float = Field(ge=0.0, le=1.0, description="Overall quality/risk score.")
    verdict: str = Field(description="Short rationale for approval/rejection.")
    violations: list[str] = Field(
        default_factory=list,
        description="Specific rule/context violations.",
    )


# =============================================================================
# PRE-TRADE RESEARCH AGENT
# =============================================================================


def _trade_opinion_schema() -> dict[str, Any]:
    """Return strict JSON schema for provider-native structured output."""
    schema = TradeOpinion.model_json_schema()
    if isinstance(schema, dict):
        schema.setdefault("additionalProperties", False)
    return schema


def _response_format_candidates() -> list[dict[str, Any]]:
    """
    Ordered response format preferences.

    1) Strict json_schema for providers that support schema-constrained output.
    2) json_object fallback for providers that only support JSON mode.
    """
    return _response_format_candidates_for_schema(
        name="trade_opinion",
        schema=_trade_opinion_schema(),
    )


def _response_format_candidates_for_schema(
    *,
    name: str,
    schema: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build ordered response format candidates for any strict JSON schema."""
    return [
        {
            "type": "json_schema",
            "json_schema": {
                "name": name,
                "strict": True,
                "schema": schema,
            },
        },
        {"type": "json_object"},
    ]


def _judge_schema() -> dict[str, Any]:
    """Return strict JSON schema for trade-opinion judge verdicts."""
    schema = TradeOpinionJudgeVerdict.model_json_schema()
    if isinstance(schema, dict):
        schema.setdefault("additionalProperties", False)
    return schema


def _judge_response_format_candidates() -> list[dict[str, Any]]:
    """Response formats for judge verdict generation."""
    return _response_format_candidates_for_schema(
        name="trade_opinion_judge", schema=_judge_schema()
    )


def _extract_text_content(raw: Any) -> str:
    """Normalize OpenAI-compatible message content into a single string."""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        chunks: list[str] = []
        for item in raw:
            if isinstance(item, str):
                chunks.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    chunks.append(text)
        return "\n".join(part.strip() for part in chunks if part.strip())
    return ""


def _parse_json_object(text: str) -> dict[str, Any]:
    """Parse JSON object with defensive fallbacks for markdown-wrapped payloads."""
    normalized = (text or "").strip()
    if not normalized:
        raise json.JSONDecodeError("Empty response", text, 0)

    candidates: list[str] = [normalized]
    match = JSON_BLOCK_RE.search(normalized)
    if match:
        candidates.append(match.group(1).strip())

    first = normalized.find("{")
    last = normalized.rfind("}")
    if first >= 0 and last > first:
        candidates.append(normalized[first : last + 1].strip())

    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    raise json.JSONDecodeError("No JSON object found in response", normalized, 0)


def _request_structured_completion(
    client: Any,
    *,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    response_formats: list[dict[str, Any]] | None = None,
    temperature: float | None = None,
) -> Any:
    """
    Call provider with structured output settings.

    Tries strict schema mode first, then falls back to generic JSON mode.
    """
    candidates = response_formats if response_formats is not None else _response_format_candidates()
    last_exc: Exception | None = None
    for fmt in candidates:
        try:
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "response_format": fmt,
            }
            if temperature is not None:
                kwargs["temperature"] = temperature
            return client.chat.completions.create(**kwargs)
        except Exception as exc:
            last_exc = exc
            logger.debug(
                "Trade opinion: response_format=%s unsupported/failed (%s)",
                fmt.get("type"),
                exc,
            )
            continue

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("No response_format candidates configured")


def _is_truthy(value: str | None) -> bool:
    """Return True for standard truthy env values."""
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _float_env(name: str, default: float) -> float:
    """Read float from env with safe fallback."""
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning(
            "Trade opinion: invalid float env %s=%r, using default %.4f", name, raw, default
        )
        return default


def _int_env(name: str, default: int) -> int:
    """Read int from env with safe fallback."""
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Trade opinion: invalid int env %s=%r, using default %d", name, raw, default)
        return default


def _stable_sample(seed: str, sample_rate: float) -> bool:
    """
    Deterministic sampling decision in [0,1] for stable replayability.

    Uses a daily bucket to ensure traffic sample rotates each UTC day.
    """
    if sample_rate <= 0.0:
        return False
    if sample_rate >= 1.0:
        return True
    day_seed = datetime.now(timezone.utc).date().isoformat()
    digest = hashlib.sha256(f"{day_seed}:{seed}".encode()).hexdigest()
    value = int(digest[:8], 16) / 0xFFFFFFFF
    return value < sample_rate


def _needs_consensus(opinion: TradeOpinion) -> bool:
    """
    Decide whether to run additional samples for uncertainty reduction.

    Triggers when confidence is near the decision boundary or when explicit
    risk flags are present.
    """
    if not _is_truthy(os.getenv("TRADE_OPINION_CONSENSUS_ENABLED", "true")):
        return False

    half_band = max(0.0, min(0.5, _float_env("TRADE_OPINION_UNCERTAIN_BAND", 0.15)))
    low = 0.5 - half_band
    high = 0.5 + half_band
    near_boundary = low <= opinion.confidence <= high
    has_risk_flags = bool(opinion.risk_flags)
    return near_boundary or has_risk_flags


def _aggregate_consensus(opinions: list[TradeOpinion]) -> TradeOpinion:
    """Aggregate multiple independent opinions into a single consensus object."""
    if not opinions:
        raise ValueError("opinions must not be empty")
    if len(opinions) == 1:
        return opinions[0]

    should_trade_votes = [o.should_trade for o in opinions]
    true_votes = sum(1 for vote in should_trade_votes if vote)
    false_votes = len(should_trade_votes) - true_votes
    if true_votes == false_votes:
        should_trade = False
        tie_risk_flag = ["consensus_tie"]
    else:
        should_trade = true_votes > false_votes
        tie_risk_flag = []

    majority_count = max(true_votes, false_votes)
    agreement = max(0.0, min(1.0, majority_count / len(opinions)))

    regimes = [o.regime.strip() for o in opinions if o.regime.strip()]
    regime = Counter(regimes).most_common(1)[0][0] if regimes else opinions[0].regime

    filtered = [o for o in opinions if o.should_trade == should_trade] or opinions
    best_reason = max(filtered, key=lambda x: x.confidence).reasoning

    avg_confidence = sum(o.confidence for o in opinions) / len(opinions)
    confidence = max(0.0, min(1.0, avg_confidence * agreement))

    avg_delta = sum(o.suggested_short_delta for o in opinions) / len(opinions)
    avg_dte = round(sum(o.suggested_dte for o in opinions) / len(opinions))

    all_risk_flags: list[str] = []
    for opinion in opinions:
        all_risk_flags.extend(opinion.risk_flags)
    all_risk_flags.extend(tie_risk_flag)
    deduped_flags = sorted({flag for flag in all_risk_flags if flag})

    return TradeOpinion(
        should_trade=should_trade,
        confidence=confidence,
        regime=regime,
        suggested_short_delta=max(0.05, min(0.30, avg_delta)),
        suggested_dte=max(14, min(60, avg_dte)),
        reasoning=best_reason,
        risk_flags=deduped_flags,
        consensus_samples=len(opinions),
        consensus_agreement=agreement,
    )


def _emit_judge_telemetry(payload: dict[str, Any]) -> None:
    """Append judge telemetry payload to JSONL when enabled."""
    if not _is_truthy(os.getenv("TRADE_OPINION_JUDGE_LOG_ENABLED", "true")):
        return
    log_path = Path(
        os.getenv("TRADE_OPINION_JUDGE_LOG_PATH", "data/telemetry/trade_opinion_judge.jsonl")
    )
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
    except Exception as exc:
        logger.warning("Trade opinion judge: failed to write telemetry (%s)", exc)


def _judge_system_prompt() -> str:
    """System prompt for strong-model judge evaluation."""
    return """You are a strict risk/compliance judge for SPY iron-condor pre-trade opinions.

Evaluate whether the candidate opinion is internally consistent with context and rules:
- Avoid high-risk conditions (major catalysts, extreme volatility, explicit risk flags)
- Confidence should match evidence quality (no overconfident weak rationale)
- Trade recommendation should be conservative when uncertainty is high

Respond ONLY with valid JSON matching the schema."""


def _build_judge_prompt(context_prompt: str, opinion: TradeOpinion) -> str:
    """Build judge prompt from original context and candidate opinion."""
    opinion_json = json.dumps(opinion.model_dump(), sort_keys=True)
    return (
        "Evaluate the candidate opinion below.\n\n"
        f"Original context:\n{context_prompt}\n\n"
        f"Candidate opinion JSON:\n{opinion_json}\n\n"
        "Return JSON with fields: approved, score, verdict, violations."
    )


def get_trade_opinion(
    vix_current: float | None = None,
    thompson_stats: dict[str, Any] | None = None,
    regime: str | None = None,
    recent_lessons: list[str] | None = None,
) -> TradeOpinion | None:
    """
    Get pre-trade opinion from DeepSeek-R1 via OpenRouter.

    This is the autonomous research agent. It:
    1. Gathers context (VIX, Thompson stats, regime, RAG lessons)
    2. Sends structured prompt to DeepSeek-R1
    3. Returns a typed TradeOpinion object

    Returns None if the LLM call fails (trade proceeds with existing logic).
    """
    primary_cfg, fallback_cfg = resolve_openrouter_primary_and_fallback_configs()
    if not primary_cfg.api_key:
        logger.warning(
            "Trade opinion disabled: no OpenAI-compatible API key resolved "
            "(set OPENROUTER_API_KEY or gateway key env vars)."
        )
        return None

    # Select model via BATS framework
    selector = get_model_selector()
    model_id = selector.select_model("pre_trade_research")
    provider = selector.get_model_provider(model_id)
    transport_model_id = selector.get_transport_model_id(model_id)

    if provider != "openrouter":
        logger.info(f"Trade opinion: model {model_id} is not OpenRouter, skipping")
        return None

    logger.info(
        "Trade opinion route: provider=%s canonical_model=%s transport_model=%s",
        provider,
        model_id,
        transport_model_id,
    )

    prompt = _build_prompt(vix_current, thompson_stats, regime, recent_lessons)
    max_samples = max(1, min(5, _int_env("TRADE_OPINION_MAX_SAMPLES", 3)))
    base_temperature = max(0.0, min(1.5, _float_env("TRADE_OPINION_TEMPERATURE", 0.1)))
    temperature_step = max(0.0, min(1.0, _float_env("TRADE_OPINION_TEMPERATURE_STEP", 0.2)))

    judge_enabled = _is_truthy(os.getenv("TRADE_OPINION_JUDGE_ENABLED", "false"))
    judge_sample_rate = max(0.0, min(1.0, _float_env("TRADE_OPINION_JUDGE_SAMPLE_RATE", 0.15)))
    judge_enforce = _is_truthy(os.getenv("TRADE_OPINION_JUDGE_ENFORCE", "false"))

    try:
        from openai import OpenAI

        client = OpenAI(api_key=primary_cfg.api_key, base_url=primary_cfg.base_url)
        fallback_client: Any = None
        using_gateway = bool(primary_cfg.base_url) and (
            primary_cfg.base_url.rstrip("/") != OPENROUTER_BASE_URL.rstrip("/")
        )
        model_for_call = transport_model_id if using_gateway else model_id

        def run_completion(
            *,
            canonical_model: str,
            primary_model: str,
            fallback_model: str,
            messages: list[dict[str, str]],
            max_tokens: int,
            response_formats: list[dict[str, Any]] | None = None,
            temperature: float | None = None,
        ) -> Any:
            nonlocal fallback_client
            try:
                response = _request_structured_completion(
                    client,
                    model=primary_model,
                    messages=messages,
                    max_tokens=max_tokens,
                    response_formats=response_formats,
                    temperature=temperature,
                )
            except Exception as primary_exc:
                if not fallback_cfg:
                    raise
                logger.warning(
                    "Trade opinion: gateway call failed (%s). Retrying via OpenRouter direct.",
                    primary_exc,
                )
                if fallback_client is None:
                    fallback_client = OpenAI(
                        api_key=fallback_cfg.api_key, base_url=fallback_cfg.base_url
                    )
                response = _request_structured_completion(
                    fallback_client,
                    model=fallback_model,
                    messages=messages,
                    max_tokens=max_tokens,
                    response_formats=response_formats,
                    temperature=temperature,
                )

            if response.usage:
                selector.log_usage(
                    canonical_model,
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                )
            return response

        def parse_trade_opinion_response(response: Any) -> TradeOpinion:
            text = (
                _extract_text_content(response.choices[0].message.content)
                if response.choices
                else ""
            )
            if not text:
                raise json.JSONDecodeError("Empty response", "", 0)
            data = _parse_json_object(text)
            return TradeOpinion.model_validate(data)

        messages = [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": prompt},
        ]

        first_response = run_completion(
            canonical_model=model_id,
            primary_model=model_for_call,
            fallback_model=model_id,
            messages=messages,
            max_tokens=2048,
            temperature=base_temperature,
        )
        first_opinion = parse_trade_opinion_response(first_response)

        samples: list[TradeOpinion] = [first_opinion]
        if max_samples > 1 and _needs_consensus(first_opinion):
            for idx in range(1, max_samples):
                sample_temperature = min(1.5, base_temperature + (idx * temperature_step))
                try:
                    sample_response = run_completion(
                        canonical_model=model_id,
                        primary_model=model_for_call,
                        fallback_model=model_id,
                        messages=messages,
                        max_tokens=2048,
                        temperature=sample_temperature,
                    )
                    samples.append(parse_trade_opinion_response(sample_response))
                except Exception as sample_exc:
                    logger.warning(
                        "Trade opinion consensus sample %d failed: %s",
                        idx + 1,
                        sample_exc,
                    )

        opinion = _aggregate_consensus(samples)
        if len(samples) > 1:
            logger.info(
                "Trade opinion consensus: samples=%d agreement=%.2f should_trade=%s",
                opinion.consensus_samples,
                opinion.consensus_agreement,
                opinion.should_trade,
            )

        judge_sampled = False
        judge_verdict: TradeOpinionJudgeVerdict | None = None
        judge_model = ""
        judge_seed = f"{model_id}:{prompt}:{json.dumps(opinion.model_dump(), sort_keys=True)}"
        if judge_enabled and _stable_sample(judge_seed, judge_sample_rate):
            judge_sampled = True
            judge_model = (os.getenv("TRADE_OPINION_JUDGE_MODEL") or "").strip()
            if not judge_model:
                judge_model = selector.select_model("risk_assessment")
                if selector.get_model_provider(judge_model) != "openrouter":
                    logger.warning(
                        "Trade opinion judge skipped: selected judge model is not OpenRouter (%s)",
                        judge_model,
                    )
                    judge_model = ""

            if judge_model:
                judge_transport_model = (
                    selector.get_transport_model_id(judge_model) if using_gateway else judge_model
                )
                judge_messages = [
                    {"role": "system", "content": _judge_system_prompt()},
                    {"role": "user", "content": _build_judge_prompt(prompt, opinion)},
                ]
                try:
                    judge_response = run_completion(
                        canonical_model=judge_model,
                        primary_model=judge_transport_model,
                        fallback_model=judge_model,
                        messages=judge_messages,
                        max_tokens=1024,
                        response_formats=_judge_response_format_candidates(),
                        temperature=max(
                            0.0, min(1.0, _float_env("TRADE_OPINION_JUDGE_TEMPERATURE", 0.0))
                        ),
                    )
                    judge_text = (
                        _extract_text_content(judge_response.choices[0].message.content)
                        if judge_response.choices
                        else ""
                    )
                    if judge_text:
                        judge_verdict = TradeOpinionJudgeVerdict.model_validate(
                            _parse_json_object(judge_text)
                        )
                    if judge_verdict and judge_enforce and not judge_verdict.approved:
                        reason = f"{opinion.reasoning} | judge: {judge_verdict.verdict}".strip()
                        flags = sorted({*opinion.risk_flags, "judge_rejected"})
                        opinion = opinion.model_copy(
                            update={
                                "should_trade": False,
                                "risk_flags": flags,
                                "reasoning": reason,
                            }
                        )
                except Exception as judge_exc:
                    logger.warning("Trade opinion judge failed: %s", judge_exc)

        _emit_judge_telemetry(
            {
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "model": model_id,
                "consensus_samples": opinion.consensus_samples,
                "consensus_agreement": opinion.consensus_agreement,
                "judge_enabled": judge_enabled,
                "judge_sampled": judge_sampled,
                "judge_model": judge_model or None,
                "judge_approved": (judge_verdict.approved if judge_verdict else None),
                "judge_score": (judge_verdict.score if judge_verdict else None),
                "judge_enforce": judge_enforce,
                "final_should_trade": opinion.should_trade,
                "final_confidence": opinion.confidence,
                "risk_flags": opinion.risk_flags,
            }
        )

        logger.info(
            "Trade opinion: should_trade=%s, confidence=%.2f, regime=%s, delta=%.2f, dte=%d",
            opinion.should_trade,
            opinion.confidence,
            opinion.regime,
            opinion.suggested_short_delta,
            opinion.suggested_dte,
        )
        if opinion.risk_flags:
            logger.warning("Trade opinion risk flags: %s", opinion.risk_flags)
        return opinion

    except ImportError:
        logger.warning("Trade opinion: openai package not installed")
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"Trade opinion: failed to parse JSON response: {e}")
        return None
    except Exception as e:
        logger.warning(f"Trade opinion: LLM call failed: {e}")
        return None


def _system_prompt() -> str:
    """System prompt for the pre-trade research agent."""
    return """You are a quantitative options trading research agent.

Your role: Analyze market conditions and advise on SPY iron condor entry.

RULES (Phil Town Rule #1: Don't Lose Money):
- Iron condors profit when SPY stays in a range
- Ideal conditions: low/moderate volatility, no major catalysts
- VIX 15-25 is optimal. Below 15 = premiums too thin. Above 30 = too risky.
- 15-delta short strikes = ~85% probability of profit
- 30-45 DTE optimal for theta decay
- NEVER recommend trading during earnings, FOMC, or extreme volatility

You must respond with valid JSON matching the TradeOpinion schema.
Be concise in reasoning (1-2 sentences max)."""


def _build_prompt(
    vix_current: float | None,
    thompson_stats: dict[str, Any] | None,
    regime: str | None,
    recent_lessons: list[str] | None,
) -> str:
    """Build the research prompt with all available context."""
    sections = ["Analyze whether to enter a SPY iron condor today.\n"]

    # VIX context
    if vix_current is not None:
        sections.append(f"Current VIX: {vix_current:.2f}")

    # Thompson sampling stats
    if thompson_stats:
        wins = thompson_stats.get("wins", 0)
        losses = thompson_stats.get("losses", 0)
        posterior = thompson_stats.get("posterior_mean", 0.5)
        recommendation = thompson_stats.get("recommendation", "UNKNOWN")
        sections.append(
            f"Thompson Sampling: {wins}W/{losses}L, "
            f"posterior_mean={posterior:.3f}, recommendation={recommendation}"
        )

    # Market regime
    if regime:
        sections.append(f"Market Regime: {regime}")

    # RAG lessons (recent failures to avoid)
    if recent_lessons:
        sections.append("\nRecent lessons learned (avoid these mistakes):")
        for lesson in recent_lessons[:5]:  # Cap at 5 to control token usage
            sections.append(f"- {lesson[:200]}")

    sections.append(
        "\nRespond with JSON: {should_trade, confidence, regime, "
        "suggested_short_delta, suggested_dte, reasoning, risk_flags}"
    )

    return "\n".join(sections)
